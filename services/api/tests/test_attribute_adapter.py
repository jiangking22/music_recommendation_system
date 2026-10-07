import asyncio
import json

import httpx

from app.agent.providers import LocalLLMProvider, OpenAICompatibleProvider


def test_attribute_assistance_is_structured_and_not_a_new_playlist():
    def respond(request):
        body = json.loads(request.content)
        assert body['response_format'] == {'type': 'json_object'}
        data = json.loads(body['messages'][1]['content'])
        assert data['context']['task'] == 'attributes'
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({
            'evidence': [{'track_id': 'song::artist', 'attribute': 'vocals', 'value': 'vocal',
                          'origin': 'model', 'basis': 'Familiar vocal recording.'}]})}}]})

    provider = OpenAICompatibleProvider('https://model.example/v1', 'mock-key', 'fixture',
                                        httpx.MockTransport(respond))
    result = asyncio.run(provider.assess_attributes({'tracks': [{'id': 'song::artist'}]}))
    assert result['evidence'][0]['value'] == 'vocal'
    assert asyncio.run(LocalLLMProvider().assess_attributes({})) == {'evidence': []}
