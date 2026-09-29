from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_stable_service_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "music-recommendation-api"}


def test_device_endpoint_rejects_an_invalid_identifier() -> None:
    response = client.get("/v1/device", headers={"X-Device-Id": "short"})

    assert response.status_code == 422
