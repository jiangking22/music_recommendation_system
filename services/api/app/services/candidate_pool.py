"""Bounded per-conversation canonical candidate memory, independent of model history."""

from time import time

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.discovery import rank_related
from app.domain.listening import AttributeEvidence
from app.domain.music import ProviderResult, Track
from app.domain.pipeline import deduplicate, rank


class CandidatePool(BaseModel):
    model_config = ConfigDict(extra='forbid')
    captured_at: float = 0
    seed: str = Field(default='', max_length=120)
    intent: str = Field(default='auto', max_length=10)
    candidates: list[Track] = Field(default_factory=list, max_length=150)
    evidence: list[AttributeEvidence] = Field(default_factory=list, max_length=450)
    queries: list[str] = Field(default_factory=list, max_length=60)
    shown: list[str] = Field(default_factory=list, max_length=500)
    sources: dict[str, ProviderResult] = Field(default_factory=dict)
    seed_track: Track | None = None

    @classmethod
    def load(cls, state):
        try:
            return cls.model_validate(state)
        except (ValidationError, TypeError):
            return cls()

    def fresh(self):
        return 0 <= time() - self.captured_at < 1800

    def ranked(self, profile):
        candidates = deduplicate(self.candidates)
        return (rank_related(candidates, self.seed_track, profile) if self.seed_track
                else rank(candidates, self.seed, profile))

    def merge(self, candidates, sources):
        tracks = list(self.candidates)
        for item in candidates:
            tracks.extend(item.track.model_copy(update={'source': source}) for source in item.provenance)
        # A richer metadata representative wins; retained provider identities preserve provenance.
        merged = deduplicate(tracks)
        self.candidates = [c.track.model_copy(update={'source': source})
                           for c in merged for source in c.provenance][:150]
        for name, result in sources.items():
            self.sources[name] = result.model_copy(update={'tracks': result.tracks[:25]})

    def save(self, conversation):
        conversation.search_state = self.model_dump(mode='json')
