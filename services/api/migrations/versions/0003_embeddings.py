"""Store local song and preference vectors in pgvector.

Revision ID: 0003_embeddings
Revises: 0002_feedback_profiles
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_embeddings"
down_revision = "0002_feedback_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_preference_profiles", sa.Column("embedding", sa.Text(), nullable=True))
    op.execute("ALTER TABLE user_preference_profiles ALTER COLUMN embedding TYPE vector(16) USING embedding::vector(16)")
    op.create_table("song_embeddings",
                    sa.Column("track_key", sa.String(length=512), primary_key=True),
                    sa.Column("embedding", sa.Text(), nullable=False),
                    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.execute("ALTER TABLE song_embeddings ALTER COLUMN embedding TYPE vector(16) USING embedding::vector(16)")


def downgrade() -> None:
    op.drop_table("song_embeddings")
    op.drop_column("user_preference_profiles", "embedding")
