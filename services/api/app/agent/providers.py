import json
import logging
import ssl
from time import perf_counter
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.agent.intents import (
    is_discussion,
    is_followup,
    preference_updates,
    quoted_song,
    theme_seed,
)
from app.agent.prompts import (
    ANSWER_PROMPT,
    CHAT_ANSWER_PROMPT,
    PLAN_PROMPT,
    SEED_PROMPT,
)
from app.agent.schemas import ModelCapabilities, NativeSearchState
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
        if context.get("last_seed") and message.strip().startswith(("曲风", "风格")) and theme_seed(message):
            return {"calls": []}
        if is_discussion(message):
            return {"calls": []}
        theme = theme_seed(message)
        song = quoted_song(message)
        updates = preference_updates(message)
        recommendation = theme is not None or song is not None or bool(updates) or is_followup(message) or any(word in message for word in (
            "推荐", "听什么", "再来", "recommend", "playlist", "more like", "more songs"))
        if not recommendation:
            if any(word in message for word in ("介绍", "了解", "什么是", "who", "what is", "tell me about")):
                return {"calls": [{"name": "search_music_knowledge", "arguments": {"query": message[:120]}}]}
            return {"calls": []}
        seed = theme or song or message[:120]
        intent = "theme" if theme else "song" if song else "auto"
        if is_followup(message) or updates:
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
        message = context["message"].casefold()
        if any(word in message for word in ("联网", "上网", "web search", "search online")):
            return {"answer": "当前模型接口暂不支持联网检索。我可以继续讨论一般音乐概念，或根据已有曲库与本地资料回答。你想了解哪一方面？"}
        if any(word in message for word in ("bpm", "每分钟几拍", "精确速度")):
            if any(word in message for word in ("是什么", "什么意思", "what is", "meaning")) and not any(
                    word in message for word in ("这首", "精确", "准确", "数值", "this song")):
                return {"answer": "BPM 是每分钟的节拍数，用来描述拍速。它和听感不完全相同：同样拍速的音乐，律动、音色与留白不同，也会显得松弛或紧凑。"}
            return {"answer": "当前资料没有可核对的 BPM 数值，因此无法给出精确拍速。听感上的舒缓、松弛可以从律动、音色和情绪继续讨论。"}
        if any(word in message for word in ("具体乐器", "哪些乐器", "录音版本", "最新动态", "最近发行")):
            return {"answer": "这类具体资料需要对应作品与可靠来源，目前基础模式无法核实。请补充歌名、歌手和你关注的版本，我可以根据已有资料继续说明。"}
        if recommendation is not None:
            count = len(recommendation["output"]["items"])
            if not count:
                constraints = recommendation["output"].get("constraints", {})
                if any(constraints.values()):
                    wants = "、".join(value for value in (
                        {"zh": "华语", "en": "英语"}.get(constraints.get("language")),
                        {"vocal": "带人声", "instrumental": "纯音乐"}.get(constraints.get("vocals"))) if value)
                    return {"answer": f"记住了你想听{wants}。当前曲库资料不足，暂时没有能确认满足这些条件的曲目。你有偏好的歌手或参考歌曲吗？"}
                candidates = recommendation["output"].get("seed_candidates", [])
                if candidates:
                    artists = "、".join(dict.fromkeys(item["artist"] for item in candidates))
                    return {"answer": f"找到多个同名歌曲，请确认歌手：{artists}。请带上歌名和歌手再试。"}
                return {"answer": "暂时没有符合要求的曲目，请补充歌名、歌手，或试试“舒缓的歌”。"}
            return {"answer": f"本地助手为你找到 {count} 首歌，已结合已有偏好。曲目按推荐器顺序展示。"}
        knowledge = next((r["output"]["citations"] for r in results
                          if r["name"] == "search_music_knowledge"), [])
        if not knowledge:
            previous = context.get("last_recommendation", [])
            if context.get("last_seed") and message.strip().startswith(("曲风", "风格")) and theme_seed(message) == "calm":
                return {"answer": "明白，你想要整体舒缓、松弛的听感。慢板抒情、舒缓民谣和偏柔和的 R&B 都是可以讨论的方向，它们的律动、音色和情绪各有侧重。你更偏向温暖治愈，还是安静伤感？"}
            if previous and any(word in message for word in ("为什么", "为何", "解释", "why", "explain")):
                factors = "；".join(f"{item['title']}：{item['explanation']}" for item in previous[:5])
                return {"answer": f"上一轮的匹配依据是：{factors}。这些是推荐器已有的匹配因素；风格与听感可以作为补充解读。"[:2000]}
            if "爵士" in message and "摇滚" in message:
                return {"answer": "一般听感上，爵士常重视即兴、切分与和声变化；摇滚常突出节拍、吉他和能量。这是一般风格描述，具体作品也会交叉。你偏爱松弛的律动，还是更有力量的节奏？"}
            if any(word in message for word in ("有点累", "心情", "难过", "疲惫")):
                return {"answer": "听起来你想让自己缓一缓。我们可以先从听感聊起：你希望音乐陪着情绪，还是帮助你放松下来？"}
            return {"answer": "我们可以继续聊听歌感受、风格或选择依据。当前基础模式能查询的作品资料有限；你想先聊哪种风格，或者补充一位喜欢的歌手？"}
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
        text_answer = data.get("context", {}).get("task") == "conversation" and "results" in data
        request_body = {
            "model": self.model, "max_tokens": 8192 if deep else 1200,
            "response_format": {"type": "text" if text_answer else "json_object"},
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
        if text_answer:
            return {"answer": payload.choices[0].message.content}
        value = json.loads(payload.choices[0].message.content)
        if not isinstance(value, dict):
            raise TypeError("Expected structured LLM output")
        return value

    async def plan(self, context: dict, tools: list[dict]) -> dict:
        return await self._complete(PLAN_PROMPT, {"context": context, "tools": tools})

    async def answer(self, context: dict, results: list[dict]) -> dict:
        prompt = CHAT_ANSWER_PROMPT if context.get("task") == "conversation" else ANSWER_PROMPT
        return await self._complete(prompt, {"context": context, "results": results})

    async def identify_seed(self, context: dict) -> dict:
        return await self._complete(SEED_PROMPT, {"context": context}, "identify_seed")


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "local" or not settings.llm_api_key:
        return LocalLLMProvider()
    return OpenAICompatibleProvider(settings.llm_base_url, settings.llm_api_key.get_secret_value(),
                                    settings.llm_model)


def model_capabilities(provider: LLMProvider) -> ModelCapabilities:
    # Advertise only capabilities verified at this adapter boundary. DeepSeek's
    # documented Chat/Responses interfaces do not execute built-in web search.
    reason = ("local_mode" if provider.name == "local" else "unsupported"
              if isinstance(provider, OpenAICompatibleProvider) and provider.supports_deep_thinking else "unverified")
    return ModelCapabilities(provider=provider.name,
                             supports_deep_thinking=getattr(provider, "supports_deep_thinking", False),
                             native_search=NativeSearchState(reason=reason))
