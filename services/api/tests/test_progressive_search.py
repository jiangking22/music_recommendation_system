import asyncio
from threading import Event

import httpx
import pytest
from pydantic import SecretStr
from test_candidate_pool import chat
from test_candidate_pool import setup as pool_setup

setup = pool_setup

from app.agent.core import Agent
from app.agent.providers import LocalLLMProvider
from app.agent.schemas import AgentRequest
from app.domain.music import ProviderResult, SearchResult, WebClue
from app.providers.brave import BraveSearch
from app.providers.registry import ProviderRegistry


def test_insufficient_pool_expands_different_queries_and_merges(setup):
    agent, registry = setup
    batches = [registry.tracks[:1], registry.tracks[1:3], registry.tracks[3:8]]

    def search(query, limit):
        registry.calls.append(query)
        tracks = batches[min(len(registry.calls) - 1, 2)]
        return SearchResult(tracks=tracks, sources={'itunes': ProviderResult(provider='itunes', tracks=tracks)})

    registry.search_tracks = search
    first = chat(agent, '不要纯音乐')
    assert len(first.recommended_tracks) == 5
    assert len(registry.calls) == len(set(registry.calls)) == 3
    assert first.search_report.expanded
    assert first.search_report.external_requests <= 24
    assert first.search_report.returned == 5


def test_enough_pool_stops_and_missing_web_key_is_reported(setup):
    agent, registry = setup
    first = chat(agent, '不要纯音乐')
    assert len(registry.calls) == 1
    assert first.search_report.web_search == 'not_configured'
    registry.calls.clear()
    result = chat(agent, '偏华语一点', first.conversation_id)
    assert len(result.recommended_tracks) == 5 and not registry.calls
    assert result.search_report.reused


def test_brave_exposes_bounded_canonical_snippets_and_preserves_links():
    def respond(request):
        assert request.headers['X-Subscription-Token'] == 'mock-key'
        return httpx.Response(200, json={'web': {'results': [
            {'title': '<b>Song</b>', 'url': 'https://music.163.com/song?id=1', 'description': '<b>vocal</b>'},
            {'title': 'Unsafe', 'url': 'https://127.0.0.1/a', 'description': 'secret'}]}})

    brave = BraveSearch(SecretStr('mock-key'), httpx.Client(transport=httpx.MockTransport(respond)))
    clues = brave.search('calm')
    assert len(clues) == 1 and clues[0].description == 'vocal'
    assert brave.links('calm') == [clues[0].url]


def test_cancellation_during_provider_call_does_not_schedule_another(setup):
    agent, registry = setup
    started, release = Event(), Event()

    def search(query, limit):
        registry.calls.append(query)
        started.set()
        release.wait(2)
        return SearchResult(tracks=[], sources={})

    registry.search_tracks = search

    async def cancel():
        task = asyncio.create_task(agent.chat(AgentRequest(message='不要纯音乐',
            user_id='account_test', session_id='session_test')))
        while not started.is_set():
            await asyncio.sleep(.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        await asyncio.sleep(.05)
    asyncio.run(cancel())
    assert len(registry.calls) == 1


def test_web_link_requires_matching_catalog_id_before_it_can_recommend(setup):
    base, registry = setup
    track = registry.tracks[0]
    track.source.provider = 'netease'

    class Catalog:
        name = 'netease'
        def search_tracks(self, query, limit):
            return ProviderResult(provider=self.name)
        def lookup_track(self, identifier):
            return ProviderResult(provider=self.name, tracks=[track])

    class Web:
        def search(self, query):
            return [WebClue(title='Song 0 Artist 0', url='https://music.163.com/song?id=0'),
                    WebClue(title='Invented', url='https://music.163.com/song?id=999')]

    agent = Agent(base.engine, ProviderRegistry([Catalog()], web_search=Web()), LocalLLMProvider())
    result = chat(agent, '不要纯音乐')
    assert len(result.recommended_tracks) == 1
    assert result.web_references and all(track.canonical_key in r.track_ids for r in result.web_references)
    assert all('999' not in r.url for r in result.web_references)
    assert result.search_report.web_search == 'used'


def test_deadline_returns_partial_and_does_not_start_later_operations(setup, monkeypatch):
    from app.services import progressive_search
    monkeypatch.setattr(progressive_search, 'SEARCH_SECONDS', .01)
    agent, registry = setup
    original = registry.search_tracks
    import time
    def slow(query, limit):
        time.sleep(.05)
        return original(query, limit)
    registry.search_tracks = slow
    result = chat(agent, '不要纯音乐')
    assert result.search_report.end_reason == 'deadline'
    assert result.search_report.external_requests == 1


def test_external_budget_counts_all_rounds_and_returns_only_qualifying_tracks(setup, monkeypatch):
    from app.services import progressive_search
    monkeypatch.setattr(progressive_search, 'MAX_OPERATIONS', 2)
    agent, registry = setup
    registry.tracks = []
    result = chat(agent, '不要纯音乐')
    assert result.search_report.end_reason == 'budget_exhausted'
    assert result.search_report.external_requests == 2
    assert not result.recommended_tracks
