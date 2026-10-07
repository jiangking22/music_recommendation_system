from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.api.schemas import RecommendationItem, SearchAttempt
from app.domain.listening import ListeningConstraints
from app.domain.music import ProviderResult
from app.rag.schemas import Citation

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ToolName = Literal["recommend_tracks", "get_user_profile", "search_music_knowledge", "explain_recommendation"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ChatRequest(StrictModel):
    message: Text
    conversation_id: UUID | None = Field(default=None, strict=False)
    deep_thinking: bool = False


class AgentRequest(ChatRequest):
    """Internal request only; ownership never comes from public JSON."""
    user_id: str
    session_id: str


class EmptyInput(StrictModel):
    pass


class RecommendInput(StrictModel):
    seed: Query
    limit: int = Field(default=5, ge=1, le=10)
    intent: Literal["auto", "theme", "song"] = "auto"
    constraints: ListeningConstraints | None = None
    refinement: bool = False
    queries: list[Query] = Field(default_factory=list, max_length=3)


class KnowledgeInput(StrictModel):
    query: Query
    limit: int = Field(default=3, ge=1, le=5)


class ToolCall(StrictModel):
    name: ToolName
    arguments: dict = Field(default_factory=dict)


class Plan(StrictModel):
    calls: list[ToolCall] = Field(min_length=0, max_length=4)


class Answer(StrictModel):
    answer: Text


class ToolTrace(StrictModel):
    name: ToolName
    status: Literal["ok", "error"]


class NativeSearchState(StrictModel):
    status: Literal["unavailable"] = "unavailable"
    reason: Literal["unsupported", "unverified", "local_mode"]


class ModelCapabilities(StrictModel):
    provider: str
    supports_deep_thinking: bool
    native_search: NativeSearchState
    music_catalog_search: Literal['available', 'unavailable'] = 'unavailable'
    web_search: Literal['available', 'not_configured'] = 'not_configured'


class AgentSearchReport(StrictModel):
    requested: int = Field(ge=1, le=10)
    returned: int = Field(ge=0, le=10)
    reused: bool = False
    expanded: bool = False
    external_requests: int = Field(default=0, ge=0, le=24)
    web_search: Literal['not_configured', 'not_needed', 'used', 'error'] = 'not_configured'
    end_reason: Literal['enough', 'insufficient_matches', 'insufficient_evidence', 'upstream_failure',
                        'deadline', 'budget_exhausted', 'ambiguous'] = 'insufficient_matches'
    attempts: list[SearchAttempt] = Field(default_factory=list, max_length=24)


class WebReference(StrictModel):
    title: str = Field(max_length=200)
    url: str = Field(max_length=2000)
    track_ids: list[str] = Field(max_length=25)


class ChatResponse(BaseModel):
    conversation_id: UUID
    answer: str
    recommended_tracks: list[RecommendationItem]
    used_tools: list[ToolTrace]
    explanation: str
    citations: list[Citation] = Field(default_factory=list)
    sources: dict[str, ProviderResult] = Field(default_factory=dict)
    provider: str
    fallback_reason: Literal["llm_unavailable"] | None = None
    thinking_mode: Literal["basic", "standard", "deep"] = "standard"
    thinking_unavailable_reason: Literal["unsupported", "llm_unavailable"] | None = None
    native_search: NativeSearchState = Field(default_factory=lambda: NativeSearchState(reason="unverified"))
    search_report: AgentSearchReport | None = None
    web_references: list[WebReference] = Field(default_factory=list, max_length=10)
