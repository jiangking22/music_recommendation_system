"""Model-assisted seed identification must remain grounded in canonical catalog data."""

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
