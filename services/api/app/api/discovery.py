import asyncio
from time import perf_counter
from typing import Annotated
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.agent.providers import LLMProvider, get_llm_provider
from app.api.schemas import (
    DiscoveryRequest,
    DiscoveryResponse,
    OriginalIdentificationRequest,
    OriginalIdentificationResponse,
    RecommendationItem,
)
from app.auth.dependencies import CurrentIdentity
from app.domain.artist_names import enrich_track
from app.domain.discovery import original_hint
from app.domain.music import SearchResult
from app.domain.profile import PreferenceProfile
from app.infrastructure.database import get_session
from app.infrastructure.workers import run_blocking
from app.observability.events import emit, request_id
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.repository.feedback import load_profile
from app.services.discovery_guidance import add_guidance, local_guidance
from app.services.original_identification import IdentificationError, identify_original
from app.services.recommendation import (
    DiscoveryResult,
    DiscoverySearch,
    begin_discovery,
    finish_discovery,
    match_model_seed,
)
from app.services.recording_resolution import RecordingResolver, ResolutionError
from app.services.seed_identification import (
    explicit_theme,
    identify_seed,
    needs_identification,
    pending_resolution,
)

router = APIRouter(prefix="/v1/recommendations", tags=["recommendations"])
_discovery_slots = WeakKeyDictionary()


def discovery_slots() -> asyncio.Semaphore:
    return _discovery_slots.setdefault(asyncio.get_running_loop(), asyncio.Semaphore(4))


@router.post("/identify-original", response_model=OriginalIdentificationResponse)
async def original_identification(
    request: OriginalIdentificationRequest,
    session: Annotated[Session, Depends(get_session)],
    registry: Annotated[ProviderRegistry, Depends(get_provider_registry)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
):
    started = perf_counter()
    status, code = "error", None
    try:
        slots = discovery_slots()
        if slots.locked():
            raise IdentificationError("identification_busy", 503,
                                      "Music discovery is busy. Please try again.")
        async with slots, asyncio.timeout(45):
            result = await identify_original(request, provider, registry, session.get_bind())
            status = result.status
            return result
    except TimeoutError:
        code = "identification_timeout"
        return JSONResponse(status_code=504, content={"error": {
            "code": code, "message": "Original identification timed out. Please try again."}})
    except IdentificationError as error:
        code = error.code
        return JSONResponse(status_code=error.status, content={"error": {
            "code": code, "message": error.message}})
    finally:
        emit("original_identification", operation="identify_original", status=status,
             code=code, latency_ms=round((perf_counter() - started) * 1000, 3))


@router.post("/discover", response_model=DiscoveryResponse)
async def discovery(
    request: DiscoveryRequest,
    session: Annotated[Session, Depends(get_session)],
    registry: Annotated[ProviderRegistry, Depends(get_provider_registry)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    identity: CurrentIdentity,
):
    slots = discovery_slots()
    if slots.locked():
        return JSONResponse(status_code=503, content={"error": {
            "code": "discovery_busy", "message": "Music discovery is busy. Please try again."}})
    engine = session.get_bind()
    resolver = None
    if hasattr(registry, "catalogs"):
        sources = registry.for_storefront(request.seed_storefront) if request.seed_storefront else registry
        resolver = RecordingResolver(sources, engine, request.seed, request.seed_artist)

    def compute():
        # The worker owns its session until completion, including request cancellation.
        with Session(engine) as worker_session:
            profile = load_profile(worker_session, identity.user_id)
            if resolver:
                if request.resolution_id:
                    resolution = resolver.confirm(request.resolution_id, request.seed_artist)
                    state = DiscoverySearch(request.seed, request.limit, resolver, profile or PreferenceProfile(),
                        request.seed_artist, resolution)
                    state.searches.append(SearchResult(tracks=resolver.tracks, sources=resolver.sources))
                    return state
                return begin_discovery(request.seed, request.limit, resolver, profile, request.seed_artist)
            sources = registry.for_storefront(request.seed_storefront) if request.seed_storefront else registry
            return begin_discovery(request.seed, request.limit, sources, profile, request.seed_artist)

    try:
        async with slots, asyncio.timeout(45):
            started = perf_counter()
            async with asyncio.timeout(37):
                state = await run_blocking(compute)
            compute_seconds = perf_counter() - started
            suggestion, attempted, unavailable = await identify_seed(state, provider)
            source = "none"

            def finish():
                nonlocal source
                resolution = state.resolution
                theme = False
                if needs_identification(state):
                    resolution = pending_resolution(state)
                    if suggestion and suggestion.kind == "song":
                        match = match_model_seed(state, suggestion.title, suggestion.artist)
                        if match.track:
                            resolution, source = match, "model"
                    elif suggestion and suggestion.kind == "theme":
                        theme = not resolution.title_matches
                    else:
                        theme = not resolution.title_matches and explicit_theme(state.seed)
                elif resolution.track:
                    source = ("user" if request.seed_artist else "verified_hint"
                              if original_hint(request.seed) else "catalog")
                if (resolver and not resolution.track and not theme and resolution.status == "unresolved"
                        and (not suggestion or suggestion.kind != "song")):
                    expanded = resolver.expand()
                    state.searches.append(SearchResult(tracks=resolver.tracks, sources=resolver.sources))
                    resolution = expanded
                    if expanded.track:
                        source = "catalog"
                if resolver and resolution.track:
                    resolver.end_reason = "matched"
                    resolver.preferred = resolver.registry.catalog(resolution.track.source.provider, resolver.region(resolution.track))
                elif resolver and resolution.status == "ambiguous":
                    resolver.end_reason = "ambiguous"
                if source == "model":
                    # Catalog evidence verifies a recording, not the user's intended artist.
                    # Do not recall or rank until the user supplies the confirmed artist.
                    return DiscoveryResult([], state.search, resolution.track,
                                           resolution.candidates, resolution.status)
                return finish_discovery(state, resolution, allow_theme=theme)

            async with asyncio.timeout(max(0.001, 37 - compute_seconds)):
                result = await run_blocking(finish)
            response = DiscoveryResponse(
                request_id=request_id(),
                items=[RecommendationItem(id=item.key, title=item.track.title,
                    artist=item.track.artist.name, explanation=item.explanation, track=enrich_track(item.track),
                    score=item.score, score_breakdown=item.score_breakdown,
                    provenance=list(item.provenance)) for item in result.items],
                sources=result.search.sources,
                seed_track=enrich_track(result.seed_track) if result.seed_track else None,
                seed_candidates=[enrich_track(track) for track in result.seed_candidates[:5]],
                seed_status=result.seed_status, seed_resolution_source=source,
                requires_confirmation=source == "model",
                seed_storefront=(request.seed_storefront if result.seed_track
                                 and result.seed_track.source.provider == "itunes" else None),
                guidance="", guidance_provider="local", guidance_status="ready")
            if resolver:
                response.search_report = resolver.report()
                response.seed_storefront = resolver.region(result.seed_track) if result.seed_track else None
                if response.seed_storefront == "US":
                    response.seed_storefront = None
                # Persistent references are issued by a worker, never with the request-owned session.
                def references():
                    if result.seed_track:
                        response.resolution_id = resolver.issue(result.seed_track)
                    response.candidate_resolutions = {track.canonical_key: resolver.issue(track)
                                                       for track in result.seed_candidates[:5]}
                await run_blocking(references)
                if response.seed_status == "unresolved" and not result.items:
                    response.guidance = ("未在已检索平台找到该歌曲，请检查歌名、歌手或来源链接。" if request.language == "zh"
                        else "The song was not found on the searched platforms. Check the title, artist or source link.")
                    return response
            if attempted:
                response.guidance = local_guidance(response, request.language)
                if unavailable:
                    response.guidance_status = "unavailable"
                return response
            return await add_guidance(response, request, provider)
    except ResolutionError as error:
        return JSONResponse(status_code=error.status, content={"error": {"code": error.code, "message": error.message}})
    except TimeoutError:
        emit("request_error", code="discovery_timeout", status=504)
        return JSONResponse(status_code=504, content={"error": {
            "code": "discovery_timeout", "message": "Music discovery timed out. Please try again."}})
