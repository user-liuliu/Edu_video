import io
import json
import re
import wave

import pytest

from app.studio.contract import ActorState, Seam, Segment, StageState
from app.studio.film import (FilmError, assemble_audio, build_film_html, film_captions,
                             film_duration, timeline)
from app.studio.runtime.assets import runtime_url
from app.studio.words import Word


def seg(id, duration, code='', start=None, end=None, **extra):
    return Segment(id=id, code=code, duration=duration, words=extra.pop('words', []),
                   narration=extra.pop('narration', ''), start_state=start or StageState(),
                   end_state=end or StageState(), **extra)


def wav(seconds, rate=24000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b'\x01\x00' * round(seconds * rate))
    return buf.getvalue()


def wav_seconds(data):
    with wave.open(io.BytesIO(data), 'rb') as w:
        return w.getnframes() / w.getframerate()


def film_data(html):
    return json.loads(re.search(r'id="edu-studio-film">(.*?)</script>', html, re.S)[1])


def test_timeline_places_seam_gaps_between_segments():
    segs = [seg('a', 4.0), seg('b', 3.0)]
    t = timeline(segs, [Seam(kind='transition', transition='push', duration=0.8)])
    assert [(x.get('id') or x['kind'], x['start'], x['end']) for x in t] == [
        ('a', 0, 4.0), ('transition', 4.0, 4.8), ('b', 4.8, 7.8)]
    assert film_duration(segs, [Seam(kind='continue', duration=0.3)]) == pytest.approx(7.3)


def test_timeline_entry_shapes():
    t = timeline([seg('a', 2), seg('b', 2)], [Seam(kind='transition', transition='wipe', duration=0.5)])
    assert t[0] == {'id': 'a', 'start': 0, 'end': 2}
    assert t[1] == {'seam': 0, 'start': 2, 'end': 2.5, 'kind': 'transition', 'transition': 'wipe'}
    assert t[2]['id'] == 'b'


def test_build_film_html_wraps_segments_and_embeds_runtime():
    html = build_film_html([seg('a', 2), seg('b', 2)], [Seam(kind='continue', duration=0.2)])
    assert 'EduStudio.defineSegment("a", function(ctx){' in html
    assert runtime_url('gsap.min.js') in html and "connect-src 'none'" in html
    data = json.loads(re.search(r'id="edu-studio-film">(.*?)</script>', html, re.S)[1])
    assert data['duration'] == pytest.approx(4.2)


def test_build_film_html_script_order_and_csp():
    html = build_film_html([seg('a', 2)], [], characters_code='var CH=1;', style_css='.x{color:red}')
    csp = ("default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
           "font-src 'self'; img-src data:; connect-src 'none'")
    assert f'<meta http-equiv="Content-Security-Policy" content="{csp}">' in html
    order = [html.index(runtime_url(n)) for n in (
        'gsap.min.js', 'DrawSVGPlugin.min.js', 'MorphSVGPlugin.min.js', 'MotionPathPlugin.min.js',
        'SplitText.min.js', 'katex.min.js', 'three.iife.js', 'rough.js', 'edu_motion.js', 'film_runtime.js')]
    assert order == sorted(order)
    for css in ('katex.min.css', 'fonts.css'):
        assert f'<link rel="stylesheet" href="{runtime_url(css)}">' in html
    assert f'<script src="{runtime_url("gsap.min.js")}"></script>' in html
    assert '<style>.x{color:red}</style>' in html
    assert html.index('var CH=1;') < html.index('EduStudio.defineSegment')
    assert html.rstrip().splitlines()[-1].startswith('<script>EduFilm.boot()</script>')


def test_build_film_html_json_block_contents():
    words = [Word('你好', 0.0, 0.5, 0, 2)]
    a = seg('a', 2, narration='你好。', words=words)
    html = build_film_html([a, seg('b', 2)], [Seam(kind='transition', transition='fade', duration=0.5)],
                           width=1280, height=720)
    data = film_data(html)
    assert set(data) == {'timeline', 'duration', 'width', 'height', 'segments', 'seams', 'captions'}
    assert (data['width'], data['height']) == (1280, 720)
    assert data['duration'] == pytest.approx(4.5)
    assert set(data['segments'][0]) == {'id', 'duration', 'words', 'narration', 'highlights',
                                        'start_state', 'end_state'}
    assert data['segments'][0]['words'][0]['text'] == '你好'
    assert data['seams'] == [{'kind': 'transition', 'transition': 'fade', 'duration': 0.5}]
    assert data['captions'] == [{'text': '你好。', 'start': 0.0, 'end': 0.5}]


def test_json_block_escapes_html_in_narration():
    html = build_film_html([seg('a', 2, narration='</script><b>x')], [])
    block = re.search(r'id="edu-studio-film">(.*?)</script>', html, re.S)[1]
    assert '<' not in block
    assert film_data(html)['segments'][0]['narration'] == '</script><b>x'


def test_build_film_rejects_lint_mismatch_and_bad_seams():
    with pytest.raises(FilmError, match='第 b 段.*setInterval'):
        build_film_html([seg('a', 2), seg('b', 2, code='setInterval(f,9)')], [Seam(kind='continue', duration=0)])
    moved = seg('b', 2, start=StageState(actors={'kr': ActorState(x=300, y=600)}))
    with pytest.raises(FilmError, match='接缝'):
        build_film_html([seg('a', 2, end=StageState(actors={'kr': ActorState(x=100, y=600)})), moved],
                        [Seam(kind='continue', duration=0)])
    with pytest.raises(FilmError):
        build_film_html([seg('a', 2)], [Seam(kind='continue', duration=0)])


def test_transition_seams_do_not_require_matching_states():
    moved = seg('b', 2, start=StageState(actors={'kr': ActorState(x=300, y=600)}))
    build_film_html([seg('a', 2), moved], [Seam(kind='transition', transition='fade', duration=0.5)])


def test_transition_longer_than_segment_rejected():
    with pytest.raises(FilmError, match='接缝 0 比相邻片段还长'):
        build_film_html([seg('a', 1.0), seg('b', 3)], [Seam(kind='transition', transition='wipe', duration=0.9)])


def test_transition_exactly_half_of_shorter_segment_is_allowed():
    build_film_html([seg('a', 1.0), seg('b', 3)], [Seam(kind='transition', transition='wipe', duration=0.5)])


def test_missing_seams_for_multiple_segments_rejected():
    with pytest.raises(FilmError, match='接缝'):
        build_film_html([seg('a', 2), seg('b', 2)], [])
    with pytest.raises(FilmError):
        build_film_html([], [])
    with pytest.raises(FilmError):
        timeline([seg('a', 2), seg('b', 2)], [])


def test_duplicate_segment_ids_rejected():
    with pytest.raises(FilmError, match='重复'):
        build_film_html([seg('a', 2), seg('a', 2)], [Seam(kind='continue', duration=0)])


def test_script_breakout_in_code_rejected():
    for bad in ('x="</script><b>"', 'x="</SCRIPT >"', 'x="<!--"'):
        with pytest.raises(FilmError, match='第 a 段'):
            build_film_html([seg('a', 2, code=bad)], [])
    with pytest.raises(FilmError, match='角色'):
        build_film_html([seg('a', 2)], [], characters_code='</script>')
    with pytest.raises(FilmError, match='样式'):
        build_film_html([seg('a', 2)], [], style_css='</style>')


def test_segment_code_is_inserted_verbatim():
    html = build_film_html([seg('a', 2, code='ctx.tl.to(1,{x:2});')], [])
    assert 'EduStudio.defineSegment("a", function(ctx){\nctx.tl.to(1,{x:2});\n});</script>' in html


def test_film_captions_offset_by_segment_start():
    a = seg('a', 2, narration='你好。', words=[Word('你好', 0.1, 0.9, 0, 2)])
    b = seg('b', 3, narration='再见。', words=[Word('再见', 0.2, 1.0, 0, 2)])
    caps = film_captions([a, b], [Seam(kind='transition', transition='fade', duration=0.5)])
    assert caps == [{'text': '你好。', 'start': pytest.approx(0.1), 'end': pytest.approx(0.9)},
                    {'text': '再见。', 'start': pytest.approx(2.7), 'end': pytest.approx(3.5)}]


def test_film_captions_are_single_line_length():
    text = '同学们好今天我们一起来研究二次函数的图像和性质首先观察抛物线的开口方向。'
    words = [Word(text[i:i + 2], 0.2 * i, 0.2 * i + 0.3, i, i + 2) for i in range(0, len(text) - 1, 2)]
    caps = film_captions([seg('a', 10, narration=text, words=words)], [])
    assert len(caps) == 2
    assert ''.join(c['text'] for c in caps) == text
    assert all(len(c['text'].rstrip('。')) <= 24 for c in caps)
    assert caps[0]['end'] == pytest.approx(caps[1]['start'])


def test_assemble_audio_inserts_silence_and_checks_lengths():
    segs = [seg('a', 1.0), seg('b', 2.0)]
    out = assemble_audio([wav(1.0), wav(2.0)], segs, [Seam(kind='transition', transition='fade', duration=0.5)])
    assert wav_seconds(out) == pytest.approx(3.5, abs=1/48000)
    with pytest.raises(FilmError, match='第 b 段配音时长'):
        assemble_audio([wav(1.0), wav(1.5)], segs, [Seam(kind='continue', duration=0)])


def test_assemble_audio_silence_is_zeroed_between_clips():
    segs = [seg('a', 1.0), seg('b', 1.0)]
    out = assemble_audio([wav(1.0), wav(1.0)], segs, [Seam(kind='continue', duration=0.5)])
    with wave.open(io.BytesIO(out), 'rb') as w:
        frames = w.readframes(w.getnframes())
        rate = w.getframerate()
    gap = frames[2 * rate:2 * (rate + rate // 2)]
    assert gap == b'\x00\x00' * (rate // 2)
    assert frames[:2] == b'\x01\x00' and frames[2 * (rate + rate // 2):][:2] == b'\x01\x00'


def test_assemble_audio_allows_one_frame_of_drift_and_rejects_more():
    segs = [seg('a', 1.0)]
    assemble_audio([wav(1.0 + 1 / 40)], segs, [])
    with pytest.raises(FilmError, match='第 a 段配音时长与动画不一致'):
        assemble_audio([wav(1.0 + 1 / 20)], segs, [])


def test_assemble_audio_rejects_wrong_clip_count_and_mixed_formats():
    segs = [seg('a', 1.0), seg('b', 1.0)]
    seams = [Seam(kind='continue', duration=0)]
    with pytest.raises(FilmError):
        assemble_audio([wav(1.0)], segs, seams)
    with pytest.raises(FilmError, match='格式'):
        assemble_audio([wav(1.0, 24000), wav(1.0, 16000)], segs, seams)
    with pytest.raises(FilmError, match='第 a 段'):
        assemble_audio([b'not a wav', wav(1.0)], segs, seams)


def test_film_needs_webgl_only_for_code_that_uses_three():
    from app.studio.page import film_needs_webgl
    plain = build_film_html([seg('a', 2, code='ctx.svg.innerHTML = "";')], [])
    assert 'three.iife.js' in plain  # every film loads the bundle; that alone needs no WebGL
    assert not film_needs_webgl(plain)
    # Narration lives in the film JSON block, not in code.
    assert not film_needs_webgl(build_film_html([seg('a', 2, narration='THREE.js 是什么')], []))
    assert film_needs_webgl(build_film_html([seg('a', 2, code='const r = new THREE.WebGLRenderer();')], []))
    assert film_needs_webgl(build_film_html([seg('a', 2)], [], characters_code='const {Mesh} = THREE;'))
    assert not film_needs_webgl(build_film_html([seg('a', 2, code='const MY_THREE = 3;')], []))
