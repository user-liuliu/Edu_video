from copy import deepcopy
import re
from uuid import uuid4
from sqlalchemy import func, select
from app.errors import api_error
from app.credits.service import reserve_video
from app.jobs.service import create_job, require_generation_capacity, require_idle, JobView
from app.models import OutlineJob, VideoVersion, VideoSegment
from app.outline.review import needs_save, review_state
from app.projects.service import get_owned_project, check_revision
from app.model_configs import resolve
from app.purposes import Purpose
from app.settings_store import get_generation_params
from .cache import cache_fingerprint
from .skill_guidance import bundle_metadata
from .quality import resolve_style
from .timeline import narration_chunks, SEGMENTATION_VERSION
from .schemas import VersionView, SegmentView


DEFAULT_WORKFLOW = 'html-preview-1'


def config_fingerprint(config):
    return cache_fingerprint({'url': config.base_url, 'model': config.model, 'extra': config.extra})


async def owned_version(db, owner_id, project_id, version_id):
    version = await db.scalar(select(VideoVersion).where(VideoVersion.id==version_id, VideoVersion.owner_id==owner_id, VideoVersion.project_id==project_id))
    if version is None: raise api_error(404, 'video_not_found', '视频版本不存在')
    return version


async def version_view(db, version):
    job = await db.get(OutlineJob, version.job_id)
    segments = (await db.scalars(select(VideoSegment).where(VideoSegment.version_id==version.id).order_by(VideoSegment.position))).all()
    base = f'/api/projects/{version.project_id}/videos/{version.id}/media'
    status = {'pending':'queued','running':'running','failed':'failed','succeeded':'succeeded'}[job.status]
    if job.status == 'succeeded':
        status = version.status
    export_job = await db.get(OutlineJob, version.snapshot['export_job_id']) if version.snapshot.get('export_job_id') else None
    target=version.snapshot.get('form_values',{}).get('duration_seconds')
    notice=None
    tolerance=version.snapshot.get('params',{}).get('duration_tolerance_pct',15)
    if status in ('preview_ready','succeeded') and version.duration is not None and isinstance(target,(int,float)) and target>0 and abs(version.duration-target)>target*tolerance/100:
        notice=f'实际时长{version.duration:.1f}秒，目标时长{target:g}秒，超出允许偏差{tolerance}%。已保留完整讲解，可返回大纲调整内容后重新生成。'
    whole=bool(version.snapshot.get('direct_manifest')) and status in ('preview_ready','succeeded')
    film_base=f'/api/projects/{version.project_id}/videos/{version.id}/film'
    return VersionView(playback_mode='whole_html',html_url=film_base+'/html' if whole else None,audio_url=film_base+'/audio' if whole else None,id=version.id,project_id=version.project_id,number=version.number,outline_revision=version.outline_revision,source_version_id=version.source_version_id,status=status,aspect_ratio=version.snapshot.get('form_values',{}).get('aspect_ratio','16:9'),workflow=DEFAULT_WORKFLOW,export_status=export_job.status if export_job else None,export_job=JobView.model_validate(export_job) if export_job else None,duration=version.duration,target_duration=target,duration_notice=notice,created_at=version.created_at,style=version.snapshot['style'],job=JobView.model_validate(job),segments=[SegmentView.model_validate(s) for s in segments],media_url=base+'/final' if version.media_key else None)


async def start_video(db, user, project_id, body, box, *, source_version_id=None):
    project = await get_owned_project(db, user.id, project_id, lock=True)
    existing = await db.scalar(select(OutlineJob).where(OutlineJob.owner_id==user.id, OutlineJob.project_id==project_id, OutlineJob.kind=='video', OutlineJob.idempotency_key==body.idempotency_key))
    if existing:
        if existing.payload.get('request') != body.model_dump(mode='json') or existing.payload.get('revision_source') != (str(source_version_id) if source_version_id else None):
            raise api_error(409,'idempotency_conflict','相同请求标识不能用于不同生成内容')
        return await db.scalar(select(VideoVersion).where(VideoVersion.job_id==existing.id))
    check_revision(project, body.revision)
    await require_idle(db, project)
    if project.needs_regeneration: raise api_error(409,'regeneration_required','需求或素材已变化，请先重新生成大纲')
    if needs_save(project.outline): raise api_error(409,'outline_save_required','请先保存大纲，再确认大纲')
    if any(review_state(s)!='passed' for s in project.outline['segments']): raise api_error(409,'review_required','存在未通过审核的片段，请先完成审核')
    if project.status not in ('outline_confirmed','completed','video_failed','preview_ready'):
        raise api_error(409,'outline_confirmation_required','请先确认已保存的大纲')
    params = await get_generation_params(db)
    await require_generation_capacity(db,user.id,params.max_concurrent_jobs)
    from .system_speech import SYSTEM_VOICE,config as system_config
    writer = await resolve(db,box,Purpose.outline_llm)
    requested_voice=project.form_values.get('voice')
    try:tts=system_config() if requested_voice==SYSTEM_VOICE else await resolve(db,box,Purpose.tts)
    except ValueError as error:raise api_error(409,'system_voice_unavailable',str(error)) from None
    if not writer or not tts: raise api_error(409,'video_models_unavailable','动画或配音模型尚不可用，请联系管理员')
    voice = project.form_values.get('voice') or next((v['speaker_id'] for v in tts.extra.get('voices',[]) if v.get('speaker_id')), None)
    if voice not in [v.get('speaker_id') for v in tts.extra.get('voices',[])]: raise api_error(409,'voice_unavailable','所选配音音色已不可用，请重新选择')
    snapshot = {'outline':deepcopy(project.outline),'title':project.title,'prompt':project.prompt,'form_values':deepcopy(project.form_values),'voice':voice,'style':resolve_style(project.form_values),'models':{'writer':config_fingerprint(writer),'tts':config_fingerprint(tts)},'params':params.model_dump(),'renderer_version':'direct-html-1'}
    snapshot['form_values'].pop('style', None)
    from .timing import TIMING_PROTOCOL
    from .expression import EXPRESSION_PROTOCOL
    from .direct_html import DIRECT_PROTOCOL
    snapshot.update(workflow=DEFAULT_WORKFLOW,timing_protocol=TIMING_PROTOCOL,expression_protocol=EXPRESSION_PROTOCOL,direct_html_protocol=DIRECT_PROTOCOL)
    source = None
    if body.retry_version_id or source_version_id:
        source = await owned_version(db,user.id,project.id,source_version_id or body.retry_version_id)
        expected = 'succeeded' if source_version_id else 'failed'
        source_job = await db.get(OutlineJob,source.job_id)
        if source_job.status!=expected or source.outline_revision!=project.revision:
            raise api_error(409,'retry_not_available','来源版本状态或大纲已变化，请重新生成视频')
        if not source.snapshot.get('direct_html_protocol'):
            raise api_error(409,'video_version_retired','此版本已退役，请使用新版重新生成完整视频')
        if source.snapshot['models'] != snapshot['models']:
            raise api_error(409,'video_config_changed','模型配置已更新，请重新生成完整视频')
        snapshot = {**deepcopy(source.snapshot),**{k:snapshot[k] for k in ('workflow','models','style') if k in snapshot}}
        snapshot['form_values'].pop('style', None)
        for key in ('export_job_id','compiler_digest'):
            snapshot.pop(key,None)
        snapshot.pop('direct_manifest',None)
        snapshot.pop('direct_assets',None)
        if source_version_id and body.mode=='visual':
            from .film_modules import FILM_MODULE_PROTOCOL
            if snapshot.get('direct_source',{}).get('module_protocol')!=FILM_MODULE_PROTOCOL:
                raise api_error(409,'local_revision_unavailable','此版本尚不支持局部修改，请先重新生成完整视频')
            snapshot['direct_source']={key:value for key,value in snapshot['direct_source'].items() if key!='revision_applied'}
    number = int(await db.scalar(select(func.max(VideoVersion.number)).where(VideoVersion.project_id==project.id)) or 0)+1
    version_id=uuid4()
    payload={'version_id':str(version_id),'request':body.model_dump(mode='json'),'revision_source':str(source_version_id) if source_version_id else None}
    if body.retry_version_id and source_job.payload.get('instruction'):
        # Retry keeps the selected scope and original modification request.
        payload.update(instruction=source_job.payload['instruction'],selected_segment_ids=source_job.payload.get('selected_segment_ids',[]),mode=source_job.payload.get('mode','visual'))
    if source_version_id:
        if re.search(r'改写|修改(?:讲稿|旁白|内容|台词)|知识点|台词|讲稿内容|narration|script|knowledge',body.instruction,re.I) or (body.mode=='visual' and re.search(r'讲稿|旁白',body.instruction)):
            raise api_error(409,'outline_content_change_required','涉及讲稿或知识点的修改，请返回大纲编辑、保存并重新审核确认')
        selected={str(i) for i in body.segment_ids}
        segments=(await db.scalars(select(VideoSegment).where(VideoSegment.version_id==source.id).order_by(VideoSegment.position))).all()
        if not selected or len(selected)!=len(body.segment_ids) or not selected.issubset({str(s.id) for s in segments}):
            raise api_error(422,'invalid_video_segments','请选择来源视频中完整的教学片段')
        if body.mode == 'voice' and (not source.snapshot.get('timing_protocol') or not source.snapshot.get('direct_source')):
            raise api_error(409,'voice_revision_unavailable','此版本没有可复用的动画初稿，请先重新生成完整预览')
        payload.update(selected_segment_ids=list(selected),instruction=body.instruction.strip(),mode=body.mode)
    job = await create_job(db,project,'video',body.idempotency_key,payload)
    version = VideoVersion(id=version_id,owner_id=user.id,project_id=project.id,job_id=job.id,source_version_id=source.id if source else None,number=number,outline_revision=project.revision,snapshot=snapshot)
    db.add(version); await db.flush()
    snapshot = {**snapshot,'segmentation_version':SEGMENTATION_VERSION,'animation_skills':bundle_metadata()}
    version.snapshot = snapshot
    if source:
        source_segments=(await db.scalars(select(VideoSegment).where(VideoSegment.version_id==source.id).order_by(VideoSegment.position))).all()
        prior_lineage=source_job.payload.get('segment_lineage',{})
        prior_selected=set(source_job.payload.get('selected_segment_ids',[]))
        selected_source_ids=selected if source_version_id else {str(s.id) for s in source_segments if str(s.id) in prior_selected or prior_lineage.get(str(s.id)) in prior_selected}
        if payload.get('instruction') and not selected_source_ids:
            raise api_error(409,'revision_selection_unavailable','原画面修改范围无法恢复，请重新选择片段修改')
        lineage={};new_selected=[]
        for s in source_segments:
            assets=deepcopy(s.assets)
            narration=s.narration
            if source_version_id and str(s.id) in selected:
                keep=() if body.mode=='voice' else ('audio','captions')
                metadata=('visual_instruction','audio_instruction')
                assets={k:v for k,v in assets.items() if k in (*keep,*metadata,'hashes','fingerprints')}
                assets['hashes']={k:v for k,v in assets.get('hashes',{}).items() if k in keep}
                assets['fingerprints']={k:v for k,v in assets.get('fingerprints',{}).items() if k in keep}
            segment_id=uuid4()
            lineage[str(segment_id)]=str(s.id)
            if str(s.id) in selected_source_ids:
                new_selected.append(str(segment_id))
            db.add(VideoSegment(id=segment_id,version_id=version.id,outline_segment_id=s.outline_segment_id,position=s.position,title=s.title,narration=narration,fingerprint=s.fingerprint,assets=assets))
        if snapshot.get('film_expression'):
            inverse={old:new for new,old in lineage.items()}
            snapshot={**snapshot,'film_expression':{**snapshot['film_expression'],'segments':[{**entry,'id':inverse[entry['id']]} for entry in snapshot['film_expression']['segments']]}}
            version.snapshot=deepcopy(snapshot)
        if payload.get('instruction'):
            job.payload={**job.payload,'segment_lineage':lineage,'selected_segment_ids':new_selected}
    else:
        position=0
        for section in snapshot['outline']['segments']:
            for narration in narration_chunks(section['narration']):
                db.add(VideoSegment(version_id=version.id,outline_segment_id=section['id'],position=position,title=section['title'],narration=narration))
                position+=1
    await reserve_video(db, job, project.title)
    project.status='video_generating'
    await db.commit(); await db.refresh(version)
    return version


async def start_export(db,user,project_id,version_id,body,settings):
    from .direct_pipeline import verify_direct
    from .media import MaterialStorage
    project=await get_owned_project(db,user.id,project_id,lock=True)
    version=await owned_version(db,user.id,project_id,version_id)
    existing=await db.scalar(select(OutlineJob).where(OutlineJob.owner_id==user.id,OutlineJob.project_id==project_id,OutlineJob.kind=='video_export',OutlineJob.idempotency_key==body.idempotency_key))
    if existing:
        if existing.payload.get('version_id')!=str(version.id):raise api_error(409,'idempotency_conflict','相同请求标识不能用于不同视频')
        return existing
    if version.snapshot.get('workflow')!='html-preview-1' or version.status not in ('preview_ready','succeeded'):
        raise api_error(409,'preview_not_ready','请等待动画预览生成完成后再导出')
    if version.snapshot.get('export_job_id'):
        current=await db.get(OutlineJob,version.snapshot['export_job_id'])
        if current and current.status in ('pending','running','succeeded'):return current
    await require_idle(db,project)
    params=await get_generation_params(db);await require_generation_capacity(db,user.id,params.max_concurrent_jobs)
    segments=(await db.scalars(select(VideoSegment).where(VideoSegment.version_id==version.id).order_by(VideoSegment.position))).all()
    try:await verify_direct(MaterialStorage(settings),version,segments)
    except (ValueError,KeyError,OSError) as error:raise api_error(409,'preview_integrity_error',str(error) if isinstance(error,ValueError) else '预览资源不可用，请重新生成预览') from None
    job=await create_job(db,project,'video_export',body.idempotency_key,{'version_id':str(version.id)})
    version.snapshot={**version.snapshot,'export_job_id':str(job.id)}
    project.status='video_exporting';await db.commit();await db.refresh(job)
    return job
