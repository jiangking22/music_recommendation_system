from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_stable_service_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "music-recommendation-api"}


def test_retired_device_endpoint_has_a_structured_error() -> None:
    response = client.get("/v1/device", headers={"X-Device-Id": "short"})

    assert response.status_code == 410
