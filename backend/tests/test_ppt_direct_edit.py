from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from app.presentations import generation
from app.presentations.quality import VERSION,content_digest
from tests.test_ppt_master_runtime import sample_svg
from tests.test_ppt_workflow import checked_outline

@pytest.mark.parametrize('change_content,miss_first,initial_failure',[(False,False,False),(True,False,False),(False,True,False),(True,False,True)])
@pytest.mark.parametrize('with_graphic',[False,True])
async def test_revision_edits_current_svg_without_rewriting_outline_and_preserves_other_pages(monkeypatch,change_content,miss_first,initial_failure,with_graphic):
    slides=[{'id':str(uuid4()),'layout':'cover','title':'光合作用','content':'学习目标：说清原料；解释条件；分析现象。','slots':{}} for _ in range(2)]
    pages=[]
    for slide in slides:
        p={**slide,'renderer':generation.master.VERSION,'svg':sample_svg(),'design':{'id':slide['id'],'visual_kind':'diagram','visual_brief':'树木','composition':'左文右图'}}
        p['review']={'version':VERSION,'status':'passed','issues':[],'repairs':0,'content_sha256':content_digest(p),'image_sha256':'a'*64};pages.append(p)
    if with_graphic:
        pages[0]['graphics']=[{'name':'abcdef0123456789abcdef01.png','version':'test'}]
        pages[0]['svg']=pages[0]['svg'].replace('</svg>','<image href="../images/abcdef0123456789abcdef01.png" x="64" y="400" width="100" height="100"/></svg>')
        pages[0]['review']['content_sha256']=content_digest(pages[0])
    original=checked_outline({'slides':slides})
    project=SimpleNamespace(outline=deepcopy(original),pages=deepcopy(pages),title='光合作用')
    job=SimpleNamespace(kind='revise',payload={'slide_ids':[slides[0]['id']],'instruction':'学习目标加上数字序号，保留其他布局'},checkpoint={})
    seen=[]
    async def model(config,messages,**kwargs):
        data=messages[-1]['content'];payload=json.loads(data[0]['text'] if isinstance(data,list) else data);seen.append(payload)
        if payload['operation']=='edit_svg':
            assert payload['instruction']==job.payload['instruction']
            edit_count=sum(p['operation']=='edit_svg' for p in seen)
            if initial_failure and edit_count==1:raise generation.GenerationError('暂时连接失败')
            assert payload['current_svg']==pages[0]['svg'] if edit_count<=1+int(initial_failure) else '1. 说清原料' in payload['current_svg']
            return {'svg':pages[0]['svg'].replace('光合作用','1. 说清原料'),'slide':{**slides[0],'content':'学习目标：1. 说清原料；2. 解释条件；3. 分析现象。'} if change_content else slides[0]}
        if payload['operation']=='review':return {'status':'passed','issues':[]}
        if payload['operation']=='revision_review':
            if miss_first and sum(p['operation']=='revision_review' for p in seen)==1:return {'status':'needs_attention','issues':[{'category':'generation','severity':'blocking','message':'仍为圆点','repair':'显示1、2、3'}]}
            return {'status':'passed','issues':[]}
        if payload['operation']=='knowledge_review':return {'status':'passed','issues':[]}
        raise AssertionError('unexpected operation: '+payload['operation'])
    monkeypatch.setattr(generation,'chat_json',model)
    monkeypatch.setattr(generation,'references',AsyncMock(return_value=([],[])))
    monkeypatch.setattr(generation,'resolve',AsyncMock(return_value=object()))
    async def assets(db,project,settings,needed=None,*,pages=None):
        if with_graphic and 'abcdef0123456789abcdef01.png' in (needed or []):
            assert pages and pages[0].get('graphics'), 'Current generated image descriptor must be retained'
            from tests.test_ppt_master_assets import png
            return {'abcdef0123456789abcdef01.png':png()}
        return {}
    monkeypatch.setattr(generation,'load_assets',assets)
    monkeypatch.setattr(generation.master,'compile_deck',lambda *a:b'PK-test')
    monkeypatch.setattr(generation,'render_review_images',lambda data,count:[b'actual-rendered-page']*count)
    async def progress(value,stage,checkpoint=None):
        if checkpoint is not None:job.checkpoint=deepcopy(checkpoint)
    result=await generation.build_result(None,project,job,SimpleNamespace(master_key='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='),progress)
    assert '1. 说清原料' in result['pages'][0]['svg']
    assert result['pages'][1]==pages[1]
    if with_graphic:assert result['pages'][0]['graphics']==pages[0]['graphics']
    checkpoint=deepcopy(job.checkpoint)
    resumed=await generation.build_result(None,project,job,SimpleNamespace(master_key='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='),progress)
    assert resumed['pages']==result['pages']
    assert job.checkpoint['generation_attempts']==checkpoint['generation_attempts']
    if change_content:assert result['outline']['slides'][0]['content'].startswith('学习目标：1.')
    else:assert result['outline']==original
    if miss_first:assert result['pages'][0]['review']['repairs']==1
    assert any(p['operation']=='revision_review' and p['instruction']==job.payload['instruction'] for p in seen)
    assert not any(p['operation'] in ('rewrite','design') for p in seen)

async def test_direct_editor_rejects_changed_id_and_unsafe_svg(monkeypatch):
    from app.presentations.revisions import edit_page
    slide={'id':str(uuid4()),'layout':'concept','title':'光合作用','content':'植物利用光能','slots':{}}
    async def model(*args,**kwargs):return {'slide':{**slide,'id':str(uuid4())},'svg':'<svg><script>bad</script></svg>'}
    monkeypatch.setattr(generation,'call',model)
    with pytest.raises(generation.GenerationError,match='局部修改未完成'):
        await edit_page(object(),slide,{'slides':[slide]},[],{'svg':sample_svg()}, {},'加编号')

async def test_quality_repairs_cannot_silently_change_reviewed_teaching_content(monkeypatch):
    slide={'id':str(uuid4()),'layout':'concept','title':'光合作用','content':'植物利用光能','slots':{}}
    async def edit(*a,**k):return {**slide,'content':'未经核查的新知识','svg':sample_svg()}
    monkeypatch.setattr(generation,'edit_page',edit)
    with pytest.raises(generation.GenerationError,match='内容'):
        await generation.render_page(object(),slide,{'slides':[slide]},[],{}, {},current={**slide,'svg':sample_svg()},instruction='增加序号',issues=[{'message':'序号缺失'}],freeze_content=True)

@pytest.mark.parametrize('accepted',[False,True])
async def test_downgraded_revision_must_still_fulfil_request_before_replacing_old_deck(monkeypatch,accepted):
    slide={'id':str(uuid4()),'layout':'concept','title':'光合作用','content':'植物利用光能','slots':{}}
    old={**slide,'renderer':generation.master.VERSION,'svg':sample_svg(),'design':{'id':slide['id'],'visual_kind':'text','visual_brief':'文字','composition':'保留原页'}}
    old['review']={'version':VERSION,'status':'passed','issues':[],'repairs':0,'content_sha256':content_digest(old),'image_sha256':'a'*64}
    project=SimpleNamespace(outline=checked_outline({'slides':[slide]}),pages=[deepcopy(old)],title='课件')
    job=SimpleNamespace(kind='revise',payload={'slide_ids':[slide['id']],'instruction':'学习目标加上数字序号'},checkpoint={})
    seen=[]
    async def model(config,messages,**kwargs):
        content=messages[-1]['content'];data=json.loads(content[0]['text'] if isinstance(content,list) else content);seen.append(data)
        if data['operation']=='edit_svg':raise generation.GenerationError('模型未完成局部编辑')
        if data['operation']=='review':return {'status':'passed','issues':[]}
        if data['operation']=='revision_review':
            assert data['instruction']==job.payload['instruction']
            assert data['current_pages'] and len(content)==len(data['current_pages'])+1
            return {'status':'passed','issues':[]} if accepted else {'status':'needs_attention','issues':[{'category':'generation','severity':'blocking','message':'未显示序号','repair':'添加数字序号'}]}
        raise AssertionError(data['operation'])
    monkeypatch.setattr(generation,'chat_json',model)
    monkeypatch.setattr(generation,'references',AsyncMock(return_value=([],[])))
    monkeypatch.setattr(generation,'resolve',AsyncMock(return_value=object()))
    monkeypatch.setattr(generation,'load_assets',AsyncMock(return_value={}))
    monkeypatch.setattr(generation.master,'compile_deck',lambda *args:b'PK-test')
    monkeypatch.setattr(generation,'render_review_images',lambda data,count:[b'final-render']*count)
    progress=AsyncMock();settings=SimpleNamespace(master_key='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
    if not accepted:
        with pytest.raises(generation.GenerationError,match='修改要求.*原课件已保留'):
            await generation.build_result(None,project,job,settings,progress)
    else:
        result=await generation.build_result(None,project,job,settings,progress)
        assert result['pages'] and any(data['operation']=='revision_review' for data in seen)
    assert project.pages==[old]
