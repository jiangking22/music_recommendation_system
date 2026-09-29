from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    DeviceResponse,
    HealthResponse,
    ReadyResponse,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
)
from app.domain.device import DEVICE_ID_PATTERN
from app.infrastructure.cache import get_redis
from app.infrastructure.database import get_session
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
def recommendations(request: RecommendationRequest) -> RecommendationResponse:
    songs = recommend(request.seed, request.limit)
    items = [
        RecommendationItem(
            id=song.id,
            title=song.title,
            artist=song.artist,
            explanation="Bundled fixture example; no live catalog or ranking is used.",
        )
        for song in songs
    ]
    return RecommendationResponse(request_id=str(uuid4()), items=items)
