import base64
import io
import json
from pathlib import Path
import wave

import httpx
import pytest
from pydantic import ValidationError

from app.studio.contract import Camera, Highlight, Segment, StageState
from app.studio.film import build_film_html
from app.studio.render_contract import (InspectRequest, InspectResult, Issue, RenderRequest,
                                        StudioInputError, film_data)
from app.studio.runtime.assets import runtime_digest

DIGEST = '0' * 64


def wav(seconds, rate=24000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b'\x00\x00' * round(seconds * rate))
    return base64.b64encode(buf.getvalue()).decode()


def film(duration=2.0):
    segment = Segment(id='a', code='', duration=duration, words=[], narration='',
                      start_state=StageState(), end_state=StageState())
    return build_film_html([segment], [])


# ---- contract ---------------------------------------------------------------------------

def test_inspect_request_limits():
    with pytest.raises(ValidationError):
        InspectRequest(runtime_digest='0' * 64, html='x', duration=1, frame_times=[0.0] * 41, checks=[])
    with pytest.raises(ValidationError):
        InspectRequest(runtime_digest='0' * 64, html='x', duration=1, frame_times=[], checks=['nope'])


def test_inspect_request_rejects_extra_fields_bad_digest_and_out_of_range_frames():
    ok = dict(runtime_digest=DIGEST, html='x', duration=2, frame_times=[0, 2], checks=['bounds'])
    InspectRequest(**ok)
    for change in ({'extra': 1}, {'runtime_digest': 'abc'}, {'frame_times': [2.5]},
                   {'frame_times': [-0.1]}, {'html': 'x' * 4_000_001}, {'duration': 0}):
        with pytest.raises(ValidationError):
            InspectRequest(**{**ok, **change})
    with pytest.raises(ValidationError):
        Issue(code='bounds', segment='a', t=1, element=None, message='x', extra=1)


def test_render_request_checks_audio_and_size():
    ok = dict(runtime_digest=DIGEST, html=film(), audio_base64=wav(2.0), duration=2.0)
    request = RenderRequest(**ok)
    assert (request.width, request.height, request.fps) == (1280, 720, 30)
    for change in ({'audio_base64': wav(1.5)}, {'audio_base64': 'not base64!'}, {'width': 1281},
                   {'fps': 0}, {'audio_base64': ''}, {'extra': 1}):
        with pytest.raises(ValidationError):
            RenderRequest(**{**ok, **change})


def test_film_data_reads_the_film_block_and_rejects_others():
    data = film_data(film(2.5))
    assert data['duration'] == 2.5 and data['width'] == 1280 and data['segments'][0]['id'] == 'a'
    for html in ('<html></html>', '<script type="application/json" id="edu-studio-film">{bad</script>'):
        with pytest.raises(StudioInputError):
            film_data(html)


def test_inspect_result_shape():
    result = InspectResult(issues=[], frames=[{'t': 0.5, 'png_base64': 'AA=='}],
                           states={'a': {'start': StageState(), 'end': StageState(camera=Camera(zoom=2))}})
    assert result.states['a'].end.camera.zoom == 2


# ---- pure analysis helpers ----------------------------------------------------------------

def box(i, x, y, w, h, label='[data-edu-id="t"]', inside=(), world=None, camera=False, offstage=False):
    """Screen box (x, y, w, h) after the camera; `world` is the box before it (default: same)."""
    wx, wy, ww, wh = world or (x, y, w, h)
    return {'i': i, 'x': x, 'y': y, 'w': w, 'h': h, 'wx': wx, 'wy': wy, 'ww': ww, 'wh': wh,
            'camera': camera, 'offstage': offstage, 'label': label, 'inside': list(inside)}


def test_bounds_measures_canvas_before_the_camera_and_subtitles_after_it():
    from app.studio.inspect import box_issues
    run = lambda b: box_issues([{'segment': 'a', 't': 1.5, 'local': 1.5, 'boxes': [b]}], {'bounds'}, 1280, 720)
    # A push-in carries an edge title off screen: inside the canvas before the camera, no issue.
    assert run(box(0, -60, -40, 300, 80, world=(80, 80, 190, 50), camera=True)) == []
    # Laid out past the right edge before any camera move: reported, with the offstage hint.
    issues = run(box(0, 1100, 100, 400, 40, '[data-edu-id="wide"]'))
    assert len(issues) == 1 and '超出画布' in issues[0].message and 'data-edu-offstage' in issues[0].message
    # The camera brings text down into the subtitle zone: reported and the camera is named.
    issues = run(box(0, 500, 640, 200, 40, world=(520, 560, 150, 30), camera=True))
    assert len(issues) == 1 and '字幕区' in issues[0].message and '镜头' in issues[0].message
    # Pushed completely off the visible canvas below: not a subtitle problem.
    assert run(box(0, 500, 800, 200, 40, world=(520, 560, 150, 30), camera=True)) == []


def test_box_issues_name_segment_time_element_and_reason():
    from app.studio.inspect import box_issues
    samples = [{'segment': 'a', 't': 1.25, 'local': 1.25, 'boxes': [box(0, 100, 630, 200, 40, '[data-edu-id="low"]')]},
               {'segment': 'a', 't': 1.5, 'local': 1.5, 'boxes': [box(0, 100, 630, 200, 40, '[data-edu-id="low"]')]},
               {'segment': 'b', 't': 3.0, 'local': 0.5, 'boxes': [box(0, 1200, 100, 200, 40, '[data-edu-id="wide"]')]}]
    issues = box_issues(samples, {'bounds'}, 1280, 720)
    assert [(i.code, i.segment, i.t, i.element) for i in issues] == [
        ('bounds', 'a', 1.25, '[data-edu-id="low"]'), ('bounds', 'b', 3.0, '[data-edu-id="wide"]')]
    assert '字幕区' in issues[0].message and '第 a 段' in issues[0].message and '1.25' in issues[0].message
    assert '超出画布' in issues[1].message and '右' in issues[1].message
    # Inside the canvas and above y=625: nothing.
    assert box_issues([{'segment': 'a', 't': 0, 'local': 0, 'boxes': [box(0, 0, 0, 1280, 625)]}], {'bounds'}, 1280, 720) == []


def test_overlap_threshold_and_nested_elements():
    from app.studio.inspect import box_issues
    a = box(0, 100, 100, 100, 100, '[data-edu-id="p"]')
    over = box(1, 180, 100, 100, 100, '[data-edu-id="q"]')    # 20 % of the smaller one
    under = box(1, 190, 100, 100, 100, '[data-edu-id="q"]')   # 10 %
    nested = box(1, 110, 110, 50, 50, '[data-edu-id="p"] 里的 公式', inside=[0])
    run = lambda boxes: box_issues([{'segment': 'a', 't': 2, 'local': 2, 'boxes': boxes}], {'overlap'}, 1280, 720)
    issues = run([a, over])
    assert len(issues) == 1 and issues[0].code == 'overlap' and issues[0].segment == 'a'
    assert 'p' in issues[0].message and 'q' in issues[0].message and '20%' in issues[0].message
    assert run([a, under]) == [] and run([a, nested]) == []
    # Only the requested checks run.
    assert box_issues([{'segment': 'a', 't': 2, 'local': 2, 'boxes': [a, over]}], {'bounds'}, 1280, 720) == []


def test_overlap_uses_the_core_band_of_each_text_box():
    from app.studio.inspect import OVERLAP_CORE_INSET, box_issues
    assert OVERLAP_CORE_INSET == 0.15
    run = lambda boxes: box_issues([{'segment': 'a', 't': 0, 'local': 0, 'boxes': boxes}], {'overlap'}, 1280, 720)
    # Stacked 40 px lines: the content boxes (58 px tall) overlap by 10 px at line-height 1.2
    # (48 px apart) and by 18 px at 1.0, which is 17 % / 31 % of a box; the glyph bodies do not.
    for step in (48, 40):
        assert run([box(0, 100, 100, 300, 58, '[data-edu-id="l1"]'),
                    box(1, 100, 100 + step, 300, 58, '[data-edu-id="l2"]')]) == []
    # Two texts drawn on top of each other are still reported.
    issues = run([box(0, 100, 100, 300, 58, '[data-edu-id="l1"]'), box(1, 100, 104, 280, 58, '[data-edu-id="l2"]')])
    assert len(issues) == 1 and issues[0].code == 'overlap'


def test_offstage_only_exempts_off_canvas():
    from app.studio.inspect import box_issues
    run = lambda b, checks={'bounds'}: box_issues([{'segment': 'a', 't': 0, 'local': 0, 'boxes': b}], checks, 1280, 720)
    assert run([box(0, 1300, 100, 200, 40, offstage=True)]) == []                    # parked off canvas
    issues = run([box(0, 500, 640, 200, 40, offstage=True)])                       # visible, in the subtitles
    assert len(issues) == 1 and '字幕区' in issues[0].message
    # Two labels parked on top of each other beyond the canvas cannot be seen: no overlap.
    parked = [box(0, 1300, 100, 200, 40, '[data-edu-id="p"]', offstage=True),
              box(1, 1300, 100, 200, 40, '[data-edu-id="q"]', offstage=True)]
    assert run(parked, {'overlap'}) == []


def test_highlight_issues():
    from app.studio.inspect import highlight_issues
    wanted = [Highlight(phrase='顶点', occurrence=2, target='vertex')]
    good = [{'target': '[data-edu-id="vertex"]', 'at': 3.05, 'kind': 'highlight', 'labels': ['vertex']}]
    assert highlight_issues('a', wanted, [{'cue': 3.0}], good) == []
    assert highlight_issues('a', wanted, [{'cue': 3.0}], [], start=10.0)[0].t == 13.0  # film time
    for records in ([], [dict(good[0], at=3.3)], [dict(good[0], kind='circle')],
                    [dict(good[0], labels=['other'], target='[data-edu-id="other"]')]):
        issues = highlight_issues('a', wanted, [{'cue': 3.0}], records)
        assert len(issues) == 1 and issues[0].code == 'highlights' and issues[0].segment == 'a'
        assert '顶点' in issues[0].message and '第 2 处' in issues[0].message and '3' in issues[0].message
    # A selector target such as a KaTeX term class matches the recorded selector.
    term = [Highlight(phrase='顶点', target='.t-a')]
    assert highlight_issues('a', term, [{'cue': 1.0}], [{'target': '.t-a', 'at': 1.0, 'kind': 'highlight', 'labels': []}]) == []
    # A cue lookup failure names the segment even though the JS message might not.
    issues = highlight_issues('a', wanted, [{'error': '旁白里找不到第 2 处"顶点"'}], good)
    assert len(issues) == 1 and issues[0].message.startswith('第 a 段') and issues[0].code == 'highlights'


def test_state_issues_compare_declared_with_measured():
    from app.studio.inspect import state_issues
    declared = {'start_state': StageState().model_dump(), 'end_state': StageState(camera=Camera(zoom=1.5)).model_dump()}
    measured_end = StageState(camera=Camera(zoom=1.0), keep=[])
    issues = state_issues('a', declared, StageState(keep=['x']), measured_end, start_t=0.0, end_t=2.0)
    assert len(issues) == 1 and issues[0].code == 'states' and issues[0].segment == 'a' and issues[0].t == 2.0
    assert '结束' in issues[0].message and '镜头缩放' in issues[0].message
    assert state_issues('a', declared, StageState(), StageState(camera=Camera(zoom=1.5)), start_t=0.0, end_t=2.0) == []
    # The start is compared too (keep is not: it lists what the previous segment left).
    moved = StageState(camera=Camera(x=700))
    issues = state_issues('a', declared, moved, StageState(camera=Camera(zoom=1.5)), start_t=4.0, end_t=6.0)
    assert len(issues) == 1 and issues[0].t == 4.0 and '开头' in issues[0].message and '镜头 x' in issues[0].message


# ---- service endpoints --------------------------------------------------------------------

def inspect_payload(digest):
    return {'runtime_digest': digest, 'html': film(), 'duration': 2.0, 'frame_times': [0.5], 'checks': ['bounds']}


def render_payload(digest):
    return {'runtime_digest': digest, 'html': film(), 'audio_base64': wav(2.0), 'duration': 2.0}


@pytest.fixture
def service(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    from renderer import app as service
    return service


async def test_studio_endpoints_reject_digest_and_bad_input_before_launch(service, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError('No worker should start')
    monkeypatch.setattr(service.asyncio, 'create_subprocess_exec', forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app), base_url='http://renderer') as http:
        assert (await http.post('/studio/inspect', json=inspect_payload(DIGEST))).status_code == 409
        assert (await http.post('/studio/render', json=render_payload(DIGEST))).status_code == 409
        assert (await http.post('/studio/inspect', json={'html': 'x'})).status_code == 422
        bad = {**render_payload(runtime_digest()), 'audio_base64': wav(1.0)}
        assert (await http.post('/studio/render', json=bad)).status_code == 422
    assert not service.busy


async def test_studio_endpoints_run_the_studio_worker(service, monkeypatch):
    calls = []

    class Process:
        returncode = 0

        async def wait(self):
            return 0

    async def launch(*args, **kwargs):
        calls.append(args[1:-1])
        folder = Path(args[-1])
        assert json.loads((folder / 'request.json').read_text(encoding='utf-8'))['runtime_digest'] == runtime_digest()
        if args[-2] == 'inspect':
            (folder / 'result.json').write_text(json.dumps({'issues': [], 'frames': [], 'states': {}}))
        else:
            (folder / 'output.mp4').write_bytes(b'mp4')
            (folder / 'metadata.json').write_text(json.dumps({'duration': 2.0, 'width': 1280, 'height': 720}))
        return Process()

    async def stop(*args):
        pass
    monkeypatch.setattr(service.asyncio, 'create_subprocess_exec', launch)
    monkeypatch.setattr(service, 'terminate_process', stop)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app), base_url='http://renderer') as http:
        r = await http.post('/studio/inspect', json=inspect_payload(runtime_digest()))
        assert r.status_code == 200 and r.json() == {'issues': [], 'frames': [], 'states': {}}
        r = await http.post('/studio/render', json=render_payload(runtime_digest()))
        assert r.status_code == 200 and base64.b64decode(r.json()['mp4_base64']) == b'mp4'
        assert r.json()['metadata']['duration'] == 2.0
    assert calls == [('-m', 'renderer.studio_worker', 'inspect'), ('-m', 'renderer.studio_worker', 'render')]
    assert not service.busy


async def test_audio_base64_cap_matches_the_decoded_cap():
    import math
    from app.studio.render_contract import MAX_AUDIO_BYTES
    limit = RenderRequest.model_fields['audio_base64'].metadata
    assert any(getattr(m, 'max_length', None) == math.ceil(MAX_AUDIO_BYTES / 3) * 4 for m in limit)


def test_diagnostic_issues_and_timeout_issue():
    from app.studio.inspect import diagnostic_issues, timeout_issue
    issues = diagnostic_issues([{'segment': 'a', 'message': '第 a 段：构建失败：坏了'},
                                {'segment': 'a', 'message': '第 a 段：角色零件形状被修改（kr）'}],
                               ['boom', 'boom'], {'第 a 段：构建失败：坏了': 1.5})
    assert [(i.code, i.segment, i.t) for i in issues] == [('runtime', 'a', 1.5), ('geometry', 'a', None),
                                                          ('runtime', None, None)]
    issue = timeout_issue('b', 'paint', 2.0, 5)
    assert (issue.code, issue.segment, issue.t) == ('runtime', 'b', 2.0)
    assert issue.message.startswith('第 b 段：绘制超时，可能有死循环')
    assert timeout_issue('a', 'build', None, 30).message.startswith('第 a 段：构建超时，可能有死循环')
    generic = timeout_issue(None, None, None, 30)
    assert generic.segment is None and '死循环' in generic.message


async def test_studio_runtime_error_is_reported(service, monkeypatch):
    issues = [{'code': 'runtime', 'segment': 'a', 't': None, 'element': None, 'message': '第 a 段：构建失败：坏了'}]

    class Process:
        returncode = 2

        async def wait(self):
            return 2

    async def launch(*args, **kwargs):
        (Path(args[-1]) / 'error.json').write_text(json.dumps(
            {'code': 'studio_runtime', 'message': '动画运行出错，不能导出', 'issues': issues}))
        return Process()

    async def stop(*args):
        pass
    monkeypatch.setattr(service.asyncio, 'create_subprocess_exec', launch)
    monkeypatch.setattr(service, 'terminate_process', stop)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app), base_url='http://renderer') as http:
        r = await http.post('/studio/render', json=render_payload(runtime_digest()))
    assert r.status_code == 422 and r.json()['detail']['code'] == 'studio_runtime'
    assert r.json()['detail']['issues'] == issues
    assert not service.busy


async def test_studio_worker_input_error_is_reported(service, monkeypatch):
    class Process:
        returncode = 2

        async def wait(self):
            return 2

    async def launch(*args, **kwargs):
        (Path(args[-1]) / 'error.json').write_text(json.dumps({'code': 'studio_input', 'message': '整片时长不一致'}))
        return Process()

    async def stop(*args):
        pass
    monkeypatch.setattr(service.asyncio, 'create_subprocess_exec', launch)
    monkeypatch.setattr(service, 'terminate_process', stop)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app), base_url='http://renderer') as http:
        r = await http.post('/studio/inspect', json=inspect_payload(runtime_digest()))
    assert r.status_code == 422 and r.json()['detail'] == {'code': 'studio_input', 'message': '整片时长不一致'}
