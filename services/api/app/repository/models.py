from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.repository.vector import Vector16


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(32), nullable=False)
    username_key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.user_id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AccountFeedback(Base):
    __tablename__ = "account_feedback"
    __table_args__ = (CheckConstraint("value IN ('like', 'dislike')", name="ck_account_feedback_value"),)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.user_id"), primary_key=True)
    track_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    value: Mapped[str] = mapped_column(String(8), nullable=False)
    artist: Mapped[str] = mapped_column(String(200), nullable=False)
    genres: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    language: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AccountProfile(Base):
    __tablename__ = "account_profiles"
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.user_id"), primary_key=True)
    artist_affinity: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    genre_affinity: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    tag_affinity: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    language_affinity: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector16(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AccountConversation(Base):
    __tablename__ = "account_conversations"
    conversation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.user_id"), index=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("login_sessions.session_id"), index=True)
    messages: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    search_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default='{}')
    last_seed: Mapped[str | None] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AccountPreferenceSummary(Base):
    __tablename__ = "account_preference_summaries"
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("login_sessions.session_id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.user_id"), index=True)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VerifiedRecording(Base):
    __tablename__ = "verified_recordings"
    knowledge_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    normalized_title: Mapped[str] = mapped_column(String(200), index=True)
    artist_identity: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(40), nullable=False)
    recording_id: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str | None] = mapped_column(String(2))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    track: Mapped[dict] = mapped_column(JSON, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stale: Mapped[bool] = mapped_column(default=False, nullable=False)


class RecordingResolution(Base):
    __tablename__ = "recording_resolutions"
    resolution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seed: Mapped[str] = mapped_column(String(120), nullable=False)
    track: Mapped[dict] = mapped_column(JSON, nullable=False)
    region: Mapped[str | None] = mapped_column(String(2))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


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


class AgentConversation(Base):
    __tablename__ = "agent_conversations"

    conversation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), ForeignKey("device_users.device_id"), index=True)
    messages: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    last_seed: Mapped[str | None] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentPreferenceSummary(Base):
    __tablename__ = "agent_preference_summaries"

    device_id: Mapped[str] = mapped_column(String(128), ForeignKey("device_users.device_id"), primary_key=True)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KnowledgeDocument(Base):
    __tablename__ = "music_knowledge_documents"
    __table_args__ = (CheckConstraint("category IN ('artist', 'genre', 'album', 'explanation')",
                                     name="ck_knowledge_category"),)

    document_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class KnowledgeChunk(Base):
    __tablename__ = "music_knowledge_chunks"

    chunk_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(80), ForeignKey("music_knowledge_documents.document_id"), index=True)
    text: Mapped[str] = mapped_column(String(600), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector16(), nullable=False)
