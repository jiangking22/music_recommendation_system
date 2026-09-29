from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_reports_service_readiness() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "music-recommendation-api"}


def test_recommendations_require_a_valid_anonymous_device_id() -> None:
    response = client.post("/v1/recommendations", json={"seed": "晴天"})

    assert response.status_code == 422


def test_recommendations_return_explainable_seed_catalog_results() -> None:
    response = client.post(
        "/v1/recommendations",
        headers={"X-Device-Id": "device_01HZX7N2Q8J3K4M5N6P7Q8R9"},
        json={"seed": "晴天", "limit": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requestId"]
    assert len(payload["items"]) == 2
    assert payload["items"][0]["explanation"]
    assert payload["items"][0]["source"] == "CATALOG"
