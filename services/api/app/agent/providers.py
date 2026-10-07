import json
import logging
import ssl
from time import perf_counter
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.agent.intents import is_followup, quoted_song, theme_seed
from app.agent.prompts import ANSWER_PROMPT, PLAN_PROMPT, SEED_PROMPT
from app.infrastructure.config import get_settings
from app.observability.events import correlation_headers, emit


class LLMProvider(Protocol):
    name: str
    supports_deep_thinking: bool

    async def plan(self, context: dict, tools: list[dict]) -> dict: ...

    async def answer(self, context: dict, results: list[dict]) -> dict: ...

    async def identify_seed(self, context: dict) -> dict: ...


class LocalLLMProvider:
    """Deterministic offline intent router, explicitly not a language model."""

    name = "local"
    supports_deep_thinking = False

    async def identify_seed(self, context: dict) -> dict:
        return {"kind": "unknown", "title": None, "artist": None}

    async def plan(self, context: dict, tools: list[dict]) -> dict:
        message = context["message"].lower()
        theme = theme_seed(message)
        song = quoted_song(message)
        recommendation = theme is not None or song is not None or is_followup(message) or any(word in message for word in (
            "推荐", "听什么", "再来", "recommend", "playlist", "more like", "more songs"))
        if not recommendation:
            return {"calls": [{"name": "search_music_knowledge", "arguments": {"query": message[:120]}}]}
        seed = theme or song or message[:120]
        intent = "theme" if theme else "song" if song else "auto"
        if is_followup(message):
            seed = context.get("last_seed") or "calm jazz"
            intent = context.get("last_intent", "auto") if context.get("last_seed") else "theme"
        return {"calls": [
            {"name": "get_user_profile", "arguments": {}},
            {"name": "recommend_tracks", "arguments": {"seed": seed, "limit": 5, "intent": intent}},
            {"name": "search_music_knowledge", "arguments": {"query": seed}},
            {"name": "explain_recommendation", "arguments": {}},
        ]}

    async def answer(self, context: dict, results: list[dict]) -> dict:
        recommendation = next((r for r in results if r["name"] == "recommend_tracks"), None)
        if recommendation is not None:
            count = len(recommendation["output"]["items"])
            if not count:
                candidates = recommendation["output"].get("seed_candidates", [])
                if candidates:
                    artists = "、".join(dict.fromkeys(item["artist"] for item in candidates))
                    return {"answer": f"找到多个同名歌曲，请确认歌手：{artists}。请带上歌名和歌手再试。"}
                return {"answer": "暂时没有符合要求的曲目，请补充歌名、歌手，或试试“舒缓的歌”。"}
            return {"answer": f"本地助手为你找到 {count} 首歌，已结合已有偏好。曲目按推荐器顺序展示。"}
        knowledge = next((r["output"]["citations"] for r in results
                          if r["name"] == "search_music_knowledge"), [])
        if not knowledge:
            return {"answer": "本地知识库没有相关资料。复杂问题可稍后重试，也可以试试介绍周杰伦、爵士乐或《叶惠美》。"}
        return {"answer": "本地知识库：\n" + "\n".join(f"{c['title']}：{c['text']}" for c in knowledge)}


class CompletionMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    content: str = Field(min_length=1, max_length=16000)


class CompletionChoice(BaseModel):
    message: CompletionMessage
    finish_reason: str | None = None


class ModelOutputTruncated(ValueError):
    pass


class CompletionPayload(BaseModel):
    choices: list[CompletionChoice] = Field(min_length=1, max_length=1)
    usage: dict | None = None


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model
        self.transport = transport

    @property
    def supports_deep_thinking(self) -> bool:
        return urlsplit(self.base_url).hostname == "api.deepseek.com"

    async def _complete(self, prompt: str, data: dict, operation: str | None = None) -> dict:
        started = perf_counter()
        usage = {}
        status = "error"
        failure = {}
        try:
            result = await self._request(prompt, data, usage)
            status = "ok"
            return result
        except httpx.HTTPError as exc:
            failure = {"error_type": type(exc).__name__, "code": "llm_http_error"}
            cause = exc
            for _ in range(6):
                if isinstance(cause, ssl.SSLCertVerificationError):
                    failure["code"] = "tls_verification_failed"
                    break
                cause = cause.__cause__ or cause.__context__
                if cause is None:
                    break
            raise
        finally:
            emit("llm_call", provider=self.name, model=self.model,
                 operation=operation or ("plan" if "tools" in data else "answer"), status=status,
                 latency_ms=round((perf_counter() - started) * 1000, 3), **usage, **failure,
                 level=logging.INFO if status == "ok" else logging.WARNING)

    async def _request(self, prompt: str, data: dict, usage: dict) -> dict:
        deep = self.supports_deep_thinking and data.get("context", {}).get("deep_thinking") is True
        request_body = {
            "model": self.model, "max_tokens": 8192 if deep else 1200,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
        }
        if self.supports_deep_thinking:
            request_body["thinking"] = {"type": "enabled" if deep else "disabled"}
        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(50 if deep else 10, connect=5),
                              transport=self.transport, follow_redirects=False,
                              verify=ssl.create_default_context(), trust_env=False) as client,
            client.stream("POST", f"{self.base_url}/chat/completions",
                          headers={"Authorization": f"Bearer {self.api_key}", **correlation_headers()},
                          json=request_body) as response,
        ):
            response.raise_for_status()
            body = bytearray()
            async for part in response.aiter_bytes():
                body.extend(part)
                if len(body) > (262144 if deep else 65536):
                    raise ValueError("LLM response exceeds limit")
        payload = CompletionPayload.model_validate_json(body)
        if payload.choices[0].finish_reason == "length":
            raise ModelOutputTruncated("Model output truncated")
        if payload.choices[0].finish_reason not in (None, "stop"):
            raise ValueError("Model did not complete an answer")
        # Optional usage is telemetry only; malformed metadata must not break an answer.
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = (payload.usage or {}).get(key)
            if type(value) is int and 0 <= value <= 1_000_000_000:
                usage[key] = value
        value = json.loads(payload.choices[0].message.content)
        if not isinstance(value, dict):
            raise TypeError("Expected structured LLM output")
        return value

    async def plan(self, context: dict, tools: list[dict]) -> dict:
        return await self._complete(PLAN_PROMPT, {"context": context, "tools": tools})

    async def answer(self, context: dict, results: list[dict]) -> dict:
        return await self._complete(ANSWER_PROMPT, {"context": context, "results": results})

    async def identify_seed(self, context: dict) -> dict:
        return await self._complete(SEED_PROMPT, {"context": context}, "identify_seed")


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "local" or not settings.llm_api_key:
        return LocalLLMProvider()
    return OpenAICompatibleProvider(settings.llm_base_url, settings.llm_api_key.get_secret_value(),
                                    settings.llm_model)
