import asyncio
from typing import Annotated
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.agent.providers import LLMProvider, get_llm_provider
from app.api.schemas import DiscoveryRequest, DiscoveryResponse, RecommendationItem
from app.domain.device import DEVICE_ID_PATTERN
from app.infrastructure.database import get_session
from app.infrastructure.workers import run_blocking
from app.observability.events import emit, request_id
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.repository.feedback import load_profile
from app.services.discovery_guidance import add_guidance
from app.services.recommendation import discover

router = APIRouter(prefix="/v1/recommendations", tags=["recommendations"])
_discovery_slots = WeakKeyDictionary()


@router.post("/discover", response_model=DiscoveryResponse)
async def discovery(
    request: DiscoveryRequest,
    session: Annotated[Session, Depends(get_session)],
    registry: Annotated[ProviderRegistry, Depends(get_provider_registry)],
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    x_device_id: Annotated[str | None, Header(alias="X-Device-Id", min_length=16,
                                              max_length=128, pattern=DEVICE_ID_PATTERN)] = None,
):
    slots = _discovery_slots.setdefault(asyncio.get_running_loop(), asyncio.Semaphore(4))
    if slots.locked():
        return JSONResponse(status_code=503, content={"error": {
            "code": "discovery_busy", "message": "Music discovery is busy. Please try again."}})
    engine = session.get_bind()

    def compute():
        # The worker owns its session until completion, including request cancellation.
        with Session(engine) as worker_session:
            profile = load_profile(worker_session, x_device_id) if x_device_id else None
            return discover(request.seed, request.limit, registry, profile, request.seed_artist)

    try:
        async with slots, asyncio.timeout(45):
            async with asyncio.timeout(37):
                result = await run_blocking(compute)
            response = DiscoveryResponse(
                request_id=request_id(),
                items=[RecommendationItem(id=item.key, title=item.track.title,
                    artist=item.track.artist.name, explanation=item.explanation, track=item.track,
                    score=item.score, score_breakdown=item.score_breakdown,
                    provenance=list(item.provenance)) for item in result.items],
                sources=result.search.sources, seed_track=result.seed_track,
                seed_candidates=result.seed_candidates[:5], seed_status=result.seed_status,
                guidance="", guidance_provider="local", guidance_status="ready")
            return await add_guidance(response, request, provider)
    except TimeoutError:
        emit("request_error", code="discovery_timeout", status=504)
        return JSONResponse(status_code=504, content={"error": {
            "code": "discovery_timeout", "message": "Music discovery timed out. Please try again."}})
