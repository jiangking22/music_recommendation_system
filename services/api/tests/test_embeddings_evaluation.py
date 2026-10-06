from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.embedding import cosine_similarity, embed_song, embed_user
from app.domain.evaluation import evaluate
from app.domain.music import Artist, ProviderSource, Track
from app.domain.profile import PreferenceProfile
from app.repository.embedding import similar_songs, store_song_embedding
from app.repository.models import Base


def test_vector_reflection_retains_dimensions_for_migration_drift():
    from app.repository.vector import Vector16

    assert Vector16().get_col_spec() == "vector(16)"
    assert Vector16(8).get_col_spec() == "vector(8)"


def test_local_embedding_is_deterministic_and_has_similarity() -> None:
    song = Track(title="Blue Window", artist=Artist(name="Demo Quartet"),
                 source=ProviderSource(provider="fixture", provider_track_id="blue"),
                 canonical_key="blue window::demo quartet", genres=["jazz"])
    first = embed_song(song)
    assert first == embed_song(song)
    assert len(first) == 16
    assert cosine_similarity(first, first) == 1.0
    user = embed_user(PreferenceProfile(genre_affinity={"jazz": 1.0}))
    assert len(user) == 16
    assert any(value != 0 for value in user)


def test_song_embedding_persists_and_sqlite_similarity_fallback_works(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'vectors.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        store_song_embedding(session, "blue", [1.0] + [0.0] * 15)
        store_song_embedding(session, "red", [0.0, 1.0] + [0.0] * 14)
        result = similar_songs(session, [1.0] + [0.0] * 15, limit=2)
        empty = similar_songs(session, [0.0] * 16, limit=2)
    assert [row[0] for row in result] == ["blue", "red"]
    assert result[0][1] > result[1][1]
    assert empty == []
    engine.dispose()


def test_versioned_offline_evaluation_is_reproducible() -> None:
    first = evaluate()
    assert first == evaluate()
    assert first["version"] == "evaluation_v1"
    assert first["relevance"] > 0
    assert first["personalization_effect"] > 0
    assert first["diversity"] > 0
    assert first["coverage"] > 0
