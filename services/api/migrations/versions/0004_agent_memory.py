"""Bounded conversation context and durable anonymous preference summaries."""

import sqlalchemy as sa
from alembic import op

revision = "0004_agent_memory"
down_revision = "0003_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("agent_conversations",
                    sa.Column("conversation_id", sa.String(36), primary_key=True),
                    sa.Column("device_id", sa.String(128), sa.ForeignKey("device_users.device_id"), nullable=False),
                    sa.Column("messages", sa.JSON(), nullable=False),
                    sa.Column("last_seed", sa.String(120)),
                    sa.Column("version", sa.Integer(), nullable=False),
                    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_agent_conversations_device_id", "agent_conversations", ["device_id"])
    op.create_table("agent_preference_summaries",
                    sa.Column("device_id", sa.String(128), sa.ForeignKey("device_users.device_id"), primary_key=True),
                    sa.Column("summary", sa.String(1000), nullable=False),
                    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    op.drop_table("agent_preference_summaries")
    op.drop_table("agent_conversations")
