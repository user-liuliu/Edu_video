from copy import deepcopy
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from app.presentations import generation

def outline():
    return {'slides':[{'id':str(uuid4()),'layout':'concept','title':'顶点公式','content':'y=ax²+bx+c 的对称轴为 x=b/(2a)，a≠0','slots':{}}]}

async def test_knowledge_check_corrects_formula_and_returns_exact_content_approval(monkeypatch):
    from app.presentations.knowledge import check_outline,require_reviewed_outline
    original=outline();sid=original['slides'][0]['id'];requests=[]
    async def model(config,payload,**kwargs):
        requests.append(deepcopy(payload))
        if payload['operation']=='knowledge_review':
            bad='x=b/' in payload['outline']['slides'][0]['content']
            return {'status':'needs_attention' if bad else 'passed','issues':[{'slide_id':sid,'message':'对称轴符号错误','repair':'改为 x=-b/(2a)'}] if bad else []}
        assert payload['operation']=='knowledge_repair'
        return {'slides':[{**original['slides'][0],'content':'y=ax²+bx+c 的对称轴为 x=-b/(2a)，a≠0'}]}
    monkeypatch.setattr(generation,'call',model)
    result=await check_outline(object(),original,[])
    require_reviewed_outline(result)
    assert 'x=-b/(2a)' in result['slides'][0]['content']
    assert result['review']['changes'][0]['slide_id']==sid
    assert original['slides'][0]['content'].startswith('y=ax²+bx+c 的对称轴为 x=b/')
    assert [r['operation'] for r in requests]==['knowledge_review','knowledge_repair','knowledge_review']
    result['slides'][0]['content']='后来改错的公式'
    with pytest.raises(ValueError):require_reviewed_outline(result)

async def test_knowledge_check_retains_unresolved_issues_after_bounded_corrections(monkeypatch):
    from app.presentations.knowledge import check_outline,require_reviewed_outline
    original=outline();sid=original['slides'][0]['id'];repairs=[]
    async def model(config,payload,**kwargs):
        if payload['operation']=='knowledge_review':return {'status':'needs_attention','issues':[{'slide_id':sid,'message':'公式错误','repair':'修正公式'}]}
        repairs.append(payload);return original
    monkeypatch.setattr(generation,'call',model)
    result=await check_outline(object(),original,[])
    assert len(repairs)==2 and result['review']['status']=='needs_attention'
    with pytest.raises(ValueError):require_reviewed_outline(result)

@pytest.mark.parametrize('verdict',[{}, {'status':'passed','issues':[{'slide_id':'wrong','message':'错','repair':'改'}]}, {'status':'needs_attention','issues':[]}])
async def test_invalid_knowledge_verdict_never_passes(monkeypatch,verdict):
    from app.presentations.knowledge import check_outline
    monkeypatch.setattr(generation,'call',AsyncMock(return_value=verdict))
    with pytest.raises(ValueError):await check_outline(object(),outline(),[])

async def test_knowledge_repair_cannot_rewrite_an_unselected_page(monkeypatch):
    from app.presentations.knowledge import check_outline
    original=outline();other={**original['slides'][0],'id':str(uuid4()),'title':'无错误页','content':'二次项系数不为零'};original['slides'].append(other)
    async def model(config,payload,**kwargs):
        if payload['operation']=='knowledge_review':return {'status':'needs_attention','issues':[{'slide_id':original['slides'][0]['id'],'message':'符号错','repair':'改符号'}]}
        return {'slides':[{**s,'content':'全改了'} for s in original['slides']]}
    monkeypatch.setattr(generation,'call',model)
    with pytest.raises(ValueError):await check_outline(object(),original,[])


async def test_selected_outline_rewrite_does_not_repair_unselected_knowledge(monkeypatch):
    from types import SimpleNamespace
    first=outline()['slides'][0];second={**first,'id':str(uuid4()),'title':'另一页'}
    project=SimpleNamespace(outline={'slides':[first,second]},pages=[],prompt='函数')
    job=SimpleNamespace(kind='rewrite',payload={'slide_ids':[first['id']],'instruction':'精简'},checkpoint={})
    monkeypatch.setattr(generation,'references',AsyncMock(return_value=([],[])))
    monkeypatch.setattr(generation,'resolve',AsyncMock(return_value=object()))
    monkeypatch.setattr(generation,'rewrite_outline',AsyncMock(return_value=project.outline))
    calls=[]
    async def model(config,payload,**kwargs):
        calls.append(payload['operation'])
        if payload['operation']=='knowledge_review':return {'status':'needs_attention','issues':[{'slide_id':second['id'],'message':'未选页公式错','repair':'修改符号'}]}
        return {'slides':[{**second,'content':'被悄悄改动'}]}
    monkeypatch.setattr(generation,'call',model)
    async def progress(*args):pass
    with pytest.raises(ValueError,match='未选页面'):
        await generation.build_result(None,project,job,SimpleNamespace(master_key='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='),progress)
    assert calls==['knowledge_review']

async def test_knowledge_check_can_correct_a_formula_in_the_title(monkeypatch):
    from app.presentations.knowledge import check_outline,require_reviewed_outline
    original=outline();original['slides'][0]['title']='对称轴 x=b/(2a)';sid=original['slides'][0]['id']
    async def model(config,payload,**kwargs):
        if payload['operation']=='knowledge_review':
            bad='x=b/' in payload['outline']['slides'][0]['title']
            return {'status':'needs_attention' if bad else 'passed','issues':[{'slide_id':sid,'message':'标题公式错','repair':'修正负号'}] if bad else []}
        return {'slides':[{**original['slides'][0],'title':'对称轴 x=-b/(2a)'}]}
    monkeypatch.setattr(generation,'call',model)
    result=await check_outline(object(),original,[])
    require_reviewed_outline(result)
    assert result['slides'][0]['title']=='对称轴 x=-b/(2a)' and result['review']['changes']
