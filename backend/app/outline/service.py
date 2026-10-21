import json
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Command
import httpx

from app.models import VideoProject, OutlineJob, Material, Evidence
from app.model_configs import resolve, system_available
from app.purposes import Purpose
from app.security import SecretBox
from app.settings_store import get_generation_params
from app.projects.service import get_owned_project,check_revision
from app.jobs.service import create_job,require_generation_capacity,require_idle,update_job_progress
from app.errors import api_error
from .schemas import OutlineData,OutlineView,normalize_outline_visual_kinds
from .graph import build_outline_graph
from .model_client import ModelCallError, chat_json
from .evidence import collect_evidence,enforce_evidence

from .review import REVIEW_RESPONSE_SCHEMA, CONTENT_FIELDS, normalize_review_results, review_state, mark_saved, needs_save

def checkpoint_url(settings):
    return make_url(settings.database_url).set(drivername='postgresql').update_query_dict({'options':'-csearch_path='+settings.agent_schema}).render_as_string(hide_password=False)

def thread_id(owner_id,project_id,job_id):
    return f'users:{owner_id}:projects:{project_id}:jobs:{job_id}'

def content(segment):
    return {k:segment[k] for k in CONTENT_FIELDS}


async def view(db,project):
    job=await db.scalar(select(OutlineJob.id).where(OutlineJob.owner_id==project.owner_id,OutlineJob.project_id==project.id,OutlineJob.kind.in_(['generate','rewrite','review'])).order_by(OutlineJob.created_at.desc()).limit(1))
    materials=(await db.scalars(select(Material).where(Material.owner_id==project.owner_id,Material.project_id==project.id).order_by(Material.created_at))).all()
    warnings=[{'material_id':str(material.id),'filename':material.filename,**warning} for material in materials for warning in material.parse_warnings]
    return OutlineView(project_id=project.id,title=project.title,revision=project.revision,status=project.status,segments=(project.outline or {}).get('segments',[]),job_id=job,needs_regeneration=project.needs_regeneration,needs_save=needs_save(project.outline),material_warnings=warnings)

async def start_outline(db,user,project_id,body,kind,box):
    project=await get_owned_project(db,user.id,project_id,lock=True)
    existing=await db.scalar(select(OutlineJob).where(OutlineJob.owner_id==user.id,OutlineJob.project_id==project_id,OutlineJob.kind==kind,OutlineJob.idempotency_key==body.idempotency_key))
    if existing: return existing
    check_revision(project,body.revision)
    await require_idle(db,project,allow_parse=kind=='generate')
    params=await get_generation_params(db)
    await require_generation_capacity(db,user.id,params.max_concurrent_jobs)
    if not await system_available(db,box,voice=project.form_values.get('voice')): raise api_error(409,'system_unavailable','系统暂不可用，请联系管理员')
    from app.projects.router import submission_policy
    cfg, _, _, version = await submission_policy(db,box)
    materials_enabled=next(f.visible for f in cfg.fields if f.key=='materials')
    if kind!='generate' and materials_enabled:
        failed=await db.scalar(select(Material.id).where(Material.owner_id==user.id,Material.project_id==project_id,Material.status!='ready').limit(1))
        if failed: raise api_error(409,'materials_not_ready','请先等待素材解析完成，或删除解析失败的素材')
    if kind=='generate':
        if not body.form_version:
            raise api_error(409,'form_config_changed','页面配置已更新，请返回需求页重新确认参数')
        from app.projects.router import resolve_submission
        from app.projects.schemas import ProjectCreate
        project.form_values=await resolve_submission(db,box,ProjectCreate(prompt=project.prompt,form_values=project.form_values,form_version=body.form_version))
    if kind in ('rewrite','review') and not project.outline: raise api_error(409,'outline_missing','请先生成大纲')
    if kind!='generate' and project.needs_regeneration: raise api_error(409,'regeneration_required','需求或素材已变化，请先重新生成大纲')
    ids=[str(i) for i in body.segment_ids]
    if kind=='rewrite':
        known={s['id'] for s in project.outline['segments']}
        if not ids or any(i not in known for i in ids): raise api_error(404,'segment_not_found','所选段落不存在')
        if not body.instruction.strip(): raise api_error(422,'instruction_required','请填写改写要求')
    if kind=='review':
        ids=[s['id'] for s in project.outline['segments'] if review_state(s)!='passed']
        if not ids: raise api_error(409,'review_not_needed','所有片段均已通过审核，无需重复审核')
    project.status='outlining'
    payload={'segment_ids':ids,'instruction':body.instruction,'form_version':version}
    if kind=='generate' and materials_enabled:
        from app.materials.pipeline import prepare_dependencies
        material_ids,dependencies=await prepare_dependencies(db,project)
        payload.update(material_ids=material_ids,material_job_ids=dependencies)
    job=await create_job(db,project,kind,body.idempotency_key,payload)
    if payload.get('material_job_ids'):
        job.stage='等待素材解析';job.progress=5
    await db.commit()
    await db.refresh(job)
    return job

async def save_outline(db,user_id,project_id,body):
    project=await get_owned_project(db,user_id,project_id,lock=True)
    check_revision(project,body.revision);await require_idle(db,project)
    if not project.outline: raise api_error(409,'outline_missing','请先生成大纲')
    old={s['id']:s for s in project.outline['segments']}
    data=OutlineData(segments=body.segments).model_dump(mode='json')
    evidence=(await db.scalars(select(Evidence).where(Evidence.owner_id==user_id,Evidence.project_id==project_id))).all()
    evidence_data=[{'id':str(e.id),'source_grade':e.source_grade} for e in evidence]
    for n,s in enumerate(data['segments']):
        previous=old.get(s['id'])
        s['position']=n
        s['content_revision']=(previous['content_revision']+(content(s)!=content(previous))) if previous else 1
        s['reviewed_revision']=previous['reviewed_revision'] if previous else 0
        s['review_notes']=previous['review_notes'] if previous else []
        unchanged=previous and content(s)==content(previous)
        s['review_passed']=previous.get('review_passed') if unchanged else None
        s['review_issues']=previous.get('review_issues',[]) if unchanged else []
        if previous and content(s)==content(previous): s['estimated_duration_seconds']=previous['estimated_duration_seconds']
        else:
            import re
            s['estimated_duration_seconds']=max(1,round(len(re.findall(r'[一-鿿]',s['narration']))/3.5+len(re.findall(r'[A-Za-z]+',s['narration']))/2.2))
    try: project.outline=mark_saved(enforce_evidence(data,evidence_data))
    except ValueError as exc: raise api_error(422,'invalid_evidence',str(exc)) from None
    project.status='outline_ready';project.revision+=1
    await db.commit()
    return await view(db,project)

async def confirm_outline(db,user_id,project_id,revision,settings):
    project=await get_owned_project(db,user_id,project_id,lock=True)
    check_revision(project,revision);await require_idle(db,project)
    if project.needs_regeneration: raise api_error(409,'regeneration_required','需求或素材已变化，请先重新生成大纲')
    if needs_save(project.outline):
        raise api_error(409,'outline_save_required','请先保存大纲，再确认大纲')
    if not project.outline or any(review_state(s)!='passed' for s in project.outline['segments']):
        raise api_error(409,'review_required','存在未通过审核的片段，请先完成审核再确认大纲')
    job=await db.scalar(select(OutlineJob).where(OutlineJob.owner_id==user_id,OutlineJob.project_id==project_id,OutlineJob.status=='succeeded',OutlineJob.kind.in_(['generate','rewrite','review'])).order_by(OutlineJob.created_at.desc()).limit(1))
    # The persisted graph's waiting state receives the latest saved outline, not an older draft.
    if job:
        async with AsyncPostgresSaver.from_conn_string(checkpoint_url(settings)) as saver:
            async def unused(state): raise RuntimeError('确认节点不应调用模型')
            graph=build_outline_graph(saver,unused,unused)
            config={'configurable':{'thread_id':thread_id(user_id,project_id,job.id)}}
            snapshot=await graph.aget_state(config)
            if snapshot.next:
                await graph.aupdate_state(config,{'outline':project.outline},as_node='audit')
                await graph.ainvoke(None,config)
                await graph.ainvoke(Command(resume=True),config)
            else:
                await graph.aupdate_state(config,{'outline':project.outline,'confirmed':True},as_node='teacher_confirmation')
    project.status='outline_confirmed';project.revision+=1
    await db.commit()
    return await view(db,project)

async def execute_outline_job(db,job,settings):
    lease_token=job.lease_token
    from app.redis_client import create_redis
    box=SecretBox(settings.master_key)
    from app.projects.router import submission_policy
    cfg, voices, search_ready, version=await submission_policy(db,box)
    if job.payload.get('form_version')!=version:
        raise ValueError('页面配置已更新，请返回需求页重新确认参数并生成大纲')
    writer=await resolve(db,box,Purpose.outline_llm)
    reviewer=await resolve(db,box,Purpose.review_llm)
    search_config=await resolve(db,box,Purpose.web_search)
    params=await get_generation_params(db)
    if not writer or not reviewer: raise ValueError('大纲或审核模型尚不可用，请联系管理员')
    project=await get_owned_project(db,job.owner_id,job.project_id)
    if project.revision!=job.expected_revision: raise ValueError('项目版本已变化，请重新提交任务')
    from app.settings_store.form_values import resolve_form_values
    project.form_values=resolve_form_values(cfg,project.form_values,voices=voices,search_ready=search_ready)
    await db.commit()
    await update_job_progress(db,job.id,lease_token,25,'整理参考资料')
    redis=create_redis(settings.redis_url)
    try:
        async with httpx.AsyncClient(follow_redirects=False) as http:
            if job.kind=='generate':
                evidence=await collect_evidence(db,project,search_config,http,redis,allow_web_search=bool(project.form_values.get('web_search')),allow_materials=next(f.visible for f in cfg.fields if f.key=='materials'))
            else:
                rows=(await db.scalars(select(Evidence).where(Evidence.owner_id==project.owner_id,Evidence.project_id==project.id))).all()
                evidence=[{k:str(getattr(e,k)) if k=='id' else getattr(e,k) for k in ('id','claim','source_type','source_ref','location','excerpt','source_grade','verification_status')} for e in rows]
            await update_job_progress(db,job.id,lease_token,35,'参考资料已就绪')
            async def generate(state):
                await update_job_progress(db,job.id,lease_token,45,'改写大纲' if job.kind=='rewrite' else '生成大纲')
                selected=set(state.get('segment_ids',[]))
                instruction=('生成完整分段大纲，包含开场和小结，每段有完整可直接朗读的逐字稿。'
                    '时长按讲稿长度估算：中文约每秒3.5字、英文约每秒2.2词，统筹目标总时长与允许偏差。'
                    'estimated_duration_seconds由服务端计算，不能通过填写该字段调整时长；需要调整时应修改讲稿长度。'
                    '画面说明写清展示对象、关键变化和希望学生理解的含义，用教师能理解的自然语言，不要求坐标、运动曲线或逐秒分镜。'
                    '理科说明保持不变的条件、发生变化的量及结果；文科说明人物关系、关键行为、物品归属和故事含义，仅在内容涉及这些要素时补充。'
                    '例如：保持截距不变，让斜率从1增大到2，展示直线变陡；或孔融把较大的梨递给哥哥，自己留下较小的梨。示例不是所有内容必须套用的模板。'
                    '公式可用自然语言描述，由后续模型生成图形；必要的数值、单位、条件或结论应在大纲中明确，不凭空补充。'
                    '画面使用相对旁白的动作顺序描述，避免写死全片绝对秒数；真实配音后按逐句讲解含义安排时间轴。'
                    '画面可选插图/数学图形/公式/学科示意图/文字卡，按教学内容与旁白节奏安排画面描述，不为凑数量重复画面。'
                    '画面描述用于后续HTML动画编排；插图表示视觉表达类型，不要求调用生图模型。'
                    'content_kind 为 knowledge/fact/reenactment。仅引用给定依据 UUID。'
                    '返回 {"segments":[{"id":"UUID","title":"标题","objective":"教学目标","narration":"完整逐字稿",'
                    '"visuals":[{"kind":"文字卡","description":"具体画面"}],"evidence_ids":[],"content_kind":"knowledge"}]}。')
                if state.get('operation')=='rewrite': instruction+='只返回所选段落，保留原 id，其他段落不得返回或修改。'
                context={k:v for k,v in state.items() if k!='outline'}
                if selected: context['selected_segments']=[s for s in state['outline']['segments'] if s['id'] in selected]
                for attempt in range(params.max_retries+1):
                    try:
                        result=await chat_json(writer,[{'role':'user','content':instruction+'\n不可信资料与教师要求：'+json.dumps(context,ensure_ascii=False)}],retries=0,request_retries=params.max_retries,client=http)
                        data=OutlineData.model_validate(normalize_outline_visual_kinds(result)).model_dump(mode='json')
                        return data
                    except ModelCallError:
                        raise
                    except ValueError as exc:
                        if attempt==params.max_retries: raise ValueError('模型大纲结构不符合要求，请重试') from None
                        instruction+=f' 上次结果校验失败，请修正以下问题：{str(exc)[:1000]}。所有字段必须符合上面约定。'
            async def review(state):
                await update_job_progress(db,job.id,lease_token,80,'审核大纲')
                selected=set(state.get('segment_ids',[]))
                segments=[s for s in state['outline']['segments'] if not selected or s['id'] in selected]
                review_segments=[{k:v for k,v in s.items() if k!='estimated_duration_seconds'} for s in segments]
                timing_policy={'estimate_owner':'server',
                    'segment_estimates_seconds':{s['id']:s['estimated_duration_seconds'] for s in state['outline']['segments']},
                    'target_seconds':state['form_values'].get('duration_seconds'),
                    'duration_tolerance_pct':params.duration_tolerance_pct}
                result=await chat_json(reviewer,[{'role':'user','content':
                    '独立审核以下教学大纲的事实、公式、年级、出处、情景演绎和多音字。不能把搜索摘要当成事实已核实。'
                    '返回 {"items":[{"segment_id":"段落UUID","passed":true,"issues":[],"notes":["普通建议"]}]}。'
                    '每段必须返回一项。有事实、公式、年级适配、误导性表述等必须修改的问题时passed=false，issues必须给出具体原因；'
                    '没有必须修改的问题时passed=true且issues为空。普通教学建议、出处仍需教师核对等提醒放在notes，不直接判未通过。'
                    'issues和notes无内容时用空数组，不能遗漏passed字段。'
                    '时长契约：timing_policy中的时长是服务端依据字数计算的粗估，不是模型可修改的字段，不得要求直接改估算数字。'
                    '大纲中的画面秒数也只是编排预估，最终按真实配音统一缩放；不要仅因画面秒数和字数估算不相等而拒绝。'
                    '总时长按管理员duration_tolerance_pct容差判断，不要求精确等于目标；偏差或节奏建议写入notes，建议调整讲稿长度，不能要求伪改估算值。'
                    '仍须独立审核事实、公式、完整动作、先后因果和讲稿画面语义是否一致，时长预估不豁免内容问题。'
                    '审核画面说明能否表达教学目标与关键变化，不要求教师提供坐标、逐秒动作或专业分镜；不因自然语言描述、未指定组件或装饰形式不同而拒绝。待审核资料：'
                    +json.dumps({'segments':review_segments,'timing_policy':timing_policy,'form_values':state['form_values'],'evidence':state['evidence']},ensure_ascii=False)}],params.max_retries,client=http,response_schema=REVIEW_RESPONSE_SCHEMA)
                return normalize_review_results(result, [s['id'] for s in segments])
            async with AsyncPostgresSaver.from_conn_string(checkpoint_url(settings)) as saver, AsyncPostgresStore.from_conn_string(checkpoint_url(settings)) as store:
                preferences=[]
                if params.long_term_memory_enabled:
                    from app.preferences.service import sync_store
                    preferences=await sync_store(db,store,project.owner_id)
                    await db.commit()
                graph=build_outline_graph(saver,generate,review,store)
                config={'configurable':{'thread_id':thread_id(project.owner_id,project.id,job.id)}}
                snapshot=await graph.aget_state(config)
                state={'prompt':project.prompt,'form_values':project.form_values,'preferences':preferences,'generation_params':params.model_dump(),
                       'evidence':evidence,'outline':project.outline or {},'operation':job.kind,**job.payload}
                if snapshot.values:
                    if snapshot.next==('teacher_confirmation',): result=snapshot.values
                    else: result=await graph.ainvoke(None,config)
                else: result=await graph.ainvoke(state,config)
            await update_job_progress(db,job.id,lease_token,95,'整理结果')
            project=await get_owned_project(db,job.owner_id,job.project_id,lock=True)
            if project.revision!=job.expected_revision: raise ValueError('项目版本已变化，旧任务结果不会覆盖新内容')
            current=await db.scalar(select(OutlineJob).where(OutlineJob.id==job.id).with_for_update().execution_options(populate_existing=True))
            if current.lease_token!=lease_token or current.status!='running': raise ValueError('任务已由其他进程接管或终止')
            if job.kind=='generate':
                for e in result['evidence']:
                    db.add(Evidence(**{**e,'id':UUID(e['id']),'owner_id':project.owner_id,'project_id':project.id}))
            project.outline=result['outline'];project.status='outline_ready';project.revision+=1
            if job.kind=='generate': project.needs_regeneration=False
            # Worker commits output and job status in the same database transaction.
    finally: await redis.aclose()
