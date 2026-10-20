import io
import wave
from uuid import UUID
import httpx
import pytest
from sqlalchemy import delete
from app.models import ModelConfigRow,VideoVersion
from app.videos.speech import synthesize_narration
from app.model_configs.schemas import ResolvedConfig
from app.purposes import Purpose

async def test_system_voice_is_available_and_saved_without_tts_configuration(teacher_client):
    config=(await teacher_client.get('/api/config/form')).json()
    voice=next((f for f in config['fields'] if f['key']=='voice'),None)
    assert voice is not None
    assert any(o['value']=='system:zh-CN' for o in voice['options'])
    response=await teacher_client.post('/api/projects',json={'title':'系统配音','prompt':'测试','form_values':{'voice':'system:zh-CN'}})
    assert response.status_code==201,response.text
    assert response.json()['form_values']['voice']=='system:zh-CN'

async def test_system_video_does_not_resolve_tts_model(db,teacher_client,box,monkeypatch):
    from test_videos import ready_project
    from app.videos import service
    project,path=await ready_project(db,teacher_client,box)
    project.form_values={**project.form_values,'voice':'system:zh-CN'}
    await db.execute(delete(ModelConfigRow).where(ModelConfigRow.purpose=='tts'));await db.commit()
    original=service.resolve
    async def guarded(db,box,purpose,**kwargs):
        if purpose==Purpose.tts:raise AssertionError('System voice must never resolve a TTS model')
        return await original(db,box,purpose,**kwargs)
    monkeypatch.setattr(service,'resolve',guarded)
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'offline'})
    assert response.status_code==202,response.text
    version=await db.get(VideoVersion,UUID(response.json()['id']))
    assert version.snapshot['voice']=='system:zh-CN'

async def test_admin_does_not_mark_tts_required_when_system_voice_is_available(admin_client):
    response=await admin_client.get('/api/admin/model-configs')
    tts=next(c for c in response.json() if c['purpose']=='tts')
    assert tts['required'] is False

async def test_missing_offline_components_does_not_offer_a_broken_option(teacher_client,monkeypatch):
    monkeypatch.setattr('app.videos.system_speech.available',lambda:False)
    config=(await teacher_client.get('/api/config/form')).json()
    assert not any(o['value']=='system:zh-CN' for f in config['fields'] for o in f['options'])

async def test_system_synthesis_produces_real_pcm_and_sentence_times_without_network():
    cfg=ResolvedConfig(Purpose.tts,'system://offline','','espeak-ng-cmn-1',{'voices':[{'speaker_id':'system:zh-CN','label':'系统配音'}]})
    def forbidden(request):raise AssertionError('System speech must not make an HTTP request')
    async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as http:
        result=await synthesize_narration(cfg,'大家好。今天学习一次函数！',http,speaker='system:zh-CN')
    with wave.open(io.BytesIO(result.audio),'rb') as audio:
        assert (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())==(1,2,48000)
        duration=audio.getnframes()/48000
        assert 1<duration<20
        assert any(audio.readframes(audio.getnframes()))
    assert [c['text'] for c in result.captions]==['大家好。','今天学习一次函数！']
    assert result.captions[0]['start']==0
    assert result.captions[0]['end']==result.captions[1]['start']
    assert abs(result.captions[-1]['end']-duration)<1/48000

async def test_unknown_system_voice_is_rejected_without_network():
    cfg=ResolvedConfig(Purpose.tts,'system://offline','','espeak-ng-cmn-1',{})
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:pytest.fail('No external request'))) as http:
        with pytest.raises(ValueError,match='音色'):
            await synthesize_narration(cfg,'你好。',http,speaker='system:invalid')

async def test_system_ready_without_tts_and_model_speech_still_requires_tts(db,teacher_client,box):
    from test_model_configs import _configure_required_direct
    from app.model_configs import system_available
    await _configure_required_direct(db,box)
    await db.execute(delete(ModelConfigRow).where(ModelConfigRow.purpose=='tts'));await db.commit()
    assert await system_available(db,box,voice='system:zh-CN') is True
    assert await system_available(db,box,voice='external-voice') is False
    assert (await teacher_client.get('/api/config/form')).json()['system_available'] is True

async def test_system_video_pipeline_uses_offline_audio_without_tts_lookup(db,teacher_client,box,settings,monkeypatch):
    from test_direct_pipeline import prepare
    from app.jobs.tasks import run_job
    from app.videos import direct_pipeline,pipeline,speech
    project,path,store,renderer,counts,calls=await prepare(db,teacher_client,box,settings,monkeypatch)
    project.form_values={**project.form_values,'voice':'system:zh-CN'}
    await db.execute(delete(ModelConfigRow).where(ModelConfigRow.purpose=='tts'));await db.commit()
    monkeypatch.setattr(pipeline,'synthesize_narration',speech.synthesize_narration)
    original=direct_pipeline.resolve
    async def guarded(db,box,purpose,**kwargs):
        if purpose==Purpose.tts:raise AssertionError('Offline execution must not resolve TTS')
        return await original(db,box,purpose,**kwargs)
    monkeypatch.setattr(direct_pipeline,'resolve',guarded)
    response=await teacher_client.post(path,json={'revision':1,'idempotency_key':'system-pipeline'})
    assert response.status_code==202,response.text
    await run_job(response.json()['job']['id'],settings)
    result=(await teacher_client.get(path+'/'+response.json()['id'])).json()
    assert result['status']=='preview_ready',result
    audio=await teacher_client.get(result['audio_url']);assert audio.status_code==200
    with wave.open(io.BytesIO(audio.content),'rb') as wav:assert wav.getnframes()>48000
    assert len(calls)==1
