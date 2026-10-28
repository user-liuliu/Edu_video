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
    # A label whose box reaches into the subtitle zone, and an offstage one that must be ignored.
    return one_segment(
        f"ctx.svg.innerHTML = '<text data-edu-id=\"low\" x=\"640\" y=\"{y}\" text-anchor=\"middle\" "
        "font-size=\"40\">字幕区里的字</text>' + '<text data-edu-id=\"parked\" data-edu-offstage=\"1\" "
        "x=\"640\" y=\"700\" font-size=\"40\">候场</text>';")


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


if __name__ == '__main__':
    from renderer.resources import limit_cpu_affinity
    limit_cpu_affinity()
    unittest.main()
