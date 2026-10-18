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

# Exercise real HTTPX responses; only the external transport and waits are replaced.
import httpx
from unittest.mock import AsyncMock
import app.outline.model_client as model_client


@pytest.fixture
def reviewer_config():
    return ResolvedConfig(Purpose.review_llm, 'https://model.example/v1', 'private-test-key', 'reviewer', {})


@pytest.fixture
def retry_wait(monkeypatch):
    import asyncio
    wait = AsyncMock()
    monkeypatch.setattr(asyncio, 'sleep', wait)
    return wait


def success_response():
    return httpx.Response(200, json={'choices': [{'message': {'content': '{"items": []}'}}]})


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [408, 429, 500, 502, 503, 504])
async def test_temporary_http_failure_retries_original_payload(status, reviewer_config, retry_wait):
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(status, json={'error': {'message': 'temporary'}}) if len(requests) == 1 else success_response()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await chat_json(reviewer_config, [{'role': 'user', 'content': '审核'}], client=client)
    assert result == {'items': []}
    assert len(requests) == 2
    assert requests[0].content == requests[1].content
    assert retry_wait.await_count == 1
    assert 0 < retry_wait.await_args.args[0] <= 30


@pytest.mark.asyncio
@pytest.mark.parametrize(('status', 'message'), [(401, '认证失败'), (403, '权限'), (404, '模型名称'), (400, '参数'), (422, '参数')])
async def test_permanent_http_failure_is_classified_without_retry(status, message, reviewer_config, retry_wait, caplog):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(status, json={'error': {'message': 'private-test-key private teacher prompt'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError) as error:
            await chat_json(reviewer_config, [{'role': 'user', 'content': 'private teacher prompt'}], client=client, response_schema={'name': 'review', 'schema': {}})
    assert message in str(error.value)
    assert str(status) in str(error.value)
    assert len(calls) == 1
    assert retry_wait.await_count == 0
    assert f'status={status}' in caplog.text
    assert 'purpose=review_llm' in caplog.text
    for private in ('private-test-key', 'private teacher prompt', 'https://model.example'):
        assert private not in str(error.value) + caplog.text


@pytest.mark.asyncio
async def test_transient_retry_exhaustion_is_bounded(reviewer_config, retry_wait, caplog):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(503, text='private-test-key')
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError, match='503'):
            await chat_json(reviewer_config, [], retries=2, client=client)
    assert len(calls) == 3
    assert retry_wait.await_count == 2
    assert 'private-test-key' not in caplog.text


@pytest.mark.asyncio
async def test_quota_error_does_not_retry_as_rate_limit(reviewer_config, retry_wait):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(429, json={'error': {'code': 'insufficient_quota', 'message': 'secret'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError, match='额度'):
            await chat_json(reviewer_config, [], client=client)
    assert len(calls) == 1
    assert retry_wait.await_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(('header', 'expected'), [('7', 7), ('3600', 30), ('bad-value', None)])
async def test_retry_after_is_respected_with_bounded_wait(header, expected, reviewer_config, retry_wait):
    responses = [httpx.Response(429, headers={'Retry-After': header}), success_response()]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: responses.pop(0))) as client:
        assert await chat_json(reviewer_config, [], client=client) == {'items': []}
    delay = retry_wait.await_args.args[0]
    assert 0 < delay <= 30
    if expected is not None:
        assert delay == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('exception', [httpx.ConnectError, httpx.ReadTimeout])
async def test_network_failure_can_recover(exception, reviewer_config, retry_wait):
    calls = []
    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            raise exception('private-test-key', request=request)
        return success_response()
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await chat_json(reviewer_config, [], client=client) == {'items': []}
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_timeout_exhaustion_has_safe_error(reviewer_config, retry_wait, caplog):
    calls = []
    def respond(request):
        calls.append(request)
        raise httpx.ReadTimeout('private-test-key', request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError, match='超时') as error:
            await chat_json(reviewer_config, [], retries=1, client=client)
    assert len(calls) == 2
    assert 'private-test-key' not in str(error.value) + caplog.text


@pytest.mark.asyncio
async def test_schema_fallback_does_not_consume_transient_retry(reviewer_config, retry_wait):
    responses = [httpx.Response(503), httpx.Response(400, json={'error': {'message': 'json_schema response_format not supported'}}), success_response()]
    payloads = []
    import json
    def respond(request):
        payloads.append(json.loads(request.content))
        return responses.pop(0)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await chat_json(reviewer_config, [], retries=1, client=client, response_schema={'name': 'review', 'schema': {}})
    assert result == {'items': []}
    assert [x['response_format']['type'] for x in payloads] == ['json_schema', 'json_schema', 'json_object']


@pytest.mark.asyncio
async def test_invalid_json_after_fallback_cannot_silently_return_none(reviewer_config, retry_wait):
    responses = [httpx.Response(400, text='json_schema is not supported'), httpx.Response(200, json={'choices': [{'message': {'content': 'invalid'}}]})]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: responses.pop(0))) as client:
        with pytest.raises(ValueError, match='JSON'):
            await chat_json(reviewer_config, [], retries=0, client=client, response_schema={'name': 'review', 'schema': {}})


@pytest.mark.asyncio
async def test_writer_can_retry_transport_without_retrying_invalid_json(reviewer_config, retry_wait):
    responses = [httpx.Response(503), httpx.Response(200, json={'choices': [{'message': {'content': 'invalid'}}]})]
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: responses.pop(0))) as client:
        with pytest.raises(ValueError, match='JSON'):
            await chat_json(reviewer_config, [], retries=0, request_retries=1, client=client)
    assert len(responses) == 0
