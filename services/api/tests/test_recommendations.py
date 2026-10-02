from fastapi.testclient import TestClient

from app.domain.music import (
    Artist,
    ProviderError,
    ProviderResult,
    ProviderSource,
    SearchResult,
    Track,
)
from app.main import app
from app.providers.registry import get_provider_registry


class PartialRegistry:
    def search_tracks(self, query: str, limit: int) -> SearchResult:
        track = Track(title="Blue Window", artist=Artist(name="Demo Quartet"),
                      source=ProviderSource(provider="itunes", provider_track_id="123"),
                      canonical_key="blue window::demo quartet", genres=["jazz"], tags=["calm"])
        return SearchResult(tracks=[track], sources={
            "itunes": ProviderResult(provider="itunes", tracks=[track]),
            "netease": ProviderResult(provider="netease", error=ProviderError(code="timeout", message="Unavailable")),
        })


def test_recommendations_use_pipeline_and_survive_partial_provider_failure() -> None:
    app.dependency_overrides[get_provider_registry] = lambda: PartialRegistry()
    try:
        with TestClient(app) as client:
            response = client.post("/v1/recommendations", json={"seed": "jazz", "limit": 2})
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload["request_id"], str)
        assert len(payload["items"]) == 2
        assert payload["items"][0]["track"]["title"] == "Blue Window"
        assert payload["items"][0]["score"] == sum(payload["items"][0]["score_breakdown"].values())
        assert payload["items"][0]["provenance"][0]["provider"] == "itunes"
        assert payload["sources"]["netease"]["error"]["code"] == "timeout"
    finally:
        app.dependency_overrides.clear()


def test_recommendation_input_is_bounded_and_errors_are_structured() -> None:
    with TestClient(app) as client:
        response = client.post("/v1/recommendations", json={"seed": "", "limit": 999})
        blank_response = client.post("/v1/recommendations", json={"seed": "   ", "limit": 2})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert blank_response.status_code == 422


def test_unknown_api_route_uses_error_envelope() -> None:
    with TestClient(app) as client:
        response = client.get("/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"
