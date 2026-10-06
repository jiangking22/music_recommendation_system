"""One explicit model lookup after the user rejects all catalog candidates."""

import asyncio

import httpx

from app.agent.providers import LLMProvider
from app.api.schemas import (
    OriginalIdentificationRequest,
    OriginalIdentificationResponse,
    SongIdentity,
)
from app.domain.artist_names import (
    artist_aliases,
    artist_identity,
    enrich_track,
    preferred_artist_name,
)
from app.domain.discovery import SeedResolution, resolve_seed, title_matches_query
from app.domain.music import normalize_text
from app.domain.profile import PreferenceProfile
from app.infrastructure.workers import run_blocking
from app.observability.events import request_id
from app.providers.registry import ProviderRegistry
from app.services.recommendation import MAX_DISCOVERY_OPERATIONS, DiscoverySearch
from app.services.seed_identification import SeedIdentification


class IdentificationError(Exception):
    def __init__(self, code: str, status: int, message: str):
        self.code, self.status, self.message = code, status, message
        super().__init__(message)


async def identify_original(request: OriginalIdentificationRequest, provider: LLMProvider,
                            registry: ProviderRegistry) -> OriginalIdentificationResponse:
    if provider.name == "local":
        raise IdentificationError("identification_not_configured", 503,
                                  "No model API is configured on the server.")
    context = {"task": "identify_original", "message": request.seed,
               "rejected_candidates": [item.model_dump() for item in request.rejected_candidates]}
    try:
        async with asyncio.timeout(8):
            suggestion = SeedIdentification.model_validate(await provider.identify_seed(context))
    except (TimeoutError, httpx.TimeoutException) as error:
        raise IdentificationError("identification_timeout", 504,
                                  "Original identification timed out. Please try again.") from error
    except httpx.HTTPError as error:
        raise IdentificationError("identification_unavailable", 502,
                                  "The model API is unavailable. Please try again.") from error
    except (ValueError, TypeError, KeyError) as error:
        raise IdentificationError("identification_invalid_output", 502,
                                  "The model returned invalid identification data.") from error

    rejected = {artist_identity(item.artist) for item in request.rejected_candidates}
    response = OriginalIdentificationResponse(request_id=request_id(), status="unknown")
    if (suggestion.kind != "song" or artist_identity(suggestion.artist) in rejected
            or not title_matches_query(request.seed, suggestion.title, suggestion.artist, suggestion.artist)):
        return response
    response.suggestion = SongIdentity(title=suggestion.title, artist=suggestion.artist)

    def verify():
        # No profile or recommendation work: only the existing bounded catalog matcher.
        state = DiscoverySearch(request.seed, 3, registry, PreferenceProfile(), suggestion.artist,
                                SeedResolution(None, [], "unresolved"))
        # Reserve a registry operation for online verification beyond the default US catalog.
        queried = set()
        for artist in (suggestion.artist, *artist_aliases(suggestion.artist)):
            query = f"{suggestion.title} {artist}"[:120]
            key = normalize_text(query)
            if key in queried:
                continue
            if len(queried) == MAX_DISCOVERY_OPERATIONS - 1:
                break
            queried.add(key)
            state.query(query)
            resolution = resolve_seed(state.seed, state.search.tracks, suggestion.artist)
            if resolution.track:
                return resolution.track, state.search.sources, None
        query = f"{suggestion.title} {preferred_artist_name(suggestion.artist)}"[:120]
        for storefront in ("TW", "HK"):
            if len(state.searches) == MAX_DISCOVERY_OPERATIONS:
                break
            state.registry = registry.for_storefront(storefront)
            state.query(query)
            resolution = resolve_seed(state.seed, state.search.tracks, suggestion.artist)
            if resolution.track:
                verified_storefront = storefront if resolution.track.source.provider == "itunes" else None
                return resolution.track, state.search.sources, verified_storefront
        return None, state.search.sources, None

    async with asyncio.timeout(37):
        track, response.sources, response.verified_storefront = await run_blocking(verify)
    response.status = "matched" if track else "unverified"
    response.matched_track = enrich_track(track) if track else None
    return response
