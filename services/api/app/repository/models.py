from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.repository.vector import Vector16


class Base(DeclarativeBase):
    pass


class DeviceUser(Base):
    __tablename__ = "device_users"

    device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TrackFeedback(Base):
    __tablename__ = "track_feedback"
    __table_args__ = (CheckConstraint("value IN ('like', 'dislike')", name="ck_feedback_value"),)

    device_id: Mapped[str] = mapped_column(String(128), ForeignKey("device_users.device_id"), primary_key=True)
    track_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    value: Mapped[str] = mapped_column(String(8), nullable=False)
    artist: Mapped[str] = mapped_column(String(200), nullable=False)
    genres: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    language: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserPreferenceProfile(Base):
    __tablename__ = "user_preference_profiles"

    device_id: Mapped[str] = mapped_column(String(128), ForeignKey("device_users.device_id"), primary_key=True)
    artist_affinity: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    genre_affinity: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    tag_affinity: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    language_affinity: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector16(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SongEmbedding(Base):
    __tablename__ = "song_embeddings"

    track_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector16(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
