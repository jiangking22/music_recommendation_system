import os

import httpx
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture(autouse=True)
def prohibit_external_http(monkeypatch):
    """Tests must use ASGI/MockTransport; real provider/model HTTP is a failure."""
    def forbidden(*_args, **_kwargs):
        raise AssertionError("External HTTP is disabled in tests.")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
