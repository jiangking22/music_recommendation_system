"""Create anonymous device users and enable pgvector.

Revision ID: 0001_device_users
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_device_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "device_users",
        sa.Column("device_id", sa.String(length=128), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("device_users")
