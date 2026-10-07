import asyncio
import json

import httpx

from app.agent.attribute_assistance import infer_attributes
from app.agent.providers import LocalLLMProvider, OpenAICompatibleProvider
from app.domain.listening import ListeningConstraints
from app.domain.music import Artist, ProviderSource, Track


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


def test_invalid_model_rows_do_not_discard_other_valid_recording_evidence():
    track=Track(title='Song',artist=Artist(name='Artist'),canonical_key='song::artist',
        source=ProviderSource(provider='itunes',provider_track_id='1'))
    valid={'track_id':track.canonical_key,'attribute':'vocals','value':'vocal','origin':'model','basis':'Familiar recording.'}
    class Model:
        name='openai_compatible'
        async def assess_attributes(self,context):
            return {'evidence':[valid,{**valid,'value':'unsupported'},
                {**valid,'track_id':'invented::artist'}, {**valid,'origin':'provider'},
                {**valid,'source_url':'https://invented.example/song'}]}
    result=asyncio.run(infer_attributes(Model(),[track],ListeningConstraints(vocals='vocal')))
    assert len(result)==1 and result[0].value=='vocal'
