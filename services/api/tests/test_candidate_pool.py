import asyncio

import pytest
from account_helpers import seed_account
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.core import Agent
from app.agent.providers import LocalLLMProvider
from app.agent.schemas import AgentRequest
from app.domain.music import (
    Artist,
    ProviderResult,
    ProviderSource,
    SearchResult,
    Track,
    canonical_key,
)
from app.repository.models import AccountConversation, Base


class Catalog:
    def __init__(self):
        self.calls = []
        self.tracks = [Track(title=f'Song {i}', artist=Artist(name=f'Artist {i}'),
            tags=['calm', 'vocal'], language='zh', canonical_key=canonical_key(f'Song {i}', f'Artist {i}'),
            source=ProviderSource(provider='itunes', provider_track_id=str(i))) for i in range(12)]

    def search_tracks(self, query, limit):
        self.calls.append(query)
        return SearchResult(tracks=self.tracks, sources={'itunes': ProviderResult(provider='itunes', tracks=self.tracks)})


@pytest.fixture
def setup(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "pool.db"}')
    Base.metadata.create_all(engine)
    seed_account(engine)
    registry = Catalog()
    yield Agent(engine, registry, LocalLLMProvider()), registry
    engine.dispose()


def chat(agent, message, conversation_id=None):
    return asyncio.run(agent.chat(AgentRequest(message=message, conversation_id=conversation_id,
        user_id='account_test', session_id='session_test')))


def test_enough_previous_candidates_are_reused_without_network(setup):
    agent, registry = setup
    first = chat(agent, '舒缓的歌')
    registry.calls.clear()
    result = chat(agent, '不要纯音乐', first.conversation_id)
    assert len(result.recommended_tracks) == 5
    assert registry.calls == []
    with Session(agent.engine) as db:
        pool = db.get(AccountConversation, str(first.conversation_id)).search_state
        assert len(pool['candidates']) >= 12


def test_more_songs_use_unseen_pool_and_expired_pool_searches_again(setup):
    agent, registry = setup
    first = chat(agent, '舒缓的歌')
    more = chat(agent, '再来几首', first.conversation_id)
    assert not {i.id for i in first.recommended_tracks} & {i.id for i in more.recommended_tracks}
    with Session(agent.engine) as db:
        row = db.get(AccountConversation, str(first.conversation_id))
        row.search_state = {**row.search_state, 'captured_at': 0}
        db.commit()
    registry.calls.clear()
    chat(agent, '偏华语一点', first.conversation_id)
    assert registry.calls


def test_fresh_theme_searches_and_user_requested_count_is_respected(setup):
    agent, registry = setup
    first = chat(agent, '舒缓的歌')
    registry.calls.clear()
    result = chat(agent, '推荐3首摇滚歌曲', first.conversation_id)
    assert len(result.recommended_tracks) == 3
    assert registry.calls
