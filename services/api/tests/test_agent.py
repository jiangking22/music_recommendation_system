import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.core import Agent, AgentError
from app.agent.memory import Memory, MemoryError
from app.agent.providers import LocalLLMProvider
from app.agent.schemas import ChatRequest
from app.domain.music import SearchResult
from app.repository.feedback import save_feedback
from app.repository.models import AgentConversation, AgentPreferenceSummary, Base
from app.services.recommendation import local_catalog


class EmptyRegistry:
    def search_tracks(self, query: str, limit: int) -> SearchResult:
        return SearchResult(tracks=[], sources={})


@pytest.fixture
def agent(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'agent.db'}")
    Base.metadata.create_all(engine)
    yield Agent(engine, EmptyRegistry(), LocalLLMProvider())
    engine.dispose()


def chat(agent, message, conversation_id=None, device_id="device_1234567890"):
    return asyncio.run(agent.chat(ChatRequest(message=message, device_id=device_id,
                                             conversation_id=conversation_id)))


def test_recommendation_tools_preserve_pipeline_order(agent):
    result = chat(agent, "推荐适合学习的歌")
    assert [call.name for call in result.used_tools] == [
        "get_user_profile", "recommend_tracks", "search_music_knowledge", "explain_recommendation"]
    assert all(call.status == "ok" for call in result.used_tools)
    assert result.recommended_tracks[0].title == "Blue Window"
    assert result.explanation
    assert "本地" in result.answer


def test_conversation_context_survives_new_agent_instance(agent):
    first = chat(agent, "推荐适合学习的歌")
    fresh = Agent(agent.engine, EmptyRegistry(), LocalLLMProvider())
    again = chat(fresh, "再来几首", first.conversation_id)
    assert again.recommended_tracks[0].id == first.recommended_tracks[0].id
    assert again.conversation_id == first.conversation_id
    with pytest.raises(AgentError, match="conversation_not_found"):
        chat(fresh, "再来几首", first.conversation_id, "device_9876543210")


def test_allowlist_and_call_budget_reject_invalid_model_plan(agent):
    class BadProvider(LocalLLMProvider):
        async def plan(self, context, tools):
            return {"calls": [{"name": "execute_code", "arguments": {}}]}

    agent.provider = BadProvider()
    with pytest.raises(AgentError, match="invalid_model_output"):
        chat(agent, "运行代码")

    class LoopProvider(LocalLLMProvider):
        async def plan(self, context, tools):
            return {"calls": [{"name": "get_user_profile", "arguments": {}}] * 5}

    agent.provider = LoopProvider()
    with pytest.raises(AgentError, match="invalid_model_output"):
        chat(agent, "推荐")


def test_timeout_is_bounded(agent):
    class SlowProvider(LocalLLMProvider):
        async def plan(self, context, tools):
            await asyncio.sleep(1)

    agent.provider = SlowProvider()
    agent.timeout_seconds = 0.02
    with pytest.raises(AgentError, match="agent_timeout"):
        chat(agent, "推荐")


def test_preferences_and_bounded_context_persist(agent):
    with Session(agent.engine) as session:
        save_feedback(session, "device_1234567890", local_catalog()[0], "like")
    result = chat(agent, "推荐适合学习的歌")
    for _ in range(7):
        result = chat(agent, "再来几首", result.conversation_id)
    with Session(agent.engine) as session:
        row = session.get(AgentConversation, str(result.conversation_id))
        summary = session.get(AgentPreferenceSummary, "device_1234567890")
        assert len(row.messages) == 12
        assert row.messages[-2]["content"] == "再来几首"
        assert "demo quartet" in summary.summary
        assert "jazz" in summary.summary
        assert row.last_seed == "calm jazz"


@pytest.mark.parametrize("calls", [
    [{"name": "recommend_tracks", "arguments": {"seed": "jazz", "limit": 100}}],
    [{"name": "get_user_profile", "arguments": {"device_id": "another_device"}}],
    [{"name": "get_user_profile", "arguments": {}}] * 2,
    [{"name": "explain_recommendation", "arguments": {}}],
])
def test_invalid_arguments_duplicates_and_order_fail_before_tools(agent, calls):
    class InvalidProvider(LocalLLMProvider):
        async def plan(self, context, tools):
            return {"calls": calls}

    agent.provider = InvalidProvider()
    with pytest.raises(AgentError, match="invalid_model_output"):
        chat(agent, "推荐")


def test_model_cannot_supply_tracks_or_ranking(agent):
    class InvalidAnswer(LocalLLMProvider):
        async def answer(self, context, results):
            return {"answer": "ignored", "recommended_tracks": ["invented track"]}

    agent.provider = InvalidAnswer()
    with pytest.raises(AgentError, match="invalid_model_output"):
        chat(agent, "推荐")


def test_concurrent_requests_are_bounded(agent):
    async def exercise():
        entered = 0
        all_entered = asyncio.Event()
        finish = asyncio.Event()

        class WaitingProvider(LocalLLMProvider):
            async def plan(self, context, tools):
                nonlocal entered
                entered += 1
                if entered == 4:
                    all_entered.set()
                await finish.wait()
                return await super().plan(context, tools)

        agent.provider = WaitingProvider()
        requests = [asyncio.create_task(agent.chat(ChatRequest(
            message="推荐", device_id=f"device_123456789{i}"))) for i in range(4)]
        try:
            await asyncio.wait_for(all_entered.wait(), 2)
            with pytest.raises(AgentError, match="agent_busy"):
                await agent.chat(ChatRequest(message="推荐", device_id="device_1234567894"))
        finally:
            finish.set()
            await asyncio.gather(*requests)

    asyncio.run(exercise())


def test_stale_memory_write_cannot_overwrite_a_completed_turn(agent):
    memory = Memory(agent.engine)
    request = ChatRequest(message="first turn", device_id="device_1234567890")
    first = memory.load(request)
    resumed_request = ChatRequest(message="stale turn", device_id=request.device_id,
                                  conversation_id=first.id)
    stale = memory.load(resumed_request)
    memory.save(request, first, "first answer")
    with pytest.raises(MemoryError, match="conversation_conflict"):
        memory.save(resumed_request, stale, "stale answer")
    current = memory.load(resumed_request)
    assert current.messages[-1]["content"] == "first answer"
    assert current.version == 1
