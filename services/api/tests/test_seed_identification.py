"""Model-assisted seed identification must remain grounded in canonical catalog data."""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.providers import get_llm_provider
from app.domain.music import (
    Artist,
    ProviderResult,
    ProviderSource,
    SearchResult,
    Track,
    canonical_key,
)
from app.infrastructure.database import get_session
from app.main import app
from app.providers.registry import get_provider_registry
from app.repository.models import Base


def track(title, artist, *, genres=("folk",), tags=(), popularity=50):
    return Track(title=title, artist=Artist(name=artist), genres=list(genres), tags=list(tags),
                 popularity=popularity,
                 source=ProviderSource(provider="itunes", provider_track_id=f"{title}-{artist}"),
                 canonical_key=canonical_key(title, artist))


class IdentificationRegistry:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def search_tracks(self, query, limit):
        self.calls.append((query, limit))
        tracks = self.responses.get(query, [])
        return SearchResult(tracks=tracks, sources={
            "itunes": ProviderResult(provider="itunes", tracks=tracks)})


class IdentificationModel:
    name = "openai_compatible"

    def __init__(self, output, error=None):
        self.output = output
        self.error = error
        self.identify_calls = []
        self.answer_calls = []

    async def identify_seed(self, context):
        self.identify_calls.append(context)
        if self.error is not None:
            raise self.error
        return self.output

    async def answer(self, context, results):
        self.answer_calls.append((context, results))
        return {"answer": "Related tracks follow the measured recommendation factors."}


@pytest.fixture
def identification_case(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'identification.db'}")
    Base.metadata.create_all(engine)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client:
            def configure(responses, output=None, error=None):
                registry = IdentificationRegistry(responses)
                model = IdentificationModel(output if output is not None else {
                    "kind": "song", "title": "Shared Title", "artist": "Second"}, error)
                app.dependency_overrides[get_provider_registry] = lambda: registry
                app.dependency_overrides[get_llm_provider] = lambda: model
                return client, registry, model

            yield configure
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def discover(client, seed="Shared Title", **extra):
    response = client.post("/v1/recommendations/discover", json={
        "seed": seed, "limit": 3, "language": "zh", **extra})
    assert response.status_code == 200
    return response.json()


def assert_identification_budget(registry, model):
    assert len(model.identify_calls) == 1
    assert model.answer_calls == []
    assert len(registry.calls) <= 3
    assert all(1 <= limit <= 25 and 1 <= len(query) <= 120 for query, limit in registry.calls)


def test_model_identifies_an_original_artist_already_in_the_first_catalog_page(identification_case):
    second = track("Shared Title", "Second", popularity=1)
    client, registry, model = identification_case({
        "Shared Title": [track("Shared Title", "First", popularity=100), second],
        "Second": [second, track("Neighbour", "Second")],
    })
    body = discover(client)
    assert body["seed_status"] == "matched"
    assert body["seed_resolution_source"] == "model"
    assert body["seed_track"] == second.model_dump(mode="json")
    assert [item["title"] for item in body["items"]] == ["Neighbour"]
    assert_identification_budget(registry, model)


def test_model_artist_proposal_can_trigger_one_qualified_catalog_search(identification_case):
    second = track("Shared Title", "Second", tags=("acoustic",))
    client, registry, model = identification_case({
        "Shared Title": [track("Shared Title", "First")],
        "Shared Title Second": [second],
        "Second": [track("Neighbour", "Second")],
        "folk acoustic": [track("Extra", "Third")],
    })
    body = discover(client)
    assert body["seed_track"] == second.model_dump(mode="json")
    assert body["seed_resolution_source"] == "model"
    assert [item["title"] for item in body["items"]] == ["Neighbour"]
    assert [query for query, _ in registry.calls] == [
        "Shared Title", "Shared Title Second", "Second"]
    assert_identification_budget(registry, model)


def test_one_unverified_catalog_artist_still_needs_model_identification(identification_case):
    second = track("Shared Title", "Second")
    client, registry, model = identification_case({
        "Shared Title": [second], "Second": [track("Neighbour", "Second")],
    })
    body = discover(client)
    assert body["seed_resolution_source"] == "model"
    assert body["seed_track"] == second.model_dump(mode="json")
    assert_identification_budget(registry, model)


@pytest.mark.parametrize("artists", [[], ["First"], ["First", "Second"]])
def test_unknown_model_response_preserves_choices_without_recommending_a_cover(
        identification_case, artists):
    client, registry, model = identification_case({
        "Shared Title": [track("Shared Title", artist) for artist in artists],
    }, {"kind": "unknown", "title": None, "artist": None})
    body = discover(client)
    assert body["seed_status"] == ("ambiguous" if artists else "unresolved")
    assert body["seed_track"] is None
    assert body["items"] == []
    assert {candidate["artist"]["name"] for candidate in body["seed_candidates"]} == set(artists)
    assert body["seed_resolution_source"] == "none"
    assert_identification_budget(registry, model)


@pytest.mark.parametrize("output,error", [
    ({"kind": "song", "title": "Shared Title", "artist": "Second", "items": []}, None),
    ({"kind": "song", "title": 7, "artist": "Second"}, None),
    ({"kind": "song", "title": "Shared Title"}, None),
    ({"kind": "unexpected", "title": "Shared Title", "artist": "Second"}, None),
    (None, TimeoutError("private timeout details")),
    (None, httpx.ConnectError("private endpoint details")),
])
def test_invalid_or_failed_identification_retains_ambiguity_and_safe_local_guidance(
        identification_case, output, error):
    client, registry, model = identification_case({
        "Shared Title": [track("Shared Title", "First"), track("Shared Title", "Second")],
        "Second": [track("Neighbour", "Second")],
    }, output, error)
    body = discover(client)
    assert body["seed_status"] == "ambiguous"
    assert body["seed_track"] is None
    assert body["items"] == []
    assert body["seed_resolution_source"] == "none"
    assert body["guidance_provider"] == "local"
    assert "private" not in json.dumps(body)
    assert_identification_budget(registry, model)


def test_invented_model_artist_never_becomes_a_synthetic_seed_or_playlist(identification_case):
    client, registry, model = identification_case({
        "Shared Title": [track("Shared Title", "First"), track("Shared Title", "Second")],
        "Imaginary": [track("Unrelated", "Imaginary")],
    }, {"kind": "song", "title": "Shared Title", "artist": "Imaginary"})
    body = discover(client)
    assert body["seed_track"] is None
    assert body["items"] == []
    assert body["seed_status"] == "ambiguous"
    assert {candidate["artist"]["name"] for candidate in body["seed_candidates"]} == {"First", "Second"}
    assert body["seed_resolution_source"] == "none"
    assert not any(query == "Imaginary" for query, _ in registry.calls)
    assert_identification_budget(registry, model)


def test_model_must_match_title_as_well_as_artist_in_qualified_search(identification_case):
    client, registry, model = identification_case({
        "Shared Title": [], "Shared Title Second": [track("Different Title", "Second")],
    })
    body = discover(client)
    assert body["seed_status"] == "unresolved"
    assert body["seed_track"] is None
    assert body["items"] == []
    assert_identification_budget(registry, model)


@pytest.mark.parametrize("seed,artist", [("我好想你", "蘇打綠"), ("匆匆那年", "Faye Wong")])
def test_verified_hints_skip_model_identification(identification_case, seed, artist):
    client, registry, model = identification_case({
        seed: [track(seed, "Cover Singer"), track(seed, artist)],
        artist: [track("Neighbour", artist)],
    })
    body = discover(client, seed)
    assert body["seed_status"] == "matched"
    assert body["seed_resolution_source"] == "verified_hint"
    assert body["seed_track"]["artist"]["name"] == artist
    assert model.identify_calls == []
    assert len(model.answer_calls) <= 1
    assert len(registry.calls) <= 3


def test_manual_cover_artist_overrides_a_verified_original_hint(identification_case):
    cover = track("我好想你", "Cover Singer")
    client, registry, model = identification_case({
        "我好想你": [track("我好想你", "蘇打綠"), cover],
        "Cover Singer": [track("Their Next Song", "Cover Singer")],
    })
    body = discover(client, "我好想你", seed_artist="Cover Singer")
    assert body["seed_track"] == cover.model_dump(mode="json")
    assert body["seed_resolution_source"] == "user"
    assert [item["title"] for item in body["items"]] == ["Their Next Song"]
    assert model.identify_calls == []
    assert len(registry.calls) <= 3


def test_model_identification_never_pads_related_results_with_unrelated_popular_tracks(
        identification_case):
    client, registry, model = identification_case({
        "Shared Title": [track("Shared Title", "Second", genres=("folk",))],
        "Second": [track("Unrelated", "Pop Star", genres=("dance",), popularity=100)],
        "folk": [],
    })
    body = discover(client)
    assert body["seed_status"] == "matched"
    assert body["items"] == []
    assert_identification_budget(registry, model)


def test_model_and_manual_selection_preserve_the_same_deterministic_scores(identification_case):
    client, registry, model = identification_case({
        "Shared Title": [track("Shared Title", "First"), track("Shared Title", "Second")],
        "Second": [track("Neighbour", "Second"), track("Other Folk", "Third", popularity=99)],
    })
    model_result = discover(client)
    assert_identification_budget(registry, model)
    user_result = discover(client, seed_artist="Second")
    assert model_result["items"] == user_result["items"]
    assert model_result["seed_resolution_source"] == "model"
    assert user_result["seed_resolution_source"] == "user"
    assert len(model.identify_calls) == 1


def test_identification_cannot_treat_a_marked_live_recording_as_original(identification_case):
    client, registry, model = identification_case({
        "Shared Title": [track("Shared Title (Live)", "Second")],
        "Shared Title Second": [track("Shared Title (Cover)", "Second")],
    })
    body = discover(client)
    assert body["seed_track"] is None
    assert body["items"] == []
    assert body["seed_status"] == "unresolved"
    assert_identification_budget(registry, model)


def test_theme_identification_preserves_existing_theme_recommendations(identification_case):
    client, registry, model = identification_case({
        "calm jazz": [track("Quiet Jazz", "Player", genres=("jazz",), tags=("calm",))],
    }, {"kind": "theme", "title": None, "artist": None})
    body = discover(client, "calm jazz")
    assert body["seed_track"] is None
    assert body["items"]
    assert any(item["title"] == "Quiet Jazz" for item in body["items"])
    assert_identification_budget(registry, model)


def test_artist_qualified_catalog_match_does_not_claim_verified_original(identification_case):
    client, registry, model = identification_case({
        "Shared Title by Second": [track("Shared Title", "Second")],
        "Second": [track("Neighbour", "Second")],
    })
    body = discover(client, "Shared Title by Second")
    assert body["seed_resolution_source"] == "catalog"
    assert body["seed_track"]["artist"]["name"] == "Second"
    assert model.identify_calls == []
    assert len(model.answer_calls) <= 1
    assert len(registry.calls) <= 3


def test_explicit_theme_survives_model_outage_without_guessing_a_song(identification_case):
    client, registry, model = identification_case({"calm jazz": []}, error=TimeoutError())
    body = discover(client, "calm jazz")
    assert body["seed_track"] is None
    assert body["items"]
    assert body["guidance_status"] == "unavailable"
    assert_identification_budget(registry, model)


def test_model_theme_cannot_override_a_real_title_match(identification_case):
    client, registry, model = identification_case({"Shared Title": [track("Shared Title", "Second")]},
        {"kind": "theme", "title": None, "artist": None})
    body = discover(client)
    assert body["seed_status"] == "ambiguous"
    assert body["items"] == []
    assert_identification_budget(registry, model)


def identify_original(client, **extra):
    return client.post("/v1/recommendations/identify-original", json={
        "seed": "Shared Title", "language": "zh", "rejected_candidates": [
            {"title": "Shared Title", "artist": "First"}], **extra})


def test_rejected_candidates_trigger_one_model_call_and_only_a_catalog_check(identification_case):
    second = track("Shared Title", "Second")
    client, registry, model = identification_case({"Shared Title Second": [second]})
    response = identify_original(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "matched"
    assert body["suggestion"] == {"title": "Shared Title", "artist": "Second"}
    assert body["matched_track"] == second.model_dump(mode="json")
    assert "items" not in body
    assert [query for query, _ in registry.calls] == ["Shared Title Second"]
    assert len(model.identify_calls) == 1
    assert model.identify_calls[0] == {"task": "identify_original", "message": "Shared Title",
        "rejected_candidates": [{"title": "Shared Title", "artist": "First"}]}
    assert model.answer_calls == []
    confirmed = discover(client, seed_artist="Second")
    assert confirmed["seed_track"]["artist"]["name"] == "Second"
    assert len(model.identify_calls) == 1


def test_valid_model_suggestion_without_catalog_match_is_unverified(identification_case):
    client, registry, model = identification_case({})
    response = identify_original(client)
    assert response.status_code == 200
    assert response.json()["status"] == "unverified"
    assert response.json()["suggestion"] == {"title": "Shared Title", "artist": "Second"}
    assert response.json()["matched_track"] is None
    assert len(registry.calls) <= 3
    assert len(model.identify_calls) == 1


@pytest.mark.parametrize("output,rejected", [
    ({"kind": "song", "title": "Shared Title", "artist": "FIRST"}, "First"),
    ({"kind": "song", "title": "Shared Title", "artist": "Faye Wong"}, "王菲"),
    ({"kind": "song", "title": "Other Title", "artist": "Second"}, "First"),
    ({"kind": "theme", "title": None, "artist": None}, "First"),
    ({"kind": "unknown", "title": None, "artist": None}, "First"),
])
def test_rejected_alias_unrelated_title_and_abstention_never_become_suggestions(
        identification_case, output, rejected):
    client, registry, model = identification_case({}, output)
    response = identify_original(client, rejected_candidates=[
        {"title": "Shared Title", "artist": rejected}])
    assert response.status_code == 200
    assert response.json()["status"] == "unknown"
    assert response.json()["suggestion"] is None
    assert response.json()["matched_track"] is None
    assert registry.calls == []
    assert len(model.identify_calls) == 1


@pytest.mark.parametrize("output,error,status,code", [
    (None, TimeoutError("private timeout"), 504, "identification_timeout"),
    (None, httpx.ReadTimeout("private HTTP timeout"), 504, "identification_timeout"),
    (None, httpx.ConnectError("private credentials"), 502, "identification_unavailable"),
    ({"kind": "song", "title": 3, "artist": "Second"}, None, 502, "identification_invalid_output"),
])
def test_original_identification_errors_are_distinct_and_private(
        identification_case, output, error, status, code):
    client, registry, model = identification_case({}, output, error)
    response = identify_original(client)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "private" not in response.text
    assert registry.calls == []
    assert len(model.identify_calls) == 1


def test_original_identification_requires_a_real_configured_model(identification_case):
    from app.agent.providers import LocalLLMProvider

    client, registry, model = identification_case({})
    app.dependency_overrides[get_llm_provider] = LocalLLMProvider
    response = identify_original(client)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "identification_not_configured"
    assert registry.calls == model.identify_calls == []


@pytest.mark.parametrize("extra", [
    {"seed": " "}, {"seed": "x" * 121}, {"language": "fr"},
    {"rejected_candidates": []},
    {"rejected_candidates": [{"title": "Shared Title", "artist": "First"}] * 6},
    {"rejected_candidates": [{"title": "Shared Title", "artist": " "}]},
    {"rejected_candidates": [{"title": "Shared Title", "artist": "First", "payload": {}}]},
    {"api_key": "private"},
])
def test_original_identification_bounds_external_inputs(identification_case, extra):
    client, registry, model = identification_case({})
    response = identify_original(client, **extra)
    assert response.status_code == 422
    assert registry.calls == model.identify_calls == []


def test_original_identification_matches_reviewed_title_and_artist_aliases(identification_case):
    client, registry, model = identification_case({"I Miss You So sodagreen": [
        track("我好想你", "蘇打綠")]}, {"kind": "song", "title": "I Miss You So", "artist": "sodagreen"})
    # Reviewed translated titles still refer to the same recording and artist identity.
    response = identify_original(client, seed="我好想你")
    assert response.status_code == 200
    assert response.json()["status"] == "matched"
    assert response.json()["matched_track"]["artist"]["name"] == "蘇打綠"
    assert len(registry.calls) <= 3
    assert len(model.identify_calls) == 1


def test_original_identification_searches_reviewed_artist_spellings_within_shared_budget(identification_case):
    client, registry, model = identification_case({"Shared Title 王菲": [
        track("Shared Title", "王菲")]}, {"kind": "song", "title": "Shared Title", "artist": "Faye Wong"})
    response = identify_original(client)
    assert response.status_code == 200
    assert response.json()["status"] == "matched"
    assert [query for query, _ in registry.calls] == ["Shared Title Faye Wong", "Shared Title 王菲"]
    assert len(model.identify_calls) == 1


def test_original_identification_retains_partial_provider_failure_without_fabrication(identification_case):
    from app.domain.music import ProviderError

    client, registry, model = identification_case({})

    def failed_search(query, limit):
        registry.calls.append((query, limit))
        return SearchResult(tracks=[], sources={"itunes": ProviderResult(provider="itunes", tracks=[],
            error=ProviderError(code="unavailable", message="Source unavailable."))})

    registry.search_tracks = failed_search
    response = identify_original(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unverified"
    assert body["matched_track"] is None
    assert body["sources"]["itunes"]["error"]["code"] == "unavailable"
    assert len(model.identify_calls) == 1


def test_original_identification_and_discovery_share_four_active_slots(identification_case):
    _client, _registry, model = identification_case({})

    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()
        active = 0

        async def wait_for_model(context):
            nonlocal active
            active += 1
            if active == 4:
                entered.set()
            await release.wait()
            return {"kind": "unknown", "title": None, "artist": None}

        model.identify_seed = wait_for_model
        body = {"seed": "Shared Title", "rejected_candidates": [
            {"title": "Shared Title", "artist": "First"}]}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as browser:
            tasks = [asyncio.create_task(browser.post("/v1/recommendations/identify-original", json=body))
                     for _ in range(4)]
            try:
                await asyncio.wait_for(entered.wait(), 3)
                busy = await browser.post("/v1/recommendations/identify-original", json=body)
                assert busy.status_code == 503
                assert busy.json()["error"]["code"] == "identification_busy"
                discovery = await browser.post("/v1/recommendations/discover", json={"seed": "Shared Title"})
                assert discovery.status_code == 503
                assert discovery.json()["error"]["code"] == "discovery_busy"
            finally:
                release.set()
                results = await asyncio.gather(*tasks)
            assert all(result.status_code == 200 for result in results)
            assert (await browser.post("/v1/recommendations/identify-original", json=body)).status_code == 200

    asyncio.run(exercise())


def test_confirmed_model_artist_is_revalidated_before_recommendation(identification_case):
    client, registry, model = identification_case({"Shared Title Second": [track("Shared Title", "Second")]})
    assert identify_original(client).json()["status"] == "matched"
    registry.responses.clear()
    registry.responses["Second"] = [track("Neighbour", "Second")]
    confirmed = discover(client, seed_artist="Second")
    assert confirmed["seed_status"] == "unresolved"
    assert confirmed["seed_track"] is None
    assert confirmed["items"] == []
    assert len(model.identify_calls) == 1


def test_original_identification_logs_only_correlated_status_not_song_or_model_content(
        identification_case, caplog):
    client, registry, model = identification_case({})
    response = identify_original(client)
    records = [json.loads(record.message) for record in caplog.records
               if record.name == "music_api" and '"original_identification"' in record.message]
    assert len(records) == 1
    assert records[0]["request_id"] == response.headers["X-Request-Id"] == response.json()["request_id"]
    assert records[0]["status"] == "unverified"
    assert records[0]["latency_ms"] >= 0
    assert "Shared Title" not in json.dumps(records)
    assert "Second" not in json.dumps(records)
    assert len(registry.calls) <= 3
    assert len(model.identify_calls) == 1


def test_catalog_timeout_returns_a_safe_timeout_error(identification_case, monkeypatch):
    from app.services import original_identification

    async def timed_out(_operation):
        raise TimeoutError("private worker details")

    client, registry, model = identification_case({})
    monkeypatch.setattr(original_identification, "run_blocking", timed_out)
    response = identify_original(client)
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "identification_timeout"
    assert "private" not in response.text
    assert registry.calls == []
    assert len(model.identify_calls) == 1


def test_original_identification_cannot_verify_live_or_cover_recordings(identification_case):
    client, registry, model = identification_case({"Shared Title Second": [
        track("Shared Title (Live)", "Second"), track("Shared Title (Cover)", "Second")]})
    body = identify_original(client).json()
    assert body["status"] == "unverified"
    assert body["matched_track"] is None
    assert body["suggestion"] == {"title": "Shared Title", "artist": "Second"}
    assert len(model.identify_calls) == 1
    assert len(registry.calls) <= 3
