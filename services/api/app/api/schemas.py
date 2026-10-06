from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

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


class DiscoveryRequest(RecommendationRequest):
    language: Literal["en", "zh"] = "en"
    seed_artist: str | None = Field(default=None, min_length=1, max_length=200)
    seed_storefront: Literal["TW", "HK"] | None = None
    resolution_id: str | None = Field(default=None,
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

    @model_validator(mode="after")
    def require_confirmed_artist(self):
        if self.seed_storefront and not self.seed_artist:
            raise ValueError("A verification storefront requires an explicit artist")
        return self

    @field_validator("seed_artist", mode="before")
    @classmethod
    def strip_artist(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class DiscoveryResponse(RecommendationResponse):
    seed_track: Track | None = None
    seed_candidates: list[Track] = Field(default_factory=list, max_length=5)
    seed_status: Literal["matched", "ambiguous", "unresolved"]
    seed_storefront: Literal["TW", "HK"] | None = None
    seed_resolution_source: Literal["verified_hint", "user", "model", "catalog", "none"] = "none"
    guidance: str = Field(max_length=2000)
    guidance_provider: Literal["local", "openai_compatible"]
    guidance_status: Literal["ready", "unavailable"]
    search_report: "SearchReport | None" = None
    resolution_id: str | None = None
    candidate_resolutions: dict[str, str] = Field(default_factory=dict)


class SongIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    artist: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class OriginalIdentificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    seed: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    language: Literal["en", "zh"] = "en"
    rejected_candidates: list[SongIdentity] = Field(min_length=1, max_length=5)


class OriginalIdentificationResponse(BaseModel):
    request_id: str
    status: Literal["matched", "unverified", "unknown"]
    suggestion: SongIdentity | None = None
    matched_track: Track | None = None
    verified_storefront: Literal["TW", "HK"] | None = None
    sources: dict[str, ProviderResult] = Field(default_factory=dict)
    search_report: "SearchReport | None" = None
    resolution_id: str | None = None


class SearchAttempt(BaseModel):
    platform: str
    region: str | None = None
    stage: Literal["memory", "common", "expanded", "web", "manual", "confirmation", "recall"]
    operation: Literal["search", "lookup", "web"] = "search"
    status: Literal["hit", "no_results", "error", "not_configured", "not_executed", "unavailable", "auth_required"]
    result_count: int = 0
    error_code: str | None = None


class SearchReport(BaseModel):
    attempts: list[SearchAttempt] = Field(default_factory=list, max_length=60)
    end_reason: Literal["matched", "ambiguous", "not_found", "budget_exhausted", "deadline",
                        "unsupported_platform", "unavailable", "partial_failure"]
    external_requests: int = Field(ge=0, le=24)
    incomplete: bool = False


class RecordingResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    artist: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    language: Literal["en", "zh"] = "en"
    platform: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)] | None = None
    song_url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)] | None = None


class ResolvedChoice(BaseModel):
    track: Track
    resolution_id: str


class RecordingResolveResponse(BaseModel):
    request_id: str
    status: Literal["matched", "ambiguous", "not_found", "unsupported_platform", "unavailable", "incomplete"]
    matched_track: Track | None = None
    resolution_id: str | None = None
    candidates: list[ResolvedChoice] = Field(default_factory=list, max_length=5)
    search_report: SearchReport
    sources: dict[str, ProviderResult] = Field(default_factory=dict)


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


class ProfileAffinity(BaseModel):
    name: str
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    weight: float


class RecentFeedback(BaseModel):
    track_key: str
    artist: str
    artist_display_name: str | None = Field(default=None, min_length=1, max_length=200)
    value: Literal["like", "dislike"]


class ProfileResponse(BaseModel):
    artists: list[ProfileAffinity]
    genres: list[ProfileAffinity]
    tags: list[ProfileAffinity]
    languages: list[ProfileAffinity]
    recent_feedback: list[RecentFeedback]


class ProvidersResponse(BaseModel):
    providers: list[ProviderCapabilities]


class ProvidersHealthResponse(BaseModel):
    providers: dict[str, ProviderHealth]


class TrackSearchResponse(SearchResult):
    pass
