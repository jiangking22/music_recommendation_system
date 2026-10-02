from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.api.schemas import RecommendationItem
from app.domain.device import DEVICE_ID_PATTERN
from app.domain.music import ProviderResult
from app.rag.schemas import Citation

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ToolName = Literal["recommend_tracks", "get_user_profile", "search_music_knowledge", "explain_recommendation"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ChatRequest(StrictModel):
    message: Text
    device_id: str = Field(min_length=16, max_length=128, pattern=DEVICE_ID_PATTERN)
    conversation_id: UUID | None = Field(default=None, strict=False)


class EmptyInput(StrictModel):
    pass


class RecommendInput(StrictModel):
    seed: Query
    limit: int = Field(default=5, ge=1, le=10)


class KnowledgeInput(StrictModel):
    query: Query
    limit: int = Field(default=3, ge=1, le=5)


class ToolCall(StrictModel):
    name: ToolName
    arguments: dict = Field(default_factory=dict)


class Plan(StrictModel):
    calls: list[ToolCall] = Field(min_length=1, max_length=4)


class Answer(StrictModel):
    answer: Text


class ToolTrace(StrictModel):
    name: ToolName
    status: Literal["ok", "error"]


class ChatResponse(BaseModel):
    conversation_id: UUID
    answer: str
    recommended_tracks: list[RecommendationItem]
    used_tools: list[ToolTrace]
    explanation: str
    citations: list[Citation] = Field(default_factory=list)
    sources: dict[str, ProviderResult] = Field(default_factory=dict)
    provider: str
