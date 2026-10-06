from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.domain.embedding import embed_song, embed_user
from app.domain.music import Track, normalize_text
from app.domain.pipeline import dedup_key
from app.domain.policy import POLICY
from app.domain.profile import FeedbackSignal, PreferenceProfile, profile_from_feedback
from app.repository.models import (
    Account,
    AccountFeedback,
    AccountProfile,
    SongEmbedding,
)
from app.repository.vector import Vector16


def _insert(session: Session, model: type):
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return pg_insert(model)
    if dialect == "sqlite":
        return sqlite_insert(model)
    raise RuntimeError("Feedback requires PostgreSQL or SQLite.")


def save_feedback(session: Session, user_id: str, track: Track, value: str) -> str:
    key = dedup_key(track)
    with session.begin():
        # Serialize profile rebuilds across devices, within this feedback transaction.
        if session.get_bind().dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        else:
            session.execute(text("SET LOCAL lock_timeout = '3000ms'"))
            session.execute(text("SET LOCAL statement_timeout = '5000ms'"))
        if session.scalar(select(Account.user_id).where(Account.user_id == user_id).with_for_update()) is None:
            raise ValueError("Account unavailable.")
        now = datetime.now(UTC)
        columns = {
            "value": value,
            "artist": normalize_text(track.artist.name),
            "genres": [normalize_text(genre) for genre in track.genres],
            "tags": [normalize_text(tag) for tag in track.tags],
            "language": normalize_text(track.language) if track.language else None,
            "updated_at": now,
        }
        feedback = _insert(session, AccountFeedback).values(user_id=user_id, track_key=key, **columns)
        feedback = feedback.on_conflict_do_update(index_elements=["user_id", "track_key"], set_=columns)
        session.execute(feedback)
        song_embedding = embed_song(track)
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("INSERT INTO song_embeddings (track_key, embedding, updated_at) "
                                 "VALUES (:key, CAST(:embedding AS vector), :updated_at) "
                                 "ON CONFLICT (track_key) DO UPDATE SET embedding = EXCLUDED.embedding, "
                                 "updated_at = EXCLUDED.updated_at"),
                            {"key": key, "embedding": Vector16().bind_processor(None)(song_embedding),
                             "updated_at": now})
        else:
            song = _insert(session, SongEmbedding).values(track_key=key, embedding=song_embedding, updated_at=now)
            song = song.on_conflict_do_update(index_elements=["track_key"],
                                              set_={"embedding": song_embedding, "updated_at": now})
            session.execute(song)
        rows = session.scalars(select(AccountFeedback).where(AccountFeedback.user_id == user_id)
                               .order_by(AccountFeedback.updated_at.desc(), AccountFeedback.track_key)
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
        if session.get_bind().dialect.name == "sqlite":
            profile_columns["embedding"] = embed_user(profile)
        statement = _insert(session, AccountProfile).values(user_id=user_id, **profile_columns)
        statement = statement.on_conflict_do_update(index_elements=["user_id"], set_=profile_columns)
        session.execute(statement)
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("UPDATE account_profiles "
                                 "SET embedding = CAST(:embedding AS vector) WHERE user_id = :user_id"),
                            {"embedding": Vector16().bind_processor(None)(embed_user(profile)),
                             "user_id": user_id})
    return key


def load_profile(session: Session, user_id: str) -> PreferenceProfile:
    row = session.get(AccountProfile, user_id)
    if row is None:
        return PreferenceProfile()
    recent = session.scalars(select(AccountFeedback).where(AccountFeedback.user_id == user_id)
                             .order_by(AccountFeedback.updated_at.desc(), AccountFeedback.track_key)
                             .limit(POLICY.recent_feedback_limit)).all()
    disliked = {item.track_key for item in recent if item.value == "dislike"}
    return PreferenceProfile(artist_affinity=row.artist_affinity, genre_affinity=row.genre_affinity,
                             tag_affinity=row.tag_affinity, language_affinity=row.language_affinity,
                             disliked_tracks=disliked)


def recent_feedback(session: Session, user_id: str, limit: int = 5) -> list[AccountFeedback]:
    return list(session.scalars(select(AccountFeedback).where(AccountFeedback.user_id == user_id)
                                .order_by(AccountFeedback.updated_at.desc(), AccountFeedback.track_key)
                                .limit(limit)).all())
