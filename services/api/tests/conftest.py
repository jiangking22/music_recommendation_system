import logging
import os

import httpx
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture(autouse=True)
def capture_application_events(caplog):
    logger = logging.getLogger("music_api")
    logger.addHandler(caplog.handler)
    try:
        yield
    finally:
        logger.removeHandler(caplog.handler)


@pytest.fixture(autouse=True)
def prohibit_external_http(monkeypatch):
    """Tests must use ASGI/MockTransport; real provider/model HTTP is a failure."""
    def forbidden(*_args, **_kwargs):
        raise AssertionError("External HTTP is disabled in tests.")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)


@pytest.fixture(autouse=True)
def subsystem_auth_context(request, tmp_path):
    """Existing provider/domain tests isolate their subject from authentication.

    Dedicated auth/access suites use real cookies, CSRF, database accounts and limits.
    No production bypass exists; these are ordinary FastAPI test dependency overrides.
    """
    if request.path.name in {"test_auth.py", "test_account_access.py"} or "TestClient" not in request.path.read_text(encoding="utf-8"):
        yield
        return
    from account_helpers import TEST_SESSION, TEST_USER, seed_account
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.auth.dependencies import business_csrf, current_identity
    from app.auth.service import Identity
    from app.infrastructure.database import get_session
    from app.main import app
    from app.repository.models import Base

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'subsystem.db'}")
    Base.metadata.create_all(engine)
    seed_account(engine)

    def sessions():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = sessions
    app.dependency_overrides[current_identity] = lambda: Identity(TEST_USER, TEST_USER, TEST_SESSION)
    app.dependency_overrides[business_csrf] = lambda: None
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
