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
from app.agent.providers import (
    LLMProvider,
    LocalLLMProvider,
    ModelOutputTruncated,
    model_capabilities,
)
from app.agent.schemas import AgentRequest, Answer, ChatResponse, Plan, ToolTrace
from app.agent.tools import TOOL_INPUTS, ToolContext, invoke_tool, tool_schemas
from app.infrastructure.workers import run_blocking
from app.observability.events import emit
from app.providers.registry import ProviderRegistry
from app.services.progressive_search import progressive_recommendation

_agent_slots = WeakKeyDictionary()
DEEP_TIMEOUT_SECONDS = 120


class AgentError(Exception):
    def __init__(self, code: str, status: int = 502) -> None:
        super().__init__(code)
        self.code, self.status = code, status


class Agent:
    def __init__(self, engine: Engine, registry: ProviderRegistry, provider: LLMProvider,
                 timeout_seconds: float = 90) -> None:
        self.engine, self.registry, self.provider = engine, registry, provider
        self.timeout_seconds = timeout_seconds

    async def events(self, request: AgentRequest) -> AsyncIterator[dict]:
        traces = []
        try:
            slots = _agent_slots.setdefault(asyncio.get_running_loop(), asyncio.Semaphore(4))
            if slots.locked():
                raise AgentError("agent_busy", 503)
            deep = request.deep_thinking and getattr(self.provider, "supports_deep_thinking", False)
            async with slots, asyncio.timeout(DEEP_TIMEOUT_SECONDS if deep else self.timeout_seconds):
                yield {"event": "status", "data": {"stage": "analyzing", "label": "分析需求"}}
                memory = Memory(self.engine)
                conversation = await run_blocking(lambda: memory.load(request))
                context = {"task": "conversation", "message": request.message, "history": conversation.messages,
                           "last_seed": conversation.last_seed,
                           "last_intent": conversation.last_intent,
                           "preference_summary": conversation.preference_summary, "deep_thinking": deep,
                           "listening_constraints": conversation.constraints.model_dump(),
                           "last_recommendation": conversation.recommendation_context,
                           "native_search": model_capabilities(self.provider).native_search.model_dump()}
                if deep:
                    yield {"event": "status", "data": {"stage": "thinking", "label": "深入理解上下文"}}
                provider = self.provider
                fallback_reason = None
                started = perf_counter()
                try:
                    plan_data = await provider.plan(context, tool_schemas())
                except httpx.HTTPError:
                    provider, fallback_reason = LocalLLMProvider(), "llm_unavailable"
                    emit("agent_fallback", operation="plan", code=fallback_reason, level=logging.WARNING)
                    yield {"event": "status", "data": {"stage": "fallback", "label": "已切换基础模式"}}
                    plan_data = await provider.plan(context, tool_schemas())
                plan = Plan.model_validate(plan_data)
                if provider.name == "local":
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
                tools = ToolContext(self.engine, self.registry, request.user_id, conversation,
                                    message=request.message, defer_recall=True)
                results = []
                for call in plan.calls:
                    started = perf_counter()
                    yield {"event": "status", "data": {
                        "stage": "preferences" if call.name == "get_user_profile" else "tool",
                        "label": "查询偏好" if call.name == "get_user_profile" else "调用工具",
                        "tool": call.name}}
                    try:
                        output = await run_blocking(partial(invoke_tool, call, tools))
                        if call.name == 'recommend_tracks':
                            async for progress in progressive_recommendation(call, tools, provider, output):
                                if 'output' in progress:
                                    output = progress['output']
                                else:
                                    yield {'event': 'status', 'data': progress}
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
                yield {"event": "status", "data": {"stage": "composing", "label": "整理回答"}}
                try:
                    answer_data = await provider.answer(context, results)
                except httpx.HTTPError:
                    provider, fallback_reason = LocalLLMProvider(), "llm_unavailable"
                    emit("agent_fallback", operation="answer", code=fallback_reason, level=logging.WARNING)
                    yield {"event": "status", "data": {"stage": "fallback", "label": "已切换基础模式"}}
                    answer_data = await provider.answer(context, results)
                answer = Answer.model_validate(answer_data)
                if provider.name == "local":
                    emit("llm_call", provider="local", model="rule-router", operation="answer", status="ok",
                         latency_ms=round((perf_counter() - started) * 1000, 3))
                response = ChatResponse(conversation_id=conversation.id, answer=answer.answer,
                                        recommended_tracks=tools.items, used_tools=traces,
                                        explanation=tools.explanation, citations=tools.citations,
                                        sources=tools.sources, provider=provider.name,
                                        fallback_reason=fallback_reason,
                                        thinking_mode="basic" if provider.name == "local" else "deep" if deep else "standard",
                                        thinking_unavailable_reason=(fallback_reason or "unsupported")
                                        if request.deep_thinking and (provider.name == "local" or not deep) else None,
                                        native_search=model_capabilities(provider).native_search,
                                        search_report=tools.search_report, web_references=tools.web_references)
                await run_blocking(lambda: memory.save(request, conversation, answer.answer))
                yield {"event": "status", "data": {"stage": "complete", "label": "返回结果"}}
                yield {"event": "done", "data": response.model_dump(mode="json")}
        except TimeoutError as exc:
            raise AgentError("agent_timeout", 504) from exc
        except MemoryError as exc:
            raise AgentError(str(exc), 404 if str(exc) == "conversation_not_found" else 409) from exc
        except ModelOutputTruncated as exc:
            raise AgentError("model_output_truncated") from exc
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

    async def chat(self, request: AgentRequest) -> ChatResponse:
        async with aclosing(self.events(request)) as events:
            async for event in events:
                if event["event"] == "done":
                    return ChatResponse.model_validate(event["data"])
        raise AgentError("agent_incomplete")
