from dataclasses import dataclass, field

from sqlalchemy import Engine

from app.agent.intents import is_followup, quoted_song, theme_seed
from app.agent.memory import Conversation, bounded_session
from app.agent.schemas import EmptyInput, KnowledgeInput, RecommendInput, ToolCall
from app.api.schemas import RecommendationItem
from app.providers.registry import ProviderRegistry
from app.rag.repository import retrieve
from app.repository.feedback import load_profile
from app.services.recommendation import discover

TOOL_INPUTS = {
    "get_user_profile": EmptyInput,
    "recommend_tracks": RecommendInput,
    "search_music_knowledge": KnowledgeInput,
    "explain_recommendation": EmptyInput,
}
DESCRIPTIONS = {
    "get_user_profile": "Read authenticated account musical preferences; accepts no device override.",
    "recommend_tracks": "Call deterministic recommender. Use theme intent for mood/tempo/genre, song for a recording. Preserves scores and ordering.",
    "search_music_knowledge": "Retrieve small local music knowledge with citations.",
    "explain_recommendation": "Explain already returned tracks using measured factors and knowledge.",
}


def tool_schemas() -> list[dict]:
    return [{"name": name, "description": DESCRIPTIONS[name], "inputSchema": model.model_json_schema()}
            for name, model in TOOL_INPUTS.items()]


@dataclass
class ToolContext:
    engine: Engine
    registry: ProviderRegistry
    user_id: str
    conversation: Conversation
    message: str = ""
    items: list[RecommendationItem] = field(default_factory=list)
    sources: dict = field(default_factory=dict)
    citations: list = field(default_factory=list)
    explanation: str = ""


def invoke_tool(call: ToolCall, context: ToolContext) -> dict:
    args = TOOL_INPUTS[call.name].model_validate(call.arguments)
    if call.name == "get_user_profile":
        with bounded_session(context.engine) as session:
            profile = load_profile(session, context.user_id)
        parts = []
        for label, values in (("歌手", profile.artist_affinity), ("流派", profile.genre_affinity),
                              ("标签", profile.tag_affinity), ("语言", profile.language_affinity)):
            preferred = sorted((k for k, v in values.items() if v > 0), key=lambda k: (-values[k], k))[:5]
            if preferred:
                parts.append(f"{label}：{', '.join(preferred)}")
        context.conversation.preference_summary = ("；".join(parts) or "尚无音乐偏好反馈。")[:1000]
        return {"summary": context.conversation.preference_summary}
    if call.name == "recommend_tracks":
        with bounded_session(context.engine) as session:
            profile = load_profile(session, context.user_id)
        theme = theme_seed(context.message)
        seed, intent = (theme, "theme") if theme else (args.seed, args.intent)
        song = quoted_song(context.message)
        if song:
            seed, intent = song, "song"
        if is_followup(context.message) and context.conversation.last_seed:
            seed, intent = context.conversation.last_seed, context.conversation.last_intent
        result = discover(seed, args.limit, context.registry, profile, intent=intent)
        songs, search = result.items, result.search
        context.conversation.last_seed = seed
        context.conversation.last_intent = intent
        context.sources = search.sources
        context.items = [RecommendationItem(id=s.key, title=s.track.title, artist=s.track.artist.name,
                                             explanation=s.explanation, track=s.track, score=s.score,
                                             score_breakdown=s.score_breakdown, provenance=list(s.provenance))
                         for s in songs]
        # LLM receives only explanation material, never full upstream result payloads.
        output = {"items": [{"title": i.title, "artist": i.artist, "explanation": i.explanation}
                            for i in context.items],
                  "partial_sources": any(s.error for s in search.sources.values())}
        if not context.items:
            output.update(seed_status=result.seed_status, seed_candidates=[
                {"title": track.title, "artist": track.artist.name}
                for track in result.seed_candidates[:5]])
        return output
    if call.name == "search_music_knowledge":
        with bounded_session(context.engine) as session:
            context.citations = retrieve(session, args.query, args.limit)
        return {"citations": [hit.model_dump() for hit in context.citations]}
    if not context.items:
        return {"explanation": "尚无可解释的推荐曲目；请根据推荐工具返回的候选确认歌手或补充需求。"}
    context.explanation = "\n".join(f"{i.title}：{i.explanation}" for i in context.items)
    if context.citations:
        context.explanation += "\n一般聆听参考：" + context.citations[0].text
    return {"explanation": context.explanation}
