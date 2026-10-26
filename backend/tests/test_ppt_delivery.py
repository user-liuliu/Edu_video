from copy import deepcopy
from uuid import uuid4
from io import BytesIO
from pptx import Presentation
import pytest
from app.presentations import delivery,master_runtime as master
from app.presentations.quality import QualityError,require_approved_pages
from tests.test_ppt_master_runtime import sample_svg

def page():
    return {'id':str(uuid4()),'layout':'concept','title':'教学内容','content':'已确认的知识点','slots':{},'renderer':master.VERSION,'svg':sample_svg(),'design':{'visual_brief':'知识点','composition':'清晰'},'review':{'status':'needs_attention','issues':[{'category':'teaching','message':'尚需确认','repair':'教师核对'}],'repairs':2,'rebuilds':1}}

def test_delivery_is_bound_to_exact_file_content_without_faking_review():
    source=page();result=delivery.certify_pages([source],[b'actual-exported-page'])
    delivery.require_deliverable_pages(result)
    assert result[0]['review']==source['review'] and 'delivery' not in source
    with pytest.raises(QualityError):require_approved_pages(result)
    changed=deepcopy(result);changed[0]['svg']=changed[0]['svg'].replace('光合作用','错误')
    with pytest.raises(ValueError):delivery.require_deliverable_pages(changed)
    with pytest.raises(ValueError):delivery.certify_pages([source],[])
    with pytest.raises(ValueError):delivery.certify_pages([source],[b''])

async def test_verified_last_resort_is_previewable_downloadable_and_completed(teacher_client,db):
    from app.presentations.models import PptProject
    from tests.test_ppt_api import create
    from uuid import UUID
    created=await create(teacher_client);project=await db.get(PptProject,UUID(created['id']))
    source=page();project.outline={'slides':[{k:source[k] for k in ('id','layout','title','content','slots')}]};project.pages=delivery.certify_pages([source],[b'actual-exported-page']);project.status='ready';project.rendered_revision=project.confirmed_revision=1
    await db.commit();base='/api/presentations/'+created['id']
    preview=await teacher_client.get(base+'/slides/'+source['id']+'/preview')
    assert preview.status_code==200,preview.text
    exported=await teacher_client.get(base+'/export')
    assert exported.status_code==200,exported.text
    assert len(Presentation(BytesIO(exported.content)).slides)==1
    completed=(await teacher_client.get('/api/presentations?scope=completed')).json()
    assert created['id'] in [p['id'] for p in completed['items']]
    assert not (await teacher_client.get('/api/presentations?scope=drafts')).json()['items']

@pytest.mark.parametrize('vision_available',[True,False])
async def test_last_resort_occurs_after_quality_repairs_and_template_review(monkeypatch,vision_available):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.presentations import generation
    from app.presentations.knowledge import VERSION,outline_digest
    from app.purposes import Purpose
    source=page();slide={k:source[k] for k in ('id','layout','title','content','slots')}
    outline={'slides':[slide]};outline['review']={'version':VERSION,'status':'passed','issues':[],'content_sha256':outline_digest(outline)}
    project=SimpleNamespace(outline=outline,pages=[],title='兜底顺序')
    job=SimpleNamespace(kind='render',payload={'slide_ids':[],'instruction':''},checkpoint={})
    monkeypatch.setattr(generation,'references',AsyncMock(return_value=([],[])))
    async def resolve(db,box,purpose):return None if purpose==Purpose.vision_llm and not vision_available else object()
    monkeypatch.setattr(generation,'resolve',resolve)
    monkeypatch.setattr(generation,'load_assets',AsyncMock(return_value={}))
    design={'id':slide['id'],'visual_kind':'text','visual_brief':'内容','composition':'清晰'}
    monkeypatch.setattr(generation,'plan_pages',AsyncMock(return_value={'pages':[design]}))
    events=[]
    async def render_page(config,s,*args,**kwargs):
        events.append('rebuild' if kwargs.get('simplified') else 'repair' if kwargs.get('current') else 'generate')
        return {**s,'renderer':master.VERSION,'svg':sample_svg(),'design':design}
    monkeypatch.setattr(generation,'render_page',render_page)
    def compile_deck(candidate,*args):events.append('export-fallback' if candidate[0].get('fallback') else 'export-model');return b'PK-test'
    monkeypatch.setattr(master,'compile_deck',compile_deck)
    monkeypatch.setattr(generation,'render_review_images',lambda data,count:[b'actual']*count)
    async def review(config,p,image,context):
        events.append('review-fallback' if p.get('fallback') else 'review-model')
        return [{'category':'readability','message':'内容需进一步确认','repair':'调整排版'}]
    monkeypatch.setattr(generation,'review_page',review)
    async def progress(value,stage,checkpoint=None):
        if stage=='验证整份课件文件，准备交付':events.append('last-resort-file-check')
    result=await generation.build_result(None,project,job,SimpleNamespace(master_key='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='),progress)
    delivery.require_deliverable_pages(result['pages'])
    assert result['pages'][0]['delivery']['mode']=='fallback'
    if vision_available:
        assert events[:4]==['generate','export-model','review-model','repair']
        assert events.count('repair')==2 and events.count('rebuild')==1
        assert events.index('rebuild')<events.index('review-fallback')<events.index('last-resort-file-check')
    assert events[-2:]==['last-resort-file-check','export-fallback']


async def test_broken_final_file_preserves_previous_delivery(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.presentations import generation
    from app.presentations.knowledge import VERSION,outline_digest
    source=page();slide={k:source[k] for k in ('id','layout','title','content','slots')}
    outline={'slides':[slide]};outline['review']={'version':VERSION,'status':'passed','issues':[],'content_sha256':outline_digest(outline)}
    project=SimpleNamespace(outline=outline,pages=[],title='文件失败保留')
    job=SimpleNamespace(kind='render',payload={'slide_ids':[],'instruction':''},checkpoint={})
    monkeypatch.setattr(generation,'references',AsyncMock(return_value=([],[])))
    monkeypatch.setattr(generation,'resolve',AsyncMock(return_value=object()))
    monkeypatch.setattr(generation,'load_assets',AsyncMock(return_value={}))
    monkeypatch.setattr(generation,'plan_pages',AsyncMock(side_effect=generation.GenerationError('规划服务暂不可用')))
    monkeypatch.setattr(master,'compile_deck',lambda *args:(_ for _ in ()).throw(master.MasterError('文件无法导出')))
    async def progress(*args):pass
    with pytest.raises(generation.GenerationError,match='原课件已保留'):
        await generation.build_result(None,project,job,SimpleNamespace(master_key='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='),progress)
    assert project.pages==[] and project.outline==outline

async def test_worker_publishes_last_resort_after_file_verification(teacher_client,db,settings,monkeypatch):
    from uuid import UUID
    from unittest.mock import AsyncMock
    from app.presentations import generation,router,tasks
    from app.presentations.models import PptProject
    from app.presentations.knowledge import VERSION,outline_digest
    from tests.test_ppt_api import create
    created=await create(teacher_client);project=await db.get(PptProject,UUID(created['id']))
    source=page();outline={'slides':[{k:source[k] for k in ('id','layout','title','content','slots')}]};outline['review']={'version':VERSION,'status':'passed','issues':[],'content_sha256':outline_digest(outline)}
    project.outline=outline;project.confirmed_revision=1;await db.commit()
    pages=delivery.certify_pages([source],[b'exported-final-file'])
    monkeypatch.setattr(router,'resolve',AsyncMock(return_value=object()))
    monkeypatch.setattr(generation,'build_result',AsyncMock(return_value={'outline':outline,'pages':pages,'warnings':[],'partial':False}))
    base='/api/presentations/'+created['id']
    response=await teacher_client.post(base+'/jobs/render',json={'revision':1,'idempotency_key':'last-resort'})
    assert response.status_code==200,response.text
    await tasks.run_job(response.json()['id'],settings)
    state=(await teacher_client.get(base)).json()
    assert state['job']['status']=='succeeded' and state['status']=='ready'
    assert state['pages'][0]['review']['status']=='needs_attention'
    assert state['pages'][0]['delivery']==pages[0]['delivery']
    assert (await teacher_client.get(base+'/export')).status_code==200


async def test_missing_vision_service_does_not_block_confirmed_generation(teacher_client,db,monkeypatch):
    from uuid import UUID
    from app.presentations import router
    from app.presentations.models import PptProject
    from app.presentations.knowledge import VERSION,outline_digest
    from app.purposes import Purpose
    from tests.test_ppt_api import create
    created=await create(teacher_client);project=await db.get(PptProject,UUID(created['id']))
    source=page();outline={'slides':[{k:source[k] for k in ('id','layout','title','content','slots')}]};outline['review']={'version':VERSION,'status':'passed','issues':[],'content_sha256':outline_digest(outline)}
    project.outline=outline;project.confirmed_revision=1;await db.commit()
    async def resolve(db,box,purpose):return None if purpose==Purpose.vision_llm else object()
    monkeypatch.setattr(router,'resolve',resolve)
    response=await teacher_client.post('/api/presentations/'+created['id']+'/jobs/render',json={'revision':1,'idempotency_key':'no-vision-service'})
    assert response.status_code==200,response.text

async def test_completed_delivery_list_paginates_before_loading_full_decks(teacher_client,db,app):
    from sqlalchemy import event
    from uuid import UUID
    from app.presentations.models import PptProject
    from tests.test_ppt_api import create
    created=await create(teacher_client);project=await db.get(PptProject,UUID(created['id']))
    source=page();project.outline={'slides':[{k:source[k] for k in ('id','layout','title','content','slots')}]};project.pages=delivery.certify_pages([source],[b'actual-file']);project.rendered_revision=project.confirmed_revision=1;project.status='ready';project.exported_revision=1;await db.commit()
    statements=[]
    engine=app.state.engine.sync_engine
    def observe(conn,cursor,statement,parameters,context,executemany):
        if 'FROM ppt_projects' in statement and 'count(' not in statement:statements.append(statement)
    event.listen(engine,'before_cursor_execute',observe)
    try:
        response=await teacher_client.get('/api/presentations?scope=completed&page=1')
        assert response.status_code==200
        assert response.json()['total']==1
        assert any('LIMIT' in s and 'OFFSET' in s for s in statements),statements
    finally:event.remove(engine,'before_cursor_execute',observe)


def test_certification_preserves_unchanged_teacher_page_when_other_page_is_generated():
    teacher=delivery.confirm_teacher_page(page(),uuid4())
    generated=page()
    result=delivery.certify_pages([teacher,generated],[b'rendered-teacher',b'rendered-generated'])
    assert result[0]==teacher
    assert delivery.teacher_confirmed(result[0])
    assert result[1]['delivery']['mode']=='fallback'
    delivery.require_deliverable_pages(result)
