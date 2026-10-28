import base64
import io
import json
import re
import wave
from pathlib import Path

import pytest

from app.studio import demo
from app.studio.contract import state_diff
from app.studio.film import FilmError
from app.studio.render_client import StudioRenderError
from app.studio.render_contract import InspectResult, Issue, film_data
from app.studio.speech import WordNarration
from app.studio.words import Word, cue

DEMO = Path(__file__).with_name('fixtures') / 'studio' / 'demo'
SHIFT, EXTRA = 0.2, 0.5  # the fake voice starts 0.2 s later and lasts 0.5 s longer than the fixture
SEAMS = 0.3 + 0.8  # continue + push


def wav(seconds, rate=48000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b'\x00\x00' * round(seconds * rate))
    return buf.getvalue()


def wav_seconds(data):
    with wave.open(io.BytesIO(data), 'rb') as w:
        return w.getnframes() / w.getframerate()


def fixture():
    return json.loads((DEMO / 'film.json').read_text(encoding='utf-8'))


class FakeVoice:
    """Fixed word timings: the fixture's, shifted by SHIFT; the clip is EXTRA longer."""

    def __init__(self):
        self.calls = []
        self.durations = {}

    async def __call__(self, text, *, speaker, rate='-5%'):
        self.calls.append((text, speaker))
        segment = next(s for s in fixture()['segments'] if s['narration'] == text)
        words = [w for w in demo.fixture_words(text, segment['words'])]
        words = [Word(w.text, w.start + SHIFT, w.end + SHIFT, w.char_start, w.char_end) for w in words]
        duration = segment['duration'] + EXTRA
        self.durations[segment['id']] = duration
        return WordNarration(wav(duration), duration, words)


class FakeRenderer:
    def __init__(self, issues=(), render_error=None):
        self.issues = list(issues)
        self.render_error = render_error
        self.inspected = []
        self.rendered = []

    async def inspect(self, req):
        self.inspected.append(req)
        return InspectResult(issues=self.issues, frames=[], states={})

    async def render(self, req):
        self.rendered.append(req)
        if self.render_error:
            raise self.render_error
        return {'mp4_base64': base64.b64encode(b'fake-mp4').decode(), 'metadata': {'duration': req.duration}}


ISSUES = [Issue(code='overlap', segment='vertex', t=17.5, element='[data-edu-id="vertex-label"]', message='文字重叠'),
          Issue(code='highlights', segment='parabola', t=11.6, element='formula', message='高亮没对上')]


async def test_build_demo_writes_mp4_and_html_with_the_voice_timing(tmp_path):
    voice, renderer = FakeVoice(), FakeRenderer()
    path = await demo.build_demo('edge:zh-CN-YunxiNeural', tmp_path, synthesize=voice, renderer=renderer)

    assert path == tmp_path / 'demo.mp4' and path.read_bytes() == b'fake-mp4'
    html = (tmp_path / 'demo.html').read_text(encoding='utf-8')
    assert html.count('EduStudio.defineSegment(') == 3
    assert [speaker for _, speaker in voice.calls] == ['edge:zh-CN-YunxiNeural'] * 3

    # Segment durations and words come from the voice, not from the fixture.
    data = film_data(html)
    expected = sum(voice.durations.values()) + SEAMS
    assert data['duration'] == pytest.approx(expected)
    assert [s['duration'] for s in data['segments']] == [voice.durations[i] for i in ('parabola', 'vertex', 'story')]
    first = fixture()['segments'][0]['words'][0]
    assert data['segments'][0]['words'][0]['start'] == pytest.approx(first[1] + SHIFT)

    (inspected,) = renderer.inspected
    assert set(inspected.checks) == {'determinism', 'bounds', 'overlap', 'highlights', 'geometry', 'states'}
    assert inspected.duration == pytest.approx(expected) and inspected.html == html
    (rendered,) = renderer.rendered
    assert rendered.duration == pytest.approx(expected)
    assert wav_seconds(base64.b64decode(rendered.audio_base64)) == pytest.approx(expected, abs=1 / 30)


async def test_inspect_issues_stop_the_demo_and_are_all_listed(tmp_path):
    renderer = FakeRenderer(issues=ISSUES)
    with pytest.raises(FilmError) as error:
        await demo.build_demo('edge:zh-CN-YunxiNeural', tmp_path, synthesize=FakeVoice(), renderer=renderer)
    message = str(error.value)
    for issue in ISSUES:
        assert issue.segment in message and issue.message in message and issue.element in message
    assert '17.5' in message and '11.6' in message
    assert renderer.rendered == [] and not (tmp_path / 'demo.mp4').exists()


async def test_render_runtime_issues_are_listed(tmp_path):
    failure = StudioRenderError({'code': 'studio_runtime', 'message': '动画运行出错'}, code='studio_runtime', issues=ISSUES)
    with pytest.raises(FilmError) as error:
        await demo.build_demo('edge:zh-CN-YunxiNeural', tmp_path, synthesize=FakeVoice(),
                              renderer=FakeRenderer(render_error=failure))
    assert all(issue.message in str(error.value) for issue in ISSUES)
    assert not (tmp_path / 'demo.mp4').exists()


def test_fixture_film_is_consistent():
    segments, seams, characters = demo.load_film()
    assert [s.id for s in segments] == ['parabola', 'vertex', 'story']
    assert [(s.kind, s.transition) for s in seams] == [('continue', None), ('transition', 'push')]
    assert state_diff(segments[0].end_state, segments[1].start_state) == []
    for segment in segments:
        # Spoken form only: Edge reads symbols aloud and the word alignment fails on them.
        assert not re.search(r'[+=^()²]', segment.narration), segment.id
        assert segment.words[-1].end <= segment.duration
        for h in segment.highlights:
            cue(segment.words, segment.narration, h.phrase, h.occurrence)
    assert "defineCharacter('kongrong'" in characters and "defineCharacter('brother'" in characters
    html = demo.demo_html(segments, seams, characters)
    assert html.count('EduStudio.defineSegment(') == 3
