import base64
import json
from types import SimpleNamespace

import httpx
import pytest

from app.studio.render_client import StudioRenderError, StudioRenderer
from app.studio.render_contract import InspectRequest, Issue, RenderRequest

DIGEST = '0' * 64
INSPECT_RESULT = {'issues': [{'code': 'overlap', 'segment': 's1', 't': 1.0, 'element': 'h1', 'message': '文字重叠'}],
                  'frames': [], 'states': {}}


def inspect_request():
    return InspectRequest(runtime_digest=DIGEST, html='<html></html>', duration=2.0, frame_times=[0.5], checks=['bounds'])


def render_request():
    # model_construct skips the WAV validation, the client only forwards the payload
    return RenderRequest.model_construct(runtime_digest=DIGEST, html='<html></html>', audio_base64='AAAA',
                                         duration=2.0, width=1280, height=720, fps=30)


def make(handler, url='http://renderer:8080/', sleeps=None):
    async def fake_sleep(seconds):
        if sleeps is not None:
            sleeps.append(seconds)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return StudioRenderer(SimpleNamespace(renderer_url=url), http, sleep=fake_sleep)


async def test_inspect_posts_to_studio_inspect_and_parses_result():
    seen = {}

    def handler(request):
        seen['url'] = str(request.url)
        seen['body'] = json.loads(request.content)
        return httpx.Response(200, json=INSPECT_RESULT)

    result = await make(handler).inspect(inspect_request())
    assert seen['url'] == 'http://renderer:8080/studio/inspect'
    assert seen['body']['runtime_digest'] == DIGEST and seen['body']['checks'] == ['bounds']
    assert result.issues == [Issue(code='overlap', segment='s1', t=1.0, element='h1', message='文字重叠')]


async def test_render_posts_to_studio_render_and_returns_payload():
    seen = {}
    mp4 = base64.b64encode(b'mp4-bytes').decode()

    def handler(request):
        seen['url'] = str(request.url)
        return httpx.Response(200, json={'mp4_base64': mp4, 'metadata': {'duration': 2.0}})

    result = await make(handler).render(render_request())
    assert seen['url'] == 'http://renderer:8080/studio/render'
    assert result == {'mp4_base64': mp4, 'metadata': {'duration': 2.0}}


async def test_busy_429_waits_retry_after_then_succeeds():
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        if len(calls) <= 2:
            return httpx.Response(429, headers={'Retry-After': '3'})
        return httpx.Response(200, json=INSPECT_RESULT)

    result = await make(handler, sleeps=sleeps).inspect(inspect_request())
    assert len(calls) == 3 and sleeps == [3, 3]
    assert result.issues[0].code == 'overlap'


async def test_busy_429_default_and_capped_wait():
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429)
        if len(calls) == 2:
            return httpx.Response(429, headers={'Retry-After': '999'})
        if len(calls) == 3:
            return httpx.Response(429, headers={'Retry-After': 'soon'})
        return httpx.Response(200, json=INSPECT_RESULT)

    await make(handler, sleeps=sleeps).inspect(inspect_request())
    assert sleeps == [2, 30, 2]


async def test_busy_429_gives_up_after_ten_retries():
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, headers={'Retry-After': '1'})

    with pytest.raises(ValueError, match='渲染服务忙，请稍后重试'):
        await make(handler, sleeps=sleeps).render(render_request())
    assert len(calls) == 11 and len(sleeps) == 10


async def test_422_runtime_detail_carries_issues():
    detail = {'code': 'studio_runtime', 'message': '动画运行出错',
              'issues': [{'code': 'runtime_error', 'segment': 's2', 't': None, 'element': None, 'message': '脚本报错'}]}

    with pytest.raises(StudioRenderError) as caught:
        await make(lambda request: httpx.Response(422, json={'detail': detail})).render(render_request())
    error = caught.value
    assert error.code == 'studio_runtime'
    assert error.issues == [Issue(code='runtime_error', segment='s2', t=None, element=None, message='脚本报错')]
    assert '脚本报错' in str(error)


async def test_422_input_detail_keeps_message():
    detail = {'code': 'studio_input', 'message': '请求里的时长与整片时长不一致'}

    with pytest.raises(StudioRenderError) as caught:
        await make(lambda request: httpx.Response(422, json={'detail': detail})).inspect(inspect_request())
    assert caught.value.code == 'studio_input' and caught.value.issues == []
    assert str(caught.value) == '请求里的时长与整片时长不一致'


async def test_422_plain_detail_is_still_a_render_error():
    with pytest.raises(StudioRenderError) as caught:
        await make(lambda request: httpx.Response(422, json={'detail': 'bad'})).inspect(inspect_request())
    assert caught.value.issues == [] and str(caught.value)


async def test_422_with_garbage_body_is_still_a_render_error():
    with pytest.raises(StudioRenderError):
        await make(lambda request: httpx.Response(422, content=b'not json')).render(render_request())


async def test_409_means_runtime_digest_mismatch():
    with pytest.raises(ValueError, match='渲染服务版本不一致，请重新部署渲染服务'):
        await make(lambda request: httpx.Response(409)).render(render_request())


@pytest.mark.parametrize('status', [413, 500, 504])
async def test_other_http_errors_are_unavailable(status):
    with pytest.raises(ValueError, match='渲染服务暂时不可用'):
        await make(lambda request: httpx.Response(status)).inspect(inspect_request())


async def test_network_failure_is_unavailable():
    def handler(request):
        raise httpx.ConnectError('down')

    with pytest.raises(ValueError, match='渲染服务暂时不可用'):
        await make(handler).render(render_request())


async def test_invalid_json_or_shape_is_unavailable():
    with pytest.raises(ValueError, match='渲染服务暂时不可用'):
        await make(lambda request: httpx.Response(200, content=b'<html>')).inspect(inspect_request())
    with pytest.raises(ValueError, match='渲染服务暂时不可用'):
        await make(lambda request: httpx.Response(200, json={'mp4_base64': 'AAAA'})).render(render_request())
    with pytest.raises(ValueError, match='渲染服务暂时不可用'):
        await make(lambda request: httpx.Response(200, json={'nope': 1})).inspect(inspect_request())


async def test_oversized_response_is_rejected(monkeypatch):
    monkeypatch.setattr('app.studio.render_client.MAX_INSPECT_BYTES', 100)
    with pytest.raises(ValueError, match='渲染服务暂时不可用'):
        await make(lambda request: httpx.Response(200, content=b'x' * 1000)).inspect(inspect_request())


async def test_unconfigured_renderer_url():
    def handler(request):
        raise AssertionError('no request expected')

    for url in ('', '  '):
        with pytest.raises(ValueError, match='视频渲染服务尚未配置，请联系管理员'):
            await make(handler, url=url).inspect(inspect_request())
        with pytest.raises(ValueError, match='视频渲染服务尚未配置，请联系管理员'):
            await make(handler, url=url).render(render_request())
