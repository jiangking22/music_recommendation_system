"""Optional structured seed guidance; catalog verification remains deterministic."""

import asyncio
import logging
from typing import Annotated, Literal

import httpx
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.agent.providers import LLMProvider
from app.domain.discovery import SeedResolution, original_hint, recording_title
from app.domain.music import normalize_text
from app.observability.events import emit
from app.services.recommendation import DiscoverySearch, local_catalog

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ArtistName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class SeedIdentification(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["song", "theme", "unknown"]
    title: Title | None
    artist: ArtistName | None

    @model_validator(mode="after")
    def validate_kind(self):
        if self.kind == "song" and (self.title is None or self.artist is None):
            raise ValueError("Song identification needs title and artist")
        if self.kind != "song" and (self.title is not None or self.artist is not None):
            raise ValueError("Non-song identification must abstain from song metadata")
        return self


def needs_identification(state: DiscoverySearch) -> bool:
    if state.seed_artist or original_hint(state.seed):
        return False
    track = state.resolution.track
    # A catalog match to an explicit "title by artist" input already expresses artist choice.
    return not (track and normalize_text(state.seed) != recording_title(track.title))


def pending_resolution(state: DiscoverySearch) -> SeedResolution:
    choices = state.resolution.candidates
    return SeedResolution(None, choices, "ambiguous" if choices else "unresolved",
                          state.resolution.title_matches)


def explicit_theme(seed: str) -> bool:
    # Offline fallback is deliberately narrow: an unknown title is never fixture padding.
    vocabulary = {normalize_text(tag) for track in local_catalog() for tag in track.tags}
    vocabulary.update({"rock", "pop", "folk", "classical", "study", "focus", "relax",
                       "学习", "专注", "放松", "爵士", "摇滚", "古典", "安静"})
    tokens = normalize_text(seed).split()
    return bool(tokens) and all(token in vocabulary for token in tokens)


async def identify_seed(state: DiscoverySearch, provider: LLMProvider
                        ) -> tuple[SeedIdentification | None, bool, bool]:
    """Return suggestion, whether a model was attempted, and whether it was unavailable."""
    if not needs_identification(state) or provider.name == "local":
        return None, False, False
    context = {"task": "seed_identification", "message": state.seed,
               "candidates": [{"title": track.title[:200], "artist": track.artist.name[:200]}
                              for track in state.search.tracks[:25]]}
    try:
        async with asyncio.timeout(8):
            output = SeedIdentification.model_validate(await provider.identify_seed(context))
        return output, True, False
    except (TimeoutError, httpx.HTTPError, ValueError, TypeError, KeyError):
        emit("seed_identification", operation="identify_seed", status="error",
             code="llm_unavailable", level=logging.WARNING)
        return None, True, True
