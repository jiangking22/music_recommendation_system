import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.discovery import discovery_slots
from app.api.schemas import RecordingResolveRequest, RecordingResolveResponse
from app.infrastructure.database import get_session
from app.infrastructure.workers import run_blocking
from app.observability.events import request_id
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.services.recording_resolution import RecordingResolver

router = APIRouter(prefix="/v1/recordings", tags=["recordings"])


@router.post("/resolve", response_model=RecordingResolveResponse)
async def resolve_recording(request: RecordingResolveRequest,
    session: Annotated[Session, Depends(get_session)],
    registry: Annotated[ProviderRegistry, Depends(get_provider_registry)]):
    slots = discovery_slots()
    if slots.locked():
        return JSONResponse(status_code=503, content={"error": {
            "code": "discovery_busy", "message": "Music discovery is busy. Please try again."}})
    resolver = RecordingResolver(registry, session.get_bind(), request.seed, request.artist, manual=True)
    try:
        async with slots, asyncio.timeout(30):
            return await run_blocking(lambda: resolver.resolve(platform=request.platform, song_url=request.song_url))
    except TimeoutError:
        resolver.end_reason = "deadline"
        resolver.deadline = 0
        return RecordingResolveResponse(request_id=request_id(),
            status="incomplete", search_report=resolver.report())
