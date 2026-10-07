import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def canonical_key(title: str, artist: str) -> str:
    def normalize(value: str) -> str:
        value = unicodedata.normalize("NFKC", value).casefold()
        return re.sub(r"\s+", " ", value).strip()

    return f"{normalize(title)}::{normalize(artist)}"


class Artist(BaseModel):
    name: str = Field(min_length=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    provider_artist_id: str | None = None


class Album(BaseModel):
    name: str = Field(min_length=1)
    provider_album_id: str | None = None


class ProviderSource(BaseModel):
    provider: str
    provider_track_id: str
    external_url: str | None = None


class Track(BaseModel):
    title: str = Field(min_length=1)
    artist: Artist
    album: Album | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    artwork_url: str | None = None
    source: ProviderSource
    language: str | None = None
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    popularity: float | None = Field(default=None, ge=0, le=100)
    canonical_key: str


class ProviderCapabilities(BaseModel):
    provider: str
    search_tracks: bool
    search_artist_tracks: bool
    stability: Literal["documented", "unverified"]
    max_results: int = Field(ge=1, le=25)


class ProviderError(BaseModel):
    code: Literal["timeout", "upstream_error", "invalid_payload", "unavailable", "auth_required"]
    message: str


class ProviderResult(BaseModel):
    provider: str
    tracks: list[Track] = Field(default_factory=list)
    error: ProviderError | None = None


class ProviderHealth(BaseModel):
    status: Literal["unknown", "available", "degraded"]
    last_error: ProviderError | None = None


class SearchResult(BaseModel):
    tracks: list[Track]
    sources: dict[str, ProviderResult]


class WebClue(BaseModel):
    title: str = Field(max_length=200)
    url: str = Field(min_length=1, max_length=2000)
    description: str = Field(default='', max_length=700)
