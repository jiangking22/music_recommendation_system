from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    DeviceResponse,
    HealthResponse,
    ProvidersHealthResponse,
    ProvidersResponse,
    ReadyResponse,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
    TrackSearchResponse,
)
from app.domain.device import DEVICE_ID_PATTERN
from app.infrastructure.cache import get_redis
from app.infrastructure.database import get_session
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.services.device import resolve_device
from app.services.recommendation import recommend

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="music-recommendation-api")


@router.get("/health/ready", response_model=ReadyResponse)
def ready(session: Annotated[Session, Depends(get_session)]) -> ReadyResponse:
    try:
        session.execute(text("SELECT 1"))
        get_redis().ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dependencies unavailable.") from exc
    return ReadyResponse(status="ok")


@router.get("/v1/device", response_model=DeviceResponse)
def get_device(
    session: Annotated[Session, Depends(get_session)],
    x_device_id: Annotated[str, Header(alias="X-Device-Id", min_length=16, max_length=128, pattern=DEVICE_ID_PATTERN)],
) -> DeviceResponse:
    device = resolve_device(session, x_device_id)
    return DeviceResponse(deviceId=device.device_id)


@router.post("/v1/recommendations", response_model=RecommendationResponse)
def recommendations(
    request: RecommendationRequest,
    registry: Annotated[ProviderRegistry, Depends(get_provider_registry)],
) -> RecommendationResponse:
    songs, search = recommend(request.seed, request.limit, registry)
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
    return RecommendationResponse(request_id=str(uuid4()), items=items, sources=search.sources)


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
