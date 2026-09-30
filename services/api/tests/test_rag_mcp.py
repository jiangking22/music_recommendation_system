from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.mcp.tools import MCPRequest, MusicTools
from app.providers.registry import ProviderRegistry
from app.rag.repository import ingest_fixture, retrieve
from app.repository.models import Base, KnowledgeChunk, KnowledgeDocument


@pytest.fixture
def engine(tmp_path: Path):
    db = create_engine(f"sqlite+pysqlite:///{tmp_path / 'rag.db'}")
    Base.metadata.create_all(db)
    yield db
    db.dispose()


def test_fixture_ingest_is_idempotent_and_chunks_retrieve_all_categories(engine):
    with Session(engine) as session:
        ingest_fixture(session)
        ingest_fixture(session)
        assert session.scalar(select(func.count()).select_from(KnowledgeDocument)) == 4
        assert session.scalar(select(func.count()).select_from(KnowledgeChunk)) == 4
        for query, category in [("介绍周杰伦", "artist"), ("爵士乐 jazz", "genre"),
                                ("叶惠美 album", "album"), ("calm jazz study", "explanation")]:
            hits = retrieve(session, query, 2)
            assert hits[0].category == category
            assert hits[0].chunk_id and hits[0].document_id and hits[0].text
            assert len(hits) <= 2
        assert retrieve(session, "unrelated quantum elephants", 3) == []


def test_mcp_schema_and_call_do_not_need_agent_or_llm(engine):
    tools = MusicTools(ProviderRegistry([]))
    schema = tools.list_tools()[0]
    assert schema["name"] == "music_search"
    assert schema["inputSchema"]["additionalProperties"] is False
    assert schema["inputSchema"]["properties"]["limit"]["maximum"] == 25
    assert "tracks" in schema["outputSchema"]["properties"]
    result = tools.call(MCPRequest(name="music_search", arguments={"query": "jazz", "limit": 2}))
    assert result["isError"] is False
    assert len(result["structuredContent"]["tracks"]) == 2
    assert result["content"][0]["type"] == "text"
    with pytest.raises(ValidationError):
        tools.call(MCPRequest(name="music_search", arguments={"query": "jazz", "limit": 99}))
    with pytest.raises(ValidationError):
        MCPRequest(name="run_code", arguments={})
