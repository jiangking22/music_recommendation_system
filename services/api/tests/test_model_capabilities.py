import importlib.util
from pathlib import Path

import pytest

from app.agent.providers import (
    LocalLLMProvider,
    OpenAICompatibleProvider,
    model_capabilities,
)

spec = importlib.util.spec_from_file_location("probe", Path(__file__).parents[1] / "scripts/model_capability_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.mark.parametrize("provider,reason,thinking", [
    (LocalLLMProvider(), "local_mode", False),
    (OpenAICompatibleProvider("https://api.deepseek.com/v1", "placeholder", "deepseek-flash"), "unsupported", True),
    (OpenAICompatibleProvider("https://api.deepseek.com.evil.example", "placeholder", "any"), "unverified", False),
    (OpenAICompatibleProvider("https://model.example", "placeholder", "any"), "unverified", False),
])
def test_only_adapter_verified_capabilities_are_advertised(provider, reason, thinking):
    capability = model_capabilities(provider)
    assert capability.supports_deep_thinking is thinking
    assert capability.native_search.status == "unavailable"
    assert capability.native_search.reason == reason
    assert "placeholder" not in capability.model_dump_json()


def test_prose_links_and_model_claims_are_not_search_evidence():
    message = {"type": "message", "content": [{"type": "output_text", "text": "I searched https://example.com",
               "annotations": [{"type": "url_citation", "url": "https://example.com/source"}]}]}
    assert not probe.verified_search_evidence({"output": [message]})
    call = {"type": "web_search_call", "status": "completed"}
    assert probe.verified_search_evidence({"output": [call, message]})
    message["content"][0]["annotations"][0]["url"] = "http://127.0.0.1/private"
    assert not probe.verified_search_evidence({"output": [call, message]})
    assert not probe.verified_search_evidence({"output": [None, {"content": None}]})
