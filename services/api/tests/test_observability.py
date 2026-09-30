import asyncio
import json
import logging

import httpx
from fastapi.testclient import TestClient

from app.agent.providers import OpenAICompatibleProvider
from app.domain.music import ProviderError, ProviderResult
from app.main import app
from app.providers.registry import ProviderRegistry, get_provider_registry


def events(caplog):
    return [json.loads(record.message) for record in caplog.records
            if record.name.startswith("music_api")]


def test_request_and_recommendation_share_correlation_without_private_input(caplog):
    caplog.set_level(logging.INFO, logger="music_api")
    app.dependency_overrides[get_provider_registry] = lambda: ProviderRegistry([])
    try:
        with TestClient(app) as client:
            response = client.post("/v1/recommendations", json={"seed": "private-seed-marker", "limit": 2},
                                   headers={"X-Request-Id": "demo-request-123", "Authorization": "secret-marker"})
        assert response.headers["x-request-id"] == response.json()["request_id"] == "demo-request-123"
        logs = events(caplog)
        assert {log["event"] for log in logs} >= {"http_request", "recommendation"}
        assert all(log["request_id"] == "demo-request-123" for log in logs)
        assert len({log["trace_id"] for log in logs}) == 1
        request = next(log for log in logs if log["event"] == "http_request")
        assert request["route"] == "/v1/recommendations"
        assert request["status"] == 200 and request["latency_ms"] >= 0
        assert "private-seed-marker" not in caplog.text and "secret-marker" not in caplog.text
    finally:
        app.dependency_overrides.clear()


def test_invalid_correlation_and_unknown_path_are_not_logged(caplog):
    caplog.set_level(logging.INFO, logger="music_api")
    with TestClient(app) as client:
        response = client.get("/private-path-marker?q=private-query-marker",
                              headers={"X-Request-Id": "invalid secret-marker"})
    assert response.status_code == 404
    assert len(response.headers["x-request-id"]) == 32
    request = next(log for log in events(caplog) if log["event"] == "http_request")
    assert request["route"] == "unmatched" and request["status"] == 404
    assert "marker" not in caplog.text


def test_llm_logs_validated_usage_but_not_payload_or_key(caplog):
    caplog.set_level(logging.INFO, logger="music_api")
    provider = OpenAICompatibleProvider("https://model.example/v1", "key-marker", "fixture-model",
        httpx.MockTransport(lambda _: httpx.Response(200, json={
            "choices": [{"message": {"content": '{"answer":"private-answer-marker"}'}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28,
                      "private": "secret-marker"}})))
    asyncio.run(provider.answer({"message": "private-chat-marker"}, []))
    event = next(log for log in events(caplog) if log["event"] == "llm_call")
    assert event["model"] == "fixture-model" and event["provider"] == "openai_compatible"
    assert event["prompt_tokens"] == 20 and event["completion_tokens"] == 8 and event["total_tokens"] == 28
    assert "marker" not in caplog.text


def test_provider_failure_logs_latency_and_propagated_trace(caplog):
    class Failed:
        name = "itunes"

        def search_tracks(self, query, limit):
            return ProviderResult(provider=self.name, error=ProviderError(code="timeout", message="private-marker"))

    caplog.set_level(logging.INFO, logger="music_api")
    app.dependency_overrides[get_provider_registry] = lambda: ProviderRegistry([Failed()])
    try:
        with TestClient(app) as client:
            response = client.get("/v1/tracks/search?q=jazz", headers={
                "traceparent": "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"})
        assert response.status_code == 200
        event = next(log for log in events(caplog) if log["event"] == "provider_call")
        assert event["code"] == "timeout" and event["status"] == "error"
        assert event["provider"] == "itunes" and event["latency_ms"] >= 0
        assert event["trace_id"] == "0123456789abcdef0123456789abcdef"
        assert "private-marker" not in caplog.text
    finally:
        app.dependency_overrides.clear()
