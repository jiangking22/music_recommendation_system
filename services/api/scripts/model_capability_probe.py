"""Manual, content-free native-search probe using only the configured model credential.

Run from the repository root with PYTHONPATH=services/api. This does not change configuration
or enable a capability. A positive probe still requires an adapter with canonical citations.
"""

import asyncio
import json
import ssl
from urllib.parse import urlsplit

import httpx

from app.infrastructure.config import get_settings
from app.providers.base import safe_https_url


def verified_search_evidence(payload: dict) -> bool:
    output = payload.get("output")
    if not isinstance(output, list):
        return False
    calls, citations = False, False
    for item in output[:128]:
        if not isinstance(item, dict):
            continue
        calls |= item.get("type") == "web_search_call" and item.get("status") == "completed"
        content = item.get("content", [])
        if item.get("type") != "message" or not isinstance(content, list):
            continue
        for part in content[:128]:
            if not isinstance(part, dict):
                continue
            annotations = part.get("annotations", [])
            if not isinstance(annotations, list):
                continue
            citations |= any(isinstance(cite, dict) and cite.get("type") == "url_citation"
                             and safe_https_url(cite.get("url")) is not None for cite in annotations[:128])
    return calls and citations


async def probe() -> dict:
    settings = get_settings()
    if (settings.llm_provider != "openai_compatible" or not settings.llm_api_key
            or urlsplit(settings.llm_base_url).hostname != "api.deepseek.com"):
        return {"native_search_verified": False, "reason": "protocol_not_verified", "adapter_enabled": False}
    try:
        async with (
            asyncio.timeout(30),
            httpx.AsyncClient(timeout=httpx.Timeout(25, connect=5), verify=ssl.create_default_context(),
                              trust_env=False, follow_redirects=False) as client,
            client.stream("POST", settings.llm_base_url.rstrip("/") + "/responses",
                    headers={"Authorization": "Bearer " + settings.llm_api_key.get_secret_value()},
                    json={"model": settings.llm_model, "max_output_tokens": 2048,
                          "reasoning": {"effort": "none"}, "tools": [{"type": "web_search"}],
                          "input": "请使用联网工具查询 DeepSeek 官方最近发布的模型信息，引用检索来源。无法实际联网时请说明。"}) as response,
        ):
            response.raise_for_status()
            body = bytearray()
            async for part in response.aiter_bytes():
                body.extend(part)
                if len(body) > 262144:
                    raise ValueError("response_too_large")
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise TypeError("invalid_response")
        verified = verified_search_evidence(payload)
        return {"native_search_verified": verified, "adapter_enabled": False,
                "reason": "adapter_integration_required" if verified else "no_verified_search_records"}
    except (httpx.HTTPError, ValueError, TypeError, TimeoutError):
        return {"native_search_verified": False, "adapter_enabled": False, "reason": "probe_failed"}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(probe())))
