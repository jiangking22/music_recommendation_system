from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.domain.music import (
    ProviderCapabilities,
    ProviderHealth,
    ProviderResult,
    ProviderSource,
    SearchResult,
    Track,
)


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(BaseModel):
    status: str


class DeviceResponse(BaseModel):
    deviceId: str


class RecommendationRequest(BaseModel):
    seed: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=3, ge=1, le=10)

    @field_validator("seed", mode="before")
    @classmethod
    def strip_seed(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RecommendationItem(BaseModel):
    id: str
    title: str
    artist: str
    explanation: str
    track: Track
    score: float
    score_breakdown: dict[str, float]
    provenance: list[ProviderSource]


class RecommendationResponse(BaseModel):
    request_id: str
    items: list[RecommendationItem]
    sources: dict[str, ProviderResult]


class FeedbackRequest(BaseModel):
    track: Track
    value: Literal["like", "dislike"]

    @field_validator("track")
    @classmethod
    def bound_track(cls, track: Track) -> Track:
        if (not track.title.strip() or not track.artist.name.strip()
                or not track.source.provider.strip() or not track.source.provider_track_id.strip()
                or not track.canonical_key.strip()
                or len(track.title) > 200 or len(track.artist.name) > 200
                or len(track.source.provider) > 100 or len(track.source.provider_track_id) > 200
                or len(track.canonical_key) > 512 or len(track.language or "") > 32
                or len(track.genres) > 20 or len(track.tags) > 20
                or any(len(value) > 64 for value in track.genres + track.tags)
                or len(track.source.external_url or "") > 2048 or len(track.artwork_url or "") > 2048):
            raise ValueError("Track metadata exceeds limits.")
        return track


class FeedbackResponse(BaseModel):
    track_key: str
    value: Literal["like", "dislike"]


class ProvidersResponse(BaseModel):
    providers: list[ProviderCapabilities]


class ProvidersHealthResponse(BaseModel):
    providers: dict[str, ProviderHealth]


class TrackSearchResponse(SearchResult):
    pass
