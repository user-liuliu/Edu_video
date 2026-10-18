import pytest

from app.model_configs.schemas import ResolvedConfig
from app.outline.model_client import chat_json
from app.purposes import Purpose


class FakeResponse:
    def __init__(self, *, ok: bool, status_code: int = 200, body: dict | None = None, text: str = ''):
        self.is_success = ok
        self.status_code = status_code
        self.content = text.encode()
        self._body = body or {}

    def json(self):
        return self._body


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def post(self, url, *, headers, json, timeout):
        self.calls.append(json)
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_chat_json_sends_json_schema_and_falls_back_when_provider_rejects_it():
    client = FakeClient([
        FakeResponse(ok=False, status_code=400, text='response_format json_schema is not supported'),
        FakeResponse(ok=True, body={'choices': [{'message': {'content': '{"items": []}'}}]}),
    ])
    schema = {
        'name': 'outline_review',
        'strict': True,
        'schema': {'type': 'object', 'required': ['items'], 'properties': {'items': {'type': 'array'}}},
    }

    result = await chat_json(
        ResolvedConfig(Purpose.review_llm, 'https://model.example/v1', 'secret', 'reviewer', {}),
        [{'role': 'user', 'content': '审核'}],
        response_schema=schema,
        retries=0,
        client=client,
    )

    assert result == {'items': []}
    assert client.calls[0]['response_format'] == {'type': 'json_schema', 'json_schema': schema}
    assert client.calls[1]['response_format'] == {'type': 'json_object'}
