"""Account-owned preferences and session-isolated assistant context."""
import sqlalchemy as sa
from alembic import op

from app.repository.vector import Vector16

revision = "0008_account_preferences"
down_revision = "0007_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("account_feedback",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("accounts.user_id"), primary_key=True),
        sa.Column("track_key", sa.String(512), primary_key=True),
        sa.Column("value", sa.String(8), nullable=False),
        sa.Column("artist", sa.String(200), nullable=False),
        sa.Column("genres", sa.JSON(), nullable=False), sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("language", sa.String(32)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("value IN ('like', 'dislike')", name="ck_account_feedback_value"))
    op.create_table("account_profiles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("accounts.user_id"), primary_key=True),
        sa.Column("artist_affinity", sa.JSON(), nullable=False), sa.Column("genre_affinity", sa.JSON(), nullable=False),
        sa.Column("tag_affinity", sa.JSON(), nullable=False), sa.Column("language_affinity", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector16()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("account_conversations",
        sa.Column("conversation_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("accounts.user_id"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("login_sessions.session_id"), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False), sa.Column("last_seed", sa.String(120)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_account_conversations_user_id", "account_conversations", ["user_id"])
    op.create_index("ix_account_conversations_session_id", "account_conversations", ["session_id"])
    op.create_table("account_preference_summaries",
        sa.Column("session_id", sa.String(36), sa.ForeignKey("login_sessions.session_id"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("accounts.user_id"), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_account_preference_summaries_user_id", "account_preference_summaries", ["user_id"])


def downgrade() -> None:
    op.drop_table("account_preference_summaries")
    op.drop_table("account_conversations")
    op.drop_table("account_profiles")
    op.drop_table("account_feedback")
