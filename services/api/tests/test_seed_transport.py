import asyncio
import json

import httpx

from app.agent.providers import LocalLLMProvider, OpenAICompatibleProvider


def test_seed_identification_reuses_bounded_deepseek_json_transport():
    sent = []

    def respond(request):
        body = json.loads(request.content)
        sent.append(body)
        assert body["thinking"] == {"type": "disabled"}
        assert body["response_format"] == {"type": "json_object"}
        assert body["max_tokens"] == 1200
        assert "JSON" in body["messages"][0]["content"]
        data = json.loads(body["messages"][1]["content"])
        assert data["context"]["message"] == "Shared Title"
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "kind": "song", "title": "Shared Title", "artist": "Artist One"})}}]})

    provider = OpenAICompatibleProvider("https://api.deepseek.com/v1", "mock-key",
                                        "fixture-model", httpx.MockTransport(respond))
    result = asyncio.run(provider.identify_seed({"message": "Shared Title", "candidates": []}))
    assert result == {"kind": "song", "title": "Shared Title", "artist": "Artist One"}
    assert len(sent) == 1


def test_local_seed_identification_abstains_instead_of_inventing_facts():
    result = asyncio.run(LocalLLMProvider().identify_seed({"message": "Unknown Title"}))
    assert result == {"kind": "unknown", "title": None, "artist": None}
