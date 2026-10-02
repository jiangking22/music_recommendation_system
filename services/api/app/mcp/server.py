"""Minimal standard MCP stdio server. Run: python -m app.mcp.server [--offline]."""

import argparse
import asyncio
from time import perf_counter
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from app.api.schemas import (
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
)
from app.domain.music import SearchResult
from app.infrastructure.workers import run_blocking
from app.mcp.tools import MCPRequest, MusicTools
from app.observability.events import (
    configure_logging,
    emit,
    request_id,
    tool_correlation,
)
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.services.recommendation import recommend


def create_server(registry: ProviderRegistry) -> FastMCP:
    server = FastMCP("Sonora Music", log_level="CRITICAL")
    annotations = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)

    async def execute(name, operation):
        with tool_correlation():
            started, status = perf_counter(), "error"
            try:
                async with asyncio.timeout(15):
                    result = await run_blocking(operation)
                    status = "ok"
                    return result
            except Exception:  # noqa: BLE001 - sanitize all tool boundary failures.
                # SDK-generated tool errors must not echo raw upstream/validation content.
                raise ToolError("Music tool unavailable or invalid input.") from None
            finally:
                emit("mcp_tool", tool=name, status=status,
                     latency_ms=round((perf_counter() - started) * 1000, 3))

    @server.tool(annotations=annotations)
    async def music_search(query: Annotated[str, Field(min_length=1, max_length=120)],
                           limit: Annotated[int, Field(ge=1, le=25)] = 5) -> SearchResult:
        """Search canonical tracks with local fallback; unranked and read-only."""
        def search():
            result = MusicTools(registry).call(MCPRequest(name="music_search", arguments={
                "query": query, "limit": limit}))
            return SearchResult.model_validate(result["structuredContent"])
        return await execute("music_search", search)

    @server.tool(annotations=annotations)
    async def recommend_tracks(seed: Annotated[str, Field(min_length=1, max_length=120)],
                               limit: Annotated[int, Field(ge=1, le=10)] = 5) -> RecommendationResponse:
        """Read deterministic recommendations without device data; preserves pipeline order."""
        def recommendations():
            args = RecommendationRequest(seed=seed, limit=limit)
            songs, search = recommend(args.seed, args.limit, registry)
            return RecommendationResponse(request_id=request_id(), sources=search.sources, items=[
                RecommendationItem(id=s.key, title=s.track.title, artist=s.track.artist.name,
                    explanation=s.explanation, track=s.track, score=s.score,
                    score_breakdown=s.score_breakdown, provenance=list(s.provenance)) for s in songs])
        return await execute("recommend_tracks", recommendations)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use only the committed local catalog")
    args = parser.parse_args()
    configure_logging()
    create_server(ProviderRegistry([]) if args.offline else get_provider_registry()).run(transport="stdio")


if __name__ == "__main__":
    main()
