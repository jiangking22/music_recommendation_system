from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.domain.embedding import DIMENSIONS, cosine_similarity
from app.repository.models import SongEmbedding
from app.repository.vector import Vector16


def store_song_embedding(session: Session, track_key: str, embedding: list[float]) -> None:
    if not 1 <= len(track_key) <= 512:
        raise ValueError("Invalid track key.")
    Vector16().bind_processor(None)(embedding)
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("INSERT INTO song_embeddings (track_key, embedding, updated_at) "
                             "VALUES (:key, CAST(:embedding AS vector), :updated_at) "
                             "ON CONFLICT (track_key) DO UPDATE SET embedding = EXCLUDED.embedding, "
                             "updated_at = EXCLUDED.updated_at"),
                        {"key": track_key, "embedding": Vector16().bind_processor(None)(embedding),
                         "updated_at": datetime.now(UTC)})
        session.commit()
        return
    insert = sqlite_insert
    columns = {"embedding": embedding, "updated_at": datetime.now(UTC)}
    statement = insert(SongEmbedding).values(track_key=track_key, **columns)
    statement = statement.on_conflict_do_update(index_elements=["track_key"], set_=columns)
    session.execute(statement)
    session.commit()


def similar_songs(session: Session, query: list[float], limit: int = 10) -> list[tuple[str, float]]:
    if len(query) != DIMENSIONS or not 1 <= limit <= 25:
        raise ValueError("Invalid vector or result limit.")
    if not any(query):
        return []
    vector_literal = Vector16().bind_processor(None)(query)
    if session.get_bind().dialect.name == "postgresql":
        rows = session.execute(text("SELECT track_key, 1 - (embedding <=> CAST(:query AS vector)) AS similarity "
                                    "FROM song_embeddings ORDER BY embedding <=> CAST(:query AS vector), track_key "
                                    "LIMIT :limit"), {"query": vector_literal, "limit": limit}).all()
        return [(key, round(score, 6)) for key, score in rows]
    rows = session.scalars(select(SongEmbedding).order_by(SongEmbedding.track_key).limit(1000)).all()
    scored = [(row.track_key, cosine_similarity(row.embedding, query)) for row in rows]
    return sorted(scored, key=lambda item: (-item[1], item[0]))[:limit]
