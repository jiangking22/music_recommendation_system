import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from app.agent.providers import (
    LocalLLMProvider,
    OpenAICompatibleProvider,
    get_llm_provider,
)
from app.agent.schemas import Answer, Plan
from app.agent.tools import tool_schemas
from app.infrastructure.config import Settings


def test_openai_compatible_adapter_uses_mock_transport_for_plan_and_answer():
    def respond(request):
        assert str(request.url) == "https://model.example/v1/chat/completions"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert body["max_tokens"] == 1200
        assert body["model"] == "fixture-model"
        assert request.headers["authorization"] == "Bearer mock-key"
        data = json.loads(body["messages"][1]["content"])
        if "tools" in data:
            assert {t["name"] for t in data["tools"]} == {t["name"] for t in tool_schemas()}
            output = {"calls": [{"name": "search_music_knowledge", "arguments": {"query": "jazz"}}]}
        else:
            output = {"answer": "Jazz has improvisation."}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(output)}}]})

    provider = OpenAICompatibleProvider("https://model.example/v1", "mock-key", "fixture-model",
                                        httpx.MockTransport(respond))
    plan = Plan.model_validate(asyncio.run(provider.plan({"message": "介绍爵士乐"}, tool_schemas())))
    assert plan.calls[0].name == "search_music_knowledge"
    answer = Answer.model_validate(asyncio.run(provider.answer({"message": "jazz"}, [])))
    assert answer.answer == "Jazz has improvisation."


@pytest.mark.parametrize("payload", [
    {"choices": []}, {"choices": [{"message": {"content": "not-json"}}]},
    {"choices": [{"message": {"content": "[]"}}]},
])
def test_llm_payload_validation(payload):
    provider = OpenAICompatibleProvider("https://model.example/v1", "mock-key", "fixture-model",
                                        httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
    with pytest.raises((ValidationError, ValueError, TypeError)):
        asyncio.run(provider.plan({"message": "jazz"}, tool_schemas()))


def test_missing_or_empty_key_uses_local_fallback(monkeypatch):
    from app.agent import providers

    for key in (None, ""):
        config = Settings(database_url="sqlite+pysqlite:///:memory:", redis_url="redis://localhost:6379/0",
                          llm_provider="openai_compatible", llm_api_key=key)
        monkeypatch.setattr(providers, "get_settings", lambda config=config: config)
        assert isinstance(get_llm_provider(), LocalLLMProvider)


def test_llm_size_cap():
    provider = OpenAICompatibleProvider("https://model.example/v1", "mock-key", "fixture-model",
                                        httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 65537)))
    with pytest.raises(ValueError, match="exceeds limit"):
        asyncio.run(provider.plan({"message": "jazz"}, tool_schemas()))
