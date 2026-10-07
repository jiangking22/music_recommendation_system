import json
import logging
from pathlib import Path

import httpx
import pytest
from account_helpers import seed_account
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.providers import LocalLLMProvider, get_llm_provider
from app.domain.music import Artist, ProviderSource, SearchResult, Track, canonical_key
from app.infrastructure.database import get_session
from app.main import app
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.rag.repository import ingest_fixture
from app.repository.models import Base


@pytest.fixture
def client(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'agent_api.db'}")
    Base.metadata.create_all(engine)
    seed_account(engine)
    with Session(engine) as session:
        ingest_fixture(session)

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    app.dependency_overrides[get_provider_registry] = lambda: ProviderRegistry([])
    app.dependency_overrides[get_llm_provider] = LocalLLMProvider
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


BODY = {"message": "推荐适合学习的歌"}


def test_legacy_timeout_setting_still_allows_the_full_progressive_chat_budget(monkeypatch):
    from types import SimpleNamespace

    from app.api import agent as agent_api
    monkeypatch.setattr(agent_api, 'get_settings', lambda: SimpleNamespace(agent_timeout_seconds=30))
    session = SimpleNamespace(get_bind=lambda: None)
    agent = agent_api.get_agent(session, ProviderRegistry([]), LocalLLMProvider())
    assert agent.timeout_seconds == 90


def test_real_recommendation_tool_emits_display_name_without_replacing_identity(client):
    class FayeRegistry:
        def search_tracks(self, query, limit):
            return SearchResult(tracks=[Track(title=title, artist=Artist(name="Faye Wong"),
                source=ProviderSource(provider="itunes", provider_track_id=title),
                canonical_key=canonical_key(title, "Faye Wong")) for title in ("匆匆那年", "红豆")],
                sources={})

    class FixedSeed(LocalLLMProvider):
        async def plan(self, context, tools):
            return {"calls": [{"name": "recommend_tracks", "arguments": {"seed": "匆匆那年"}}]}

    app.dependency_overrides[get_provider_registry] = FayeRegistry
    app.dependency_overrides[get_llm_provider] = FixedSeed
    response = client.post("/v1/agent/chat", json={**BODY, "message": "推荐与匆匆那年类似的歌"})
    assert response.status_code == 200
    item = response.json()["recommended_tracks"][0]
    assert item["title"] == "红豆"
    assert item["artist"] == "Faye Wong"
    assert item["track"]["artist"]["display_name"] == "王菲"
    assert item["id"] == canonical_key("红豆", "Faye Wong")


def test_chat_and_follow_up_route(client):
    response = client.post("/v1/agent/chat", json=BODY)
    assert response.status_code == 200
    result = response.json()
    assert result["recommended_tracks"][0]["title"] == "Blue Window"
    again = client.post("/v1/agent/chat", json={**BODY, "message": "再来几首",
                                             "conversation_id": result["conversation_id"]})
    assert again.status_code == 200
    assert again.json()["conversation_id"] == result["conversation_id"]
    direct = client.post("/v1/recommendations", json={"seed": "calm jazz", "limit": 5},
                         headers={"X-Device-Id": "account_test"})
    assert result["recommended_tracks"] == direct.json()["items"]
    assert result["citations"]


def test_artist_question_is_grounded_in_rag_and_mcp_surface_is_independent(client):
    response = client.post("/v1/agent/chat", json={**BODY, "message": "介绍周杰伦"})
    assert response.status_code == 200
    assert "周杰伦" in response.json()["answer"]
    assert response.json()["recommended_tracks"] == []
    assert response.json()["used_tools"] == [{"name": "search_music_knowledge", "status": "ok"}]
    assert response.json()["citations"][0]["category"] == "artist"
    listing = client.get("/v1/mcp/tools")
    assert listing.json()["tools"][0]["name"] == "music_search"
    called = client.post("/v1/mcp/tools/call", json={"name": "music_search", "arguments": {"query": "jazz"}})
    assert called.status_code == 200
    assert len(called.json()["structuredContent"]["tracks"]) == 2
    bad = client.post("/v1/mcp/tools/call", json={"name": "music_search", "arguments": {"query": " "}})
    assert bad.status_code == 422


def test_sse_has_public_statuses_and_one_terminal_result(client, caplog):
    caplog.set_level(logging.INFO, logger="music_api")
    response = client.post("/v1/agent/chat/stream", json=BODY)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    blocks = response.text.strip().split("\n\n")
    events = [(block.splitlines()[0][7:], json.loads(block.splitlines()[1][6:])) for block in blocks]
    assert events[0] == ("status", {"stage": "analyzing", "label": "分析需求"})
    stages = [data['stage'] for name, data in events if name == 'status']
    assert [stage for stage in stages if stage not in ('filtering', 'catalog_search', 'verifying', 'web_search')] == [
        "analyzing", "preferences", "tool", "tool", "tool", "composing", "complete"]
    assert 'filtering' in stages and 'catalog_search' in stages and 'verifying' in stages
    assert [name for name, data in events].count("done") == 1
    assert events[-1][1]["recommended_tracks"]
    assert "reasoning" not in response.text
    logs = [json.loads(record.message) for record in caplog.records if record.name.startswith("music_api")]
    assert {log["event"] for log in logs} >= {"http_request", "agent_tool", "llm_call", "recommendation"}
    assert all(log["request_id"] == response.headers["x-request-id"] for log in logs)
    assert all(log["trace_id"] == response.headers["x-trace-id"] for log in logs)
    assert all(log["route"] == "/v1/agent/chat/stream" for log in logs)
    assert BODY["message"] not in caplog.text and "account_test" not in caplog.text


@pytest.mark.parametrize("changes", [
    {"message": " "}, {"message": "x" * 2001}, {"device_id": "bad"},
    {"conversation_id": "bad"}, {"extra": "no"},
])
def test_chat_validation(client, changes):
    response = client.post("/v1/agent/chat", json={**BODY, **changes})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("suffix", ["", "/stream"])
def test_deep_thinking_request_is_accepted_with_honest_local_mode(client, suffix):
    response = client.post(f"/v1/agent/chat{suffix}", json={**BODY, "deep_thinking": True})
    assert response.status_code == 200
    result = (json.loads(response.text.split("event: done\ndata: ")[1].split("\n\n")[0])
              if suffix else response.json())
    assert result["thinking_mode"] == "basic"
    assert result["thinking_unavailable_reason"] == "unsupported"


def test_thinking_flag_is_strict_boolean(client):
    assert client.post("/v1/agent/chat", json={**BODY, "deep_thinking": "true"}).status_code == 422


def test_capabilities_and_chat_do_not_claim_native_search(client):
    capability = client.get("/v1/agent/capabilities")
    assert capability.status_code == 200
    assert capability.json() == {"provider": "local", "supports_deep_thinking": False,
                                  "native_search": {"status": "unavailable", "reason": "local_mode"},
                                  "music_catalog_search": "unavailable", "web_search": "not_configured"}
    response = client.post("/v1/agent/chat", json={"message": "请联网查询最新音乐动态"})
    assert response.status_code == 200
    assert response.json()["native_search"]["status"] == "unavailable"
    assert "暂不支持联网检索" in response.json()["answer"]
    assert response.json()["citations"] == []


def test_invalid_llm_output_is_safe_in_json_and_sse(client):
    class Bad(LocalLLMProvider):
        async def plan(self, context, tools):
            return {"calls": [{"name": "run_shell", "arguments": {}}]}

    app.dependency_overrides[get_llm_provider] = Bad
    response = client.post("/v1/agent/chat", json=BODY)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_model_output"
    streamed = client.post("/v1/agent/chat/stream", json=BODY)
    assert "event: error" in streamed.text
    assert "invalid_model_output" in streamed.text
    assert "event: done" not in streamed.text


def test_unexpected_provider_failure_does_not_log_private_content(client, caplog):
    class Failed(LocalLLMProvider):
        async def plan(self, context, tools):
            raise RuntimeError("private-chat-marker mock-secret-marker")

    app.dependency_overrides[get_llm_provider] = Failed
    result = client.post("/v1/agent/chat", json={**BODY, "message": "private-chat-marker"})
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "agent_unavailable"
    assert "private-chat-marker" not in result.text + caplog.text
    assert "mock-secret-marker" not in result.text + caplog.text


def test_tool_latency_measures_each_call_independently(client, caplog, monkeypatch):
    from app.agent import core

    clock = [0.0]
    original = core.invoke_tool

    def measured(call, context):
        output = original(call, context)
        clock[0] += 1.0  # controlled duration for each business call, without wall-clock flakiness
        return output

    monkeypatch.setattr(core, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(core, "invoke_tool", measured)
    caplog.set_level(logging.INFO, logger="music_api")
    assert client.post("/v1/agent/chat", json=BODY).status_code == 200
    logs = [json.loads(record.message) for record in caplog.records if record.name.startswith("music_api")]
    assert [log["latency_ms"] for log in logs if log["event"] == "agent_tool"] == [1000.0] * 4


@pytest.mark.parametrize("suffix", ["", "/stream"])
def test_http_failure_returns_basic_mode_in_json_and_sse(client, caplog, suffix):
    class Offline(LocalLLMProvider):
        name = "openai_compatible"

        async def plan(self, context, tools):
            raise httpx.ReadTimeout("private-upstream-marker")

    caplog.set_level(logging.INFO, logger="music_api")
    app.dependency_overrides[get_llm_provider] = Offline
    response = client.post(f"/v1/agent/chat{suffix}", json={**BODY, "message": "缓慢的歌"})
    assert response.status_code == 200
    if suffix:
        assert response.text.count("event: done") == 1
        assert "event: error" not in response.text
        frame = response.text.split("event: done\ndata: ")[1].split("\n\n")[0]
        result = json.loads(frame)
    else:
        result = response.json()
    assert result["provider"] == "local" and result["fallback_reason"] == "llm_unavailable"
    assert result["recommended_tracks"]
    assert "private-upstream-marker" not in response.text + caplog.text
