from fastapi.testclient import TestClient

from app.main import app


def test_fixture_recommendations_cross_api_and_domain() -> None:
    with TestClient(app) as client:
        response = client.post("/v1/recommendations", json={"seed": "jazz", "limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["request_id"], str)
    assert len(payload["items"]) == 2
    assert payload["items"][0] == {
        "id": "fixture-blue-window",
        "title": "Blue Window",
        "artist": "Demo Quartet",
        "explanation": "Bundled fixture example; no live catalog or full ranking is used.",
    }


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
