from pathlib import Path

import pytest
from account_helpers import seed_account
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.domain.music import Artist, ProviderSource, Track, canonical_key
from app.infrastructure.database import get_session
from app.main import app
from app.repository.models import AccountFeedback, AccountProfile, Base


def test_known_artist_aliases_have_one_identity_and_source_backed_chinese_display():
    from app.domain.artist_names import artist_identity, preferred_artist_name

    assert artist_identity("Faye Wong") == artist_identity("王菲")
    assert preferred_artist_name(" FAYE WONG ") == "王菲"
    assert artist_identity("sodagreen") == artist_identity("蘇打綠")
    assert preferred_artist_name("Soda Green") == "苏打绿"


@pytest.mark.parametrize("name,preferred", [
    ("Jay Chou", "周杰伦"), ("周杰倫", "周杰伦"),
    ("JJ Lin", "林俊杰"), ("林俊傑", "林俊杰"),
    ("Eason Chan", "陈奕迅"), ("陳奕迅", "陈奕迅"),
    ("Rene Liu", "刘若英"), ("René Liu", "刘若英"), ("劉若英", "刘若英"),
    ("TimoFeng", "冯提莫"), ("Feng Timo", "冯提莫"), ("馮提莫", "冯提莫"),
])
def test_common_chinese_artist_aliases_use_reviewed_chinese_names(name, preferred):
    from app.domain.artist_names import (
        artist_identity,
        enrich_track,
        preferred_artist_name,
    )

    assert artist_identity(name) == artist_identity(preferred)
    assert preferred_artist_name(name) == preferred
    track = Track(title="Catalog song", artist=Artist(name=name),
                  source=ProviderSource(provider="itunes", provider_track_id="existing-id"),
                  canonical_key=canonical_key("Catalog song", name))
    enriched = enrich_track(track)
    assert enriched.artist.display_name == preferred
    assert enriched.artist.name == name
    assert enriched.canonical_key == track.canonical_key


@pytest.mark.parametrize("name", ["Taylor Swift", "泰勒·斯威夫特", "泰勒絲"])
def test_reviewed_foreign_artist_aliases_keep_preferred_english_name(name):
    from app.domain.artist_names import artist_identity, preferred_artist_name

    assert preferred_artist_name(name) == "Taylor Swift"
    assert artist_identity(name) == artist_identity("Taylor Swift")


def test_short_nicknames_and_combined_credits_are_not_assumed_to_be_known_artists():
    from app.domain.artist_names import artist_identity, preferred_artist_name

    assert preferred_artist_name("JJ") == "JJ"
    assert preferred_artist_name("霉霉") == "霉霉"
    assert artist_identity("Jay Chou, JJ Lin") != artist_identity("周杰伦")


def test_unknown_artists_and_foreign_names_are_preserved_without_guessed_translation():
    from app.domain.artist_names import artist_identity, preferred_artist_name

    assert preferred_artist_name("Taylor Swift") == "Taylor Swift"
    assert preferred_artist_name("Unverified Chinese Singer") == "Unverified Chinese Singer"
    assert artist_identity("Taylor Swift") != artist_identity("Taylor Swift Tribute")
    assert artist_identity("Faye Wong, Eason Chan") != artist_identity("王菲")


def test_track_display_enrichment_preserves_provider_metadata_and_feedback_identity():
    from app.domain.artist_names import enrich_track

    track = Track(title="匆匆那年", artist=Artist(name="Faye Wong", provider_artist_id="41760704"),
                  source=ProviderSource(provider="itunes", provider_track_id="966805715"),
                  canonical_key=canonical_key("匆匆那年", "Faye Wong"))
    enriched = enrich_track(track)
    assert enriched.artist.display_name == "王菲"
    assert enriched.artist.name == track.artist.name
    assert enriched.artist.provider_artist_id == track.artist.provider_artist_id
    assert enriched.canonical_key == track.canonical_key
    assert enriched.source == track.source
    assert track.artist.display_name is None


def test_artist_display_name_is_bounded_external_input():
    assert Artist(name="Faye Wong", display_name="王菲").display_name == "王菲"
    with pytest.raises(ValidationError):
        Artist(name="Faye Wong", display_name="x" * 201)


def test_profile_projects_known_display_names_without_rewriting_saved_affinities(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'artist-names.db'}")
    Base.metadata.create_all(engine)
    seed_account(engine)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    headers = {"X-Device-Id": "device_1234567890"}
    track = {"title": "匆匆那年", "artist": {"name": "Faye Wong"},
             "source": {"provider": "itunes", "provider_track_id": "966805715"},
             "canonical_key": "匆匆那年::faye wong"}
    try:
        with TestClient(app) as client:
            saved = client.post("/v1/feedback", json={"track": track, "value": "like"}, headers=headers)
            response = client.get("/v1/profile", headers=headers)
        assert saved.status_code == response.status_code == 200
        assert response.json()["artists"] == [{"name": "faye wong", "display_name": "王菲", "weight": 1.0}]
        assert response.json()["recent_feedback"][0]["artist"] == "faye wong"
        assert response.json()["recent_feedback"][0]["artist_display_name"] == "王菲"
        with Session(engine) as session:
            profile = session.get(AccountProfile, "account_test")
            feedback = session.scalar(select(AccountFeedback))
            assert profile.artist_affinity == {"faye wong": 1.0}
            assert feedback.artist == "faye wong"
            assert feedback.track_key == "匆匆那年::faye wong"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
