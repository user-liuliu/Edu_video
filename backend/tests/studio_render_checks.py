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

THREE_SEGMENT = (Path(__file__).with_name('fixtures') / 'studio' / 'three_segment.js').read_text(encoding='utf-8')
STAGE_RGB = (0xfd, 0xfa, 0xf3)  # STYLE's stage background
# A shadow-casting scene whose cube turns: a stale shadow map shows as a misplaced shadow.
SHADOW_SCENE = '''const {renderer} = ctx.three();
const scene = new THREE.Scene();
const cam = new THREE.PerspectiveCamera(40, ctx.width / ctx.height, 0.1, 100);
cam.position.set(0, 5, 9); cam.lookAt(0, 0, 0);
scene.add(new THREE.AmbientLight(0xffffff, 0.3));
const sun = new THREE.DirectionalLight(0xffffff, 2.5);
sun.position.set(3, 8, 4); sun.castShadow = true;
scene.add(sun);
const floor = new THREE.Mesh(new THREE.PlaneGeometry(12, 8), new THREE.MeshStandardMaterial({color: 0xeeeeee}));
floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true;
scene.add(floor);
const cube = new THREE.Mesh(new THREE.BoxGeometry(2, 2, 2), new THREE.MeshStandardMaterial({color: 0x2b6cb0}));
cube.position.y = 1.2; cube.castShadow = true;
scene.add(cube);
const s = {rot: 0};
ctx.tl.to(s, {rot: Math.PI, duration: ctx.duration, ease: 'none'}, 0);
ctx.paint(function () {
  renderer.shadowMap.enabled = true;
  cube.rotation.y = s.rot; cube.position.x = 2 * Math.sin(s.rot);
  renderer.render(scene, cam);
});'''
# Leaves the shared renderer in a non-default state, at build and after its own render.
STATE_MESSER = '''function mess() {
  renderer.shadowMap.autoUpdate = false;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.setClearColor(0xff0000, 1);
  renderer.setScissor(0, 0, 100, 100);
  renderer.setScissorTest(true);
  renderer.getContext().colorMask(false, false, false, false);
}
mess();
ctx.paint(function () { mess(); });'''
OWN_RENDERER = 'const r = new THREE.WebGLRenderer();'
LATE_OWN_RENDERER = "ctx.paint(function (t) { if (t > 0.5) new THREE.WebGLRenderer(); });"
OWN_RENDERER_MESSAGE = '请用 ctx.three() 获取渲染器，不要自己创建 WebGLRenderer'


def three_film(ids, duration=1.0, codes=None, seam=None):
    """Segments that each say a short line, so every frame carries a caption; by default all
    are the three.js fixture. ``seam`` is the Seam between neighbours (default: cut)."""
    from studio_runtime_checks import _ev
    from app.studio.words import align_words
    codes = codes or {}
    segments = [Segment(id=sid, code=codes.get(sid, THREE_SEGMENT), duration=duration,
                        words=align_words('立方体。', [_ev(0.05, duration * 0.4, '立方'), _ev(duration * 0.5, duration * 0.4, '体')]),
                        narration='立方体。', start_state=StageState(), end_state=StageState()) for sid in ids]
    seams = [seam or Seam(kind='continue', duration=0) for _ in ids[1:]]
    return build_film_html(segments, seams, style_css=STYLE)


def rgb(png):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(io.BytesIO(png)).convert('RGB')).astype('int16')


def drawn_share(pixels):
    """Share of pixels that are not the stage background (3D content plus the caption)."""
    import numpy as np
    return float((np.abs(pixels - np.array(STAGE_RGB, dtype='int16')).max(axis=2) > 24).mean())


def mp4_frame(path, t):
    """One decoded frame of the mp4 at ``t`` seconds, at the review size (as inspect frames)."""
    import subprocess
    from PIL import Image
    from app.studio.render_contract import REVIEW_SIZE
    from app.videos.export import executable
    png = subprocess.run([executable('ffmpeg'), '-v', 'error', '-ss', f'{t:.3f}', '-i', str(path), '-frames:v', '1',
                          '-f', 'image2pipe', '-vcodec', 'png', '-'], check=True, capture_output=True).stdout
    out = io.BytesIO()
    Image.open(io.BytesIO(png)).convert('RGB').resize(REVIEW_SIZE, Image.LANCZOS).save(out, format='PNG')
    return out.getvalue()


async def caption_baseline(blank, times):
    """Drawn share at ``times`` of ``blank``, the same film with empty segments: the caption alone."""
    result = await inspect_film(req(blank, frames=times, checks=[]))
    return {f.t: drawn_share(rgb(base64.b64decode(f.png_base64))) for f in result.frames}
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

    # ---- 3D (Task 9): three.js on SwiftShader, no GPU, one shared renderer -----------------
    async def test_three_segment_renders_deterministically_without_gpu(self):
        from app.studio.inspect import _same_png
        from app.studio.page import film_needs_webgl, studio_page

        html = one_segment(THREE_SEGMENT)
        self.assertTrue(film_needs_webgl(html))
        baseline = (await caption_baseline(one_segment(''), [1.5]))[1.5]

        async with studio_page(html, webgl=film_needs_webgl(html)) as (page, errors):
            renderer = await page.evaluate('''() => {
              const gl = document.createElement('canvas').getContext('webgl2');
              if (!gl) return null;
              const info = gl.getExtension('WEBGL_debug_renderer_info');
              const name = info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
              gl.getExtension('WEBGL_lose_context').loseContext();  // the probe context only
              return name;
            }''')
            print(f'\n[3d] WebGL renderer: {renderer}')

            async def shot(t):
                await page.evaluate('t => window.renderFrame(t)', t)
                return await page.screenshot(type='png')

            # 1. no errors, not blank: well above the caption-only frame, and it moves.
            first, middle = await shot(0.0), await shot(1.5)
            drawn = drawn_share(rgb(middle))
            moved = float(abs(rgb(first) - rgb(middle)).mean())
            print(f'[3d] drawn share {drawn:.3f} (caption only {baseline:.3f}), mean change 0 s -> 1.5 s {moved:.2f}')
            self.assertEqual(errors, [])
            self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])
            self.assertGreaterEqual(drawn, 3 * baseline)
            self.assertGreater(moved, 1.0)

            # 2. same t, same pixels: forward, then reversed after seeking elsewhere, then again.
            times = [0.0, 0.75, 1.5, 2.25, 2.999]
            forward = {t: await shot(t) for t in times}
            exact = 0
            for t in reversed(times):
                again = await shot(t)
                self.assertTrue(_same_png(forward[t], again), f'{t} s differs after seeking away')
                exact += forward[t] == again
            repeat = await shot(1.5)
            self.assertTrue(_same_png(forward[1.5], repeat))
            exact += forward[1.5] == repeat
            print(f'[3d] bit-identical revisits: {exact}/{len(times) + 1}')

            # 3. frame cost at 1280x720: renderFrame (paint + copy) + PNG screenshot, as exported.
            costs = []
            for k in range(60):
                started = time.monotonic()
                await shot(k * 3.0 / 60)
                costs.append(time.monotonic() - started)
            costs.sort()
            mean, p95 = sum(costs) / len(costs), costs[int(len(costs) * 0.95) - 1]
            print(f'[3d] per frame: mean {mean:.3f} s, p95 {p95:.3f} s, max {costs[-1]:.3f} s')
            self.assertLessEqual(mean, 0.5)

        # 4. the 3 s segment exports to mp4, and the video shows the 3D picture.
        with tempfile.TemporaryDirectory() as tmp:
            started = time.monotonic()
            meta = await render_film(render_req(html), Path(tmp) / 'three.mp4')
            print(f'[3d] mp4 export of the 3 s segment: {time.monotonic() - started:.2f} s')
            self.assertAlmostEqual(meta['duration'], 3.0, delta=1 / 30)
            self.assertEqual((meta['width'], meta['height']), (1280, 720))
            frame = drawn_share(rgb(mp4_frame(Path(tmp) / 'three.mp4', 1.5)))
            print(f'[3d] mp4 frame at 1.5 s: drawn share {frame:.3f}')
            self.assertGreaterEqual(frame, 3 * baseline)

    async def test_three_segment_has_no_inspect_issues(self):
        started = time.monotonic()
        result = await inspect_film(req(one_segment(THREE_SEGMENT), frames=[1.5]))
        print(f'\n[3d] inspect with all checks: {time.monotonic() - started:.2f} s, issues {result.issues}')
        self.assertEqual(result.issues, [])

    async def test_twenty_3d_segments_share_one_context(self):
        # More 3D segments than Chromium's 16 live WebGL contexts per page: with a context per
        # segment the first ones went blank in both inspect and export, without any error.
        ids = [f's{i}' for i in range(20)]
        html = three_film(ids)
        times = [0.5, 9.5, 19.5]  # in s0, s9 and s19
        baseline = await caption_baseline(three_film(ids, codes={sid: '' for sid in ids}), times)
        started = time.monotonic()
        result = await inspect_film(req(html, frames=times))
        print(f'\n[3d] inspect of 20 x 1 s 3D segments: {time.monotonic() - started:.1f} s')
        self.assertEqual(result.issues, [])
        for frame in result.frames:
            share = drawn_share(rgb(base64.b64decode(frame.png_base64)))
            print(f'[3d] inspect frame {frame.t} s: drawn {share:.3f}, caption only {baseline[frame.t]:.3f}')
            self.assertGreaterEqual(share, 3 * baseline[frame.t], frame.t)
        with tempfile.TemporaryDirectory() as tmp:
            started = time.monotonic()
            meta = await render_film(render_req(html), Path(tmp) / 'twenty.mp4')
            print(f'[3d] mp4 export of 20 x 1 s 3D segments: {time.monotonic() - started:.1f} s')
            self.assertAlmostEqual(meta['duration'], 20.0, delta=1 / 30)
            for t in (times[0], times[-1]):
                share = drawn_share(rgb(mp4_frame(Path(tmp) / 'twenty.mp4', t)))
                print(f'[3d] mp4 frame {t} s: drawn {share:.3f}')
                self.assertGreaterEqual(share, 3 * baseline[t], t)

    async def test_wipe_between_two_3d_segments_shows_both_pictures(self):
        import numpy as np
        from app.studio.inspect import _same_png
        from app.studio.page import studio_page
        # a: stage colour, blue cube; b: light-blue clear, red cube (cubes on the left, gold
        # surfaces on the right). Wipe 1 s from 2 s to 3 s: at 2.5 s b fills the left half and
        # a the right half.
        html = three_film(['a', 'b'], duration=2.0, seam=Seam(kind='transition', transition='wipe', duration=1.0))
        async with studio_page(html, webgl=True) as (page, errors):
            async def shot(t):
                await page.evaluate('t => window.renderFrame(t)', t)
                return await page.screenshot(type='png')
            forward = [await shot(t) for t in (0.5, 2.5, 4.5)]
            backward = await shot(4.5), await shot(2.5)
            self.assertTrue(_same_png(forward[1], backward[1]))
            self.assertTrue(_same_png(forward[2], backward[0]))
            p = rgb(forward[1])[:600]
            r, g, b = p[..., 0], p[..., 1], p[..., 2]
            light_blue = (np.abs(p - np.array([0xbe, 0xe3, 0xf8])).max(axis=2) <= 12)
            red = (r - g > 40) & (np.abs(g - b) < 30)
            gold = (g - b > 40) & (r > g)
            stage = (np.abs(p - np.array(STAGE_RGB)).max(axis=2) <= 12)
            left, right = slice(0, 600), slice(680, 1280)
            share = lambda mask, cols: float(mask[:, cols].mean())  # noqa: E731
            print(f'\n[3d] wipe at 2.5 s: left light-blue {share(light_blue, left):.2f} red {share(red, left):.3f} '
                  f'stage {share(stage, left):.3f}; right stage {share(stage, right):.2f} '
                  f'gold {share(gold, right):.3f} light-blue {share(light_blue, right):.3f}')
            self.assertGreater(share(light_blue, left), 0.3)  # b's own clear colour, not a's
            self.assertGreater(share(red, left), 0.005)       # b's cube
            self.assertLess(share(stage, left), 0.001)
            self.assertEqual(share(light_blue, right), 0)     # a keeps its own (transparent) clear
            self.assertGreater(share(stage, right), 0.3)
            self.assertGreater(share(gold, right), 0.05)      # a's surface
            self.assertEqual(errors, [])
            self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])

    async def test_renderer_state_never_carries_over_between_segments(self):
        from app.studio.page import studio_page
        # a changes renderer state at build and in its painter (also raw GL); b and c use the
        # defaults and a shadow-casting light. Their frames must equal b and c in a film
        # without a, whichever frames were drawn before.
        codes = {'a': SHADOW_SCENE + '\n' + STATE_MESSER, 'b': SHADOW_SCENE, 'c': SHADOW_SCENE}
        polluted, clean = three_film(['a', 'b', 'c'], codes=codes), three_film(['b', 'c'], codes=codes)
        local = [('b', 0.25), ('b', 0.75), ('c', 0.25), ('c', 0.75)]

        async def shots(html, offset, order):
            async with studio_page(html, webgl=True) as (page, errors):
                out = []
                for t in order:
                    await page.evaluate('t => window.renderFrame(t)', t)
                    out.append((round(t - offset, 6), rgb(await page.screenshot(type='png'))))
                self.assertEqual(errors, [])
                self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])
                return out

        def at(segment, t, first):  # film time of a local time in b or c
            return round(first + {'b': 0, 'c': 1}[segment] + t, 6)
        wanted = [at(s, t, 0) for s, t in local]
        reference = dict(await shots(clean, 0, wanted))
        # a's painter runs (and changes state) before each of b's and c's frames, forward and back.
        order = [x for t in wanted for x in (0.6, t + 1)] + [x for t in reversed(wanted) for x in (0.9, t + 1)]
        worst = {}
        for key, pixels in await shots(polluted, 1, order):
            if key not in reference:
                continue  # a's own frames
            delta = abs(pixels - reference[key]).max(axis=2)
            worst[key] = max(worst.get(key, (0, 0.0)), (int(delta.max()), float((delta > 0).mean())))
        print()
        for (segment, t), key in zip(local, wanted):
            print(f'[3d] {segment} @ {t} s after a (forward and backward): max diff {worst[key][0]}, '
                  f'{worst[key][1]:.4f} of pixels differ')
        self.assertEqual(len(worst), len(wanted))
        self.assertEqual({k: v[0] for k, v in worst.items()}, {k: 0 for k in wanted})

    async def test_segment_creating_its_own_renderer_is_isolated(self):
        from app.studio.page import studio_page
        codes = {'a': OWN_RENDERER, 'c': THREE_SEGMENT + '\n' + LATE_OWN_RENDERER}
        html = three_film(['a', 'b', 'c'], duration=1.0, codes=codes)
        async with studio_page(html, webgl=True) as (page, errors):
            for t in (0.5, 1.5, 2.2, 2.7):
                await page.evaluate('t => window.renderFrame(t)', t)
            diagnostics = await page.evaluate('window.studioDiagnostics')
            self.assertEqual(sorted(diagnostics, key=lambda d: d['segment']), [
                {'segment': 'a', 'message': f'第 a 段：{OWN_RENDERER_MESSAGE}'},
                {'segment': 'c', 'message': f'第 c 段：{OWN_RENDERER_MESSAGE}'}])
            self.assertEqual(errors, [])
            await page.evaluate('t => window.renderFrame(t)', 1.5)  # b is unaffected
            self.assertGreater(drawn_share(rgb(await page.screenshot(type='png'))), 0.5)  # light-blue clear

    async def test_lost_shared_context_is_reported(self):
        from app.studio.page import studio_page
        async with studio_page(one_segment(THREE_SEGMENT), webgl=True) as (page, errors):
            # Sixteen more contexts make Chromium drop the oldest one: the runtime's.
            await page.evaluate('''() => { window.__extra = [];
              for (let i = 0; i < 16; i++) window.__extra.push(document.createElement('canvas').getContext('webgl2')); }''')
            import asyncio
            diagnostics = []
            for _ in range(50):  # the event is asynchronous; the page CSP rules out wait_for_function
                await asyncio.sleep(0.1)
                diagnostics = await page.evaluate('window.studioDiagnostics')
                if diagnostics:
                    break
            self.assertEqual(diagnostics, [{'segment': None, 'message': '3D 渲染上下文丢失'}])
            self.assertEqual(errors, [])

    async def test_offstage_label_on_canvas_in_subtitles_is_reported(self):
        result = await inspect_film(req(seg_with_code(PARKED_LOW), checks=['bounds']))
        issue = next(i for i in result.issues if i.code == 'bounds')
        self.assertIn('字幕区', issue.message); self.assertIn('parked', issue.element)

    # ---- Task 10: the end-to-end demo film ----------------------------------------------
    async def test_demo_film_has_no_issues(self):
        from app.studio.demo import demo_html, load_film
        # The fixture's hand-written word timings (the image keeps tests/ apart from the app).
        segments, seams, characters = load_film(Path(__file__).with_name('fixtures') / 'studio' / 'demo')
        html = demo_html(segments, seams, characters)
        started = time.monotonic()
        result = await inspect_film(req(html))
        print(f'\n[demo] inspect of the {film_data(html)["duration"]:.2f} s demo film, all checks: '
              f'{time.monotonic() - started:.1f} s')
        self.assertEqual(result.issues, [])
        self.assertEqual(set(result.states), {'parabola', 'vertex', 'story'})


if __name__ == '__main__':
    from renderer.resources import limit_cpu_affinity
    limit_cpu_affinity()
    unittest.main()
