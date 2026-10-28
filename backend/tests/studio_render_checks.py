"""Chromium checks for the studio inspect/render service code. Run inside the renderer image."""
import base64
import io
from pathlib import Path
import tempfile
import time
import unittest
import wave

from app.studio.contract import ActorState, Camera, Highlight, Seam, Segment, StageState
from app.studio.export import render_film
from app.studio.film import assemble_audio, build_film_html
from app.studio.inspect import inspect_film
from app.studio.render_contract import InspectRequest, RenderRequest, film_data
from app.studio.runtime.assets import runtime_digest
from studio_runtime_checks import CHARACTERS, CORE, MUTATING_PART, NARRATION, WORDS, core_film, two_segment_film

ALL_CHECKS = ['determinism', 'bounds', 'overlap', 'highlights', 'geometry', 'states']
STYLE = '.edu-stage{background:#fdfaf3}'


def req(html, frames=(), checks=ALL_CHECKS):
    return InspectRequest(runtime_digest=runtime_digest(), html=html, duration=film_data(html)['duration'],
                          frame_times=list(frames), checks=list(checks))


def one_segment(code, *, highlights=(), end_state=None, duration=3.0, characters=''):
    segment = Segment(id='a', code=code, duration=duration, words=WORDS, narration=NARRATION,
                      highlights=list(highlights), start_state=StageState(),
                      end_state=end_state or StageState())
    return build_film_html([segment], [], characters_code=characters, style_css=STYLE)


def film_with_text_at(y):
    # A label whose box reaches into the subtitle zone, and an offstage one parked beyond the
    # canvas that must be ignored.
    return one_segment(
        f"ctx.svg.innerHTML = '<text data-edu-id=\"low\" x=\"640\" y=\"{y}\" text-anchor=\"middle\" "
        "font-size=\"40\">字幕区里的字</text>' + '<text data-edu-id=\"parked\" data-edu-offstage=\"1\" "
        "x=\"1400\" y=\"300\" font-size=\"40\">候场</text>';")


def bad_film():
    # Two labels on top of each other, a scripted highlight the code never makes, and an
    # end_state that promises a camera push-in the code never does.
    code = ("ctx.svg.innerHTML = '<text data-edu-id=\"one\" x=\"300\" y=\"300\" font-size=\"60\">第一行字</text>' +"
            " '<text data-edu-id=\"two\" x=\"320\" y=\"310\" font-size=\"60\">第二行字</text>';")
    return one_segment(code, highlights=[Highlight(phrase='顶点', target='one')],
                       end_state=StageState(camera=Camera(zoom=1.5)), duration=4.5)


# The painter keeps a counter across frames, so a frame depends on which frames came before.
HISTORY = ("ctx.svg.innerHTML = '<rect data-edu-id=\"box\" x=\"100\" y=\"100\" width=\"100\" height=\"100\" fill=\"#c53030\"/>';"
           "let calls = 0; const box = ctx.$('[data-edu-id=\"box\"]')[0];"
           "ctx.paint(function () { calls += 1; box.setAttribute('x', String(100 + (calls % 7) * 120)); });")


def wav(seconds, rate=24000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b'\x00\x00' * round(seconds * rate))
    return buf.getvalue()


def render_req(html):
    data = film_data(html)
    segments = [Segment(id=s['id'], code='', duration=s['duration'], words=[], narration='',
                        start_state=StageState(), end_state=StageState()) for s in data['segments']]
    seams = [Seam(**s) for s in data['seams']]
    audio = assemble_audio([wav(s.duration) for s in segments], segments, seams)
    return RenderRequest(runtime_digest=runtime_digest(), html=html, duration=data['duration'],
                         audio_base64=base64.b64encode(audio).decode())


def seg_with_code(code, duration=3.0):
    """A one-segment film whose code is inserted after linting, so it may break the lint rules."""
    marker = 'void "__T7__";'
    return one_segment(marker, duration=duration).replace(marker, code)


EDGE_TITLE = ("ctx.svg.innerHTML = '<text data-edu-id=\"title\" x=\"80\" y=\"120\" font-size=\"48\">标题文字</text>';"
              "ctx.camera.shot({zoom: 1.6}, 1.0, 0.8);")
OFF_CANVAS = "ctx.svg.innerHTML = '<text data-edu-id=\"gone\" x=\"1300\" y=\"200\" font-size=\"48\">画外</text>';"
PUSHED_DOWN = ("ctx.svg.innerHTML = '<text data-edu-id=\"mid\" x=\"640\" y=\"560\" text-anchor=\"middle\" font-size=\"40\">中间</text>';"
               "ctx.camera.shot({x: 640, y: 360, zoom: 1.5}, 1.0, 0.5);")
LONG_DIV = ("const d = document.createElement('div'); d.setAttribute('data-edu-id', 'note');"
            "d.style.cssText = 'position:absolute;left:900px;top:40px;font-size:40px;white-space:nowrap';"
            "d.textContent = '这是一句很长很长的中文说明文字会超出画面右边'; ctx.root.appendChild(d);")
TWO_DIVS = ("for (const [id, top] of [['p1', 200], ['p2', 215]]) { const d = document.createElement('div');"
            "d.setAttribute('data-edu-id', id); d.style.cssText = 'position:absolute;left:200px;top:' + top + 'px;font-size:40px';"
            "d.textContent = '网页里的文字'; ctx.root.appendChild(d); }")
BUILD_LOOP = 'while (true) {}'
PAINT_LOOP = "ctx.paint(function (t) { if (t > 1.5) { while (true) {} } });"
THROW_BUILD = 'throw new Error("坏了");'
THROW_PAINT = "ctx.paint(function (t) { if (t > 1) throw new Error('第二秒坏了'); });"
STACKED = ("for (const [font, x] of [['Noto Sans SC', 100], ['LXGW WenKai', 700]]) {"
           "  for (const [lh, top] of [[1.2, 40], [1.0, 300]]) {"
           "    const box = document.createElement('div');"
           "    box.style.cssText = 'position:absolute;left:' + x + 'px;top:' + top + 'px;font-size:40px;font-family:\"' + font + '\";line-height:' + lh;"
           "    box.innerHTML = '<p style=\"margin:0\">第一行文字说明</p><p style=\"margin:0\">第二行文字说明</p><p style=\"margin:0\">第三行文字说明</p>';"
           "    ctx.root.appendChild(box); } }")
ON_TOP = ("for (const [id, text] of [['s1', '第一句话写在这里'], ['s2', '另一句话也在这']]) { const d = document.createElement('div');"
          "d.setAttribute('data-edu-id', id); d.style.cssText = 'position:absolute;left:300px;top:300px;font-size:40px';"
          "d.textContent = text; ctx.root.appendChild(d); }")
FORMULA_BELOW = ("const t = document.createElement('div'); t.style.cssText = 'position:absolute;left:200px;top:200px;font-size:40px;line-height:1.2';"
                 "t.innerHTML = '<p style=\"margin:0\">函数的解析式是</p>'; const f = document.createElement('div');"
                 "f.style.marginTop = '8px'; t.appendChild(f); katex.render('y=x^2-2x-3', f); ctx.root.appendChild(t);")
# Text in the subtitle zone from the start; the painter hangs only around 1.5 s, which the
# state measurements at 0 and 3 s never reach but the bounds sweep does.
LATE_PAINT_LOOP = ("ctx.svg.innerHTML = '<text data-edu-id=\"low\" x=\"640\" y=\"660\" text-anchor=\"middle\" font-size=\"40\">低处</text>';"
                   "ctx.paint(function (t) { if (t > 1.4 && t < 1.6) { while (true) {} } });")
PARKED_LOW = ("ctx.svg.innerHTML = '<text data-edu-id=\"parked\" data-edu-offstage=\"1\" x=\"640\" y=\"660\" "
              "text-anchor=\"middle\" font-size=\"40\">候场</text>';")
NETWORK = ("try { new WebSocket('ws://127.0.0.1:18999/ws'); } catch (e) {}"
           "try { fetch('http://127.0.0.1:18999/f').catch(function () {}); } catch (e) {}"
           "ctx.root.insertAdjacentHTML('beforeend', '<img src=\"http://127.0.0.1:18999/i\">');")


async def post(path, body, timeout=120):
    import asyncio
    import httpx
    from renderer import app as service
    transport = httpx.ASGITransport(app=service.app)
    async with httpx.AsyncClient(transport=transport, base_url='http://renderer', timeout=timeout) as http:
        response = await asyncio.wait_for(http.post(path, content=body.model_dump_json(),
                                                    headers={'content-type': 'application/json'}), timeout)
    return response, service


class StudioRenderChecks(unittest.IsolatedAsyncioTestCase):
    async def test_text_in_caption_zone_reported(self):
        result = await inspect_film(req(film_with_text_at(y=650)))
        issue = next(i for i in result.issues if i.code == 'bounds')
        self.assertEqual(issue.segment, 'a'); self.assertIsNotNone(issue.t); self.assertIn('字幕区', issue.message)
        bounds = [i for i in result.issues if i.code == 'bounds']
        self.assertEqual(len(bounds), 1, bounds)  # the offstage label and the captions are not checked
        self.assertIn('low', bounds[0].element)
        self.assertIn('第 a 段', bounds[0].message)

    async def test_overlap_and_missing_highlight_and_state_mismatch(self):
        result = await inspect_film(req(bad_film()))
        codes = {i.code for i in result.issues}
        self.assertTrue({'overlap', 'highlights', 'states'} <= codes, result.issues)
        highlight = next(i for i in result.issues if i.code == 'highlights')
        self.assertIn('顶点', highlight.message)
        self.assertIn('2.91', highlight.message)
        state = next(i for i in result.issues if i.code == 'states')
        self.assertIn('镜头缩放', state.message)
        self.assertAlmostEqual(result.states['a'].end.camera.zoom, 1, 3)

    async def test_clean_film_has_no_issues_and_returns_frames(self):
        started = time.monotonic()
        result = await inspect_film(req(two_segment_film(seam='transition', transition='push', gap=0.8), frames=[0.5, 2.4]))
        print(f'\n[timing] inspect of a 2-segment film: {time.monotonic() - started:.2f} s')
        self.assertEqual(result.issues, []); self.assertEqual(len(result.frames), 2)
        from PIL import Image
        for frame, t in zip(result.frames, (0.5, 2.4)):
            self.assertEqual(frame.t, t)
            self.assertEqual(Image.open(io.BytesIO(base64.b64decode(frame.png_base64))).size, (640, 360))
        self.assertEqual(set(result.states), {'a', 'b'})

    async def test_scripted_highlight_on_cue_passes(self):
        # core_film's actor segment plus a highlight on the vertex label exactly at its cue.
        code = CORE + "\nctx.motion.highlight('[data-edu-id=\"vertex\"]', ctx.cue('顶点'));"
        segment = Segment(id='a', code=code, duration=4.5, words=WORDS, narration=NARRATION,
                          highlights=[Highlight(phrase='顶点', target='vertex')],
                          start_state=StageState(actors={'kr': ActorState(x=300, y=600)}),
                          end_state=StageState(camera=Camera(x=640, y=450, zoom=1.4),
                                               actors={'kr': ActorState(x=500, y=600, pose={'arm_r': -60})},
                                               keep=['vertex']))
        html = build_film_html([segment], [], characters_code=CHARACTERS, style_css=STYLE)
        result = await inspect_film(req(html, checks=['highlights', 'states', 'geometry']))
        self.assertEqual(result.issues, [])
        self.assertAlmostEqual(result.states['a'].end.actors['kr'].x, 500, 0)

    async def test_history_dependent_frame_is_reported(self):
        result = await inspect_film(req(one_segment(HISTORY), checks=['determinism']))
        issue = next(i for i in result.issues if i.code == 'determinism')
        self.assertEqual(issue.segment, 'a'); self.assertIsNotNone(issue.t)

    async def test_runtime_and_geometry_diagnostics(self):
        result = await inspect_film(req(core_film(code=MUTATING_PART), checks=['geometry']))
        geometry = [i for i in result.issues if i.code == 'geometry']
        self.assertTrue(geometry and geometry[0].segment == 'a' and '角色零件形状被修改' in geometry[0].message, result.issues)
        result = await inspect_film(req(one_segment('throw new Error("坏了")'), checks=[]))
        runtime = [i for i in result.issues if i.code == 'runtime']
        self.assertTrue(runtime and runtime[0].segment == 'a' and '坏了' in runtime[0].message, result.issues)

    async def test_render_mp4_matches_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            started = time.monotonic()
            meta = await render_film(render_req(two_segment_film(seam='continue', gap=0.2)), Path(tmp) / 'o.mp4')
            print(f'\n[timing] render of a 4.2 s film: {time.monotonic() - started:.2f} s')
            self.assertAlmostEqual(meta['duration'], 4.2, delta=1 / 30)
            self.assertEqual((meta['width'], meta['height']), (1280, 720))
            self.assertTrue((Path(tmp) / 'o.mp4').stat().st_size > 1000)


    # ---- fix round 1 ----------------------------------------------------------------------
    async def test_camera_push_in_is_not_off_canvas(self):
        result = await inspect_film(req(seg_with_code(EDGE_TITLE), checks=['bounds']))
        self.assertEqual([i for i in result.issues if i.code == 'bounds'], [])

    async def test_text_off_canvas_before_the_camera_is_reported(self):
        result = await inspect_film(req(seg_with_code(OFF_CANVAS), checks=['bounds']))
        issue = next(i for i in result.issues if i.code == 'bounds')
        self.assertIn('超出画布', issue.message); self.assertIn('gone', issue.element)

    async def test_push_in_into_subtitle_zone_is_reported(self):
        result = await inspect_film(req(seg_with_code(PUSHED_DOWN), checks=['bounds']))
        issue = next(i for i in result.issues if i.code == 'bounds')
        self.assertIn('字幕区', issue.message); self.assertIn('镜头', issue.message)
        self.assertGreater(issue.t, 1.0)

    async def test_html_text_overflow_and_overlap(self):
        result = await inspect_film(req(seg_with_code(LONG_DIV), checks=['bounds']))
        issue = next(i for i in result.issues if i.code == 'bounds')
        self.assertIn('note', issue.element); self.assertIn('右', issue.message)
        result = await inspect_film(req(seg_with_code(TWO_DIVS), checks=['overlap']))
        issue = next(i for i in result.issues if i.code == 'overlap')
        self.assertIn('p1', issue.message); self.assertIn('p2', issue.message)

    async def test_build_loop_returns_an_issue_through_the_endpoint(self):
        started = time.monotonic()
        response, service = await post('/studio/inspect', req(seg_with_code(BUILD_LOOP)))
        self.assertLess(time.monotonic() - started, 60)
        self.assertEqual(response.status_code, 200, response.text)
        issue = next(i for i in response.json()['issues'] if i['code'] == 'runtime')
        self.assertEqual(issue['segment'], 'a')
        self.assertTrue(issue['message'].startswith('第 a 段：构建超时，可能有死循环'), issue)
        self.assertFalse(service.busy)

    async def test_paint_loop_returns_an_issue(self):
        import asyncio
        started = time.monotonic()
        result = await asyncio.wait_for(inspect_film(req(seg_with_code(PAINT_LOOP))), 90)
        self.assertLess(time.monotonic() - started, 60)
        issue = next(i for i in result.issues if i.code == 'runtime')
        self.assertEqual(issue.segment, 'a')
        self.assertTrue(issue.message.startswith('第 a 段：绘制超时，可能有死循环'), issue)

    async def test_render_refuses_films_with_runtime_errors(self):
        for code, word in ((THROW_BUILD, '坏了'), (THROW_PAINT, '第二秒坏了')):
            response, service = await post('/studio/render', render_req(seg_with_code(code, duration=2.0)))
            self.assertEqual(response.status_code, 422, response.text)
            detail = response.json()['detail']
            self.assertEqual(detail['code'], 'studio_runtime')
            self.assertTrue(any(i['segment'] == 'a' and word in i['message'] for i in detail['issues']), detail)
            self.assertFalse(service.busy)

    async def test_no_network_without_the_csp_meta(self):
        import asyncio
        from app.studio.film import CSP
        hits = []

        async def handle(reader, writer):
            hits.append(await reader.read(200))
            writer.close()
        server = await asyncio.start_server(handle, '127.0.0.1', 18999)
        try:
            html = seg_with_code(NETWORK)
            meta = f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
            self.assertIn(meta, html)
            await inspect_film(req(html.replace(meta, ''), checks=[]))
            await asyncio.sleep(0.5)
        finally:
            server.close()
        self.assertEqual(hits, [])


    # ---- fix round 2 ----------------------------------------------------------------------
    async def test_stacked_lines_are_not_overlapping(self):
        result = await inspect_film(req(seg_with_code(STACKED), checks=['overlap']))
        self.assertEqual([i for i in result.issues if i.code == 'overlap'], [])

    async def test_texts_drawn_on_top_of_each_other_overlap(self):
        result = await inspect_film(req(seg_with_code(ON_TOP), checks=['overlap']))
        issue = next(i for i in result.issues if i.code == 'overlap')
        self.assertIn('s1', issue.message); self.assertIn('s2', issue.message)

    async def test_formula_below_a_line_is_not_overlapping(self):
        result = await inspect_film(req(seg_with_code(FORMULA_BELOW), checks=['overlap', 'bounds']))
        self.assertEqual(result.issues, [])

    async def test_timeout_keeps_issues_measured_before_it(self):
        result = await inspect_film(req(seg_with_code(LATE_PAINT_LOOP), checks=['bounds']))
        codes = [i.code for i in result.issues]
        self.assertIn('bounds', codes, result.issues)
        runtime = next(i for i in result.issues if i.code == 'runtime')
        self.assertTrue(runtime.message.startswith('第 a 段：绘制超时，可能有死循环'), runtime)
        self.assertAlmostEqual(runtime.t, 1.5, 3)

    async def test_offstage_label_on_canvas_in_subtitles_is_reported(self):
        result = await inspect_film(req(seg_with_code(PARKED_LOW), checks=['bounds']))
        issue = next(i for i in result.issues if i.code == 'bounds')
        self.assertIn('字幕区', issue.message); self.assertIn('parked', issue.element)


if __name__ == '__main__':
    from renderer.resources import limit_cpu_affinity
    limit_cpu_affinity()
    unittest.main()
