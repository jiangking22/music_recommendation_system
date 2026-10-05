import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.providers import (
    LocalLLMProvider,
    OpenAICompatibleProvider,
    get_llm_provider,
)
from app.domain.music import (
    Artist,
    ProviderResult,
    ProviderSource,
    SearchResult,
    Track,
    canonical_key,
)
from app.infrastructure.database import get_session
from app.main import app
from app.providers.registry import get_provider_registry
from app.repository.models import Base


def song(title, artist, identifier):
    return Track(title=title, artist=Artist(name=artist),
                 source=ProviderSource(provider="itunes", provider_track_id=identifier),
                 canonical_key=canonical_key(title, artist), genres=["Mandopop"])


class DiscoveryRegistry:
    def search_tracks(self, query, limit):
        tracks = [song("我好想你 (Cover)", "Cover Singer", "cover"),
                  song("我好想你", "蘇打綠", "original"),
                  song("小情歌", "蘇打綠", "related")]
        return SearchResult(tracks=tracks[:limit], sources={
            "itunes": ProviderResult(provider="itunes", tracks=tracks[:limit])})

    def search_artist_tracks(self, artist, limit):
        return self.search_tracks(artist, limit)


@pytest.fixture
def discovery_client(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'discovery.db'}")
    Base.metadata.create_all(engine)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_provider_registry] = DiscoveryRegistry
    app.dependency_overrides[get_llm_provider] = LocalLLMProvider
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_discovery_resolves_original_and_returns_related_songs_in_chinese(discovery_client):
    response = discovery_client.post("/v1/recommendations/discover", json={
        "seed": "我好想你", "limit": 3, "language": "zh"},
        headers={"X-Device-Id": "device_1234567890"})
    assert response.status_code == 200
    body = response.json()
    assert body["seed_status"] == "matched"
    assert body["seed_track"]["artist"]["name"] == "蘇打綠"
    assert [item["title"] for item in body["items"]] == ["小情歌"]
    assert body["guidance_provider"] == "local"
    assert body["guidance_status"] == "ready"
    assert "小情歌" not in body["guidance"]  # Guidance does not add a separate playlist.
    assert "推荐" in body["guidance"]
    assert body["request_id"] == response.headers["X-Request-Id"]


def test_discovery_reuses_assistant_model_without_changing_rank(discovery_client):
    sent = []

    def respond(request):
        payload = json.loads(request.content)
        context = json.loads(payload["messages"][1]["content"])
        sent.append(context)
        assert payload["model"] == "fixture-model"
        assert context["context"]["language"] == "en"
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "answer": "These tracks share the seed artist or musical attributes."})}}]})

    app.dependency_overrides[get_llm_provider] = lambda: OpenAICompatibleProvider(
        "https://model.example/v1", "mock-key", "fixture-model", httpx.MockTransport(respond))
    response = discovery_client.post("/v1/recommendations/discover", json={"seed": "我好想你", "limit": 3})
    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body["items"]] == ["小情歌"]
    assert body["guidance_provider"] == "openai_compatible"
    assert body["guidance"].startswith("These tracks")
    assert len(sent) == 1
    assert "authorization" not in json.dumps(sent).lower()


@pytest.mark.parametrize("failure", ["http", "invalid", "timeout"])
def test_model_failure_preserves_recommendations_with_local_guidance(discovery_client, failure):
    class BrokenProvider:
        name = "openai_compatible"

        async def answer(self, context, results):
            if failure == "http":
                raise httpx.ConnectError("private endpoint details")
            if failure == "timeout":
                raise TimeoutError("private timeout details")
            return {"answer": "", "items": [{"title": "invented"}]}

    app.dependency_overrides[get_llm_provider] = BrokenProvider
    response = discovery_client.post("/v1/recommendations/discover", json={"seed": "我好想你"})
    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body["items"]] == ["小情歌"]
    assert body["guidance_provider"] == "local"
    assert body["guidance_status"] == "unavailable"
    assert "private" not in json.dumps(body)


@pytest.mark.parametrize("extra", [{"language": "fr"}, {"seed_artist": " "},
                                   {"seed_artist": "x" * 201}, {"limit": 11}])
def test_discovery_validates_external_input(discovery_client, extra):
    response = discovery_client.post("/v1/recommendations/discover", json={"seed": "我好想你", **extra})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_discovery_rejects_fifth_active_request_and_recovers(discovery_client):
    async def exercise():
        entered = asyncio.Event()
        release = asyncio.Event()

        class WaitingProvider:
            name = "openai_compatible"
            active = 0

            async def answer(self, context, results):
                self.active += 1
                if self.active == 4:
                    entered.set()
                await release.wait()
                return {"answer": "Related tracks from the measured factors."}

        provider = WaitingProvider()
        app.dependency_overrides[get_llm_provider] = lambda: provider
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            requests = [asyncio.create_task(client.post("/v1/recommendations/discover",
                        json={"seed": "我好想你"})) for _ in range(4)]
            try:
                await asyncio.wait_for(entered.wait(), timeout=3)
                busy = await client.post("/v1/recommendations/discover", json={"seed": "我好想你"})
                assert busy.status_code == 503
                assert busy.json()["error"]["code"] == "discovery_busy"
            finally:
                release.set()
                results = await asyncio.gather(*requests)
            assert all(result.status_code == 200 for result in results)
            after = await client.post("/v1/recommendations/discover", json={"seed": "我好想你"})
            assert after.status_code == 200

    asyncio.run(exercise())
