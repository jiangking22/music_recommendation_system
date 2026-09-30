import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.providers import LocalLLMProvider, get_llm_provider
from app.infrastructure.database import get_session
from app.main import app
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.rag.repository import ingest_fixture
from app.repository.models import Base


@pytest.fixture
def client(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'agent_api.db'}")
    Base.metadata.create_all(engine)
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


BODY = {"message": "推荐适合学习的歌", "device_id": "device_1234567890"}


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
                         headers={"X-Device-Id": BODY["device_id"]})
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
    assert [data["stage"] for name, data in events if name == "status"] == [
        "analyzing", "preferences", "tool", "tool", "tool", "complete"]
    assert [name for name, data in events].count("done") == 1
    assert events[-1][1]["recommended_tracks"]
    assert "reasoning" not in response.text
    logs = [json.loads(record.message) for record in caplog.records if record.name.startswith("music_api")]
    assert {log["event"] for log in logs} >= {"http_request", "agent_tool", "llm_call", "recommendation"}
    assert all(log["request_id"] == response.headers["x-request-id"] for log in logs)
    assert all(log["trace_id"] == response.headers["x-trace-id"] for log in logs)
    assert all(log["route"] == "/v1/agent/chat/stream" for log in logs)
    assert BODY["message"] not in caplog.text and BODY["device_id"] not in caplog.text


@pytest.mark.parametrize("changes", [
    {"message": " "}, {"message": "x" * 2001}, {"device_id": "bad"},
    {"conversation_id": "bad"}, {"extra": "no"},
])
def test_chat_validation(client, changes):
    response = client.post("/v1/agent/chat", json={**BODY, **changes})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


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
