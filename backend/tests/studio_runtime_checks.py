"""Chromium checks for the studio motion runtime. Run inside the renderer image."""
import io
from pathlib import Path
import re
import unittest

from app.studio.contract import ActorState, Camera, Seam, Segment, StageState
from app.studio.film import build_film_html
from app.studio.page import film_needs_webgl, studio_page
from app.studio.runtime.assets import RUNTIME_DIR
from app.studio.words import Word, align_words
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
EMPHASIS = (FIXTURES / 'emphasis_segment.js').read_text(encoding='utf-8')
LAYOUT_DEFAULTS = (FIXTURES / 'layout_defaults_segment.js').read_text(encoding='utf-8')
OVERLAP = (FIXTURES / 'overlap_segment.js').read_text(encoding='utf-8')
SEAM_A = (FIXTURES / 'seam_a_segment.js').read_text(encoding='utf-8')
SEAM_B = (FIXTURES / 'seam_b_segment.js').read_text(encoding='utf-8')
SUBTITLE_TOP = 625  # the program draws subtitles from this y down on a 1280x720 canvas
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


def two_segment_film(*, seam='continue', transition=None, gap=0.4, b_code=SEAM_B):
    """Segment a lasts 2 s (fixture seam_a_segment.js), then a seam of `gap` seconds, then
    segment b (2 s). a says 第一句。 from 0.2 to 1.8 s, b says 第二句。 from 0.1 to 1.6 s."""
    spoken = {'a': ('第一句。', [_ev(.2, .6, '第一'), _ev(1.2, .6, '句')]),
              'b': ('第二句。', [_ev(.1, .6, '第二'), _ev(1.0, .6, '句')])}
    segments = [Segment(id=sid, code=code, duration=2.0, words=align_words(*spoken[sid]),
                        narration=spoken[sid][0], start_state=StageState(), end_state=StageState())
                for sid, code in (('a', SEAM_A), ('b', b_code))]
    seams = [Seam(kind=seam, transition=transition, duration=gap)]
    return build_film_html(segments, seams, style_css='.edu-stage{background:#fdfaf3}')


LONGEST_PIECE = '二次函数图像的顶点坐标可以用配方法求出来对吧对吧'  # 24 wide characters, no break
LONG_SENTENCE = ('同学们好，今天我们一起来研究二次函数的图像和性质，首先我们观察抛物线的开口方向'
                 '对称轴还有顶点坐标这三个关键的特征，然后用配方法求出顶点的位置，再画出图像。')  # 77
UNBREAKABLE = 'W' * 60  # one word wider than the stage at 30 px: the runtime must shrink it


def caption_film():
    """One segment saying the longest allowed piece, a 77-character sentence, and one word
    that cannot be cut; words are two characters, 0.25 s each."""
    text = LONGEST_PIECE + '。' + LONG_SENTENCE + UNBREAKABLE + '。'
    words, t, i = [], 0.0, 0
    while i < len(text):
        if not text[i].isalnum():
            i += 1
            continue
        if text[i] == 'W':
            j = i + len(UNBREAKABLE)
        else:
            j = i + 1 if i + 1 < len(text) and not text[i + 1].isalnum() else min(i + 2, len(text))
        words.append(Word(text[i:j], t, t + 0.2, i, j))
        t += 0.25
        i = j
    segment = Segment(id='a', code='', duration=round(t + 0.5, 2), words=words, narration=text,
                      start_state=StageState(), end_state=StageState())
    return build_film_html([segment], [], style_css='.edu-stage{background:#fdfaf3}')


async def frame_at(page, t):
    await page.evaluate('t=>window.renderFrame(t)', t)
    return await page.screenshot()


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
        text = API_MD.read_text(encoding='utf-8')
        blocks = re.findall(r'```js\n(.*?)```', text, re.S)
        # The 高亮写法 section shows exactly the term-naming pattern, as a body snippet.
        section = text.split('### 高亮写法', 1)[1].split('\n## ', 1)[0]
        self.assertIn(r"ctx.motion.tex('y=\\htmlClass{t-a}{x^2}", section)
        self.assertIn("ctx.motion.highlight('.t-a', ctx.cue('", section)
        characters = '\n'.join(b for b in blocks if 'defineCharacter' in b)
        body = '\n'.join(b for b in blocks if 'defineCharacter' not in b)
        self.assertTrue(characters and body)
        html = plain_film(body, characters=characters, duration=4.5)
        self.assertTrue(film_needs_webgl(html))  # the ctx.three() example
        async with studio_page(html, webgl=True) as (page, errors):
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

            # Same page: tex size is the rendered KaTeX font size in px (fixture: size 44).
            size = await page.evaluate('''parseFloat(getComputedStyle(document.querySelector(
                '.edu-stage [data-edu-id=formula] .katex')).fontSize)''')
            self.assertAlmostEqual(size, 44, 0)

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
            ("ctx.motion.timeline(['今天'], 0, 1, {y: 660})", '字幕区'),
        )
        for code, word in cases:
            async with studio_page(plain_film(code)) as (page, _):
                diagnostics = await page.evaluate('window.studioDiagnostics')
                self.assertTrue(any(d['segment'] == 'a' and d['message'].startswith('第 a 段：')
                                    and word in d['message'] for d in diagnostics), (code, diagnostics))

    async def test_short_emphasis_is_seek_safe(self):
        probe = '''(()=>{const s=document.querySelector('.edu-stage');
            const q=k=>s.querySelector('[data-edu-id='+k+']');
            const shade=s.querySelector('.edu-fx path');
            return {short: getComputedStyle(q('short')).fill, glow: q('short').style.filter,
                    blue: getComputedStyle(q('blue')).fill,
                    shade: shade.getAttribute('opacity') + '|' + shade.style.visibility}})()'''
        async with studio_page(plain_film(EMPHASIS)) as (page, errors):
            seen = []
            for before in (0, 2.5, 1.0, 2.9, 0):  # reach 1.12 from below and from above
                await page.evaluate('t=>window.renderFrame(t)', before)
                await page.evaluate('t=>window.renderFrame(t)', 1.12)
                seen.append(await page.evaluate(probe))
            for frame in seen[1:]:
                self.assertEqual(frame, seen[0])
            self.assertEqual(errors, [])

    async def test_highlight_restores_the_colour_just_before_it(self):
        blue = "getComputedStyle(document.querySelector('.edu-stage [data-edu-id=blue]')).fill"
        async with studio_page(plain_film(EMPHASIS)) as (page, errors):
            # Blue from 0.5 s; highlighted 1.0-1.5 s; must be blue again after, in both directions.
            for t in (0.8, 2.5, 0.8, 2.5):
                await page.evaluate('t=>window.renderFrame(t)', t)
                self.assertEqual(await page.evaluate(blue), 'rgb(0, 0, 255)', t)
            self.assertEqual(errors, [])
            self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])

    async def test_overlapping_emphases_resolve_by_start_time(self):
        probe = '''(()=>{const s=document.querySelector('.edu-stage');
            const q=k=>s.querySelector('[data-edu-id='+k+']');
            return [getComputedStyle(q('word')).fill, getComputedStyle(q('glow')).fill,
                    getComputedStyle(q('glow')).filter]})()'''
        times = [1.05, 1.2, 1.4, 1.6, 2.0]
        orders = (times, times[::-1], [1.4, 2.0, 1.05, 1.6, 1.2], [1.6, 0, 1.2, 3.0, 1.05, 1.4, 2.0])
        async with studio_page(plain_film(OVERLAP)) as (page, errors):
            seen = {}
            for order in orders:
                for t in order:
                    await page.evaluate('t=>window.renderFrame(t)', t)
                    frame = await page.evaluate(probe)
                    if t in seen:
                        self.assertEqual(frame, seen[t], (order, t))
                    seen[t] = frame
            # Both on: the later one (green, from 1.1 s) wins; afterwards blue is back.
            self.assertEqual(seen[1.4][0], 'rgb(0, 255, 0)')
            self.assertEqual(seen[1.4][1], 'rgb(0, 255, 0)')
            self.assertEqual(seen[2.0][0], 'rgb(0, 0, 255)')
            self.assertEqual(seen[2.0][1:], ['rgb(0, 0, 0)', 'none'])
            self.assertEqual(errors, [])
            self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])

    async def test_scene_helper_text_stays_above_subtitles(self):
        # The API.md example of timeline/mapRoute/scaleCompare, their default layouts, and each
        # helper at the lowest y API.md allows, with descenders in every label.
        text = API_MD.read_text(encoding='utf-8')
        blocks = re.findall(r'```js\n(.*?)```', text, re.S)
        example = [b for b in blocks if 'ctx.motion.timeline(' in b]
        self.assertEqual(len(example), 1)
        limits = {name: int(re.search(rf'- `{name}\(.*?y 不要超过 (\d+)', text).group(1))
                  for name in ('timeline', 'scaleCompare')}
        lowest = (f"ctx.motion.timeline([{{time: 'gjpq', label: 'gjpq'}}, '今天'], 0, 1, {{y: {limits['timeline']}}});"
                  f"ctx.motion.scaleCompare([{{label: 'gjpq', value: 2}}], 0, 1, {{y: {limits['scaleCompare']}, x: 0, w: 300}});")
        film = plain_film(example[0] + '\n' + LAYOUT_DEFAULTS + '\n' + lowest, duration=4.5)
        async with studio_page(film) as (page, errors):
            await page.evaluate('t=>window.renderFrame(t)', 3.0)
            boxes = await page.evaluate('''(()=>{const s=document.querySelector('.edu-stage');
                const top=s.getBoundingClientRect().top;
                return Array.from(s.querySelectorAll('text')).map(t=>[t.textContent,
                    t.getBoundingClientRect().bottom-top])})()''')  # unrounded
            self.assertGreaterEqual(len(boxes), 14)
            self.assertEqual([b for b in boxes if b[1] > SUBTITLE_TOP], [])
            self.assertEqual(errors, [])
            self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])

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

    async def test_continue_seam_holds_last_frame(self):
        async with studio_page(two_segment_film(seam='continue', gap=0.4)) as (page, errors):
            # Segment a lasts 2 s, b starts at 2.4 s.
            a_end = await frame_at(page, 1.9999)
            mid = await frame_at(page, 2.2)
            self.assertTrue(same_png(a_end, mid))
            self.assertFalse(same_png(mid, await frame_at(page, 2.4)))  # b's first frame
            self.assertTrue(same_png(mid, await frame_at(page, 2.2)))  # reached backward
            self.assertEqual(errors, [])
            self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])

    async def test_each_transition_runs_inside_gap_only(self):
        for name in ('push', 'wipe', 'zoom', 'match', 'fade'):
            async with studio_page(two_segment_film(seam='transition', transition=name, gap=0.8)) as (page, errors):
                a_end = await frame_at(page, 1.9999)
                start, middle, end = [await frame_at(page, t) for t in (2.0, 2.4, 2.8)]
                self.assertTrue(same_png(a_end, start), name)
                self.assertFalse(same_png(start, middle), name)
                self.assertFalse(same_png(middle, end), name)
                self.assertTrue(same_png(end, await frame_at(page, 2.8)), name)
                self.assertTrue(same_png(middle, await frame_at(page, 2.4)), name)  # reached backward
                self.assertEqual(errors, [], name)
                self.assertEqual(await page.evaluate('window.studioDiagnostics'), [], name)
                self.assertEqual(await page.evaluate('typeof EduStudio.transitions.' + name), 'function')
                if name == 'match':
                    await self._assert_match_interpolates(page)

    async def _assert_match_interpolates(self, page):
        # a leaves the matched dot at (500, 480), r 40; b starts it at (900, 250), r 70.
        dot = '''t=>{window.renderFrame(t);
            const l=Array.from(document.querySelectorAll('.edu-stage .edu-layer'))
                .filter(e=>getComputedStyle(e).opacity==='1')[0];
            const r=l.querySelector('[data-edu-match=dot]').getBoundingClientRect();
            return [l.dataset.segment, r.left+r.width/2, r.top+r.height/2, r.width]}'''
        seen = {}
        for t in (2.2, 2.6, 2.8, 2.2, 0.5, 2.6):  # progress 0.25 and 0.75, then backward
            got = await page.evaluate(dot, t)
            if t in seen:
                self.assertEqual(got, seen[t], t)
            seen[t] = got
        for t, layer in ((2.2, 'a'), (2.6, 'b')):
            seg_id, x, y, w = seen[t]
            self.assertEqual(seg_id, layer, t)
            self.assertTrue(510 < x < 890 and 260 < y < 470 and 82 < w < 138, (t, seen[t]))
        self.assertLess(seen[2.2][1], seen[2.6][1])  # moving from a's place towards b's

    async def test_caption_shows_current_sentence(self):
        caption = '.edu-caption'
        async with studio_page(two_segment_film(seam='continue', gap=0)) as (page, _):
            await page.evaluate('t=>window.renderFrame(t)', 0.5)
            self.assertEqual(await page.locator(caption).inner_text(), '第一句。')
            box = await page.locator(caption).bounding_box()
            self.assertGreaterEqual(box['y'], SUBTITLE_TOP)
            self.assertLessEqual(box['y'] + box['height'], 720)
            self.assertAlmostEqual(box['x'] + box['width'] / 2, 640, 0)
            css = await page.locator(caption).evaluate(
                'e=>[getComputedStyle(e).fontSize, getComputedStyle(e).fontFamily, getComputedStyle(e).backgroundColor]')
            self.assertEqual(css[0], '30px')
            self.assertIn('Noto Sans SC', css[1])
            self.assertRegex(css[2], r'^rgba\(.*, 0\.\d+\)$')  # translucent backing
            for t, text in ((1.9, ''), (2.5, '第二句。'), (0.5, '第一句。'), (0.1, '')):
                await page.evaluate('t=>window.renderFrame(t)', t)
                self.assertEqual((await page.locator(caption).text_content()).strip(), text, t)

    async def test_captions_are_single_lines_inside_the_subtitle_zone(self):
        probe = '''(()=>{const e=document.querySelector('.edu-caption');const r=e.getBoundingClientRect();
            const s=document.querySelector('.edu-stage').getBoundingClientRect();
            return {text: e.textContent, top: r.top-s.top, bottom: r.bottom-s.top, left: r.left-s.left,
                    right: r.right-s.left, height: r.height, size: parseFloat(getComputedStyle(e).fontSize),
                    lines: Math.round((r.height - 8) / (parseFloat(getComputedStyle(e).lineHeight)))}})()'''
        async with studio_page(caption_film()) as (page, errors):
            captions = await page.evaluate(
                'JSON.parse(document.getElementById("edu-studio-film").textContent).captions')
            self.assertEqual(captions[0]['text'], LONGEST_PIECE + '。')
            long_pieces = [c for c in captions if c['text'][0] not in 'W' and c is not captions[0]]
            self.assertGreater(len(long_pieces), 2)  # the 77-character sentence: several captions
            self.assertEqual(''.join(c['text'] for c in long_pieces), LONG_SENTENCE)
            for c in captions:
                await page.evaluate('t=>window.renderFrame(t)', (c['start'] + c['end']) / 2)
                box = await page.evaluate(probe)
                self.assertEqual(box['text'], c['text'])
                self.assertEqual(box['lines'], 1, box)
                self.assertGreaterEqual(box['top'], SUBTITLE_TOP, box)
                self.assertLessEqual(box['bottom'], 720, box)
                self.assertGreaterEqual(box['left'], 0, box)
                self.assertLessEqual(box['right'], 1280, box)
                if c['text'][0] == 'W':
                    self.assertLess(box['size'], 30, box)  # shrunk to fit, not wrapped
                else:
                    self.assertEqual(box['size'], 30, box)
            # The shrunk size depends on the text only: same after a different history.
            last = captions[-1]
            sizes = []
            for before in (0, last['end'] - 0.01, captions[1]['start']):
                await page.evaluate('t=>window.renderFrame(t)', before)
                await page.evaluate('t=>window.renderFrame(t)', (last['start'] + last['end']) / 2)
                sizes.append((await page.evaluate(probe))['size'])
            self.assertEqual(len(set(sizes)), 1, sizes)
            self.assertEqual(errors, [])

    async def test_broken_segment_is_reported_by_id(self):
        from PIL import Image

        def pixel(png, xy):
            return Image.open(io.BytesIO(png)).convert('RGB').getpixel(xy)
        async with studio_page(two_segment_film(b_code='throw new Error("坏了")')) as (page, errors):
            diag = await page.evaluate('window.studioDiagnostics')
            self.assertTrue(any(d['segment'] == 'b' and d['message'].startswith('第 b 段：')
                                and '坏了' in d['message'] for d in diag), diag)
            # Segment a still draws: its blue square is at x 175..335 at 0.5 s.
            r, g, b = pixel(await frame_at(page, 0.5), (250, 230))
            self.assertTrue(abs(r - 43) < 8 and abs(g - 108) < 8 and abs(b - 176) < 8, (r, g, b))
            # b's layer is empty: background where a's square was and nothing else.
            empty = await frame_at(page, 3.5)
            for xy in ((250, 230), (450, 230), (900, 250)):
                self.assertEqual(pixel(empty, xy), (253, 250, 243), xy)  # stage background only
            self.assertEqual(errors, [])

    async def test_held_outgoing_layer_keeps_its_last_frame_in_transition(self):
        # a's word is highlighted green from 1.5 s to its end; its canvas bar is full from 1.5 s.
        probe = '''(()=>{const a=document.querySelector('.edu-stage [data-segment=a]');
            const px=a.querySelector('canvas').getContext('2d').getImageData(150, 50, 1, 1).data;
            return [getComputedStyle(a.querySelector('[data-edu-id=word]')).fill,
                    Array.from(px).join(','), getComputedStyle(a).visibility]})()'''
        async with studio_page(two_segment_film(seam='transition', transition='push', gap=0.8)) as (page, errors):
            a_end = await frame_at(page, 1.9999)
            seen = []
            for before in (0, 4.8, 1.0, 3.5, 2.0):  # reach the middle of the push from both sides
                await page.evaluate('t=>window.renderFrame(t)', before)
                shot = await frame_at(page, 2.4)
                seen.append((shot, await page.evaluate(probe)))
            for shot, state in seen:
                self.assertEqual(state, ['rgb(0, 170, 0)', '0,0,0,255', 'visible'])
                self.assertTrue(same_png(shot, seen[0][0]))
            self.assertFalse(same_png(seen[0][0], a_end))  # the push is under way
            self.assertEqual(errors, [])
            self.assertEqual(await page.evaluate('window.studioDiagnostics'), [])


if __name__ == '__main__':
    from renderer.resources import limit_cpu_affinity
    limit_cpu_affinity()
    unittest.main()
