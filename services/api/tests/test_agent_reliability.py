from account_helpers import seed_account

"""Model outages retain deterministic music results and honest source status."""

import asyncio

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.core import Agent, AgentError
from app.agent.providers import LocalLLMProvider
from app.agent.schemas import AgentRequest
from app.domain.music import (
    Artist,
    ProviderError,
    ProviderResult,
    ProviderSource,
    SearchResult,
    Track,
    canonical_key,
)
from app.domain.pipeline import deduplicate, rank, rerank_diverse
from app.domain.profile import PreferenceProfile
from app.repository.models import AccountConversation, Base
from app.services.recommendation import discover, local_catalog


def song(title, artist, tags=()):
    return Track(title=title, artist=Artist(name=artist), tags=list(tags),
                 source=ProviderSource(provider="itunes", provider_track_id=f"{title}-{artist}"),
                 canonical_key=canonical_key(title, artist))


class CatalogRegistry:
    def __init__(self, tracks=(), partial=False):
        self.tracks = list(tracks)
        self.partial = partial
        self.calls = []

    def search_tracks(self, query, limit):
        self.calls.append((query, limit))
        tracks = self.tracks[:limit]
        sources = {"itunes": ProviderResult(provider="itunes", tracks=tracks)}
        if self.partial:
            sources["netease"] = ProviderResult(provider="netease", error=ProviderError(
                code="timeout", message="Source unavailable"))
        return SearchResult(tracks=tracks, sources=sources)


class PlanUnavailable(LocalLLMProvider):
    name = "openai_compatible"

    async def plan(self, context, tools):
        raise httpx.ConnectError("certificate verification failed")


class AnswerUnavailable(LocalLLMProvider):
    name = "openai_compatible"

    def __init__(self, seed="calm jazz", intent=None):
        self.seed, self.intent = seed, intent

    async def plan(self, context, tools):
        arguments = {"seed": self.seed, "limit": 5}
        if self.intent is not None:
            arguments["intent"] = self.intent
        return {"calls": [
            {"name": "recommend_tracks", "arguments": arguments},
            {"name": "explain_recommendation", "arguments": {}},
        ]}

    async def answer(self, context, results):
        request = httpx.Request("POST", "https://model.invalid/chat/completions")
        response = httpx.Response(503, request=request)
        raise httpx.HTTPStatusError("model unavailable", request=request, response=response)


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'reliability.db'}")
    Base.metadata.create_all(engine)
    seed_account(engine)
    yield engine
    engine.dispose()


def chat(agent, message, conversation_id=None):
    return asyncio.run(agent.chat(AgentRequest(
        message=message, user_id="account_test", session_id="session_test", conversation_id=conversation_id)))


@pytest.mark.parametrize("message", ["emo的歌", "缓慢的歌"])
def test_plan_connection_failure_returns_labeled_basic_recommendations(engine, message):
    response = chat(Agent(engine, CatalogRegistry(), PlanUnavailable()), message)
    assert response.recommended_tracks
    assert response.provider == "local"
    assert response.fallback_reason == "llm_unavailable"
    assert "本地" in response.answer
    assert all(trace.status == "ok" for trace in response.used_tools)


def test_answer_failure_preserves_exact_ranked_order_without_repeating_search(engine):
    tracks = [song("Quiet River", "First", ("calm", "jazz")),
              song("Night Air", "Second", ("jazz",))]
    registry = CatalogRegistry(tracks, partial=True)
    expected = rerank_diverse(rank(deduplicate(tracks + local_catalog()),
                                  "calm jazz", PreferenceProfile()), 5)
    response = chat(Agent(engine, registry, AnswerUnavailable()), "推荐适合学习的歌")
    assert [item.id for item in response.recommended_tracks] == [item.key for item in expected]
    assert [item.score for item in response.recommended_tracks] == [item.score for item in expected]
    assert len(registry.calls) == 1
    assert response.sources["netease"].error.code == "timeout"
    assert response.sources["itunes"].tracks == tracks
    assert response.provider == "local"
    assert response.fallback_reason == "llm_unavailable"


@pytest.mark.parametrize("message,title", [("emo的歌", "emo"), ("缓慢的歌", "slow")])
def test_short_mood_requests_survive_multiple_artists_with_same_title(engine, message, title):
    tracks = [song(title, "First", (title,)), song(title, "Second", (title,))]
    registry = CatalogRegistry(tracks)
    response = chat(Agent(engine, registry, LocalLLMProvider()), message)
    assert response.recommended_tracks
    assert any(item.track.source.provider == "itunes" for item in response.recommended_tracks)
    assert len(registry.calls) == 1
    assert response.provider == "local"
    assert response.fallback_reason is None


@pytest.mark.parametrize("seed", ["emo", "slow"])
def test_explicit_theme_intent_does_not_enter_same_title_ambiguity(seed):
    tracks = [song(seed, "First", (seed,)), song(seed, "Second", (seed,))]
    registry = CatalogRegistry(tracks)
    result = discover(seed, 5, registry, intent="theme")
    expected = rerank_diverse(rank(deduplicate(tracks + local_catalog()),
                                  seed, PreferenceProfile()), 5)
    assert [item.key for item in result.items] == [item.key for item in expected]
    assert result.seed_track is None
    assert result.seed_status != "ambiguous"
    assert len(registry.calls) == 1


def test_song_ambiguity_fallback_requests_artist_without_fixture_padding(engine):
    tracks = [song("Shared Title", "First"), song("Shared Title", "Second")]
    registry = CatalogRegistry(tracks)
    provider = AnswerUnavailable("Shared Title", intent="song")
    response = chat(Agent(engine, registry, provider), "推荐与 Shared Title 类似的歌")
    assert response.recommended_tracks == []
    assert "歌手" in response.answer
    assert any(word in response.answer for word in ("确认", "哪位", "选择"))
    assert "First" in response.answer and "Second" in response.answer
    assert response.provider == "local"
    assert response.fallback_reason == "llm_unavailable"
    assert len(registry.calls) == 1


def test_followup_after_fallback_reuses_conversation_and_listening_theme(engine):
    registry = CatalogRegistry([song("emo", "First", ("emo",)),
                                song("emo", "Second", ("emo",))])
    agent = Agent(engine, registry, PlanUnavailable())
    first = chat(agent, "emo的歌")
    second = chat(agent, "再来几首", first.conversation_id)
    assert second.conversation_id == first.conversation_id
    assert second.recommended_tracks
    assert [item.id for item in second.recommended_tracks] == [
        item.id for item in first.recommended_tracks]
    assert second.fallback_reason == "llm_unavailable"
    assert len(registry.calls) == 2
    assert registry.calls[0][0] == registry.calls[1][0]
    with Session(engine) as session:
        row = session.get(AccountConversation, str(first.conversation_id))
        assert [message["role"] for message in row.messages] == [
            "user", "assistant", "user", "assistant"]
        assert row.messages[-2]["content"] == "再来几首"


def test_malformed_remote_output_remains_an_error_instead_of_fallback(engine):
    class MalformedProvider(PlanUnavailable):
        async def plan(self, context, tools):
            return {"calls": [{"name": "execute_code", "arguments": {}}]}

    registry = CatalogRegistry()
    with pytest.raises(AgentError, match="invalid_model_output"):
        chat(Agent(engine, registry, MalformedProvider()), "emo的歌")
    assert registry.calls == []


def test_explicit_mood_overrides_model_song_seed_with_the_same_title(engine):
    registry = CatalogRegistry([song("emo", "First"), song("emo", "Second")])
    response = chat(Agent(engine, registry, AnswerUnavailable("emo", "song")), "emo的歌")
    assert response.recommended_tracks
    assert registry.calls == [("emo", 15)]


def test_quoted_theme_word_is_a_song_and_followup_preserves_ambiguity(engine):
    registry = CatalogRegistry([song("emo", "First"), song("emo", "Second")])
    agent = Agent(engine, registry, PlanUnavailable())
    first = chat(agent, "推荐《emo》")
    assert first.recommended_tracks == []
    assert "First" in first.answer and "Second" in first.answer
    second = chat(agent, "再来几首", first.conversation_id)
    assert second.recommended_tracks == []
    assert "歌手" in second.answer
    assert registry.calls == [("emo", 15), ("emo", 15)]


@pytest.mark.parametrize("message", ["介绍emo音乐", "slow dancing in the dark", "安静 周杰伦"])
def test_theme_word_inside_a_question_or_title_is_not_an_explicit_theme(message):
    from app.agent.intents import theme_seed

    assert theme_seed(message) is None


def test_successful_theme_tool_does_not_claim_song_resolution_failed(engine):
    class InspectAnswer(LocalLLMProvider):
        async def answer(self, context, results):
            output = next(result["output"] for result in results if result["name"] == "recommend_tracks")
            assert output["items"]
            assert "seed_status" not in output
            return await super().answer(context, results)

    assert chat(Agent(engine, CatalogRegistry(), InspectAnswer()), "缓慢的歌").recommended_tracks
