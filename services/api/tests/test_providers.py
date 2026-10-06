import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.infrastructure.config import Settings
from app.main import app
from app.providers.itunes import ITunesProvider
from app.providers.netease import NetEaseProvider
from app.providers.qq import QQProvider
from app.providers.registry import ProviderRegistry, get_provider_registry

FIXTURES = Path(__file__).parent / "fixtures" / "providers"


def test_default_catalog_includes_qq_and_respects_opt_out_and_offline_mode(monkeypatch):
    from app.providers import registry as module

    monkeypatch.delenv("ENABLE_QQ_PROVIDER", raising=False)
    settings = Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:",
                        redis_url="redis://localhost:6379/0")
    assert settings.enable_qq_provider is True
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    module.get_provider_registry.cache_clear()
    try:
        registry = module.get_provider_registry()
        assert [source.provider for source in registry.capabilities()] == ["itunes", "netease", "qq"]
        settings.enable_qq_provider = False
        module.get_provider_registry.cache_clear()
        assert [s.provider for s in module.get_provider_registry().capabilities()] == ["itunes", "netease"]
        settings.enable_music_providers = False
        settings.enable_qq_provider = True
        module.get_provider_registry.cache_clear()
        assert module.get_provider_registry().capabilities() == []
    finally:
        module.get_provider_registry.cache_clear()


def fixture_client(name: str, expected_host: str) -> httpx.Client:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.host == expected_host
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(respond))


def test_itunes_maps_canonical_track_and_artist_search() -> None:
    provider = ITunesProvider(client=fixture_client("itunes.json", "itunes.apple.com"))
    result = provider.search_tracks("Blue Window", 5)
    assert result.error is None
    assert len(result.tracks) == 1
    track = result.tracks[0]
    assert track.title == "Blue Window"
    assert track.artist.name == "Demo Quartet"
    assert track.album.name == "Night Sessions"
    assert track.duration_ms == 210000
    assert track.source.provider == "itunes"
    assert track.source.provider_track_id == "123"
    assert track.canonical_key == "blue window::demo quartet"
    assert provider.search_artist_tracks("Demo Quartet", 5).tracks[0] == track


def test_regional_registry_uses_fixed_official_storefront_without_changing_default():
    countries = []
    payload = json.loads((FIXTURES / "itunes.json").read_text(encoding="utf-8"))

    def respond(request):
        assert request.url.host == "itunes.apple.com"
        countries.append(request.url.params["country"])
        return httpx.Response(200, json=payload)

    registry = ProviderRegistry([ITunesProvider(client=httpx.Client(transport=httpx.MockTransport(respond)))])
    regional = registry.for_storefront("TW")
    result = regional.search_tracks("Blue Window", 5)
    assert result.tracks[0].source.provider == "itunes"
    assert result.tracks[0].source.provider_track_id == "123"
    registry.search_tracks("Blue Window", 5)
    assert countries == ["TW", "US"]
    assert ProviderRegistry([]).for_storefront("TW").search_tracks("Blue Window", 5).tracks == []


def test_netease_maps_canonical_track() -> None:
    provider = NetEaseProvider(client=fixture_client("netease.json", "music.163.com"))
    result = provider.search_tracks("Blue Window", 5)
    assert result.error is None
    track = result.tracks[0]
    assert track.title == "Blue Window"
    assert track.artist.name == "Demo Quartet"
    assert track.album.name == "Night Sessions"
    assert track.canonical_key == "blue window::demo quartet"
    assert track.source.provider_track_id == "456"


def test_qq_optional_adapter_maps_canonical_track() -> None:
    provider = QQProvider(client=fixture_client("qq.json", "c.y.qq.com"))
    result = provider.search_tracks("Blue Window", 5)
    assert result.tracks[0].canonical_key == "blue window::demo quartet"
    assert result.tracks[0].source.provider_track_id == "789"
    assert provider.capabilities().stability == "unverified"


def test_qq_accepts_legacy_jsonp_response() -> None:
    payload = (FIXTURES / "qq.json").read_text(encoding="utf-8")
    provider = QQProvider(client=httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, text=f"callback({payload});")
    )))
    assert provider.search_tracks("Blue Window", 5).tracks[0].source.provider_track_id == "789"


def test_provider_timeout_and_bad_payload_are_structured() -> None:
    def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private transport detail")

    timed = ITunesProvider(client=httpx.Client(transport=httpx.MockTransport(timeout)))
    assert timed.search_tracks("blue", 3).error.code == "timeout"
    assert "private transport detail" not in timed.search_tracks("blue", 3).error.message

    malformed = NetEaseProvider(client=httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"result": {"songs": "bad"}})
    )))
    assert malformed.search_tracks("blue", 3).error.code == "invalid_payload"


def test_adapter_rejects_unbounded_query_before_http() -> None:
    provider = ITunesProvider(client=httpx.Client(transport=httpx.MockTransport(
        lambda _request: (_ for _ in ()).throw(AssertionError("HTTP must not run"))
    )))
    assert provider.search_tracks("x" * 121, 1).error.code == "invalid_payload"


def test_registry_isolates_provider_failure_and_reports_health() -> None:
    good = ITunesProvider(client=fixture_client("itunes.json", "itunes.apple.com"))
    bad = NetEaseProvider(client=httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(503)
    )))
    registry = ProviderRegistry([good, bad])
    result = registry.search_tracks("Blue Window", 5)
    assert len(result.tracks) == 1
    assert result.sources["itunes"].error is None
    assert result.sources["netease"].error.code == "upstream_error"
    assert registry.health()["netease"].status == "degraded"
    assert registry.health()["itunes"].status == "available"


def test_registry_rejects_duplicate_providers() -> None:
    first = ITunesProvider(client=fixture_client("itunes.json", "itunes.apple.com"))
    second = ITunesProvider(client=fixture_client("itunes.json", "itunes.apple.com"))
    try:
        ProviderRegistry([first, second])
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate provider was accepted")


def test_registry_isolates_unexpected_adapter_exception() -> None:
    class BrokenNetEase(NetEaseProvider):
        def search_tracks(self, query: str, limit: int):
            raise RuntimeError("secret upstream detail")

    registry = ProviderRegistry([
        ITunesProvider(client=fixture_client("itunes.json", "itunes.apple.com")),
        BrokenNetEase(client=fixture_client("netease.json", "music.163.com")),
    ])
    result = registry.search_tracks("Blue Window", 2)
    assert len(result.tracks) == 1
    assert result.sources["netease"].error.code == "unavailable"
    assert "secret upstream detail" not in result.model_dump_json()


def test_provider_api_returns_canonical_schema_and_validation_error() -> None:
    registry = ProviderRegistry([ITunesProvider(client=fixture_client("itunes.json", "itunes.apple.com"))])
    app.dependency_overrides[get_provider_registry] = lambda: registry
    try:
        with TestClient(app) as client:
            providers = client.get("/v1/providers")
            found = client.get("/v1/tracks/search", params={"q": "Blue Window", "limit": 5})
            health = client.get("/v1/providers/health")
            invalid = client.get("/v1/tracks/search", params={"q": "  ", "limit": 100})
        assert providers.status_code == 200
        assert providers.json()["providers"][0]["provider"] == "itunes"
        assert found.status_code == 200
        assert found.json()["tracks"][0]["source"]["provider_track_id"] == "123"
        assert "trackId" not in found.text
        assert health.json()["providers"]["itunes"]["status"] == "available"
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "validation_error"
    finally:
        app.dependency_overrides.clear()


def test_search_api_returns_partial_results_when_provider_fails() -> None:
    registry = ProviderRegistry([
        ITunesProvider(client=fixture_client("itunes.json", "itunes.apple.com")),
        NetEaseProvider(client=httpx.Client(transport=httpx.MockTransport(
            lambda _request: httpx.Response(503)
        ))),
    ])
    app.dependency_overrides[get_provider_registry] = lambda: registry
    try:
        with TestClient(app) as client:
            response = client.get("/v1/tracks/search", params={"q": "Blue Window"})
        assert response.status_code == 200
        assert len(response.json()["tracks"]) == 1
        assert response.json()["sources"]["netease"]["error"]["code"] == "upstream_error"
    finally:
        app.dependency_overrides.clear()
