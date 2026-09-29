from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.domain.music import SearchResult
from app.infrastructure.database import get_session
from app.main import app
from app.providers.registry import get_provider_registry
from app.repository.models import (
    Base,
    SongEmbedding,
    TrackFeedback,
    UserPreferenceProfile,
)


class EmptyRegistry:
    def search_tracks(self, query: str, limit: int) -> SearchResult:
        return SearchResult(tracks=[], sources={})


def test_feedback_upsert_persists_profile_and_changes_later_recommendations(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'feedback.db'}")
    Base.metadata.create_all(engine)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_provider_registry] = lambda: EmptyRegistry()
    headers = {"X-Device-Id": "device_1234567890"}
    try:
        with TestClient(app) as client:
            before = client.post("/v1/recommendations", json={"seed": "unknown", "limit": 3}, headers=headers)
            target = next(item["track"] for item in before.json()["items"] if item["title"] == "Night Signal")
            liked = client.post("/v1/feedback", json={"track": target, "value": "like"}, headers=headers)
            after_like = client.post("/v1/recommendations", json={"seed": "unknown", "limit": 3}, headers=headers)
            other_device = client.post("/v1/recommendations", json={"seed": "unknown", "limit": 3},
                                       headers={"X-Device-Id": "device_9876543210"})
            disliked = client.post("/v1/feedback", json={"track": target, "value": "dislike"}, headers=headers)
            after_dislike = client.post("/v1/recommendations", json={"seed": "unknown", "limit": 3}, headers=headers)
        assert liked.status_code == disliked.status_code == 200
        assert before.status_code == after_like.status_code == after_dislike.status_code == 200
        assert after_like.json()["items"][0]["title"] == "Night Signal"
        assert other_device.json()["items"][0]["title"] == before.json()["items"][0]["title"]
        assert after_dislike.json()["items"][-1]["title"] == "Night Signal"
        with Session(engine) as session:
            feedback = session.scalars(select(TrackFeedback)).all()
            profile = session.get(UserPreferenceProfile, headers["X-Device-Id"])
            assert len(feedback) == 1
            assert feedback[0].value == "dislike"
            assert profile is not None
            assert profile.artist_affinity["example artist"] < 0
            assert len(profile.embedding) == 16
            assert len(session.scalars(select(SongEmbedding)).all()) == 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_feedback_validates_header_and_payload() -> None:
    with TestClient(app) as client:
        missing = client.post("/v1/feedback", json={"value": "like"})
        bad = client.post("/v1/feedback", headers={"X-Device-Id": "device_1234567890"},
                          json={"value": "love", "track": {}})
        blank_source = client.post("/v1/feedback", headers={"X-Device-Id": "device_1234567890"},
                                   json={"value": "like", "track": {
                                       "title": "Song", "artist": {"name": "Artist"},
                                       "source": {"provider": "itunes", "provider_track_id": "  "},
                                       "canonical_key": "song::artist"}})
    assert missing.status_code == bad.status_code == 422
    assert blank_source.status_code == 422
    assert missing.json()["error"]["code"] == "validation_error"
