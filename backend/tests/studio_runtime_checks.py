"""Chromium checks for the studio motion runtime. Run inside the renderer image."""
import io
from pathlib import Path
import re
import unittest

from app.studio.contract import ActorState, Camera, Segment, StageState
from app.studio.film import build_film_html
from app.studio.page import studio_page
from app.studio.runtime.assets import RUNTIME_DIR
from app.studio.words import align_words
from app.videos.direct_render import same_pixels

FIXTURES = Path(__file__).with_name('fixtures') / 'studio'
CHARACTERS = (FIXTURES / 'characters.js').read_text(encoding='utf-8')
CORE = (FIXTURES / 'core_segment.js').read_text(encoding='utf-8')
MUTATING_PART = CORE + '\n' + (FIXTURES / 'mutating_part.js').read_text(encoding='utf-8')
SCALING_PART = CORE + '\n' + (FIXTURES / 'scaling_part.js').read_text(encoding='utf-8')
MOVING_PART = CORE + '\n' + (FIXTURES / 'moving_part.js').read_text(encoding='utf-8')
CANVAS = (FIXTURES / 'canvas_segment.js').read_text(encoding='utf-8')
TEXT_WIDTH = (FIXTURES / 'text_width_segment.js').read_text(encoding='utf-8')
TEXT_SWITCH = (FIXTURES / 'text_switch_segment.js').read_text(encoding='utf-8')
THROWING_PAINTER = (FIXTURES / 'throwing_painter_segment.js').read_text(encoding='utf-8')
THROWING_BUILD = (FIXTURES / 'throwing_build_segment.js').read_text(encoding='utf-8')
KATEX = (FIXTURES / 'katex_segment.js').read_text(encoding='utf-8')
KATEX_HELPER = (FIXTURES / 'katex_helper.js').read_text(encoding='utf-8')
KATEX_HELPER_SEGMENT = (FIXTURES / 'katex_helper_segment.js').read_text(encoding='utf-8')
EFFECTS = (FIXTURES / 'effects_segment.js').read_text(encoding='utf-8')
API_MD = RUNTIME_DIR / 'API.md'

NARRATION = '二次函数的图像是一条抛物线，顶点就是它的最低点。'


def _ev(start, duration, text):
    return {'offset': round(start * 1e7), 'duration': round(duration * 1e7), 'text': text}


WORDS = align_words(NARRATION, [
    _ev(0.10, .35, '二次'), _ev(.46, .33, '函数'), _ev(.79, .09, '的'), _ev(.89, .51, '图像'),
    _ev(1.50, .19, '是'), _ev(1.70, .24, '一条'), _ev(1.96, .56, '抛物线'), _ev(2.91, .44, '顶点'),
    _ev(3.38, .14, '就'), _ev(3.51, .09, '是'), _ev(3.61, .11, '它'), _ev(3.73, .07, '的'),
    _ev(3.83, .55, '最低点')])


def core_film(code=CORE):
    segment = Segment(
        id='a', code=code, duration=4.5, words=WORDS, narration=NARRATION,
        start_state=StageState(actors={'kr': ActorState(x=300, y=600)}),
        end_state=StageState(camera=Camera(x=640, y=450, zoom=1.4),
                             actors={'kr': ActorState(x=500, y=600, pose={'arm_r': -60})},
                             keep=['vertex']))
    return build_film_html([segment], [], characters_code=CHARACTERS,
                           style_css='.edu-stage{background:#fdfaf3}')


def plain_film(code, *, characters='', duration=3.0):
    segment = Segment(id='a', code=code, duration=duration, words=WORDS, narration=NARRATION,
                      start_state=StageState(), end_state=StageState())
    return build_film_html([segment], [], characters_code=characters,
                           style_css='.edu-stage{background:#fdfaf3}')


def effects_film(code=EFFECTS):
    segment = Segment(id='fx', code=code, duration=7.0, words=WORDS, narration=NARRATION,
                      start_state=StageState(), end_state=StageState())
    return build_film_html([segment], [], style_css='.edu-stage{background:#fdfaf3}')


def same_png(first, second):
    import numpy as np
    from PIL import Image

    def decode(data):
        image = Image.open(io.BytesIO(data)).convert('RGB')
        return np.asarray(image.resize((640, 360))).astype('int16')
    return same_pixels(decode(first), decode(second))


class StudioRuntimeChecks(unittest.IsolatedAsyncioTestCase):
    async def test_seek_is_deterministic_forward_and_backward(self):
        async with studio_page(core_film()) as (page, errors):
            times = [0, 0.5, 1.3, 2.9, 3.4, 2.0, 0.1, 3.4]
            shots = {}
            for t in times:
                await page.evaluate('t=>window.renderFrame(t)', t)
                png = await page.screenshot()
                if t in shots:
                    self.assertTrue(same_png(shots[t], png), t)
                shots[t] = png
            # The animation really moves: different times give different pictures.
            self.assertFalse(same_png(shots[0.5], shots[3.4]))
            self.assertEqual(errors, [])
            self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])

    async def test_cue_and_missing_cue(self):
        async with studio_page(core_film()) as (page, _):
            self.assertAlmostEqual(await page.evaluate('EduFilm.instantiate("a").cue("顶点")'), 2.91, 2)
            self.assertAlmostEqual(await page.evaluate('EduFilm.instantiate("a").cueEnd("顶点")'), 3.35, 2)
            msg = await page.evaluate('(()=>{try{EduFilm.instantiate("a").cue("开口")}catch(e){return e.message}})()')
            self.assertIn('开口', msg)
            self.assertIn('第 a 段', msg)

    async def test_start_state_applied_and_end_state_measured(self):
        async with studio_page(core_film()) as (page, _):
            s0 = await page.evaluate('EduFilm.instantiate("a").state(0)')
            s1 = await page.evaluate('(f=>f.state(f.tl.duration()))(EduFilm.instantiate("a"))')
            self.assertEqual((s0['actors']['kr']['x'], s0['actors']['kr']['y']), (300, 600))
            self.assertAlmostEqual(s0['camera']['zoom'], 1, 3)
            self.assertAlmostEqual(s1['actors']['kr']['x'], 500, 0)
            self.assertAlmostEqual(s1['actors']['kr']['pose']['arm_r'], -60, 0)
            self.assertAlmostEqual(s1['camera']['zoom'], 1.4, 2)
            self.assertAlmostEqual(s1['camera']['y'], 450, 0)
            self.assertEqual(s1['keep'], ['vertex'])

    async def test_actor_geometry_never_changes(self):
        async with studio_page(core_film()) as (page, _):
            digests = await page.evaluate('''(()=>{const f=EduFilm.instantiate("a");const d=[];
                for(const t of [0,1,2,3]){f.tl.seek(t);d.push(f.geometryDigest())}return d})()''')
            self.assertEqual(len(set(digests)), 1)
        async with studio_page(core_film(code=MUTATING_PART)) as (page, errors):
            await page.evaluate('t=>window.renderFrame(t)', 1.5)
            self.assertTrue(any('角色零件形状被修改' in e['message'] for e in await page.evaluate('window.studioDiagnostics')))

    async def test_part_groups_may_only_rotate_about_their_pivot(self):
        for code in (SCALING_PART, MOVING_PART):
            async with studio_page(core_film(code=code)) as (page, _):
                await page.evaluate('t=>window.renderFrame(t)', 2.5)
                diagnostics = await page.evaluate('window.studioDiagnostics')
                self.assertTrue(any('角色零件形状被修改' in e['message'] for e in diagnostics), diagnostics)
        async with studio_page(core_film()) as (page, _):  # core pose() rotates arm_r by -60 degrees
            for t in (1.5, 4.0, 0):
                await page.evaluate('t=>window.renderFrame(t)', t)
            self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])

    async def test_canvas_frame_does_not_depend_on_seek_history(self):
        pixels = '''Array.from(document.querySelector('.edu-stage canvas').getContext('2d')
            .getImageData(0, 0, 200, 100).data).join(',')'''
        async with studio_page(plain_film(CANVAS)) as (page, errors):
            seen = {}
            for t in (0, 0.5, 1.5, 2.5, 0.5, 0, 1.5):
                await page.evaluate('t=>window.renderFrame(t)', t)
                frame = (await page.evaluate(pixels), await page.screenshot())
                if t in seen:
                    self.assertEqual(seen[t][0], frame[0], f'canvas pixels changed at {t}')
                    self.assertTrue(same_png(seen[t][1], frame[1]), t)
                seen[t] = frame
            self.assertNotEqual(seen[0][0], seen[2.5][0])
            self.assertEqual(errors, [])

    async def test_segments_are_built_with_loaded_fonts(self):
        async with studio_page(plain_film(TEXT_WIDTH)) as (page, _):
            built, now = await page.evaluate('''(()=>{const w=document.querySelector('.edu-stage .edu-world');
                return [+w.dataset.builtWidth, w.querySelector('text').getComputedTextLength()]})()''')
            self.assertAlmostEqual(built, now, 1)
            self.assertAlmostEqual(await page.evaluate('+EduFilm.instantiate("a").root.dataset.builtWidth'), now, 1)

    async def test_formulas_are_built_with_loaded_katex_fonts(self):
        # Direct call in segment code, and a call through a helper from the character code,
        # where no script on the page contains the library name followed by a dot.
        for code, characters in ((KATEX, ''), (KATEX_HELPER_SEGMENT, KATEX_HELPER)):
            async with studio_page(plain_film(code, characters=characters)) as (page, _):
                self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])
                built, now = await page.evaluate('''(()=>{const w=document.querySelector('.edu-stage .edu-world');
                    return [+w.dataset.builtWidth, w.querySelector('div').getBoundingClientRect().width]})()''')
                self.assertAlmostEqual(built, now, 1, code[:40])

    async def test_tl_set_text_switch_is_seek_safe(self):
        label = "document.querySelector('.edu-stage [data-edu-id=label]').textContent"
        called = "document.querySelector('.edu-stage [data-edu-id=called]').textContent"
        expected = {0: 'A', 0.5: 'A', 2.5: 'B'}
        async with studio_page(plain_film(TEXT_SWITCH)) as (page, errors):
            self.assertEqual(await page.evaluate(label), 'A')  # right after studioReady
            for t in (0, 0.5, 2.5, 0.5, 0, 2.5, 0.5):  # forward, backward, forward again
                await page.evaluate('t=>window.renderFrame(t)', t)
                self.assertEqual(await page.evaluate(label), expected[t], t)
                self.assertEqual(await page.evaluate(called), 'A', t)  # tl.call never drives visible state
            self.assertEqual(errors, [])

    async def test_failing_segment_draws_nothing_and_is_named(self):
        from PIL import Image

        async def centre(page, t):
            await page.evaluate('t=>window.renderFrame(t)', t)
            return Image.open(io.BytesIO(await page.screenshot())).convert('RGB').getpixel((640, 360))
        # The painter throws only from 1 s on: red before, nothing from that segment afterwards.
        for code, before, after in ((THROWING_PAINTER, (0.5,), (1.5, 0.5, 0)), (THROWING_BUILD, (), (0.5, 0))):
            async with studio_page(plain_film(code)) as (page, _):
                for t in before:
                    self.assertEqual(await centre(page, t), (255, 0, 0), t)
                for t in after:
                    self.assertNotEqual(await centre(page, t), (255, 0, 0), (code[:30], t))
                diagnostics = await page.evaluate('window.studioDiagnostics')
                self.assertTrue(any(d['segment'] == 'a' and d['message'].startswith('第 a 段')
                                    and 'boom' in d['message'] for d in diagnostics), diagnostics)

    async def test_api_examples_run_as_segment_code(self):
        # Blocks calling defineCharacter are character code; every other block is a segment body.
        blocks = re.findall(r'```js\n(.*?)```', API_MD.read_text(encoding='utf-8'), re.S)
        characters = '\n'.join(b for b in blocks if 'defineCharacter' in b)
        body = '\n'.join(b for b in blocks if 'defineCharacter' not in b)
        self.assertTrue(characters and body)
        async with studio_page(plain_film(body, characters=characters, duration=4.5)) as (page, errors):
            await page.evaluate('t=>window.renderFrame(t)', 4.0)
            self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])
            self.assertEqual(errors, [])

    async def test_tex_term_highlight_lands_on_cue(self):
        # Fixture: tex('y=\\htmlClass{t-a}{x^2}-2x-3') highlighted with highlight('.t-a') at cue("顶点").
        term = '.edu-stage .t-a'  # instantiate() adds a second copy in the sandbox
        async with studio_page(effects_film()) as (page, errors):
            hs = await page.evaluate('EduFilm.instantiate("fx").highlights()')
            self.assertEqual(hs[0]['target'], '.t-a')
            self.assertAlmostEqual(hs[0]['at'], 2.91, 2)
            self.assertEqual(hs[0]['segment'], 'fx')
            await page.evaluate('t=>window.renderFrame(t)', 2.0)
            before = await page.locator(term).evaluate('e=>getComputedStyle(e).color')
            await page.evaluate('t=>window.renderFrame(t)', 3.3)
            after = await page.locator(term).evaluate('e=>getComputedStyle(e).color')
            self.assertNotEqual(before, after)
            self.assertEqual(errors, [])

            # Same page: plot() maps the function into its box.
            # Fixture: plot(x=>x*x-2*x-3, {xRange:[-2,4], yRange:[-5,5], box:{x:100,y:80,w:600,h:400}}).
            p = await page.evaluate('EduFilm.instantiate("fx").plotProbe(1)')  # toScreen(1, f(1))
            self.assertAlmostEqual(p['x'], 100 + 600 * 3 / 6, 0)
            self.assertAlmostEqual(p['y'], 80 + 400 * (5 - (-4)) / 10, 0)

            # Same page: drawPath progress follows time (fixture: from 1.0 s for 2.0 s, ease 'none').
            prog = await page.evaluate('''(()=>{const f=EduFilm.instantiate("fx");f.tl.seek(2.0);
                const e=f.root.querySelector("#curve");
                return parseFloat(getComputedStyle(e).strokeDashoffset)/e.getTotalLength()})()''')
            self.assertAlmostEqual(abs(prog), 0.5, 1)

    async def test_bad_effect_input_names_the_segment(self):
        cases = (
            ("ctx.motion.highlight('.nope', 1)", '.nope'),
            ("ctx.motion.plot(x=>x, {xRange: [3, 1], yRange: [0, 1], box: {x: 0, y: 0, w: 100, h: 100}})", 'xRange'),
            (r"ctx.motion.tex('\\frac{1}{', {})", 'tex'),
        )
        for code, word in cases:
            async with studio_page(plain_film(code)) as (page, _):
                diagnostics = await page.evaluate('window.studioDiagnostics')
                self.assertTrue(any(d['segment'] == 'a' and d['message'].startswith('第 a 段：')
                                    and word in d['message'] for d in diagnostics), (code, diagnostics))

    async def test_every_effect_is_seek_safe(self):
        # Same time, same picture: covers tex, highlight, drawPath, plot, spotlight, circle, follow,
        # morph, splitText, rough, timeline, mapRoute and scaleCompare.
        for name in ('tex', 'highlight', 'drawPath', 'plot', 'spotlight', 'circle', 'follow', 'morph',
                     'splitText', 'rough', 'timeline', 'mapRoute', 'scaleCompare'):
            self.assertIn(f'm.{name}(', EFFECTS, name)
        async with studio_page(effects_film()) as (page, errors):
            shots = {}
            for t in [0.5, 4.5, 2.2, 6.0, 0.5, 6.0, 2.2]:
                await page.evaluate('t=>window.renderFrame(t)', t)
                png = await page.screenshot()
                if t in shots:
                    self.assertTrue(same_png(shots[t], png), t)
                shots[t] = png
            self.assertFalse(same_png(shots[0.5], shots[4.5]))
            self.assertEqual(errors, [])
            self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])

    async def test_no_autonomous_playback(self):
        async with studio_page(core_film()) as (page, _):
            await page.evaluate('t=>window.renderFrame(t)', 1.0)
            a = await page.screenshot()
            await page.wait_for_timeout(300)
            b = await page.screenshot()
            self.assertTrue(same_png(a, b))


if __name__ == '__main__':
    from renderer.resources import limit_cpu_affinity
    limit_cpu_affinity()
    unittest.main()
