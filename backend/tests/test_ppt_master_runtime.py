from uuid import uuid4
import pytest
from app.presentations.master_runtime import validate_svg, validate_plan, MasterError, compile_deck

def sample_svg():
    return '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" data-pptx-page-role="content"><rect id="background" data-pptx-role="background" width="1280" height="720" fill="#FFFFFF"/><text x="64" y="100" font-family="Microsoft YaHei, Arial" font-size="48" fill="#173359">光合作用</text><g id="teaching-visual" data-pptx-bounds="480 160 650 480"><path d="M 650 280 C 800 160 1100 250 1050 450 C 900 540 650 500 650 280 Z" fill="#DDEFE4" stroke="#2B9578" stroke-width="3"/><path d="M 690 450 L 1000 290" fill="none" stroke="#2B9578" stroke-width="4"/><circle cx="560" cy="240" r="45" fill="#F9CD53"/><line x1="570" y1="310" x2="670" y2="360" stroke="#2465D9" stroke-width="4"/><text x="680" y="580" font-family="Microsoft YaHei, Arial" font-size="28" fill="#273B53">叶片接收阳光，制造有机物</text></g></svg>'

def test_native_illustration_is_accepted_but_text_card_is_not():
    svg=sample_svg()
    assert validate_svg(svg,{},require_visual=True)==svg
    card=svg[:svg.index('<g id=')]+ '<g id="teaching-visual" data-pptx-bounds="480 160 650 480"><rect x="600" y="200" width="500" height="300" fill="#EEEEEE"/><text x="650" y="300">一张叶子</text></g></svg>'
    with pytest.raises(MasterError):validate_svg(card,{},require_visual=True)

@pytest.mark.parametrize('payload',[
    '<script>alert(1)</script>',
    '<image href="file:///etc/passwd" width="300" height="300"/>',
    '<image href="https://example.com/a.png" width="300" height="300"/>',
    '<rect width="100" height="100" fill="url(file:///secret)"/>',
    '<g onload="alert(1)"/>',
    '<g xmlns="http://evil.example"/>',
    '<g transform="scale(9999)"/>',
    '<path d="M NaN 1 L 2 3"/>',
])
def test_svg_rejects_active_external_or_unbounded_data(payload):
    with pytest.raises(MasterError):validate_svg(sample_svg().replace('</svg>',payload+'</svg>'),{})

def test_xml_entities_and_complexity_rejected():
    with pytest.raises(MasterError):validate_svg('<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>'+sample_svg(),{})
    with pytest.raises(MasterError):validate_svg(sample_svg().replace('</svg>','<g>'*20+'</g>'*20+'</svg>'),{})
    with pytest.raises(MasterError):validate_svg(sample_svg().replace('</svg>','<circle r="1"/>'*1300+'</svg>'),{})

def test_plan_covers_exact_stable_ids_and_requires_teaching_visuals():
    sid=str(uuid4());slides=[{'id':sid,'title':'叶片','content':'光合作用','layout':'image-text','slots':{}}]
    plan={'pages':[{'id':sid,'visual_kind':'diagram','visual_brief':'绘制叶片和阳光箭头','composition':'左文右图'}]}
    assert validate_plan(plan,slides)['pages'][0]['id']==sid
    with pytest.raises(MasterError):validate_plan({'pages':[]},slides)
    with pytest.raises(MasterError):validate_plan({'pages':[{**plan['pages'][0],'visual_kind':'none'}]},slides)

def test_official_native_export_contains_editable_freeform_and_text():
    from io import BytesIO
    from zipfile import ZipFile
    sid=str(uuid4());page={'id':sid,'title':'光合作用','layout':'image-text','content':'叶片获取能量','slots':{},'renderer':'ppt-master-6.7.0','svg':sample_svg(),'design':{'id':sid,'visual_kind':'diagram','visual_brief':'叶片、阳光与能量流动','composition':'左文右图'}}
    result=compile_deck([page],'植物的能量',{})
    with ZipFile(BytesIO(result)) as z:
        slide=z.read('ppt/slides/slide1.xml').decode()
        assert '光合作用' in slide and 'custGeom' in slide
        assert 'spAutoFit' not in slide and 'noAutofit' in slide
        assert '<p:pic>' not in slide
        assert b'12192000' in z.read('ppt/presentation.xml')


def test_official_native_export_embeds_only_authorized_reference_image():
    from io import BytesIO
    from zipfile import ZipFile
    from tests.test_ppt_master_assets import png
    name='a'*24+'.png';sid=str(uuid4())
    svg=sample_svg().replace('</g></svg>',f'<image href="../images/{name}" x="80" y="200" width="320" height="180"/></g></svg>')
    page={'id':sid,'title':'叶片参考图片','content':'观察叶片','svg':svg,'design':{'id':sid,'visual_kind':'reference-image','visual_brief':'实物叶片与叶片示意图','composition':'图片与图解并排'}}
    with ZipFile(BytesIO(compile_deck([page],'叶片观察',{name:png()}))) as z:
        assert any(n.startswith('ppt/media/') and n.endswith('.png') for n in z.namelist())
        assert '<p:pic>' in z.read('ppt/slides/slide1.xml').decode()
    with pytest.raises(MasterError):compile_deck([page],'叶片观察',{})


@pytest.mark.parametrize('data',[{'pages':None},{'pages':['bad']}, {'pages':[None]}])
def test_malformed_plan_rejected_with_actionable_error(data):
    with pytest.raises(MasterError):validate_plan(data,[{'id':str(uuid4())}])

@pytest.mark.parametrize('change',[
    lambda s:s.replace('id="teaching-visual"','id="teaching-visual" opacity="0"'),
    lambda s:s.replace('data-pptx-bounds="480 160 650 480"','data-pptx-bounds="0 0 1 1"'),
    lambda s:s.replace('id="teaching-visual"','id="teaching-visual" transform="scale(0.001)"'),
    lambda s:s.replace('data-pptx-bounds="480 160 650 480"',''),
])
def test_invisible_or_token_sized_teaching_visual_is_rejected(change):
    with pytest.raises(MasterError):validate_svg(change(sample_svg()),{})


@pytest.mark.parametrize('mode',['transparent-children','hidden-parent','definitions','tiny'])
def test_teaching_visual_requires_actual_visible_geometry(mode):
    import xml.etree.ElementTree as ET
    from app.presentations.master_runtime import NS
    root=ET.fromstring(sample_svg());group=root.find('{'+NS+'}g')
    if mode=='transparent-children':
        for node in group:
            if node.tag!='{'+NS+'}text':node.set('opacity','0')
    elif mode=='hidden-parent':
        holder=ET.SubElement(group,'{'+NS+'}g',{'opacity':'0'})
        for node in list(group):
            if node is not holder:group.remove(node);holder.append(node)
    elif mode=='definitions':
        holder=ET.SubElement(group,'{'+NS+'}defs')
        for node in list(group):
            if node is not holder:group.remove(node);holder.append(node)
    else:
        for node in group:
            if node.tag!='{'+NS+'}text':node.set('transform','scale(0.001)')
    with pytest.raises(MasterError):validate_svg(ET.tostring(root,encoding='unicode'),{})


def test_compilation_rejects_a_deck_that_cannot_be_previewed():
    from io import BytesIO
    from PIL import Image
    import random
    data=BytesIO();Image.frombytes('RGB',(900,700),random.Random(12).randbytes(900*700*3)).save(data,format='PNG')
    blob=data.getvalue();assert 1_800_000<len(blob)<3*1024*1024
    name='b'*24+'.png';sid=str(uuid4())
    svg=sample_svg().replace('</g></svg>',f'<image href="../images/{name}" x="80" y="200" width="320" height="180"/></g></svg>')
    page={'id':sid,'title':'叶片','content':'观察参考图片','svg':svg,'design':{'id':sid,'visual_kind':'reference-image','visual_brief':'叶片','composition':'图文并排'}}
    with pytest.raises(MasterError,match='预览'):compile_deck([page],'测试',{name:blob})


def formula_svg():
    return '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" data-pptx-page-role="content"><rect id="background" data-pptx-role="background" width="1280" height="720" fill="#FFFFFF"/><g id="formula" data-pptx-bounds="80 80 1120 480"><text x="80" y="130" font-family="Microsoft YaHei, Arial" font-size="48" fill="#173359">二次函数的对称轴</text><text x="80" y="280" font-family="Microsoft YaHei, Arial" font-size="32" fill="#273B53">y = ax² + bx + c，a ≠ 0</text><text x="80" y="380" font-family="Microsoft YaHei, Arial" font-size="32" fill="#273B53">对称轴：x = -b / (2a)</text></g><g id="divider" data-pptx-bounds="64 200 1152 400"><line x1="64" y1="500" x2="1216" y2="500" stroke="#DCE5F1" stroke-width="2"/></g></svg>'

def test_text_formula_page_with_overlapping_module_bounds_exports_editable_text():
    from io import BytesIO
    from zipfile import ZipFile
    from app.presentations.master_runtime import preview
    svg=formula_svg()
    page={'id':str(uuid4()),'title':'二次函数的对称轴','content':'对称轴 x=-b/(2a)，a≠0','svg':svg,'design':{'visual_kind':'text','visual_brief':'直接展示定义和公式','composition':'公式与条件纵向排列'}}
    assert 'x = -b' in preview(svg,{}).decode()
    with ZipFile(BytesIO(compile_deck([page],'二次函数',{}))) as z:
        xml=z.read('ppt/slides/slide1.xml').decode()
        assert 'x = -b / (2a)' in xml and '<a:t>' in xml

def test_text_plan_does_not_require_an_illustration():
    sid=str(uuid4());slide={'id':sid,'layout':'concept'}
    result=validate_plan({'pages':[{'id':sid,'visual_kind':'text','visual_brief':'展示公式','composition':'标题加公式'}]},[slide])
    assert result['pages'][0]['visual_kind']=='text'


def test_readable_font_size_outside_style_anchors_does_not_block_export():
    from io import BytesIO
    from zipfile import ZipFile
    svg=formula_svg().replace('font-size="32"','font-size="30"')
    page={'id':str(uuid4()),'title':'公式','content':'对称轴公式','svg':svg,'design':{'visual_kind':'text','visual_brief':'公式','composition':'清晰文字'}}
    with ZipFile(BytesIO(compile_deck([page],'公式',{}))) as z:
        assert 'x = -b / (2a)' in z.read('ppt/slides/slide1.xml').decode()
