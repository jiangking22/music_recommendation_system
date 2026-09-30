import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.providers.registry import ProviderRegistry
from app.services.recommendation import recommend


def test_standard_mcp_client_initializes_lists_and_calls_real_stdio_server(tmp_path):
    async def run():
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "app.mcp.server", "--offline"],
            cwd=str(Path(__file__).resolve().parents[1]), env={**os.environ, "PYTHONUTF8": "1"})
        async with asyncio.timeout(20), stdio_client(params, errlog=errors) as (read, write), ClientSession(read, write) as client:
            initialized = await client.initialize()
            assert initialized.serverInfo.name == "Sonora Music"
            tools = (await client.list_tools()).tools
            assert {tool.name for tool in tools} == {"music_search", "recommend_tracks"}
            assert all(tool.annotations.readOnlyHint for tool in tools)
            assert all(tool.inputSchema and tool.outputSchema for tool in tools)
            search = await client.call_tool("music_search", {"query": "jazz", "limit": 2})
            assert not search.isError and len(search.structuredContent["tracks"]) == 2
            result = await client.call_tool("recommend_tracks", {"seed": "calm jazz", "limit": 3})
            assert not result.isError
            expected, _ = recommend("calm jazz", 3, ProviderRegistry([]))
            assert [item["id"] for item in result.structuredContent["items"]] == [song.key for song in expected]
            bad = await client.call_tool("recommend_tracks", {"seed": "x", "limit": 99})
            assert bad.isError
            unknown = await client.call_tool("run_shell", {})
            assert unknown.isError
    with (tmp_path / "mcp-events.log").open("w+", encoding="utf-8") as errors:
        asyncio.run(run())
        errors.seek(0)
        logs = [json.loads(line) for line in errors if line.strip()]
    assert {log["event"] for log in logs} >= {"mcp_tool", "recommendation"}
    identifiers = [(log["event"], log["request_id"]) for log in logs]
    assert len(identifiers) == len(set(identifiers))  # no duplicate root/SDK handlers
    assert all(log["request_id"] and log["trace_id"] for log in logs)
