from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.infrastructure.config import Settings
from app.infrastructure.database import get_session
from app.main import app
from app.repository.models import Base


def test_configuration_rejects_missing_connection_urls() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="", redis_url="")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql+psycopg://", redis_url="redis://localhost:6379/0")


def test_device_endpoint_is_retired_without_writing_archives(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'devices.db'}")
    Base.metadata.create_all(engine)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client:
            headers = {"X-Device-Id": "device_1234567890"}
            first = client.get("/v1/device", headers=headers)
            second = client.get("/v1/device", headers=headers)
        assert first.status_code == second.status_code == 410
        assert first.json()["error"]["code"] == "device_identity_retired"
        with Session(engine) as session:
            assert session.query(Base.metadata.tables["device_users"]).count() == 0
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_validation_uses_consistent_error_envelope() -> None:
    with TestClient(app) as client:
        response = client.post("/v1/recommendations", json={"seed": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_readiness_checks_database_and_redis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import routes

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'ready.db'}")

    class FakeRedis:
        def ping(self) -> bool:
            return True

    class FailedRedis:
        def ping(self) -> bool:
            raise ConnectionError("private connection detail")

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    monkeypatch.setattr(routes, "get_redis", lambda: FakeRedis())
    try:
        with TestClient(app) as client:
            response = client.get("/health/ready")
            monkeypatch.setattr(routes, "get_redis", lambda: FailedRedis())
            failed = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert failed.status_code == 503
        assert failed.json()["error"] == {"code": "http_error", "message": "Dependencies unavailable."}
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
