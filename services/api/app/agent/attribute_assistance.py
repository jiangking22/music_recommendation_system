"""Optional, validated model evidence; never mutates provider metadata or scores."""

import asyncio

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.listening import AttributeEvidence
from app.observability.events import emit


class AttributeAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    evidence: list[object] = Field(default_factory=list, max_length=60)


async def infer_attributes(provider, tracks, constraints, *, timeout=10, clues=None):
    assess = getattr(provider, 'assess_attributes', None)
    if assess is None or provider.name == 'local' or not tracks:
        return []
    selected = tracks[:20]
    identities = {t.canonical_key for t in selected}
    try:
        async with asyncio.timeout(timeout):
            result = AttributeAssessment.model_validate(await assess({
                'constraints': constraints.model_dump(),
                'source_snippets': clues or [],
                'tracks': [{'id': t.canonical_key, 'title': t.title, 'artist': t.artist.name,
                            'album': t.album.name if t.album else None,
                            'genres': t.genres[:5], 'tags': t.tags[:5]} for t in selected]}))
        evidence = []
        for raw in result.evidence:
            try:
                row = AttributeEvidence.model_validate(raw)
            except ValidationError:
                emit('attribute_assistance', status='error', code='invalid_row')
                continue
            if row.track_id in identities and row.origin == 'model' and row.source_url is None:
                evidence.append(row)
        return evidence
    except (httpx.HTTPError, ValidationError, ValueError, TypeError, TimeoutError):
        emit('attribute_assistance', status='error', code='invalid_or_unavailable')
        return []
