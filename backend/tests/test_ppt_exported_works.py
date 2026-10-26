from uuid import UUID
from app.presentations.models import PptProject
from app.presentations.service import invalidate
from tests.test_ppt_api import create
from tests.test_ppt_rendering import page

async def prepared(client,db):
    created=await create(client);project=await db.get(PptProject,UUID(created['id']))
    slide=page();project.pages=[slide];project.outline={'slides':[slide]};project.rendered_revision=1;project.status='ready';await db.commit()
    await db.refresh(project)
    return project,'/api/presentations/'+created['id']

async def ids(client,scope):
    return [p['id'] for p in (await client.get('/api/presentations?scope='+scope)).json()['items']]

async def test_generated_ppt_stays_draft_until_successful_export(teacher_client,db):
    project,base=await prepared(teacher_client,db)
    assert str(project.id) in await ids(teacher_client,'drafts')
    assert str(project.id) not in await ids(teacher_client,'completed')
    assert (await teacher_client.get(base+'/slides/'+project.pages[0]['id']+'/preview')).status_code==200
    assert str(project.id) not in await ids(teacher_client,'completed')
    assert (await teacher_client.get(base+'/export')).status_code==200
    assert str(project.id) in await ids(teacher_client,'completed')
    assert str(project.id) not in await ids(teacher_client,'drafts')
    await db.refresh(project);assert project.exported_revision==1

async def test_failed_export_does_not_archive_ppt(teacher_client,db,monkeypatch):
    from app.presentations import router
    project,base=await prepared(teacher_client,db)
    def broken(*args):raise RuntimeError('compiler unavailable')
    monkeypatch.setattr(router,'export_pptx',broken)
    assert (await teacher_client.get(base+'/export')).status_code==503
    assert str(project.id) in await ids(teacher_client,'drafts')
    assert str(project.id) not in await ids(teacher_client,'completed')

async def test_historical_export_records_selected_revision_and_survives_new_generation(teacher_client,db):
    project,base=await prepared(teacher_client,db)
    invalidate(project);project.revision=2;slide=page();project.pages=[slide];project.outline={'slides':[slide]};project.rendered_revision=2;await db.commit()
    assert str(project.id) not in await ids(teacher_client,'completed')
    assert (await teacher_client.get(base+'/export?version=1')).status_code==200
    await db.refresh(project);assert project.exported_revision==1
    assert str(project.id) in await ids(teacher_client,'completed')
    invalidate(project);project.revision=3;await db.commit()
    assert str(project.id) in await ids(teacher_client,'completed')
    assert str(project.id) not in await ids(teacher_client,'drafts')

async def test_partial_download_does_not_count_as_full_export(teacher_client,db):
    project,base=await prepared(teacher_client,db)
    from app.presentations.quality import content_digest,VERSION
    from tests.test_ppt_master_runtime import sample_svg
    good={**project.pages[0],'renderer':'ppt-master-6.7.0','svg':sample_svg(),'design':{'visual_brief':'叶片','composition':'图文并排'}};good['review']={'status':'passed','issues':[],'repairs':0,'version':VERSION,'content_sha256':content_digest(good),'image_sha256':'a'*64}
    bad=page();bad['review']={'status':'needs_attention','issues':[{'category':'teaching','message':'needs repair'}]}
    project.pages=[good,bad];project.outline={'slides':[good,bad]};project.status='partial_ready';await db.commit()
    assert (await teacher_client.get(base+'/export?partial=true')).status_code==200
    assert str(project.id) not in await ids(teacher_client,'completed')
