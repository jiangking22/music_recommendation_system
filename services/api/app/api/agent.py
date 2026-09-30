import json
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.agent.core import Agent, AgentError
from app.agent.providers import LLMProvider, get_llm_provider
from app.agent.schemas import ChatRequest, ChatResponse
from app.infrastructure.config import get_settings
from app.infrastructure.database import get_session
from app.providers.registry import ProviderRegistry, get_provider_registry

router = APIRouter(prefix="/v1/agent", tags=["agent"])


def get_agent(session: Annotated[Session, Depends(get_session)],
              registry: Annotated[ProviderRegistry, Depends(get_provider_registry)],
              provider: Annotated[LLMProvider, Depends(get_llm_provider)]) -> Agent:
    return Agent(session.get_bind(), registry, provider, get_settings().agent_timeout_seconds)


def error_envelope(error: AgentError) -> dict:
    messages = {"conversation_not_found": "Conversation unavailable for this device.",
                "agent_busy": "Music assistant is busy. Please try again.",
                "conversation_conflict": "Conversation changed; retry the message.",
                "agent_timeout": "Music assistant timed out.",
                "llm_unavailable": "Language provider unavailable.",
                "database_unavailable": "Database unavailable.",
                "invalid_model_output": "Music assistant returned invalid output."}
    return {"error": {"code": error.code, "message": messages.get(error.code, "Music assistant unavailable.")}}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, agent: Annotated[Agent, Depends(get_agent)]):
    try:
        return await agent.chat(request)
    except AgentError as error:
        return JSONResponse(status_code=error.status, content=error_envelope(error))


@router.post("/chat/stream", response_class=StreamingResponse)
async def chat_stream(request: ChatRequest, agent: Annotated[Agent, Depends(get_agent)]):
    async def stream():
        try:
            async with aclosing(agent.events(request)) as events:
                async for event in events:
                    yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
        except AgentError as error:
            yield f"event: error\ndata: {json.dumps(error_envelope(error), ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
