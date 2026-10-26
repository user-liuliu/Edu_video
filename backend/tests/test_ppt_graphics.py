from copy import deepcopy
from io import BytesIO
import pytest
from pydantic import ValidationError
from app.presentations.graphic_contract import GraphicSpec, VERSION
from app.presentations.graphics import graphic_descriptor, compose_page
from app.presentations import master_runtime as master
from tests.test_ppt_master_assets import png


def spec():
    return {'kind':'process','items':[{'label':'暗处理与遮光','desc':'消耗原有淀粉','motif':'leaf-shade'},{'label':'光照与脱色','desc':'酒精隔水加热','motif':'beaker'},{'label':'滴碘液比较','desc':'见光区蓝黑，遮光区不变蓝','motif':'leaf-result'}]}


def test_graphic_spec_rejects_markup_urls_and_unbounded_data():
    assert GraphicSpec.model_validate(spec()).kind=='process'
    for patch in [{'kind':'../../file'}, {'html':'<script>x</script>'},{'items':[{'label':'<img src=x>','desc':'x','motif':'leaf'}]*3},{'items':[{'label':'x','desc':'x','motif':'https://evil'}]*3},{'items':[]}]:
        with pytest.raises(ValidationError):GraphicSpec.model_validate({**spec(),**patch})


def test_graphic_page_keeps_all_key_labels_native_and_asset_digest_bound():
    data=png();source=GraphicSpec.model_validate(spec()).model_dump()
    labels=[{'text':item['label'],'x':120+i*350,'y':210,'size':28,'color':'#173359','anchor':'middle'} for i,item in enumerate(source['items'])]
    desc=graphic_descriptor(source,data,labels)
    slide={'id':'a','layout':'process','title':'实验验证','content':'比较同一片叶的见光与遮光部分','slots':{}}
    design={'id':'a','visual_kind':'infographic','visual_brief':'叶片淀粉验证步骤','composition':'从左向右'}
    page=compose_page(slide,design,desc)
    assert page['graphics'][0]['version']==VERSION
    assert desc['name'] in page['svg']
    assert all(item['label'] in page['svg'] for item in source['items'])
    master.validate_svg(page['svg'],{desc['name']:data})
    assert 'data:image' not in str(page) and 'base64' not in str(page)
    changed=deepcopy(source);changed['items'][0]['label']='改变'
    assert graphic_descriptor(changed,data,labels)['name']!=desc['name']


@pytest.mark.parametrize('ppt_url,expected',[('http://ppt-renderer:8010','ppt-renderer'),('','video-renderer')])
async def test_graphic_materialization_uses_dedicated_renderer(monkeypatch,ppt_url,expected):
    import base64
    from types import SimpleNamespace
    import httpx
    from app.presentations import graphics
    data=png((2200,800))
    labels=[{'text':'步骤','x':120,'y':210,'size':28,'color':'#173359','anchor':'middle'}]*2
    requested=[]
    def handle(request):
        requested.append(request.url.host)
        return httpx.Response(200,json={'version':VERSION,'png_base64':base64.b64encode(data).decode(),'labels':labels})
    monkeypatch.setattr(graphics,'create_http',lambda:httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    actual,descriptor=await graphics.materialize(spec(),SimpleNamespace(ppt_renderer_url=ppt_url,renderer_url='http://video-renderer:8010'))
    assert actual==data
    assert requested==[expected]
    assert descriptor['sha256']


def test_graphic_page_passes_official_native_export_checks():
    data=png((2200,800));source=spec()
    labels=[{'text':item['label'],'x':120+i*350,'y':210,'size':28,'color':'#173359','anchor':'middle'} for i,item in enumerate(source['items'])]
    descriptor=graphic_descriptor(source,data,labels)
    slide={'id':'graphic','layout':'process','title':'实验验证','content':'比较同一片叶的见光与遮光部分','slots':{}}
    page=compose_page(slide,{'id':'graphic','visual_kind':'infographic','visual_brief':'实验步骤','composition':'从左向右'},descriptor)
    deck=master.compile_deck([page],'真实信息图导出',{descriptor['name']:data})
    from zipfile import ZipFile
    with ZipFile(BytesIO(deck)) as archive:
        assert any(name.startswith('ppt/media/') for name in archive.namelist())
        assert '暗处理与遮光'.encode() in archive.read('ppt/slides/slide1.xml')


def test_four_step_graphic_keeps_maximum_length_descriptions_in_canvas():
    from renderer.ppt_graphics import document
    from app.presentations.graphic_contract import WIDTH,HEIGHT
    source={'kind':'process','items':[{'label':'实验步骤','desc':'完整保留实验说明文字'*4,'motif':'beaker'}]*4}
    for item in source['items']:item['desc']=item['desc'][:36]
    _,labels=document(source)
    assert all(0<=label['x']<=WIDTH and 0<=label['y']<=HEIGHT-6 for label in labels)
    data=png((2200,800));graphic_descriptor(source,data,labels)
    for index,item in enumerate(source['items']):
        cx=WIDTH*(index+.5)/len(source['items'])
        description=''.join(label['text'] for label in labels if label['x']==cx and label['size']==22)
        assert description==item['desc']


async def test_graphic_repair_retries_invalid_schema_with_feedback(monkeypatch):
    from app.presentations import generation
    attempts=[]
    async def model(config,payload,**kwargs):
        attempts.append(payload.copy())
        return {'kind':'process','items':[]} if len(attempts)==1 else spec()
    monkeypatch.setattr(generation,'call',model)
    result=await generation.repair_graphic(None,{'id':'a'},{'graphic':spec()},None,[{'message':'标签拥挤'}])
    assert result==spec()
    assert len(attempts)==2
    assert attempts[1]['previous_error']


async def test_graphic_repair_stops_after_three_invalid_responses(monkeypatch):
    from app.presentations import generation
    calls=[]
    async def model(config,payload,**kwargs):
        calls.append(payload);return {'kind':'process','items':[]}
    monkeypatch.setattr(generation,'call',model)
    with pytest.raises(generation.GenerationError,match='信息图修复数据无效'):
        await generation.repair_graphic(None,{'id':'a'},{'graphic':spec()},None,[{'message':'标注'}])
    assert len(calls)==3


def test_native_text_wrap_keeps_punctuation_and_key_terms_together():
    from app.presentations.text_layout import wrap_text
    for value,width in [('消耗叶片中原有的淀粉。',11),('光：能量来源；叶绿体：主要场所',14),('安全提醒：酒精禁止直接加热。',8)]:
        lines=wrap_text(value,width)
        assert ''.join(lines)==value
        assert all(len(line)>1 and len(line)<=width for line in lines)
        assert all(line[0] not in '。，；：、！？）' for line in lines)
        assert not any(a.endswith('场') and b.startswith('所') or a.endswith('禁') and b.startswith('止') for a,b in zip(lines,lines[1:]))


def test_result_leaf_clips_reaction_zone_to_leaf_outline():
    from renderer.ppt_graphics import motif
    markup=motif('leaf-result',0,0,3)
    assert 'clipPath' in markup and 'clip-path=' in markup
    assert 'M-23-93 L17-96 L48 78 L8 88 Z' not in markup.split('clip-path=')[0].split('</defs>')[-1]


def test_comparison_does_not_draw_unlabelled_antv_center_circle():
    from renderer.ppt_graphics import document
    html,_=document({'kind':'compare','items':spec()['items'][:2]})
    assert '#flow{display:none}' in html


async def test_legacy_graphic_assets_use_original_renderer_version(monkeypatch):
    from app.presentations import graphics
    from app.presentations.graphic_contract import LEGACY_VERSION
    from types import SimpleNamespace
    data=png((2200,800));labels=[{'text':'步骤','x':120,'y':210,'size':28,'color':'#173359','anchor':'middle'}]*2
    descriptor=graphics.graphic_descriptor(spec(),data,labels,version=LEGACY_VERSION);seen=[]
    async def materialize(source,settings,*,version):
        seen.append(version);return data,descriptor
    monkeypatch.setattr(graphics,'materialize',materialize)
    assets=await graphics.generated_assets([{'graphics':[descriptor]}],SimpleNamespace())
    assert assets=={descriptor['name']:data} and seen==[LEGACY_VERSION]


def test_short_multiline_outline_content_reflows_without_losing_sentences():
    labels=[{'text':'步骤','x':120,'y':210,'size':28,'color':'#173359','anchor':'middle'}]*2
    descriptor=graphic_descriptor(spec(),png(),labels)
    content=chr(10).join(['暗处理消耗原有淀粉。','局部遮光后光照并取下纸条。','酒精隔水加热脱色。','漂洗滴碘比较颜色。'])
    slide={'id':'a','layout':'process','title':'实验验证','content':content,'slots':{}}
    page=compose_page(slide,{},descriptor)
    import xml.etree.ElementTree as ET
    root=ET.fromstring(page['svg']);group=next(n for n in root if n.get('id')=='explanation')
    assert ''.join(n.text or '' for n in group)==''.join(content.splitlines())
    assert len(group)<=2


async def test_long_infographic_content_uses_diagram_without_truncating_outline(monkeypatch):
    from app.presentations import generation
    from tests.test_ppt_master_runtime import sample_svg
    from unittest.mock import AsyncMock
    slide={'id':'a','layout':'process','title':'光合作用','content':'完整说明实验原理和安全操作。'*12,'slots':{}}
    design={'id':'a','visual_kind':'infographic','graphic':spec(),'visual_brief':'叶片实验图解','composition':'图文并排'}
    async def forbidden(*a,**kw):raise AssertionError('should choose fitting layout before materialization')
    model=AsyncMock(return_value={'svg':sample_svg()})
    monkeypatch.setattr(generation.graphics,'materialize',forbidden);monkeypatch.setattr(generation,'call',model)
    page=await generation.render_page(None,slide,{'slides':[slide]},[],design,{})
    assert page['content']==slide['content'] and page['design']['visual_kind']=='diagram'
    assert model.call_args.args[1]['slide']['content']==slide['content']
