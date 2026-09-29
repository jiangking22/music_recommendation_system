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


class ProvidersResponse(BaseModel):
    providers: list[ProviderCapabilities]


class ProvidersHealthResponse(BaseModel):
    providers: dict[str, ProviderHealth]


class TrackSearchResponse(SearchResult):
    pass
