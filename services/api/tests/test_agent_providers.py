import asyncio
import json
import logging
import ssl

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


@pytest.mark.parametrize("base_url, disables_thinking", [
    ("https://api.deepseek.com/", True),
    ("https://api.deepseek.com/v1/", True),
    ("https://api.deepseek.com.example.org/v1", False),
    ("https://model.example/v1", False),
])
def test_json_output_preserved_and_thinking_override_is_only_for_deepseek(
    base_url, disables_thinking,
):
    operations = []

    def respond(request):
        assert str(request.url) == f"{base_url.rstrip('/')}/chat/completions"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert body["max_tokens"] == 1200
        assert body["model"] == "fixture-model"
        if disables_thinking:
            assert body["thinking"] == {"type": "disabled"}
        else:
            assert "thinking" not in body
        data = json.loads(body["messages"][1]["content"])
        if "tools" in data:
            operations.append("plan")
            output = {"calls": [{"name": "search_music_knowledge",
                                  "arguments": {"query": "jazz"}}]}
        else:
            operations.append("answer")
            output = {"answer": "Jazz has improvisation."}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(output)}}]})

    provider = OpenAICompatibleProvider(base_url, "mock-key", "fixture-model",
                                        httpx.MockTransport(respond))
    plan = Plan.model_validate(asyncio.run(provider.plan({"message": "介绍爵士乐"}, tool_schemas())))
    assert plan.calls[0].name == "search_music_knowledge"
    answer = Answer.model_validate(asyncio.run(provider.answer({"message": "jazz"}, [])))
    assert answer.answer == "Jazz has improvisation."
    assert operations == ["plan", "answer"]


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


def test_deep_thinking_opt_in_applies_to_both_chat_calls_but_not_seed_identification():
    bodies = []

    def respond(request):
        body = json.loads(request.content)
        bodies.append(body)
        data = json.loads(body["messages"][1]["content"])
        output = ({"calls": [{"name": "search_music_knowledge", "arguments": {"query": "jazz"}}]}
                  if "tools" in data else {"kind": "unknown", "title": None, "artist": None}
                  if data["context"].get("task") == "identify_original" else {"answer": "音乐讨论"})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps(output), "reasoning_content": "private-reasoning-marker"}}]})

    provider = OpenAICompatibleProvider("https://api.deepseek.com/v1", "mock-key", "deepseek-flash",
                                        httpx.MockTransport(respond))
    context = {"message": "曲风有什么区别", "deep_thinking": True}
    asyncio.run(provider.plan(context, tool_schemas()))
    asyncio.run(provider.answer(context, []))
    asyncio.run(provider.identify_seed({"message": "晴天", "task": "identify_original"}))
    for body in bodies[:2]:
        assert body["thinking"] == {"type": "enabled"}
        assert body["max_tokens"] == 8192
        assert body["response_format"] == {"type": "json_object"}
    assert bodies[2]["thinking"] == {"type": "disabled"}
    assert bodies[2]["max_tokens"] == 1200


def test_truncated_even_valid_json_output_is_rejected():
    provider = OpenAICompatibleProvider("https://api.deepseek.com", "mock-key", "deepseek-flash",
        httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": [{
            "finish_reason": "length", "message": {"content": '{"answer":"cut off"}'}}]})))
    with pytest.raises(ValueError, match="truncated"):
        asyncio.run(provider.answer({"message": "jazz", "deep_thinking": True}, []))


def test_model_transport_uses_system_trust_with_hostname_verification(monkeypatch):
    original_client = httpx.AsyncClient
    contexts = []

    def client(**kwargs):
        context = kwargs.get("verify")
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname
        assert context.cert_store_stats()["x509_ca"] > 0
        assert kwargs["trust_env"] is False
        contexts.append(context)
        return original_client(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    provider = OpenAICompatibleProvider("https://model.example", "test-key", "test-model",
        httpx.MockTransport(lambda _: httpx.Response(200, json={
            "choices": [{"message": {"content": '{"answer":"ok"}'}}]})))
    assert asyncio.run(provider.answer({"message": "test"}, [])) == {"answer": "ok"}
    assert len(contexts) == 1


def test_tls_failure_logs_category_without_private_exception_text(caplog):
    caplog.set_level(logging.INFO, logger="music_api")

    def fail(request):
        try:
            raise ssl.SSLCertVerificationError("private-certificate-marker")
        except ssl.SSLCertVerificationError as exc:
            raise httpx.ConnectError("private-network-marker", request=request) from exc

    provider = OpenAICompatibleProvider("https://model.example", "private-key-marker", "test-model",
                                        httpx.MockTransport(fail))
    with pytest.raises(httpx.ConnectError):
        asyncio.run(provider.answer({"message": "private-chat-marker"}, []))
    events = [json.loads(record.message) for record in caplog.records if record.name == "music_api"]
    assert events[-1]["code"] == "tls_verification_failed"
    assert events[-1]["error_type"] == "ConnectError"
    assert "marker" not in caplog.text
