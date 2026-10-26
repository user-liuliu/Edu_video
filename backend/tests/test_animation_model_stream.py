import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

import app.videos.model_stream as model_stream


@pytest.mark.asyncio
async def test_animation_response_retries_temporary_failures_three_times(monkeypatch):
    calls = []
    wait = AsyncMock()
    monkeypatch.setattr(asyncio, 'sleep', wait)

    async def send(http, url, headers, payload):
        calls.append(payload)
        if len(calls) < 4:
            return httpx.Response(502)
        return httpx.Response(200, json={'choices': [{'message': {'content': 'ok'}}]})

    monkeypatch.setattr(model_stream, '_animation_response_once', send)
    payload = {'messages': [{'role': 'user', 'content': 'frozen request'}]}

    response = await model_stream.animation_response(None, 'https://model.example', {}, payload)

    assert response.status_code == 200
    assert calls == [payload] * 4
    assert wait.await_count == 3


@pytest.mark.asyncio
async def test_animation_response_stops_after_three_temporary_retries(monkeypatch, caplog):
    calls = []
    wait = AsyncMock()
    monkeypatch.setattr(asyncio, 'sleep', wait)

    async def send(http, url, headers, payload):
        calls.append(payload)
        return httpx.Response(502)

    monkeypatch.setattr(model_stream, '_animation_response_once', send)

    with pytest.raises(ValueError, match='HTTP 502'):
        await model_stream.animation_response(None, 'https://model.example', {}, {'frozen': True})

    assert len(calls) == 4
    assert wait.await_count == 3
    assert 'retry=False retry_count=3' in caplog.text


@pytest.mark.asyncio
async def test_animation_response_does_not_retry_permanent_auth_failure(monkeypatch):
    calls = []
    wait = AsyncMock()
    monkeypatch.setattr(asyncio, 'sleep', wait)

    async def send(http, url, headers, payload):
        calls.append(payload)
        return httpx.Response(401)

    monkeypatch.setattr(model_stream, '_animation_response_once', send)

    with pytest.raises(ValueError, match='认证失败'):
        await model_stream.animation_response(None, 'https://model.example', {}, {'frozen': True})

    assert len(calls) == 1
    assert wait.await_count == 0


@pytest.mark.asyncio
async def test_slow_rate_limit_keeps_existing_retries_instead_of_splitting(monkeypatch):
    calls=[];wait=AsyncMock();clock=iter([0.,121.,122.,243.,244.,365.,366.,487.])
    monkeypatch.setattr(asyncio,'sleep',wait)
    monkeypatch.setattr(model_stream,'request_clock',lambda:next(clock))
    async def send(*args):calls.append(1);return httpx.Response(429)
    monkeypatch.setattr(model_stream,'_animation_response_once',send)
    with pytest.raises(model_stream.ModelCallError) as failure:
        await model_stream.animation_response(None,'https://test.invalid',{}, {},split_on_slow_failure=True)
    assert not isinstance(failure.value,model_stream.SplitAnimationRequest)
    assert len(calls)==4 and wait.await_count==3


@pytest.mark.asyncio
async def test_fast_transient_error_retries_whole_request_before_splitting(monkeypatch):
    calls=[];wait=AsyncMock()
    monkeypatch.setattr(asyncio,'sleep',wait)
    async def send(*args):
        calls.append(1)
        return httpx.Response(502) if len(calls)==1 else httpx.Response(200,json={})
    monkeypatch.setattr(model_stream,'_animation_response_once',send)
    result=await model_stream.animation_response(None,'https://test.invalid',{}, {},split_on_slow_failure=True)
    assert result.is_success and len(calls)==2 and wait.await_count==1
