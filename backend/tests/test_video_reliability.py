from copy import deepcopy
import httpx
import pytest
from app.outline.review import mark_saved
from app.videos.timeline import narration_chunks
from test_videos import ready_project
STORY="下面我们用故事表达谦让。"*18

def test_default_chunks_keep_coherent_story_and_exact_whitespace():
    text = '  '+STORY+'\n'
    assert narration_chunks(text) == [text]


def test_long_chunks_are_balanced_without_tiny_tail_or_lost_text():
    text = ('甲'*100+'。')*7+'收尾。\n'
    chunks = narration_chunks(text, limit=360)
    assert ''.join(chunks) == text
    assert max(map(len,chunks)) <= 360
    assert min(map(len,chunks)) >= 120


async def test_new_video_does_not_split_181_character_story(db,teacher_client,box):
    project,path = await ready_project(db,teacher_client,box)
    outline=deepcopy(project.outline);outline['segments'][0]['narration']=STORY
    project.outline=mark_saved(outline);await db.commit()
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'coherent'})
    assert response.status_code==202,response.text
    assert [s['narration'] for s in response.json()['segments']]==[STORY]


@pytest.mark.parametrize('status',[429,502,503,524,401])
async def test_tts_recovers_only_transient_http_failures(status,monkeypatch):
    import base64
    from app.videos.speech import synthesize_narration
    from app.model_configs.schemas import ResolvedConfig
    from app.purposes import Purpose
    monkeypatch.setattr('app.outline.model_client._retry_delay',lambda *args:0)
    cfg=ResolvedConfig(Purpose.tts,'https://example.test','secret','tts',{'voices':[{'speaker_id':'voice'}]})
    calls=[]
    def handle(req):
        calls.append(req)
        if len(calls)==1 or status==401:return httpx.Response(status,text='secret provider body')
        return httpx.Response(200,json={'audio':base64.b64encode(b'audio').decode(),'subtitle':{'sentences':[{'text':'原文。','start_time':0,'end_time':1000}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        if status==401:
            with pytest.raises(ValueError) as exc:await synthesize_narration(cfg,'原文。',http)
            assert 'secret' not in str(exc.value) and len(calls)==1
        else:
            result=await synthesize_narration(cfg,'原文。',http)
            assert result.audio==b'audio' and len(calls)==2


def test_unpunctuated_long_narration_has_no_one_character_tail():
    chunks=narration_chunks('甲'*301)
    assert ''.join(chunks)=='甲'*301 and min(map(len,chunks))>=100


