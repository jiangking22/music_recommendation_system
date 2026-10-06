"""Confirmed provider knowledge and temporary verification references."""

import sqlalchemy as sa
from alembic import op

revision = "0006_recording_resolution"
down_revision = "0005_music_knowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("verified_recordings",
        sa.Column("knowledge_key", sa.String(64), primary_key=True),
        sa.Column("normalized_title", sa.String(200), nullable=False),
        sa.Column("artist_identity", sa.String(200), nullable=False),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("recording_id", sa.String(200), nullable=False),
        sa.Column("region", sa.String(2)), sa.Column("source_url", sa.String(2048)),
        sa.Column("track", sa.JSON(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stale", sa.Boolean(), nullable=False))
    op.create_index("ix_verified_recordings_normalized_title", "verified_recordings", ["normalized_title"])
    op.create_table("recording_resolutions",
        sa.Column("resolution_id", sa.String(36), primary_key=True),
        sa.Column("seed", sa.String(120), nullable=False),
        sa.Column("track", sa.JSON(), nullable=False), sa.Column("region", sa.String(2)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_recording_resolutions_expires_at", "recording_resolutions", ["expires_at"])


def downgrade() -> None:
    op.drop_table("recording_resolutions")
    op.drop_table("verified_recordings")
