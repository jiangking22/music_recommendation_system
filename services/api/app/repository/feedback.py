from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.domain.music import Track, normalize_text
from app.domain.pipeline import dedup_key
from app.domain.policy import POLICY
from app.domain.profile import FeedbackSignal, PreferenceProfile, profile_from_feedback
from app.repository.models import DeviceUser, TrackFeedback, UserPreferenceProfile


def _insert(session: Session, model: type):
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return pg_insert(model)
    if dialect == "sqlite":
        return sqlite_insert(model)
    raise RuntimeError("Feedback requires PostgreSQL or SQLite.")


def save_feedback(session: Session, device_id: str, track: Track, value: str) -> str:
    key = dedup_key(track)
    now = datetime.now(UTC)
    with session.begin():
        device = _insert(session, DeviceUser).values(device_id=device_id).on_conflict_do_nothing(
            index_elements=["device_id"])
        session.execute(device)
        columns = {
            "value": value,
            "artist": normalize_text(track.artist.name),
            "genres": [normalize_text(genre) for genre in track.genres],
            "tags": [normalize_text(tag) for tag in track.tags],
            "language": normalize_text(track.language) if track.language else None,
            "updated_at": now,
        }
        feedback = _insert(session, TrackFeedback).values(device_id=device_id, track_key=key, **columns)
        feedback = feedback.on_conflict_do_update(index_elements=["device_id", "track_key"], set_=columns)
        session.execute(feedback)
        rows = session.scalars(select(TrackFeedback).where(TrackFeedback.device_id == device_id)
                               .order_by(TrackFeedback.updated_at.desc(), TrackFeedback.track_key)
                               .limit(POLICY.recent_feedback_limit)).all()
        signals = [FeedbackSignal(row.track_key, row.value, row.artist, tuple(row.genres),
                                  tuple(row.tags), row.language) for row in rows]
        profile = profile_from_feedback(signals, POLICY.recent_feedback_decay)
        profile_columns = {
            "artist_affinity": profile.artist_affinity,
            "genre_affinity": profile.genre_affinity,
            "tag_affinity": profile.tag_affinity,
            "language_affinity": profile.language_affinity,
            "updated_at": now,
        }
        statement = _insert(session, UserPreferenceProfile).values(device_id=device_id, **profile_columns)
        statement = statement.on_conflict_do_update(index_elements=["device_id"], set_=profile_columns)
        session.execute(statement)
    return key


def load_profile(session: Session, device_id: str) -> PreferenceProfile:
    row = session.get(UserPreferenceProfile, device_id)
    if row is None:
        return PreferenceProfile()
    disliked = set(session.scalars(select(TrackFeedback.track_key).where(
        TrackFeedback.device_id == device_id, TrackFeedback.value == "dislike")).all())
    return PreferenceProfile(artist_affinity=row.artist_affinity, genre_affinity=row.genre_affinity,
                             tag_affinity=row.tag_affinity, language_affinity=row.language_affinity,
                             disliked_tracks=disliked)
