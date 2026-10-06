"""Expansion and successful knowledge must remain grounded in provider data."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agent.providers import get_llm_provider
from app.domain.music import (
    Artist,
    ProviderResult,
    ProviderSource,
    Track,
    canonical_key,
)
from app.infrastructure.database import get_session
from app.main import app
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.repository.models import Base, RecordingResolution, VerifiedRecording
from app.services.recording_resolution import (
    RecordingResolver,
    ResolutionError,
    parse_song_link,
)


def recording(title="Missing", artist="Artist", provider="extra", identifier="real-id"):
    return Track(title=title, artist=Artist(name=artist),
                 source=ProviderSource(provider=provider, provider_track_id=identifier,
                                       external_url="https://musicbrainz.org/recording/real-id"),
                 canonical_key=canonical_key(title, artist))


class Catalog:
    def __init__(self, name, tracks=()):
        self.name, self.tracks, self.calls = name, list(tracks), []

    def search_tracks(self, query, limit):
        self.calls.append(("search", query))
        return ProviderResult(provider=self.name, tracks=self.tracks[:limit])

    def lookup_track(self, identifier):
        self.calls.append(("lookup", identifier))
        return ProviderResult(provider=self.name, tracks=[t for t in self.tracks
                              if t.source.provider_track_id == identifier])


def test_expansion_finds_new_catalog_and_stops_after_match(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'resolve.db'}")
    Base.metadata.create_all(engine)
    first, extra, last = Catalog("itunes"), Catalog("extra", [recording()]), Catalog("last")
    resolver = RecordingResolver(ProviderRegistry([first], extensions=[extra, last]), engine, "Missing", "Artist")
    result = resolver.resolve()
    assert result.status == "matched"
    assert result.matched_track.source.provider == "extra"
    assert not last.calls
    assert result.resolution_id
    with Session(engine) as session:
        assert not session.scalars(select(VerifiedRecording)).all()  # Verification alone is not memory.
    resolver.confirm(result.resolution_id, "Artist")
    with Session(engine) as session:
        assert len(session.scalars(select(VerifiedRecording)).all()) == 1
    first.calls.clear()
    next_resolver = RecordingResolver(resolver.registry, engine, "Missing", "Artist")
    assert next_resolver.resolve().status == "matched"
    assert not first.calls
    assert next_resolver.report().attempts[0].stage == "memory"


def test_link_parser_only_accepts_registered_song_urls():
    assert parse_song_link("https://y.qq.com/n/ryqq/songDetail/004AGa4s1SF7je") == ("qq", "004AGa4s1SF7je", None)
    assert parse_song_link("https://music.163.com/#/song?id=123") == ("netease", "123", None)
    assert parse_song_link("https://music.apple.com/tw/album/name/123?i=456") == ("itunes", "456", "TW")
    for unsafe in ("http://127.0.0.1/private", "https://y.qq.com.evil.test/song/123",
                   "https://user:pass@y.qq.com/n/ryqq/songDetail/123", "https://y.qq.com:444/song/123"):
        assert parse_song_link(unsafe) is None


def test_cover_or_wrong_artist_is_not_a_success(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'resolve.db'}")
    Base.metadata.create_all(engine)
    catalog = Catalog("extra", [recording(artist="Other"), recording(title="Missing (Live)")])
    resolver = RecordingResolver(ProviderRegistry([], extensions=[catalog]), engine, "Missing", "Artist")
    result = resolver.resolve()
    assert result.status == "not_found"
    assert result.matched_track is None and result.resolution_id is None


def test_manual_link_recovers_without_model_or_fabricated_id(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'resolve.db'}")
    Base.metadata.create_all(engine)
    catalog = Catalog("qq", [recording(provider="qq", identifier="real-mid")])
    resolver = RecordingResolver(ProviderRegistry([catalog]), engine, "Missing", "Artist", manual=True)
    result = resolver.resolve(song_url="https://y.qq.com/n/ryqq/songDetail/real-mid")
    assert result.status == "matched"
    assert catalog.calls == [("lookup", "real-mid")]
    assert result.search_report.external_requests == 1


@pytest.fixture
def engine(tmp_path):
    value = create_engine(f"sqlite+pysqlite:///{tmp_path / 'resolution.db'}")
    Base.metadata.create_all(value)
    yield value
    value.dispose()


def test_stale_memory_continues_to_other_sources(engine):
    old, new = Catalog("qq", [recording(provider="qq", identifier="123")]), Catalog("extra", [recording()])
    registry = ProviderRegistry([old], extensions=[new])
    first = RecordingResolver(registry, engine, "Missing", "Artist")
    proof = first.resolve().resolution_id
    first.confirm(proof, "Artist")
    old.tracks.clear()
    result = RecordingResolver(registry, engine, "Missing", "Artist").resolve()
    assert result.matched_track.source.provider == "extra"
    with Session(engine) as session:
        assert session.scalar(select(VerifiedRecording)).stale


def test_homonyms_are_kept_separate_and_unqualified_memory_stays_ambiguous(engine):
    one, two = recording(artist="One"), recording(artist="Two", identifier="second")
    registry = ProviderRegistry([], extensions=[Catalog("extra", [one, two])])
    for artist in ("One", "Two"):
        resolver = RecordingResolver(registry, engine, "Missing", artist)
        resolver.confirm(resolver.resolve().resolution_id, artist)
    with Session(engine) as session:
        assert len(session.scalars(select(VerifiedRecording)).all()) == 2
    resolver = RecordingResolver(registry, engine, "Missing")
    assert resolver.resolve().status == "ambiguous"


def test_confirmation_expires_and_cannot_be_reused_for_other_queries(engine):
    registry = ProviderRegistry([], extensions=[Catalog("extra", [recording()])])
    resolver = RecordingResolver(registry, engine, "Missing", "Artist")
    identifier = resolver.resolve().resolution_id
    with pytest.raises(ResolutionError, match="does not match"):
        RecordingResolver(registry, engine, "Other", "Artist").confirm(identifier, "Artist")
    with Session(engine) as session:
        session.get(RecordingResolution, identifier).expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    with pytest.raises(ResolutionError, match="expired"):
        resolver.confirm(identifier, "Artist")
    with Session(engine) as session:
        assert not session.scalars(select(VerifiedRecording)).all()


def test_failed_confirmation_does_not_save_memory(engine):
    catalog = Catalog("extra", [recording()])
    registry = ProviderRegistry([], extensions=[catalog])
    resolver = RecordingResolver(registry, engine, "Missing", "Artist")
    identifier = resolver.resolve().resolution_id
    catalog.tracks.clear()
    with pytest.raises(ResolutionError, match="reverified"):
        resolver.confirm(identifier, "Artist")
    with Session(engine) as session:
        assert not session.scalars(select(VerifiedRecording)).all()


def test_budget_and_deadline_report_incomplete_not_song_absence(engine):
    registry = ProviderRegistry([Catalog("one"), Catalog("two"), Catalog("three")],
                                extensions=[Catalog(f"extra-{i}") for i in range(20)])
    resolver = RecordingResolver(registry, engine, "Missing", "Artist")
    result = resolver.resolve()
    assert result.status == "incomplete"
    assert result.search_report.end_reason == "budget_exhausted"
    assert result.search_report.external_requests <= 24
    assert len(resolver.cached) == resolver.external_requests  # no duplicate combinations
    resolver = RecordingResolver(registry, engine, "Missing", manual=True)
    resolver.deadline = 0
    result = resolver.resolve(platform="qq")
    assert result.status == "unavailable"  # platform is not configured
    result = RecordingResolver(registry, engine, "Missing", manual=True)
    result.deadline = 0
    assert result.resolve().search_report.end_reason == "deadline"


def test_brave_clues_need_real_catalog_details(engine):
    class Web:
        def links(self, query):
            return ["https://unregistered.example/song/123", "https://y.qq.com/n/ryqq/songDetail/knownmid"]
    catalog = Catalog("qq")
    registry = ProviderRegistry([catalog], web_search=Web())
    resolver = RecordingResolver(registry, engine, "Missing", "Artist")
    assert resolver.resolve().matched_track is None
    assert ("lookup", "knownmid") in catalog.calls
    assert all(track.source.provider != "brave" for track in resolver.tracks)


def test_manual_endpoint_confirmation_and_remembered_discovery(engine):
    registry = ProviderRegistry([Catalog("qq", [recording(provider="qq", identifier="123"),
                                               recording("Neighbour", provider="qq", identifier="456")])])
    class Model:
        name = "local"
    def session_override():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_provider_registry] = lambda: registry
    app.dependency_overrides[get_llm_provider] = lambda: Model()
    try:
        with TestClient(app) as client:
            reply = client.post("/v1/recordings/resolve", json={"seed": "Missing", "artist": "Artist", "platform": "qq"})
            assert reply.status_code == 200, reply.text
            body = reply.json()
            assert body["status"] == "matched" and "items" not in body
            with Session(engine) as session:
                assert not session.scalars(select(VerifiedRecording)).all()
            reply = client.post("/v1/recommendations/discover", json={"seed": "Missing", "seed_artist": "Artist",
                "resolution_id": body["resolution_id"], "language": "en"})
            assert reply.status_code == 200, reply.text
            assert reply.json()["seed_track"]["source"]["provider"] == "qq"
            assert [item["title"] for item in reply.json()["items"]] == ["Neighbour"]
            with Session(engine) as session:
                assert len(session.scalars(select(VerifiedRecording)).all()) == 1
            again = client.post("/v1/recommendations/discover", json={"seed": "Missing", "seed_artist": "Artist"})
            assert again.json()["search_report"]["attempts"][0]["stage"] == "memory"
            unsupported = client.post("/v1/recordings/resolve", json={"seed": "Missing", "platform": "unknown"})
            assert unsupported.json()["status"] == "unsupported_platform"
            invalid = client.post("/v1/recordings/resolve", json={"seed": "x", "song_url": "x" * 2049})
            assert invalid.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("catalog_tracks,status", [([recording()], "matched"), ([], "unverified")])
def test_rejection_uses_same_expansion_without_recommending_or_learning(engine, catalog_tracks, status):
    import asyncio

    from app.api.schemas import OriginalIdentificationRequest
    from app.services.original_identification import identify_original
    class Model:
        name = "openai_compatible"
        calls = 0
        async def identify_seed(self, context):
            self.calls += 1
            assert context["rejected_candidates"] == [{"title": "Missing", "artist": "Rejected"}]
            return {"kind": "song", "title": "Missing", "artist": "Artist"}
    model = Model()
    registry = ProviderRegistry([Catalog("qq")], extensions=[Catalog("extra", catalog_tracks)])
    request = OriginalIdentificationRequest(seed="Missing", rejected_candidates=[{"title": "Missing", "artist": "Rejected"}])
    result = asyncio.run(identify_original(request, model, registry, engine))
    assert result.status == status and model.calls == 1
    assert result.search_report.external_requests <= 23
    assert "items" not in result.model_dump()
    with Session(engine) as session:
        assert not session.scalars(select(VerifiedRecording)).all()


def test_partial_failure_is_not_a_completed_absence(engine):
    from app.domain.music import ProviderError
    class FailingCatalog(Catalog):
        def search_tracks(self, query, limit):
            return ProviderResult(provider=self.name, error=ProviderError(code="auth_required", message="Authorization required."))
    resolver = RecordingResolver(ProviderRegistry([FailingCatalog("qq"), Catalog("netease")]), engine, "Missing")
    result = resolver.resolve()
    assert result.status == "incomplete"
    assert result.search_report.end_reason == "partial_failure"
    assert result.search_report.attempts[0].status == "auth_required"


def test_normalized_punctuation_is_a_distinct_search_variant(engine):
    class PunctuationCatalog(Catalog):
        def search_tracks(self, query, limit):
            self.calls.append(("search", query))
            tracks = [recording("Missing Song")] if "missing song" in query.casefold() else []
            return ProviderResult(provider=self.name, tracks=tracks)
    catalog = PunctuationCatalog("extra")
    result = RecordingResolver(ProviderRegistry([], extensions=[catalog]), engine, "Missing—Song", "Artist").resolve()
    assert result.status == "matched"
    assert len(catalog.calls) == 2
