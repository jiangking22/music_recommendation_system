"""Optional, validated model evidence; never mutates provider metadata or scores."""

import asyncio

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.tools import ToolContext
from app.api.schemas import RecommendationItem
from app.domain.artist_names import enrich_track
from app.domain.listening import AttributeEvidence
from app.domain.pipeline import rerank_diverse
from app.observability.events import emit


class AttributeAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    evidence: list[AttributeEvidence] = Field(default_factory=list, max_length=60)


async def infer_attributes(provider, tracks, constraints, *, timeout=10):
    assess = getattr(provider, 'assess_attributes', None)
    if assess is None or provider.name == 'local' or not tracks:
        return []
    selected = tracks[:20]
    identities = {t.canonical_key for t in selected}
    try:
        async with asyncio.timeout(timeout):
            result = AttributeAssessment.model_validate(await assess({
                'constraints': constraints.model_dump(),
                'tracks': [{'id': t.canonical_key, 'title': t.title, 'artist': t.artist.name,
                            'album': t.album.name if t.album else None,
                            'genres': t.genres[:5], 'tags': t.tags[:5]} for t in selected]}))
        return [row for row in result.evidence if row.track_id in identities
                and row.origin == 'model' and row.source_url is None]
    except (httpx.HTTPError, ValidationError, ValueError, TypeError, TimeoutError):
        emit('attribute_assistance', status='error', code='invalid_or_unavailable')
        return []


async def invoke_recommendation(call, context: ToolContext, provider, output):
    constraints = context.conversation.constraints
    unknown = [item.track for item in context.candidates if item.track.source.provider != 'fixture'
               and constraints.assess(item.track, context.pool.evidence) == 'unknown']
    evidence = await infer_attributes(provider, unknown, constraints)
    if evidence:
        context.pool.evidence = (context.pool.evidence + evidence)[-450:]
        songs = rerank_diverse([item for item in context.candidates
                               if constraints.matches(item.track, context.pool.evidence)
                               and (not context.more or item.key not in context.pool.shown)],
                              context.requested)
        context.items = [RecommendationItem(id=s.key, title=s.track.title, artist=s.track.artist.name,
            explanation=s.explanation, track=enrich_track(s.track), score=s.score, score_breakdown=s.score_breakdown,
            provenance=list(s.provenance), attribute_evidence=[e for e in context.pool.evidence
                if e.track_id == s.track.canonical_key][:10]) for s in songs]
        context.conversation.recommendation_context = [
            {'title': i.title, 'artist': i.artist, 'explanation': i.explanation,
             'score_breakdown': i.score_breakdown} for i in context.items]
        output['items'] = [{'title': i.title, 'artist': i.artist, 'explanation': i.explanation,
                           'attribute_evidence': [e.model_dump() for e in i.attribute_evidence]} for i in context.items]
        if context.items:
            output.pop('empty_reason', None)
    context.pool.shown = list(dict.fromkeys([*context.pool.shown, *(i.id for i in context.items)]))[-500:]
    context.pool.save(context.conversation)
    return output
