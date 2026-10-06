import json
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep

import httpx
import pytest

from app.providers.itunes import ITunesProvider
from app.providers.musicbrainz import MusicBrainzProvider
from app.providers.netease import NetEaseProvider
from app.providers.qq import QQProvider


@pytest.mark.parametrize("provider,identifier,payload,host", [
    (ITunesProvider, "123", {"results": [{"wrapperType": "track", "kind": "song", "trackId": 123,
        "trackName": "Song", "artistName": "Artist"}]}, "itunes.apple.com"),
    (NetEaseProvider, "123", {"songs": [{"id": 123, "name": "Song", "artists": [{"name": "Artist"}]}]}, "music.163.com"),
    (QQProvider, "MID123", {"code": 0, "req": {"code": 0, "data": {"track_info": {
        "id": 123, "mid": "MID123", "title": "Song", "singer": [{"name": "Artist"}]}}}}, "u.y.qq.com"),
])
def test_fixed_detail_endpoint_maps_real_ids(provider, identifier, payload, host):
    def reply(request):
        assert request.url.host == host
        return httpx.Response(200, json=payload)
    catalog = provider(client=httpx.Client(transport=httpx.MockTransport(reply)))
    result = catalog.lookup_track(identifier)
    assert result.error is None
    assert result.tracks[0].source.provider_track_id == "123"
    assert result.tracks[0].title == "Song"


def test_detail_rejects_wrong_recording_id_and_external_input():
    payload = {"code": 0, "req": {"code": 0, "data": {"track_info": {
        "id": 999, "mid": "WRONG", "title": "Song", "singer": [{"name": "Artist"}]}}}}
    calls = []
    def reply(request):
        calls.append(json.loads(request.url.params["data"]))
        return httpx.Response(200, json=payload)
    catalog = QQProvider(client=httpx.Client(transport=httpx.MockTransport(reply)))
    assert catalog.lookup_track("MID123").error.code == "invalid_payload"
    assert catalog.lookup_track("https://127.0.0.1/").error.code == "invalid_payload"
    assert len(calls) == 1


def test_catalog_authorization_is_distinct_from_network_failure():
    catalog = QQProvider(client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(403))))
    assert catalog.search_tracks("Song", 5).error.code == "auth_required"


def test_global_outbound_slots_bound_concurrent_catalogs():
    lock = Lock()
    active = peak = 0
    def reply(_request):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        sleep(.03)
        with lock:
            active -= 1
        return httpx.Response(200, json={"results": []})
    catalog = ITunesProvider(client=httpx.Client(transport=httpx.MockTransport(reply)))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: catalog.search_tracks("Song", 5), range(8)))
    assert all(not result.error for result in results)
    assert peak <= 4


def test_musicbrainz_metadata_has_rate_limit_user_agent_and_no_playback(monkeypatch):
    import app.providers.musicbrainz as module
    waits, requests = [], []
    monkeypatch.setattr(module, "_last_request", 0)
    monkeypatch.setattr(module, "monotonic", lambda: 10)
    monkeypatch.setattr(module, "sleep", waits.append)
    identifier = "11111111-1111-4111-8111-111111111111"
    item = {"id": identifier, "title": "Song", "artist-credit": [{"artist": {"name": "Artist"}}],
            "disambiguation": "live recording"}
    def reply(request):
        requests.append(request)
        assert request.url.host == "musicbrainz.org"
        assert "Sonora" in request.headers["User-Agent"]
        return httpx.Response(200, json=item if request.url.path.endswith(identifier) else {"recordings": [item]})
    catalog = MusicBrainzProvider(client=httpx.Client(transport=httpx.MockTransport(reply)))
    result = catalog.search_recording('Song" OR *', "Artist", 5)
    assert result.tracks[0].tags == ["live"]
    assert result.tracks[0].source.external_url == f"https://musicbrainz.org/recording/{identifier}"
    assert catalog.lookup_track(identifier).error is None
    assert waits == [0, 1]
    assert 'recording:"Song\\" OR *"' in requests[0].url.params["query"]
