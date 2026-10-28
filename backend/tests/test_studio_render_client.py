import base64
import json
from types import SimpleNamespace

import httpx
import pytest

from app.studio.render_client import StudioRenderError, StudioRenderer, StudioUnavailable
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


class FakeClock:
    """Monotonic time that only moves when the client sleeps."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(handler, url='http://renderer:8080/', sleeps=None, clock=None):
    clock = clock or FakeClock()

    async def fake_sleep(seconds):
        if sleeps is not None:
            sleeps.append(seconds)
        clock.now += seconds

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return StudioRenderer(SimpleNamespace(renderer_url=url), http, sleep=fake_sleep, clock=clock)


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


@pytest.mark.parametrize('call', ['inspect', 'render'])
async def test_busy_429_keeps_queueing_for_the_whole_budget(call):
    """A render occupies the renderer for minutes; callers queue instead of failing after a few tries."""
    from app.studio.render_client import QUEUE_BUDGET
    assert QUEUE_BUDGET == 1800
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        if len(calls) <= 200:  # 200 x 5 s = 1000 s of waiting, well past the old ~20 s
            return httpx.Response(429, headers={'Retry-After': '5'})
        return httpx.Response(200, json=INSPECT_RESULT if call == 'inspect'
                              else {'metadata': {}, 'mp4_base64': base64.b64encode(b'mp4').decode()})

    client = make(handler, sleeps=sleeps)
    await getattr(client, call)(inspect_request() if call == 'inspect' else render_request())
    assert len(calls) == 201 and sum(sleeps) == 1000


async def test_busy_429_gives_up_when_the_wait_budget_is_spent():
    clock, calls, sleeps = FakeClock(), [], []

    def handler(request):
        calls.append(clock.now)
        return httpx.Response(429, headers={'Retry-After': '30'})

    with pytest.raises(ValueError, match='渲染服务忙，请稍后重试'):
        await make(handler, sleeps=sleeps, clock=clock).render(render_request())
    assert sum(sleeps) == 1800  # never waits past the budget
    assert all(0 < s <= 30 for s in sleeps) and len(sleeps) == 60
    assert len(calls) == 61  # one last try when the budget runs out


async def test_busy_wait_is_trimmed_to_the_remaining_budget():
    clock, sleeps = FakeClock(), []

    def handler(request):
        return httpx.Response(429, headers={'Retry-After': '7'})

    with pytest.raises(ValueError, match='渲染服务忙'):
        await make(handler, sleeps=sleeps, clock=clock).inspect(inspect_request())
    assert sum(sleeps) == pytest.approx(1800)
    assert sleeps[-1] == pytest.approx(1800 - 7 * 257)


async def test_zero_retry_after_still_waits_a_little():
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={'Retry-After': '0'})
        return httpx.Response(200, json=INSPECT_RESULT)

    await make(handler, sleeps=sleeps).inspect(inspect_request())
    assert sleeps == [0.5]


async def test_time_spent_in_requests_counts_against_the_budget():
    """The budget is wall time since the first try, not only time asleep."""
    clock, sleeps = FakeClock(), []

    def handler(request):
        clock.now += 100  # each refused request itself takes 100 s
        return httpx.Response(429, headers={'Retry-After': '30'})

    with pytest.raises(ValueError, match='渲染服务忙'):
        await make(handler, sleeps=sleeps, clock=clock).inspect(inspect_request())
    assert clock.now - 1000 <= 1800 + 100
    assert len(sleeps) < 15


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


async def unavailable(call, handler):
    with pytest.raises(StudioUnavailable) as caught:
        await call(make(handler))
    assert isinstance(caught.value, ValueError)
    return caught.value


inspect_call = lambda renderer: renderer.inspect(inspect_request())  # noqa: E731
render_call = lambda renderer: renderer.render(render_request())  # noqa: E731


async def test_504_is_timeout():
    error = await unavailable(render_call, lambda request: httpx.Response(504))
    assert (error.reason, error.status) == ('timeout', 504)
    assert str(error) == '渲染超时，请缩短片段或简化画面'


async def test_client_side_timeout_is_timeout():
    def handler(request):
        raise httpx.ReadTimeout('slow')

    error = await unavailable(inspect_call, handler)
    assert (error.reason, error.status) == ('timeout', None)
    assert str(error) == '渲染超时，请缩短片段或简化画面'


async def test_413_is_too_large():
    error = await unavailable(render_call, lambda request: httpx.Response(413))
    assert (error.reason, error.status) == ('too_large', 413)
    assert str(error) == '渲染内容过大，请缩短片段'


async def test_oversized_response_is_too_large(monkeypatch):
    monkeypatch.setattr('app.studio.render_client.MAX_INSPECT_BYTES', 100)
    error = await unavailable(inspect_call, lambda request: httpx.Response(200, content=b'x' * 1000))
    assert (error.reason, error.status) == ('too_large', 200)
    assert str(error) == '渲染内容过大，请缩短片段'


@pytest.mark.parametrize('status', [400, 500, 502, 503])
async def test_other_http_errors(status):
    error = await unavailable(inspect_call, lambda request: httpx.Response(status))
    assert (error.reason, error.status) == ('http_error', status)
    assert str(error) == '渲染服务暂时不可用'


async def test_network_failure_is_network():
    def handler(request):
        raise httpx.ConnectError('down')

    error = await unavailable(render_call, handler)
    assert (error.reason, error.status) == ('network', None)
    assert str(error) == '渲染服务暂时不可用'


async def test_invalid_json_or_shape_is_bad_response():
    good = base64.b64encode(b'mp4').decode()
    bodies = [
        (inspect_call, httpx.Response(200, content=b'<html>')),
        (inspect_call, httpx.Response(200, json={'nope': 1})),
        (render_call, httpx.Response(200, content=b'<html>')),
        (render_call, httpx.Response(200, json=[1])),
        (render_call, httpx.Response(200, json={'mp4_base64': good})),
        (render_call, httpx.Response(200, json={'metadata': {}})),
        (render_call, httpx.Response(200, json={'mp4_base64': good, 'metadata': 'x'})),
        (render_call, httpx.Response(200, json={'mp4_base64': '', 'metadata': {}})),
        (render_call, httpx.Response(200, json={'mp4_base64': 'AAA', 'metadata': {}})),  # bad padding
        (render_call, httpx.Response(200, json={'mp4_base64': '!!!!', 'metadata': {}})),  # not base64
        (render_call, httpx.Response(200, json={'mp4_base64': 5, 'metadata': {}})),
    ]
    for call, response in bodies:
        error = await unavailable(call, lambda request, response=response: response)
        assert (error.reason, error.status) == ('bad_response', None)
        assert str(error) == '渲染服务暂时不可用'


async def test_oversized_error_body_is_cut_off(monkeypatch):
    monkeypatch.setattr('app.studio.render_client.MAX_ERROR_BYTES', 50)
    body = b'{"detail": {"code": "studio_input", "message": "' + b'x' * 5000 + b'"}}'
    with pytest.raises(StudioRenderError) as caught:
        await make(lambda request: httpx.Response(422, content=body)).inspect(inspect_request())
    assert caught.value.issues == [] and caught.value.code is None


async def test_unconfigured_renderer_url():
    def handler(request):
        raise AssertionError('no request expected')

    for url in ('', '  '):
        with pytest.raises(ValueError, match='视频渲染服务尚未配置，请联系管理员'):
            await make(handler, url=url).inspect(inspect_request())
        with pytest.raises(ValueError, match='视频渲染服务尚未配置，请联系管理员'):
            await make(handler, url=url).render(render_request())
