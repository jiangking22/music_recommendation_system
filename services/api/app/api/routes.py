from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    ProfileAffinity,
    ProfileResponse,
    ProvidersHealthResponse,
    ProvidersResponse,
    ReadyResponse,
    RecentFeedback,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
    TrackSearchResponse,
)
from app.auth.dependencies import CurrentIdentity
from app.auth.service import AuthError
from app.domain.artist_names import preferred_artist_name
from app.infrastructure.cache import get_redis
from app.infrastructure.database import get_session
from app.observability.events import request_id
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.repository.feedback import load_profile, recent_feedback, save_feedback
from app.services.recommendation import recommend

router = APIRouter()
public_router = APIRouter()


@public_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="music-recommendation-api")


@public_router.get("/health/ready", response_model=ReadyResponse)
def ready(session: Annotated[Session, Depends(get_session)]) -> ReadyResponse:
    try:
        session.execute(text("SELECT 1"))
        get_redis().ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dependencies unavailable.") from exc
    return ReadyResponse(status="ok")


@router.get("/v1/device")
def get_device():
    raise AuthError("device_identity_retired", 410, "Device identity retired. Use account login.")


@router.post("/v1/recommendations", response_model=RecommendationResponse)
def recommendations(
    request: RecommendationRequest,
    registry: Annotated[ProviderRegistry, Depends(get_provider_registry)],
    session: Annotated[Session, Depends(get_session)],
    identity: CurrentIdentity,
) -> RecommendationResponse:
    profile = load_profile(session, identity.user_id)
    songs, search = recommend(request.seed, request.limit, registry, profile)
    items = [
        RecommendationItem(
            id=song.key,
            title=song.track.title,
            artist=song.track.artist.name,
            explanation=song.explanation,
            track=song.track,
            score=song.score,
            score_breakdown=song.score_breakdown,
            provenance=list(song.provenance),
        )
        for song in songs
    ]
    return RecommendationResponse(request_id=request_id(), items=items, sources=search.sources)


@router.post("/v1/feedback", response_model=FeedbackResponse)
def feedback(
    request: FeedbackRequest,
    session: Annotated[Session, Depends(get_session)],
    identity: CurrentIdentity,
) -> FeedbackResponse:
    key = save_feedback(session, identity.user_id, request.track, request.value)
    return FeedbackResponse(track_key=key, value=request.value)


@router.get("/v1/profile", response_model=ProfileResponse, response_model_exclude_none=True)
def profile(
    session: Annotated[Session, Depends(get_session)],
    identity: CurrentIdentity,
) -> ProfileResponse:
    snapshot = load_profile(session, identity.user_id)

    def display_name(name: str) -> str | None:
        preferred = preferred_artist_name(name)
        return preferred if preferred != name else None

    def preferred(values: dict[str, float], artists: bool = False) -> list[ProfileAffinity]:
        ranked = sorted(((name, weight) for name, weight in values.items() if weight > 0),
                        key=lambda pair: (-pair[1], pair[0]))
        return [ProfileAffinity(name=name, display_name=display_name(name) if artists else None,
                                weight=weight) for name, weight in ranked[:5]]

    return ProfileResponse(
        artists=preferred(snapshot.artist_affinity, artists=True),
        genres=preferred(snapshot.genre_affinity),
        tags=preferred(snapshot.tag_affinity),
        languages=preferred(snapshot.language_affinity),
        recent_feedback=[RecentFeedback(track_key=item.track_key, artist=item.artist,
                                        artist_display_name=display_name(item.artist), value=item.value)
                         for item in recent_feedback(session, identity.user_id)],
    )


@router.get("/v1/providers", response_model=ProvidersResponse)
def providers(registry: Annotated[ProviderRegistry, Depends(get_provider_registry)]) -> ProvidersResponse:
    return ProvidersResponse(providers=registry.capabilities())


@router.get("/v1/providers/health", response_model=ProvidersHealthResponse)
def providers_health(registry: Annotated[ProviderRegistry, Depends(get_provider_registry)]) -> ProvidersHealthResponse:
    return ProvidersHealthResponse(providers=registry.health())


@router.get("/v1/tracks/search", response_model=TrackSearchResponse)
def search_tracks(
    registry: Annotated[ProviderRegistry, Depends(get_provider_registry)],
    q: Annotated[str, Query(min_length=1, max_length=120)],
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> TrackSearchResponse:
    if not q.strip():
        raise HTTPException(status_code=422, detail="Invalid query.")
    return TrackSearchResponse.model_validate(registry.search_tracks(q.strip(), limit).model_dump())
