"""Persist per-device feedback and preference profile.

Revision ID: 0002_feedback_profiles
Revises: 0001_device_users
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_feedback_profiles"
down_revision = "0001_device_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_feedback",
        sa.Column("device_id", sa.String(length=128), sa.ForeignKey("device_users.device_id"), primary_key=True),
        sa.Column("track_key", sa.String(length=512), primary_key=True),
        sa.Column("value", sa.String(length=8), nullable=False),
        sa.Column("artist", sa.String(length=200), nullable=False),
        sa.Column("genres", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("language", sa.String(length=32)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("value IN ('like', 'dislike')", name="ck_feedback_value"),
    )
    op.create_table(
        "user_preference_profiles",
        sa.Column("device_id", sa.String(length=128), sa.ForeignKey("device_users.device_id"), primary_key=True),
        sa.Column("artist_affinity", sa.JSON(), nullable=False),
        sa.Column("genre_affinity", sa.JSON(), nullable=False),
        sa.Column("tag_affinity", sa.JSON(), nullable=False),
        sa.Column("language_affinity", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_preference_profiles")
    op.drop_table("track_feedback")
