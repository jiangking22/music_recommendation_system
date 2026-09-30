"""Versioned small knowledge fixture, document chunks and pgvector retrieval."""

import json

import sqlalchemy as sa
from alembic import op

from app.rag.repository import fixture_rows

revision = "0005_music_knowledge"
down_revision = "0004_agent_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    documents = op.create_table("music_knowledge_documents",
                                sa.Column("document_id", sa.String(80), primary_key=True),
                                sa.Column("title", sa.String(200), nullable=False),
                                sa.Column("category", sa.String(20), nullable=False),
                                sa.Column("content", sa.Text(), nullable=False),
                                sa.CheckConstraint("category IN ('artist', 'genre', 'album', 'explanation')",
                                                   name="ck_knowledge_category"))
    chunks = op.create_table("music_knowledge_chunks",
                             sa.Column("chunk_id", sa.String(100), primary_key=True),
                             sa.Column("document_id", sa.String(80),
                                       sa.ForeignKey("music_knowledge_documents.document_id"), nullable=False),
                             sa.Column("text", sa.String(600), nullable=False),
                             sa.Column("keywords", sa.Text(), nullable=False),
                             sa.Column("embedding", sa.Text(), nullable=False))
    op.create_index("ix_music_knowledge_chunks_document_id", "music_knowledge_chunks", ["document_id"])
    document_rows, chunk_rows = fixture_rows()
    op.bulk_insert(documents, document_rows)
    op.bulk_insert(chunks, [{**row, "keywords": json.dumps(row["keywords"], ensure_ascii=False),
                            "embedding": json.dumps(row["embedding"])} for row in chunk_rows])
    op.execute("ALTER TABLE music_knowledge_chunks ALTER COLUMN keywords TYPE json USING keywords::json")
    op.execute("ALTER TABLE music_knowledge_chunks ALTER COLUMN embedding TYPE vector(16) USING embedding::vector(16)")


def downgrade() -> None:
    op.drop_table("music_knowledge_chunks")
    op.drop_table("music_knowledge_documents")
