"""Bounded per-conversation canonical candidate memory, independent of model history."""

from time import time

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.discovery import rank_related
from app.domain.listening import AttributeEvidence
from app.domain.music import ProviderResult, Track
from app.domain.pipeline import dedup_key, deduplicate, rank


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

    def ranked(self, profile, constraints=None):
        tracks = [t for t in self.candidates if constraints is None or self.assess(t, constraints) == 'match']
        candidates = deduplicate(tracks)
        return (rank_related(candidates, self.seed_track, profile) if self.seed_track
                else rank(candidates, self.seed, profile))

    def assess(self, track, constraints):
        recordings = [t for t in self.candidates if t.canonical_key == track.canonical_key] or [track]
        source_evidence = [e for e in self.evidence if e.origin != 'model']
        states = []
        for attribute, wanted in constraints.model_dump().items():
            if wanted is None:
                continue
            single = constraints.model_copy(update={k: wanted if k == attribute else None
                for k in constraints.model_dump()})
            known = [single.assess(recording, source_evidence) for recording in recordings]
            states.append('mismatch' if 'mismatch' in known else 'match' if 'match' in known
                          else single.assess(track, self.evidence))
        return 'mismatch' if 'mismatch' in states else 'unknown' if 'unknown' in states else 'match'

    def merge(self, candidates, sources, *, retain_keys=None):
        incoming = [t for result in sources.values() for t in result.tracks[:25]]
        known_sources = {(t.source.provider, t.source.provider_track_id) for t in incoming}
        for item in candidates:
            if (item.track.source.provider, item.track.source.provider_track_id) not in known_sources:
                incoming.append(item.track)
        # Keep each provider's recording metadata intact, including its version/title.
        identities = {(t.source.provider, t.source.provider_track_id): t for t in self.candidates}
        identities.update({(t.source.provider, t.source.provider_track_id): t for t in incoming})
        new_keys = {dedup_key(t) for t in incoming}
        groups = {}
        for track in identities.values():
            groups.setdefault(dedup_key(track), []).append(track)
        # Protected matches survive; new recall displaces stale nonmatching candidates at capacity.
        keys = sorted(groups, key=lambda key: (key not in (retain_keys or set()), key not in new_keys))
        self.candidates = [t for key in keys for t in groups[key]][:150]
        for name, result in sources.items():
            self.sources[name] = result.model_copy(update={'tracks': result.tracks[:25]})

    def save(self, conversation):
        conversation.search_state = self.model_dump(mode='json')
