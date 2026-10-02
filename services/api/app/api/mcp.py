import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.infrastructure.workers import run_blocking
from app.mcp.tools import MCPRequest, MCPResponse, MusicTools, ToolsListResponse
from app.providers.registry import ProviderRegistry, get_provider_registry

router = APIRouter(prefix="/v1/mcp", tags=["mcp-style"])


@router.get("/tools", response_model=ToolsListResponse)
def list_tools(registry: Annotated[ProviderRegistry, Depends(get_provider_registry)]) -> dict:
    return {"tools": MusicTools(registry).list_tools()}


@router.post("/tools/call", response_model=MCPResponse)
async def call_tool(request: MCPRequest, registry: Annotated[ProviderRegistry, Depends(get_provider_registry)]):
    try:
        async with asyncio.timeout(15):
            return await run_blocking(lambda: MusicTools(registry).call(request))
    except ValidationError:
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "Invalid tool input."}})
    except TimeoutError:
        return JSONResponse(status_code=504, content={"error": {"code": "tool_timeout", "message": "Music tool timed out."}})
