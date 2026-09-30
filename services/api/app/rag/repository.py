import hashlib
import json
import math
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.embedding import cosine_similarity
from app.domain.music import normalize_text
from app.rag.schemas import Citation
from app.repository.models import KnowledgeChunk, KnowledgeDocument
from app.repository.vector import Vector16

FIXTURE = Path(__file__).parent / "fixtures" / "music_v1.json"


class DocumentFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(pattern="^(artist|genre|album|explanation)$")
    content: str = Field(min_length=1, max_length=2400)
    keywords: list[str] = Field(min_length=1, max_length=20)


def tokens(value: str) -> set[str]:
    normalized = normalize_text(value)
    terms = set(re.findall(r"[a-z0-9]+", normalized))
    for phrase in re.findall(r"[\u4e00-\u9fff]+", normalized):
        terms.update(phrase[i:i + 2] for i in range(max(0, len(phrase) - 1)))
    return terms - {"the", "a", "an", "介绍", "推荐", "适合"}


def embed_knowledge(value: str) -> list[float]:
    vector = [0.0] * 16
    for term in sorted(tokens(value)):
        digest = hashlib.sha256(term.encode()).digest()
        vector[int.from_bytes(digest[:4], "big") % 16] += 1 if digest[4] % 2 == 0 else -1
    norm = math.sqrt(sum(v * v for v in vector))
    return [round(v / norm, 8) for v in vector] if norm else vector


def fixture_rows() -> tuple[list[dict], list[dict]]:
    values = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if not isinstance(values, list) or len(values) > 20:
        raise ValueError("Knowledge fixture exceeds limits")
    documents, chunks = [], []
    for value in values:
        item = DocumentFixture.model_validate(value)
        if any(not k.strip() or len(k) > 64 for k in item.keywords):
            raise ValueError("Invalid fixture keywords")
        documents.append(item.model_dump(exclude={"keywords"}))
        for index, start in enumerate(range(0, len(item.content), 600)):
            chunks.append({"chunk_id": f"{item.document_id}:{index}", "document_id": item.document_id,
                           "text": item.content[start:start + 600], "keywords": item.keywords,
                           "embedding": embed_knowledge(item.title + " " + " ".join(item.keywords))})
    return documents, chunks


def ingest_fixture(session: Session) -> None:
    documents, chunks = fixture_rows()
    for row in documents:
        session.merge(KnowledgeDocument(**row))
    session.flush()
    for row in chunks:
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("INSERT INTO music_knowledge_chunks (chunk_id, document_id, text, keywords, embedding) "
                                 "VALUES (:chunk_id, :document_id, :text, CAST(:keywords AS json), CAST(:embedding AS vector)) "
                                 "ON CONFLICT (chunk_id) DO UPDATE SET text=EXCLUDED.text, keywords=EXCLUDED.keywords, "
                                 "embedding=EXCLUDED.embedding"),
                            {**row, "keywords": json.dumps(row["keywords"]),
                             "embedding": Vector16().bind_processor(None)(row["embedding"])})
        else:
            session.merge(KnowledgeChunk(**row))
    session.commit()


def retrieve(session: Session, query: str, limit: int = 3) -> list[Citation]:
    if not query.strip() or len(query) > 120 or not 1 <= limit <= 5:
        raise ValueError("Invalid knowledge query")
    query_vector = embed_knowledge(query)
    if not any(query_vector):
        return []
    if session.get_bind().dialect.name == "postgresql":
        rows = session.execute(text(
            "SELECT c.chunk_id, c.document_id, c.text, c.keywords, d.title, d.category, "
            "1 - (c.embedding <=> CAST(:query AS vector)) AS similarity "
            "FROM music_knowledge_chunks c JOIN music_knowledge_documents d USING (document_id) "
            "ORDER BY c.embedding <=> CAST(:query AS vector), c.chunk_id LIMIT 50"),
            {"query": Vector16().bind_processor(None)(query_vector)}).mappings().all()
    else:
        pairs = session.execute(select(KnowledgeChunk, KnowledgeDocument)
                                .join(KnowledgeDocument).order_by(KnowledgeChunk.chunk_id).limit(50)).all()
        rows = [{"chunk_id": c.chunk_id, "document_id": c.document_id, "text": c.text,
                 "keywords": c.keywords, "title": d.title, "category": d.category,
                 "similarity": cosine_similarity(c.embedding, query_vector)} for c, d in pairs]
    hits = []
    for row in rows:
        # Tiny hash vectors can collide. Require lexical evidence before using a
        # vector hit as grounding, rather than answering unrelated questions.
        overlap = tokens(query) & tokens(" ".join(row["keywords"]))
        if not overlap:
            continue
        score = round(len(overlap) + 0.1 * float(row["similarity"]), 6)
        hits.append(Citation(document_id=row["document_id"], title=row["title"], category=row["category"],
                             chunk_id=row["chunk_id"], text=row["text"], score=score))
    return sorted(hits, key=lambda hit: (-hit.score, hit.chunk_id))[:limit]
