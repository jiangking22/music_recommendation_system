import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.music import SearchResult
from app.domain.pipeline import deduplicate
from app.providers.registry import ProviderRegistry
from app.services.recommendation import local_catalog


class MusicSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    limit: int = Field(default=5, ge=1, le=25)


class MCPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: Literal["music_search"]
    arguments: dict


class ToolDefinition(BaseModel):
    name: Literal["music_search"]
    description: str
    inputSchema: dict
    outputSchema: dict
    annotations: dict[str, bool]


class ToolsListResponse(BaseModel):
    tools: list[ToolDefinition]


class TextContent(BaseModel):
    type: Literal["text"]
    text: str


class MCPResponse(BaseModel):
    content: list[TextContent]
    structuredContent: SearchResult
    isError: bool


class MusicTools:
    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry

    def list_tools(self) -> list[dict]:
        return [{"name": "music_search", "description": "Read canonical music search, with local fallback; unranked.",
                 "inputSchema": MusicSearchInput.model_json_schema(), "outputSchema": SearchResult.model_json_schema(),
                 "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True}}]

    def call(self, request: MCPRequest) -> dict:
        args = MusicSearchInput.model_validate(request.arguments)
        search = self.registry.search_tracks(args.query, args.limit)
        candidates = search.tracks
        if not candidates:
            candidates = [track for track in local_catalog() if args.query.casefold() in
                          (track.title + " " + track.artist.name + " " + " ".join(track.tags)).casefold()]
        result = SearchResult(tracks=[c.track for c in deduplicate(candidates)][:args.limit], sources=search.sources)
        payload = result.model_dump(mode="json")
        return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                "structuredContent": payload, "isError": False}
