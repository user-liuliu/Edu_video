"""Whole HTML preparation, immutable preview and provider-free export."""
import asyncio
import hashlib
import json
from sqlalchemy import select
import httpx
from app.models import VideoVersion,VideoSegment
from app.security import SecretBox
from app.model_configs import resolve
from app.purposes import Purpose
from app.jobs.service import update_job_progress
from .cache import cache_fingerprint
from .direct_html import generate_html,seal_html,align_clock,join_audio,direct_digest,DIRECT_PROTOCOL
from .film_modules import FILM_MODULE_PROTOCOL,extract_film
from .media_assets import read_asset,dimensions,align_audio
from .timing import estimated_cues,spoken
from .skill_guidance import animation_guidance,animation_reference_documents,bundle_metadata


def html_generation_request(snapshot,targets,duration):
    guidance=animation_guidance({
        'subject':snapshot['form_values'].get('subject',''),
        'teacher_request':snapshot['prompt'],
        'whole_film_visual_prompt':snapshot['film_expression']['visual_prompt'],
        'visuals':[target.get('visual_prompt','') for target in targets],
        'teacher_visual_instruction':[target.get('teacher_visual_instruction','') for target in targets],
        'narration':' '.join(target['narration'] for target in targets),
    },snapshot['style'])
    targets=[{**target,'render_key':target.get('render_key',f'segment-{index}')} for index,target in enumerate(targets)]
    request={'source_duration':duration,'title':snapshot['title'],'teacher_request':snapshot['prompt'],
            'approved_outline':snapshot['outline'],'whole_film_visual_prompt':snapshot['film_expression']['visual_prompt'],
            'segments':targets,'visual_style':snapshot['style'],'animation_design_references':guidance['documents'],
            'animation_reference_adapter':guidance['runtime_adapter'],'film_module_protocol':FILM_MODULE_PROTOCOL}
    expression=snapshot.get('film_expression',{})
    request['continuity_manifest']={
        'characters':expression.get('characters',[]),
        'segments':[{
            'id':target.get('id',target['render_key']),
            'scene_id':target.get('scene_id',''),
            'character_ids':target.get('character_ids',[]),
            'entry_state':target.get('entry_state',''),
            'exit_state':target.get('exit_state',''),
            'transition_in':target.get('transition_in',''),
            'transition_out':target.get('transition_out',''),
        } for target in targets],
    }
    request['connection_contracts']=[{
        'from_id':left['render_key'],'to_id':right['render_key'],
        'mode':'continuous' if left.get('scene_id') and left.get('scene_id')==right.get('scene_id') else 'scene_change',
        'boundary_state':left.get('exit_state',''),
    } for left,right in zip(targets,targets[1:])]
    if guidance['story_characters']:
        request['animation_design_references']=animation_reference_documents(guidance)
    return request


def html_repair_request(request, html):
    """Keep frozen film constraints, omit duplicated creative reference documents."""
    if request.get('film_module_protocol'):
        bundle=extract_film(html)
        kept=('source_duration','title','teacher_request','whole_film_visual_prompt','segments',
              'continuity_manifest','connection_contracts','visual_style','film_module_protocol','animation_reference_adapter')
        frozen={key:request[key] for key in kept if key in request}
        if request.get('film_revision_source'):
            # Content edits remain confined to the selected modules and their
            # adjacent transitions even when a later runtime repair is needed.
            keys=request.get('editable_segment_ids') or [item['id'] for item in bundle['segments']]
            return {**frozen,'film_revision_source':bundle,'editable_segment_ids':keys,
                    'instruction':request.get('instruction','')+'；仅修复运行错误，保留共享素材、讲稿和时间轴，不得修改未选择片段。'}
        return {**frozen,'previous_film_bundle':bundle,
                'instruction':request.get('instruction','')+'；仅修复运行错误，保留已生成的影片设计、讲稿和时间轴；必要时可修正共享画面代码。'}
    from .sprite_assets import model_source
    keys=('source_duration','title','teacher_request','whole_film_visual_prompt',
          'segments','continuity_manifest','visual_style','animation_reference_adapter','sprite_library')
    return {**{key:request[key] for key in keys if key in request},
            'previous_html':model_source(html),
            'repair_contract':'仅修复现有HTML的技术错误，保留画面设计、全部教学内容、逐句讲稿和时间轴、教师修改要求及素材API；不要重新创作影片。返回完整HTML。'}


async def execute_direct_job(db,job,settings):
    from . import pipeline as p
    from .expression import prepare_expression
    version=await db.scalar(select(VideoVersion).where(VideoVersion.job_id==job.id))
    version_id=version.id;job_id=job.id;token=job.lease_token
    box=SecretBox(settings.master_key)
    from .system_speech import SYSTEM_VOICE,config as system_config
    writer=await resolve(db,box,Purpose.outline_llm)
    tts=system_config() if version.snapshot.get('voice')==SYSTEM_VOICE else await resolve(db,box,Purpose.tts)
    if not writer or not tts or version.snapshot['models']!={'writer':p.config_fingerprint(writer),'tts':p.config_fingerprint(tts)}:
        raise ValueError('动画或配音配置已变化，请重新生成完整预览')
    await p.guard(db,job_id,token,job.project_id,job.expected_revision)
    version.status='running';await db.commit()
    storage=p.MaterialStorage(settings);await asyncio.to_thread(storage.ensure_bucket)
    segments=(await db.scalars(select(VideoSegment).where(VideoSegment.version_id==version_id).order_by(VideoSegment.position))).all()
    if not segments or len(segments)>500:raise ValueError('教学片段数量超出范围')
    # Each external operation releases the lease/project transaction first.
    async def guard():
        await p.guard(db,job_id,token,job.project_id,job.expected_revision)
        await db.commit()
    async def publish(name,data,kind,*,segment=None,fp=None):
        digest=hashlib.sha256(data).hexdigest()
        key=f'videos/{version.owner_id}/{job.project_id}/{version_id}/{token}/{segment.id if segment else "film"}/{name}-{digest}'
        await guard()
        current=await db.get(VideoVersion,version_id,populate_existing=True)
        current.asset_keys=[*current.asset_keys,key];await db.commit()
        await asyncio.to_thread(storage.put,key,data,kind)
        await guard()
        if segment:
            segment.assets={**segment.assets,name:key,'hashes':{**segment.assets.get('hashes',{}),name:digest},'fingerprints':{**segment.assets.get('fingerprints',{}),name:fp}}
        else:
            current=await db.get(VideoVersion,version_id,populate_existing=True)
            checkpoint=current.snapshot.get('direct_assets',{})
            current.snapshot={**current.snapshot,'direct_assets':{**checkpoint,name:{'key':key,'hash':digest}}}
        await db.commit()
        return key,digest
    async def cached(segment,name,fp):
        if segment.assets.get('fingerprints',{}).get(name)!=fp:return None
        try:return await read_asset(storage,segment.assets[name],segment.assets['hashes'][name],name)
        except (KeyError,ValueError,OSError):return None
    async with httpx.AsyncClient(follow_redirects=False) as http:
        snapshot=await prepare_expression(db,job,version,segments,writer,http)
        size=dimensions(snapshot);runtime=direct_digest();renderer=p.RendererClient(settings,http)
        source=snapshot.get('direct_source')
        raw=None;module_bundle=None;targets=None
        if source:
            try:
                raw=(await read_asset(storage,source['key'],source['hash'],'raw_html')).decode()
                if source.get('module_protocol')==FILM_MODULE_PROTOCOL:
                    module_data=await read_asset(storage,source['module_key'],source['module_hash'],'film_modules')
                    module_bundle=json.loads(module_data)
                    if extract_film(raw)!=module_bundle:raise ValueError('动画模块资源与预览不一致')
                else:
                    source=None;raw=None
            except (KeyError,ValueError,OSError,UnicodeError,TypeError):
                source=None;raw=None;module_bundle=None
        if source and source.get('runtime')!=runtime:
            raise ValueError('动画模块版本已更新，请重新生成完整预览')
        if source and len(source['segments'])!=len(segments):
            raise ValueError('整片动画模块与教学片段映射不一致，请重新生成完整预览')

        selected_ids=set(job.payload.get('selected_segment_ids',[]))
        if selected_ids and job.payload.get('mode')=='visual' and source is None:
            raise ValueError('来源动画模块不可用，请重新生成完整预览后修改')
        if selected_ids and job.payload.get('mode')=='voice' and source is None:
            raise ValueError('来源动画模块不可用，无法安全保留原画面；请重新生成完整预览后修改')
        visual_edit=bool(source and module_bundle and selected_ids and job.payload.get('mode')=='visual' and not source.get('revision_applied'))
        if source and visual_edit:
            targets=[]
            for index,(segment,prior) in enumerate(zip(segments,source['segments'])):
                if prior.get('narration')!=segment.narration:
                    raise ValueError('局部画面修改不能改变已配音讲稿')
                entry=next(item for item in snapshot['film_expression']['segments'] if item['id']==str(segment.id))
                instruction=job.payload.get('instruction','') if str(segment.id) in selected_ids else segment.assets.get('visual_instruction','')
                target={**prior,**entry,'id':str(segment.id),'position':segment.position,
                        'render_key':f'segment-{index}','teacher_visual_instruction':instruction}
                targets.append(target)
                segment.assets={**segment.assets,'visual_instruction':instruction}
            request=html_generation_request(snapshot,targets,source['duration'])
            request.update(film_revision_source=module_bundle,
                           editable_segment_ids=[targets[index]['render_key'] for index in range(len(targets))
                                                 if str(segments[index].id) in selected_ids],
                           instruction=job.payload.get('instruction',''))
            await update_job_progress(db,job_id,token,12,'正在修改所选画面并衔接相邻片段')
            await guard();raw=await generate_html(writer,request,http)
            module_bundle=extract_film(raw)
            module_key,module_hash=await publish('film_modules',json.dumps(module_bundle,ensure_ascii=False,separators=(',',':')).encode(),'application/json')
            key,digest=await publish('raw_html',raw.encode(),'text/html; charset=utf-8')
            source={**source,'key':key,'hash':digest,'module_key':module_key,'module_hash':module_hash,
                    'module_protocol':FILM_MODULE_PROTOCOL,'runtime':runtime,'segments':targets,'revision_applied':True}
            version=await db.get(VideoVersion,version_id,populate_existing=True)
            version.snapshot={**version.snapshot,'direct_source':source};await db.commit()
        elif source:
            targets=source['segments']

        if source is None:
            offset=0.;targets=[]
            for index,segment in enumerate(segments):
                parent=next(s for s in snapshot['outline']['segments'] if str(s['id'])==str(segment.outline_segment_id))
                duration=max(.5,min(110.,parent.get('estimated_duration_seconds',max(1,len(spoken(parent['narration']))/4))*len(spoken(segment.narration))/max(1,len(spoken(parent['narration'])))))
                cues=estimated_cues(segment.narration,duration)
                entry=next(s for s in snapshot['film_expression']['segments'] if s['id']==str(segment.id))
                local=job.payload.get('instruction','') if str(segment.id) in selected_ids and job.payload.get('mode')!='voice' else segment.assets.get('visual_instruction','')
                targets.append({**entry,'position':segment.position,'render_key':f'segment-{index}','start':offset,'end':offset+duration,
                    'sentences':[{**c,'start':offset+c['start'],'end':offset+c['end']} for c in cues],'teacher_visual_instruction':local})
                segment.assets={**segment.assets,'visual_instruction':local};offset+=duration
            if offset>7200:raise ValueError('视频总时长超过限制')
            request=html_generation_request(snapshot,targets,offset)
            await update_job_progress(db,job_id,token,12,'正在生成整片HTML动画与自然转场')
            await guard();raw=await generate_html(writer,request,http)
            module_bundle=extract_film(raw)
            module_key,module_hash=await publish('film_modules',json.dumps(module_bundle,ensure_ascii=False,separators=(',',':')).encode(),'application/json')
            key,digest=await publish('raw_html',raw.encode(),'text/html; charset=utf-8')
            source={'key':key,'hash':digest,'runtime':runtime,'duration':offset,'segments':targets,
                    'module_key':module_key,'module_hash':module_hash,'module_protocol':FILM_MODULE_PROTOCOL}
            version=await db.get(VideoVersion,version_id,populate_existing=True)
            version.snapshot={**version.snapshot,'direct_source':source};await db.commit()
        audio_parts=[];captions=[];clock=[];elapsed=0.
        for index,segment in enumerate(segments):
            target=source['segments'][index]
            if target['narration']!=segment.narration:raise ValueError('整片动画讲稿与配音不一致')
            selected=str(segment.id) in job.payload.get('selected_segment_ids',[])
            instruction=job.payload.get('instruction','') if selected and job.payload.get('mode')=='voice' else segment.assets.get('audio_instruction','')
            audio_fp=cache_fingerprint({'narration':segment.narration,'voice':snapshot['voice'],'tts':snapshot['models']['tts'],'protocol':p.NARRATION_PROTOCOL_VERSION,'frame_alignment':1,**({'instruction':instruction} if instruction else {})})
            audio=await cached(segment,'audio',audio_fp);caption_data=await cached(segment,'captions',audio_fp)
            await update_job_progress(db,job_id,token,45+int(index/len(segments)*36),f'正在制作配音并校时（{index+1}/{len(segments)}）')
            if audio is None or caption_data is None:
                await guard()
                narration=await p.synthesize_narration(tts,segment.narration,http,speaker=snapshot['voice'],**({'instruction':instruction} if instruction else {}))
                audio=align_audio(narration.audio);caption_data=json.dumps(narration.captions,ensure_ascii=False).encode()
                await publish('audio',audio,'audio/wav',segment=segment,fp=audio_fp)
                await publish('captions',caption_data,'application/json',segment=segment,fp=audio_fp)
            local_captions=json.loads(caption_data);duration=p.wav_duration(audio)
            cues=[{**c,'start':c['start']-target['start'],'end':c['end']-target['start']} for c in target['sentences']]
            local_clock=align_clock(cues,local_captions,target['end']-target['start'],duration)
            for point in local_clock:
                value={'t':point['t']+elapsed,'source':point['source']+target['start']}
                if clock and abs(clock[-1]['t']-value['t'])<1e-8:continue
                clock.append(value)
            captions.extend({**c,'start':c['start']+elapsed,'end':c['end']+elapsed} for c in local_captions)
            audio_parts.append(audio);segment.start=elapsed;elapsed+=duration;segment.end=elapsed
            segment.assets={**segment.assets,'audio_instruction':instruction};await db.commit()
        if elapsed>7200:raise ValueError('视频总时长超过限制')
        manifest={'duration':elapsed,'source_duration':source['duration'],'clock':clock,'captions':captions}
        audio=join_audio(audio_parts)
        await update_job_progress(db,job_id,token,87,'正在检查整片HTML播放与时间轴')
        from .render_contract import DirectHtmlRuntimeError
        for attempt in range(min(2,snapshot['params']['max_retries'])+1):
            try:
                await guard();await renderer.direct(raw,manifest,audio,size,validate=True)
                break
            except DirectHtmlRuntimeError as error:
                if job.payload.get('mode')=='voice':
                    raise DirectHtmlRuntimeError('配音校时后原画面运行检查未通过，已保留原画面；请先修改对应画面或重新生成完整预览') from error
                if attempt>=min(2,snapshot['params']['max_retries']):raise
                # Repair executable code only. Preserve the frozen script, cues
                # and accepted audio; this is not a video content review.
                await update_job_progress(db,job_id,token,88,'正在修复动画播放代码（保留讲稿与配音）')
                if 'request' not in locals():
                    request=html_generation_request(snapshot,source['segments'],source['duration'])
                    if selected_ids and job.payload.get('mode')=='visual':
                        editable=[target['render_key'] for target,segment in zip(source['segments'],segments)
                                  if str(segment.id) in selected_ids]
                        request['editable_segment_ids']=editable
                        request['instruction']=job.payload.get('instruction','')
                        if source.get('revision_applied'):
                            request['film_revision_source']=module_bundle
                await guard();raw=await generate_html(writer,html_repair_request(request,raw),http,feedback=str(error))
                key,digest=await publish('raw_html',raw.encode(),'text/html; charset=utf-8')
                repaired_bundle=extract_film(raw)
                module_key,module_hash=await publish('film_modules',json.dumps(repaired_bundle,ensure_ascii=False,separators=(',',':')).encode(),'application/json')
                source={**source,'key':key,'hash':digest,'module_key':module_key,'module_hash':module_hash}
                version=await db.get(VideoVersion,version_id,populate_existing=True)
                version.snapshot={**version.snapshot,'direct_source':source};await db.commit()
        html=seal_html(raw,manifest,size).encode()
        html_key,html_hash=await publish('html',html,'text/html; charset=utf-8')
        audio_key,audio_hash=await publish('whole_audio',audio,'audio/wav')
        project=await p.guard(db,job_id,token,job.project_id,job.expected_revision)
        version=await db.get(VideoVersion,version_id,populate_existing=True)
        version.snapshot={**version.snapshot,'direct_html_protocol':DIRECT_PROTOCOL,'compiler_digest':runtime,
            'direct_manifest':{'keys':{'html':html_key,'audio':audio_key},'hashes':{'html':html_hash,'audio':audio_hash},
                'timeline':manifest,'segments':[{'id':str(s.id),'start':s.start,'end':s.end} for s in segments]}}
        version.duration=elapsed;version.status='preview_ready';project.status='preview_ready'


async def verify_direct(storage,version,segments):
    if version.snapshot.get('compiler_digest')!=direct_digest():raise ValueError('动画运行版本已更新，请重新生成预览后再导出')
    source=version.snapshot['direct_source'];entry=version.snapshot['direct_manifest']
    raw=(await read_asset(storage,source['key'],source['hash'],'raw_html')).decode()
    html=await read_asset(storage,entry['keys']['html'],entry['hashes']['html'],'html')
    audio=await read_asset(storage,entry['keys']['audio'],entry['hashes']['audio'],'whole_audio')
    manifest=entry['timeline']
    if html!=seal_html(raw,manifest,dimensions(version.snapshot)).encode():raise ValueError('预览画面版本不一致，请重新生成预览')
    if entry['segments']!=[{'id':str(s.id),'start':s.start,'end':s.end} for s in segments] or version.duration!=manifest['duration']:
        raise ValueError('整片教学片段时间轴不一致')
    cursor=0.
    for s in segments:
        if s.start!=cursor or not s.end>s.start:raise ValueError('整片教学片段不连续')
        cursor=s.end
    if cursor!=version.duration:raise ValueError('整片时间轴不完整')
    from .render_contract import DirectRenderRequest
    import base64
    DirectRenderRequest(compiler_digest=direct_digest(),html=raw,manifest=manifest,audio_base64=base64.b64encode(audio).decode(),width=dimensions(version.snapshot)[0],height=dimensions(version.snapshot)[1])
    return raw,manifest,audio


async def execute_direct_export(db,job,settings):
    from . import pipeline as p
    version=await db.get(VideoVersion,job.payload['version_id'])
    if not version or version.owner_id!=job.owner_id or version.project_id!=job.project_id or version.status not in ('preview_ready','succeeded'):
        raise ValueError('动画预览尚未就绪')
    await p.guard(db,job.id,job.lease_token,job.project_id,job.expected_revision);await db.commit()
    storage=p.MaterialStorage(settings)
    segments=(await db.scalars(select(VideoSegment).where(VideoSegment.version_id==version.id).order_by(VideoSegment.position))).all()
    raw,manifest,audio=await verify_direct(storage,version,segments)
    await db.commit()
    await update_job_progress(db,job.id,job.lease_token,10,'正在将整片HTML与封存配音导出MP4')
    async with httpx.AsyncClient(follow_redirects=False) as http:
        final,metadata=await p.RendererClient(settings,http).direct(raw,manifest,audio,dimensions(version.snapshot))
    if abs(metadata['duration']-version.duration)>.15:raise ValueError('整片音画时长不一致')
    digest=hashlib.sha256(final).hexdigest()
    key=f'videos/{version.owner_id}/{version.project_id}/{version.id}/{job.lease_token}/export/final-{digest}'
    await p.guard(db,job.id,job.lease_token,job.project_id,job.expected_revision)
    version.asset_keys=[*version.asset_keys,key];await db.commit()
    await asyncio.to_thread(storage.put,key,final,'video/mp4')
    project=await p.guard(db,job.id,job.lease_token,job.project_id,job.expected_revision)
    version=await db.get(VideoVersion,version.id,populate_existing=True)
    version.media_key=key;version.status='succeeded'
    project.status='completed' if project.revision==version.outline_revision and not project.needs_regeneration else 'outline_ready'
