import base64
import copy
import httpx
import pytest
from app.model_configs.schemas import ResolvedConfig
from app.purposes import Purpose

def test_explicit_style_overrides_subject_and_legacy_selection_is_ignored():
    from app.videos.quality import resolve_style
    assert resolve_style({'subject': '数学', 'style': 'math_animation'}, '水墨故事风格')['source'] == 'request'
    assert resolve_style({'subject': '数学', 'style': 'story_sketch'})['value'] == 'science_animation'
    assert resolve_style({'subject': '数学', 'style': 'story_sketch'})['source'] == 'subject'
    assert resolve_style({'subject': '物理', 'style': 'auto'})['value'] == 'science_animation'
    assert resolve_style({'subject': '语文', 'style': 'auto'})['value'] == 'pixel_story'


def test_sentence_timeline_uses_real_audio_lengths_and_preserves_text():
    from app.videos.timeline import split_narration, caption_timeline
    assert split_narration('看图，观察直线。斜率变大！') == ['看图，观察直线。', '斜率变大！']
    assert caption_timeline(['第一句。', '第二句。'], [2.4, 3.1]) == [
        {'start': 0.0, 'end': 2.4, 'text': '第一句。'},
        {'start': 2.4, 'end': 5.5, 'text': '第二句。'},
    ]
    with pytest.raises(ValueError):
        caption_timeline(['一句'], [float('nan')])


async def test_speech_uses_selected_speaker_and_decodes_audio_without_exposing_key():
    from app.videos.speech import synthesize_speech
    def handle(req):
        import json
        body = json.loads(req.content)
        assert req.url.path == '/api/v3/tts/create'
        assert body['references'] == [{'speaker': 'teacher-voice'}]
        return httpx.Response(200, json={'code': 20000000, 'data': {'audio': base64.b64encode(b'ID3audio').decode()}})
    config = ResolvedConfig(Purpose.tts, 'https://tts.example/api/v3/tts/create', 'private', 'speech-model', {'voices': [{'speaker_id': 'teacher-voice', 'label': '教师'}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        assert await synthesize_speech(config, '你好。', http, speaker='teacher-voice') == b'ID3audio'
        with pytest.raises(ValueError, match='音色'):
            await synthesize_speech(config, '你好。', http, speaker='unknown')


async def test_speech_does_not_fetch_arbitrary_response_url_or_accept_empty_audio():
    from app.videos.speech import synthesize_speech
    config = ResolvedConfig(Purpose.tts, 'https://tts.example', 'private', 'speech-model', {'voices': [{'speaker_id': 'voice', 'label': '教师'}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={'code': 0, 'data': {'audio_url': 'http://127.0.0.1/secret'}}))) as http:
        with pytest.raises(ValueError, match='音频'):
            await synthesize_speech(config, '你好。', http)


async def test_narration_requests_dry_voice_and_uses_provider_sentence_timestamps():
    from app.videos.speech import synthesize_narration
    import json
    def handle(req):
        body=json.loads(req.content)
        assert body['text_prompt'].endswith('正文：他把大梨递给哥哥。')
        assert '干声旁白' in body['text_prompt'] and '不要背景音乐' in body['text_prompt']
        assert body['references']==[{'speaker':'teacher-voice'}]
        assert body['audio_config']=={'format':'wav','sample_rate':48000,'enable_subtitle':True}
        return httpx.Response(200,json={'code':20000000,'audio':base64.b64encode(b'RIFFaudio').decode(),
            'subtitle':{'text':'他把大梨递给哥哥。','sentences':[{'text':'他把大梨递给哥哥。','start_time':120,'end_time':3200,'words':[]}]}})
    cfg=ResolvedConfig(Purpose.tts,'https://tts.example','private','seed-audio-1.0',{'voices':[{'speaker_id':'teacher-voice','label':'教师'}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        result=await synthesize_narration(cfg,'他把大梨递给哥哥。',http)
    assert result.audio==b'RIFFaudio'
    assert result.captions==[{'start':.12,'end':3.2,'text':'他把大梨递给哥哥。'}]


@pytest.mark.parametrize('sentences',[
    [{'text':'别的内容。','start_time':0,'end_time':1000}],
    [{'text':'原文。','start_time':2000,'end_time':1000}],
    [{'text':'原文。','start_time':0,'end_time':float('nan')}],
    [{'text':'原','start_time':0,'end_time':2000},{'text':'文。','start_time':1000,'end_time':3000}],
])
async def test_narration_rejects_changed_spoken_content_or_invalid_timestamps(sentences):
    from app.videos.speech import synthesize_narration
    cfg=ResolvedConfig(Purpose.tts,'https://tts.example','private','seed-audio-1.0',{'voices':[{'speaker_id':'voice','label':'教师'}]})
    import json
    response=json.dumps({'audio':base64.b64encode(b'audio').decode(),'subtitle':{'sentences':sentences}}).encode()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,content=response,headers={'content-type':'application/json'}))) as http:
        with pytest.raises(ValueError,match='字幕|讲稿'):
            await synthesize_narration(cfg,'原文。',http)


def test_timeline_map_uses_half_open_intervals_and_is_version_bound():
    from app.videos.timeline import locate_segment
    entries = [{'id': 'a', 'start': 0.0, 'end': 2.0}, {'id': 'b', 'start': 2.0, 'end': 5.5}]
    assert locate_segment(entries, 2)['id'] == 'b'
    assert locate_segment(entries, 5.5)['id'] == 'b'
    with pytest.raises(ValueError):
        locate_segment(entries, -1)


def test_sample_cache_rejects_changed_generation_inputs_and_corrupted_files(tmp_path):
    from app.videos.cache import cache_fingerprint, read_cached_bytes, write_cached_bytes
    inputs = {'narration': '先举例。', 'speaker': 'voice-a', 'model': 'tts-a', 'base_url': 'https://a.example',
              'style': {'value': 'science_animation'}, 'rules_version': 'one', 'duration': 4.2}
    path = tmp_path / 'speech.mp3'
    path.write_bytes(b'legacy-audio')
    key = cache_fingerprint(inputs)
    assert read_cached_bytes(path, key) is None
    write_cached_bytes(path, b'matched-audio', key)
    assert read_cached_bytes(path, cache_fingerprint(dict(reversed(list(inputs.items()))))) == b'matched-audio'
    for field, value in [('narration', '后讲概念。'), ('speaker', 'voice-b'), ('model', 'tts-b'),
                         ('base_url', 'https://b.example'), ('style', {'value': 'story_sketch'}),
                         ('rules_version', 'two'), ('duration', 5.2)]:
        changed = {**inputs, field: value}
        assert read_cached_bytes(path, cache_fingerprint(changed)) is None
    path.write_bytes(b'corrupted-audio')
    assert read_cached_bytes(path, key) is None


def test_video_chunks_keep_connected_sentences_and_every_character():
    from app.videos.timeline import narration_chunks
    assert narration_chunks('他走到桌前。他把大梨递给哥哥。自己留小梨。',limit=180)==['他走到桌前。他把大梨递给哥哥。自己留小梨。']
    original='甲'*100+'。'+'乙'*100+'。'+'丙'*100+'。'
    pieces=narration_chunks(original,limit=180)
    assert ''.join(pieces)==original and max(map(len,pieces))<=180




@pytest.mark.parametrize('subject',['语文','历史','道德与法治','数学','物理','化学','生物'])
def test_automatic_style_defines_pixel_stories_and_clear_scientific_graphics(subject):
    from app.videos.quality import resolve_style
    style=resolve_style({'subject':subject})
    assert style['defaults']=={'character_stories':'detailed_pixel_art','formulas_graphs_experiments':'clean_graphics'}
    if subject in ['数学','物理','化学','生物']:
        assert style['value']=='science_animation'
    else:
        assert style['value']=='pixel_story'
