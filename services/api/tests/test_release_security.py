import asyncio

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.providers.base import safe_https_url
from app.providers.registry import get_provider_registry


def test_body_limit_counts_streamed_bytes_even_without_content_length():
    async def run():
        async def chunks():
            yield b'{"seed":"'
            yield b"x" * 65536
            yield b'"}'

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.post("/v1/recommendations", content=chunks(),
                                     headers={"Origin": "http://localhost:3000"})

    result = asyncio.run(run())
    assert result.status_code == 413
    assert result.json()["error"]["code"] == "request_too_large"
    assert result.headers["x-request-id"]
    assert result.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unexpected_failure_is_safe_json_and_logs_no_exception_content(caplog):
    def failed():
        raise RuntimeError("private-secret-marker")

    app.dependency_overrides[get_provider_registry] = failed
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            result = client.get("/v1/providers", headers={"Origin": "http://localhost:3000"})
        assert result.status_code == 500
        assert result.json()["error"]["code"] == "internal_error"
        assert result.headers["x-request-id"]
        assert result.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert "private-secret-marker" not in result.text + caplog.text
    finally:
        app.dependency_overrides.clear()


def test_provider_urls_reject_embedded_credentials_and_local_addresses():
    for url in ("https://user:secret@example.com/path", "https://127.0.0.1/x", "https://[::1]/x",
                "https://169.254.169.254/x", "https://localhost/x", "javascript:alert(1)"):
        assert safe_https_url(url) is None
    assert safe_https_url("https://music.apple.com/track/1") == "https://music.apple.com/track/1"
