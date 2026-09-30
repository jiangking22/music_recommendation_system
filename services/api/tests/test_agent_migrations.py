import io
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.infrastructure.config import Settings


def test_postgres_memory_and_vector_fixture_migrations_compile_offline(monkeypatch):
    from app.infrastructure import config

    settings = Settings(_env_file=None, database_url="postgresql+psycopg://music:placeholder@localhost/music",
                        redis_url="redis://localhost:6379/0")
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    root = Path(__file__).parents[1]
    output = io.StringIO()
    alembic = Config(str(root / "alembic.ini"), output_buffer=output)
    alembic.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(alembic, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE agent_conversations" in sql
    assert "CREATE TABLE agent_preference_summaries" in sql
    assert "CREATE TABLE music_knowledge_chunks" in sql
    assert "TYPE vector(16)" in sql
    assert sql.count("INSERT INTO music_knowledge_documents") == 4
    assert sql.count("INSERT INTO music_knowledge_chunks") == 4
    assert "周杰伦" in sql
    rollback = io.StringIO()
    alembic.output_buffer = rollback
    command.downgrade(alembic, "0005_music_knowledge:0003_embeddings", sql=True)
    assert "DROP TABLE music_knowledge_chunks" in rollback.getvalue()
    assert "DROP TABLE agent_conversations" in rollback.getvalue()
