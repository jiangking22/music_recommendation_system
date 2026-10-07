from dataclasses import dataclass, field
from time import time

from sqlalchemy import Engine

from app.agent.intents import (
    is_followup,
    preference_updates,
    quoted_song,
    requested_count,
    theme_seed,
)
from app.agent.memory import Conversation, bounded_session
from app.agent.schemas import EmptyInput, KnowledgeInput, RecommendInput, ToolCall
from app.api.schemas import RecommendationItem
from app.domain.artist_names import enrich_track
from app.domain.listening import ListeningConstraints
from app.domain.pipeline import RankedTrack, rerank_diverse
from app.providers.registry import ProviderRegistry
from app.rag.repository import retrieve
from app.repository.feedback import load_profile
from app.services.candidate_pool import CandidatePool
from app.services.recommendation import discover

TOOL_INPUTS = {
    "get_user_profile": EmptyInput,
    "recommend_tracks": RecommendInput,
    "search_music_knowledge": KnowledgeInput,
    "explain_recommendation": EmptyInput,
}
DESCRIPTIONS = {
    "get_user_profile": "Read authenticated account musical preferences; accepts no device override.",
    "recommend_tracks": "Call deterministic recommender. Use theme for mood/tempo/genre, song for a recording. Optional language/vocal constraints require catalog metadata; never guess. Preserves ranking policy.",
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
    candidates: list[RankedTrack] = field(default_factory=list)
    pool: CandidatePool = field(default_factory=CandidatePool)
    more: bool = False
    requested: int = 5


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
        updates = preference_updates(context.message)
        refine = is_followup(context.message) or bool(updates) or args.refinement
        if refine and context.conversation.last_seed and not song:
            seed, intent = context.conversation.last_seed, context.conversation.last_intent
        constraints = (context.conversation.constraints if refine else ListeningConstraints()).model_copy(
            update=args.constraints.model_dump(exclude_unset=True) if args.constraints else {})
        constraints = constraints.model_copy(update=updates)
        context.conversation.constraints = constraints
        context.more = is_followup(context.message)
        context.requested = requested_count(context.message, args.limit)
        old = CandidatePool.load(context.conversation.search_state)
        pool = old if refine and old.fresh() and old.seed == seed else CandidatePool(
            captured_at=time(), seed=seed, intent=intent, shown=old.shown)
        context.pool = pool
        context.candidates = pool.ranked(profile)
        existing = [s for s in context.candidates if constraints.matches(s.track, pool.evidence)
                    and (not context.more or s.key not in pool.shown)]
        result = None
        if len(existing) < context.requested:
            result = discover(seed, context.requested, context.registry, profile, intent=intent, constraints=constraints)
            pool.merge(result.candidates, result.search.sources)
            pool.seed_track = result.seed_track
            pool.queries = list(dict.fromkeys([*pool.queries, seed]))[-60:]
            context.candidates = pool.ranked(profile)
        songs = rerank_diverse([s for s in context.candidates if constraints.matches(s.track, pool.evidence)
                               and (not context.more or s.key not in pool.shown)], context.requested)
        context.conversation.last_seed = seed
        context.conversation.last_intent = intent
        context.sources = pool.sources
        context.items = [RecommendationItem(id=s.key, title=s.track.title, artist=s.track.artist.name,
            explanation=s.explanation, track=enrich_track(s.track), score=s.score, score_breakdown=s.score_breakdown,
            provenance=list(s.provenance), attribute_evidence=[e for e in pool.evidence
                if e.track_id == s.track.canonical_key][:10]) for s in songs]
        pool.save(context.conversation)
        # LLM receives only explanation material, never full upstream result payloads.
        output = {"items": [{"title": i.title, "artist": i.artist, "explanation": i.explanation,
                             "language": i.track.language, "genres": i.track.genres[:5], "tags": i.track.tags[:5]}
                            for i in context.items],
                  "constraints": constraints.model_dump(),
                  "partial_sources": any(s.error for s in pool.sources.values())}
        context.conversation.recommendation_context = [
            {"title": i.title, "artist": i.artist, "explanation": i.explanation,
             "score_breakdown": i.score_breakdown} for i in context.items]
        if not context.items and intent == "theme" and any(constraints.model_dump().values()):
            output["empty_reason"] = "catalog_metadata_cannot_verify_constraints"
        elif not context.items:
            output.update(seed_status=result.seed_status if result else "unresolved", seed_candidates=[
                {"title": track.title, "artist": track.artist.name}
                for track in (result.seed_candidates[:5] if result else [])])
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
