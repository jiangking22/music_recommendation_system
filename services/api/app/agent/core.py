import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import aclosing
from functools import partial
from time import perf_counter
from weakref import WeakKeyDictionary

import httpx
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.agent.memory import Memory, MemoryError
from app.agent.providers import LLMProvider
from app.agent.schemas import Answer, ChatRequest, ChatResponse, Plan, ToolTrace
from app.agent.tools import TOOL_INPUTS, ToolContext, invoke_tool, tool_schemas
from app.infrastructure.workers import run_blocking
from app.observability.events import emit
from app.providers.registry import ProviderRegistry

_agent_slots = WeakKeyDictionary()


class AgentError(Exception):
    def __init__(self, code: str, status: int = 502) -> None:
        super().__init__(code)
        self.code, self.status = code, status


class Agent:
    def __init__(self, engine: Engine, registry: ProviderRegistry, provider: LLMProvider,
                 timeout_seconds: float = 30) -> None:
        self.engine, self.registry, self.provider = engine, registry, provider
        self.timeout_seconds = timeout_seconds

    async def events(self, request: ChatRequest) -> AsyncIterator[dict]:
        traces = []
        try:
            slots = _agent_slots.setdefault(asyncio.get_running_loop(), asyncio.Semaphore(4))
            if slots.locked():
                raise AgentError("agent_busy", 503)
            async with slots, asyncio.timeout(self.timeout_seconds):
                yield {"event": "status", "data": {"stage": "analyzing", "label": "分析需求"}}
                memory = Memory(self.engine)
                conversation = await run_blocking(lambda: memory.load(request))
                context = {"message": request.message, "history": conversation.messages,
                           "last_seed": conversation.last_seed,
                           "preference_summary": conversation.preference_summary}
                started = perf_counter()
                plan = Plan.model_validate(await self.provider.plan(context, tool_schemas()))
                if self.provider.name == "local":
                    emit("llm_call", provider="local", model="rule-router", operation="plan", status="ok",
                         latency_ms=round((perf_counter() - started) * 1000, 3))
                # Validate the entire plan before any business tool is executed.
                for call in plan.calls:
                    TOOL_INPUTS[call.name].model_validate(call.arguments)
                names = [call.name for call in plan.calls]
                if len(names) != len(set(names)):
                    raise AgentError("invalid_model_output")
                if "explain_recommendation" in names and ("recommend_tracks" not in names or
                        names.index("explain_recommendation") < names.index("recommend_tracks")):
                    raise AgentError("invalid_model_output")
                tools = ToolContext(self.engine, self.registry, request.device_id, conversation)
                results = []
                for call in plan.calls:
                    started = perf_counter()
                    yield {"event": "status", "data": {
                        "stage": "preferences" if call.name == "get_user_profile" else "tool",
                        "label": "查询偏好" if call.name == "get_user_profile" else "调用工具",
                        "tool": call.name}}
                    try:
                        output = await run_blocking(partial(invoke_tool, call, tools))
                    except Exception:
                        traces.append(ToolTrace(name=call.name, status="error"))
                        emit("agent_tool", tool=call.name, status="error", level=logging.WARNING,
                             latency_ms=round((perf_counter() - started) * 1000, 3))
                        raise
                    traces.append(ToolTrace(name=call.name, status="ok"))
                    emit("agent_tool", tool=call.name, status="ok",
                         latency_ms=round((perf_counter() - started) * 1000, 3))
                    results.append({"name": call.name, "output": output})
                    yield {"event": "tool_result", "data": {"tool": call.name, "status": "ok"}}
                started = perf_counter()
                answer = Answer.model_validate(await self.provider.answer(context, results))
                if self.provider.name == "local":
                    emit("llm_call", provider="local", model="rule-router", operation="answer", status="ok",
                         latency_ms=round((perf_counter() - started) * 1000, 3))
                response = ChatResponse(conversation_id=conversation.id, answer=answer.answer,
                                        recommended_tracks=tools.items, used_tools=traces,
                                        explanation=tools.explanation, citations=tools.citations,
                                        sources=tools.sources, provider=self.provider.name)
                await run_blocking(lambda: memory.save(request, conversation, answer.answer))
                yield {"event": "status", "data": {"stage": "complete", "label": "返回结果"}}
                yield {"event": "done", "data": response.model_dump(mode="json")}
        except TimeoutError as exc:
            raise AgentError("agent_timeout", 504) from exc
        except MemoryError as exc:
            raise AgentError(str(exc), 404 if str(exc) == "conversation_not_found" else 409) from exc
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            raise AgentError("invalid_model_output") from exc
        except httpx.HTTPError as exc:
            raise AgentError("llm_unavailable", 503) from exc
        except SQLAlchemyError as exc:
            raise AgentError("database_unavailable", 503) from exc
        except AgentError:
            raise
        except Exception as exc:
            emit("agent_failed", code="agent_unavailable", level=logging.ERROR)
            raise AgentError("agent_unavailable", 503) from exc

    async def chat(self, request: ChatRequest) -> ChatResponse:
        async with aclosing(self.events(request)) as events:
            async for event in events:
                if event["event"] == "done":
                    return ChatResponse.model_validate(event["data"])
        raise AgentError("agent_incomplete")
