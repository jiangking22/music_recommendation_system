from dataclasses import dataclass, field

from sqlalchemy import Engine

from app.agent.memory import Conversation, bounded_session
from app.agent.schemas import EmptyInput, KnowledgeInput, RecommendInput, ToolCall
from app.api.schemas import RecommendationItem
from app.providers.registry import ProviderRegistry
from app.rag.repository import retrieve
from app.repository.feedback import load_profile
from app.services.recommendation import recommend

TOOL_INPUTS = {
    "get_user_profile": EmptyInput,
    "recommend_tracks": RecommendInput,
    "search_music_knowledge": KnowledgeInput,
    "explain_recommendation": EmptyInput,
}
DESCRIPTIONS = {
    "get_user_profile": "Read anonymous musical preferences; accepts no device override.",
    "recommend_tracks": "Call deterministic recommender. Preserves scores and ordering.",
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
    device_id: str
    conversation: Conversation
    items: list[RecommendationItem] = field(default_factory=list)
    sources: dict = field(default_factory=dict)
    citations: list = field(default_factory=list)
    explanation: str = ""


def invoke_tool(call: ToolCall, context: ToolContext) -> dict:
    args = TOOL_INPUTS[call.name].model_validate(call.arguments)
    if call.name == "get_user_profile":
        with bounded_session(context.engine) as session:
            profile = load_profile(session, context.device_id)
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
            profile = load_profile(session, context.device_id)
        songs, search = recommend(args.seed, args.limit, context.registry, profile)
        context.conversation.last_seed = args.seed
        context.sources = search.sources
        context.items = [RecommendationItem(id=s.key, title=s.track.title, artist=s.track.artist.name,
                                             explanation=s.explanation, track=s.track, score=s.score,
                                             score_breakdown=s.score_breakdown, provenance=list(s.provenance))
                         for s in songs]
        # LLM receives only explanation material, never full upstream result payloads.
        return {"items": [{"title": i.title, "artist": i.artist, "explanation": i.explanation}
                          for i in context.items], "partial_sources": any(s.error for s in search.sources.values())}
    if call.name == "search_music_knowledge":
        with bounded_session(context.engine) as session:
            context.citations = retrieve(session, args.query, args.limit)
        return {"citations": [hit.model_dump() for hit in context.citations]}
    if not context.items:
        raise ValueError("explain_recommendation requires recommend_tracks first")
    context.explanation = "\n".join(f"{i.title}：{i.explanation}" for i in context.items)
    if context.citations:
        context.explanation += "\n一般聆听参考：" + context.citations[0].text
    return {"explanation": context.explanation}
