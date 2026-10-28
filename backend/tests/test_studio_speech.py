import subprocess
import sys

import pytest

from app.studio.speech import VOICES, cue, synthesize_words
from app.studio.words import align_words, sentence_captions

TEXT = '二次函数的图像是一条抛物线，顶点就是它的最低点。'


def ev(s, d, t):
    return {'type': 'WordBoundary', 'offset': round(s * 1e7), 'duration': round(d * 1e7), 'text': t}


EVENTS = [ev(0.10, .35, '二次'), ev(.46, .33, '函数'), ev(.79, .09, '的'), ev(.89, .51, '图像'),
          ev(1.50, .19, '是'), ev(1.70, .24, '一条'), ev(1.96, .56, '抛物线'), ev(2.91, .44, '顶点'),
          ev(3.38, .14, '就'), ev(3.51, .09, '是'), ev(3.61, .11, '它'), ev(3.73, .07, '的'), ev(3.83, .55, '最低点')]


@pytest.fixture(scope='module')
def mp3():
    return subprocess.check_output([
        'ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
        'sine=frequency=440:duration=5', '-c:a', 'libmp3lame', '-b:a', '48k', '-f', 'mp3', 'pipe:1',
    ], timeout=15)


def test_voices_include_default_and_labelled_choices():
    ids = [v['speaker_id'] for v in VOICES]
    assert ids[0] == 'edge:zh-CN-YunxiNeural'
    assert {'edge:zh-CN-XiaoxiaoNeural', 'edge:zh-CN-YunjianNeural',
            'edge:zh-CN-XiaoyiNeural', 'edge:zh-CN-YunyangNeural'} <= set(ids)
    assert all(v['label'] for v in VOICES)


def test_words_module_does_not_import_edge_tts():
    code = 'import sys, app.studio.words; sys.exit(1 if "edge_tts" in sys.modules else 0)'
    assert subprocess.run([sys.executable, '-c', code]).returncode == 0


def test_align_words_maps_events_to_text_positions():
    words = align_words(TEXT, EVENTS)
    assert len(words) == 13
    assert TEXT[words[7].char_start:words[7].char_end] == '顶点'
    assert (words[7].start, words[7].end) == pytest.approx((2.91, 3.35))


def test_cue_returns_word_span_and_picks_nth_occurrence():
    words = align_words(TEXT, EVENTS)
    assert cue(words, TEXT, '顶点') == pytest.approx((2.91, 3.35))
    assert cue(words, TEXT, '抛物线，顶点') == pytest.approx((1.96, 3.35))
    assert cue(words, TEXT, '的', 2) == pytest.approx((3.73, 3.80))
    with pytest.raises(ValueError, match='高亮词"开口"'):
        cue(words, TEXT, '开口')
    with pytest.raises(ValueError, match='第 3 处'):
        cue(words, TEXT, '的', 3)


def test_align_words_handles_digits_and_latin():
    text = '把2代入y等于x加1。'
    events = [ev(0, .2, '把'), ev(.2, .2, '二'), ev(.4, .3, '代入'), ev(.7, .2, 'y'), ev(.9, .3, '等于'),
              ev(1.2, .2, 'x'), ev(1.4, .2, '加'), ev(1.6, .2, '一')]
    words = align_words(text, events)
    assert text[words[1].char_start:words[1].char_end] == '2'
    assert cue(words, text, 'x加1') == pytest.approx((1.2, 1.8))
    with pytest.raises(ValueError, match='对不上'):
        align_words('甲乙。', [ev(0, .2, '丙')])


def test_align_words_skips_punctuation_differences():
    text = '你好，世界！'
    words = align_words(text, [ev(0, .3, '你好,'), ev(.4, .3, '世界')])
    assert [text[w.char_start:w.char_end] for w in words] == ['你好', '世界']


def test_sentence_captions_split_on_punctuation():
    text = TEXT + '它在对称轴上。'
    words = align_words(text, EVENTS + [ev(4.6, .2, '它'), ev(4.8, .2, '在'), ev(5.0, .6, '对称轴'), ev(5.6, .2, '上')])
    caps = sentence_captions(text, words)
    assert [c['text'] for c in caps] == [TEXT, '它在对称轴上。']
    assert (caps[0]['start'], caps[0]['end']) == pytest.approx((0.10, 4.38))


async def test_synthesize_words_uses_word_boundary_and_validates_speaker(monkeypatch, mp3):
    from app.studio import speech
    seen = []

    async def stream(text, voice, rate):
        seen.append((text, voice, rate))
        return mp3, EVENTS
    monkeypatch.setattr(speech, '_stream_words', stream)
    result = await synthesize_words(TEXT, speaker='edge:zh-CN-YunxiNeural')
    assert seen == [(TEXT, 'zh-CN-YunxiNeural', '-5%')]
    assert result.audio[:4] == b'RIFF' and len(result.words) == 13
    assert 4.9 < result.duration < 5.2
    assert max(w.end for w in result.words) <= result.duration
    with pytest.raises(ValueError, match='音色不可用'):
        await synthesize_words(TEXT, speaker='system:zh-CN')
    with pytest.raises(ValueError, match='长度不符合'):
        await synthesize_words('  ', speaker='edge:zh-CN-YunxiNeural')
    with pytest.raises(ValueError, match='长度不符合'):
        await synthesize_words('字' * 2001, speaker='edge:zh-CN-YunxiNeural')


async def test_synthesize_words_retries_then_reports_clear_error(monkeypatch):
    from app.studio import speech
    calls = []

    async def unavailable(text, voice, rate):
        calls.append(text)
        raise TimeoutError('remote timeout')

    async def no_wait(seconds):
        pass
    monkeypatch.setattr(speech, '_stream_words', unavailable)
    monkeypatch.setattr(speech.asyncio, 'sleep', no_wait)
    with pytest.raises(ValueError, match='配音服务暂时不可用'):
        await synthesize_words(TEXT, speaker='edge:zh-CN-YunxiNeural')
    assert len(calls) == speech.ATTEMPTS
