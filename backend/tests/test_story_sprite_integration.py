"""Story sprite use is an executable contract, not library presence."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_missing_character_uses_explicit_or_nearest_original_cast():
    node=shutil.which('node')
    if not node:pytest.skip('Node required for runtime selection check')
    runtime=Path(__file__).parents[1]/'app/videos/sprite_motion.js'
    manifest=runtime.with_name('sprite_assets')/'manifest.json'
    code="""
const fs=require('node:fs'),vm=require('node:vm');
const scope={window:{}};vm.createContext(scope);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),scope);
const S=scope.window.EduSprites;S.configure({...JSON.parse(fs.readFileSync(process.argv[2],'utf8')),images:{}});
console.log(JSON.stringify([
 S.actor({variant:'ancient_child',age:'child',outfit:'robe'}).variant,
 S.actor({variant:'ancient_father',age:'adult',outfit:'robe'}).variant,
 S.actor({variant:'unknown_elder',age:'elder',outfit:'robe'}).variant,
 S.actor({variant:'missing',fallback_variant:'girl_rose'}).variant,
 S.actor({variant:'ochre'}).variant,
 S.actor({variant:'missing'}).variant,
 S.actor({variant:'girl_rose',age:'elder'}).variant,
 S.actor({age:'child',outfit:'robe'}).variant
]));
"""
    output=subprocess.check_output([node,'-e',code,str(runtime),str(manifest)],text=True,encoding='utf-8')
    assert json.loads(output)==['boy_blue','scholar','elder_scholar','girl_rose','farmer_m','farmer_m','girl_rose','boy_blue']


def test_detached_or_offscreen_sprite_does_not_count_as_visible_use():
    node=shutil.which('node')
    if not node:pytest.skip('Node required for visible draw check')
    runtime=Path(__file__).parents[1]/'app/videos/sprite_motion.js'
    code="""
const fs=require('node:fs'),vm=require('node:vm');
const canvas={isConnected:false,width:1280,height:720,getBoundingClientRect:()=>({left:0,top:0,right:1280,bottom:720,width:1280,height:720})};
const scope={window:{innerWidth:1280,innerHeight:720,Image:class {constructor(){this.complete=true;this.naturalWidth=512;this.naturalHeight=3072}decode(){return Promise.resolve()}}}};
vm.createContext(scope);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),scope);
const S=scope.window.EduSprites,bundle=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
S.configure({...bundle,images:{boy_blue:'data:image/png;base64,test'}});
const ctx={canvas,globalAlpha:1,save(){},restore(){},drawImage(){},getTransform:()=>({a:1,b:0,c:0,d:1,e:0,f:0})};
S.drawActor(ctx,{variant:'boy_blue',x:320,y:500});const detached=S.usage().drawnCharacters;
canvas.isConnected=true;S.drawActor(ctx,{variant:'boy_blue',x:-10000,y:500});const offscreen=S.usage().drawnCharacters;
S.drawActor(ctx,{variant:'boy_blue',x:320,y:500});const visible=S.usage().drawnCharacters;
console.log(JSON.stringify([detached,offscreen,visible]));
"""
    output=subprocess.check_output([node,'-e',code,str(runtime),str(runtime.with_name('sprite_assets')/'manifest.json')],text=True,encoding='utf-8')
    assert json.loads(output)==[0,0,1]


@pytest.mark.parametrize(('subject','prompt','narration','expected_character'),[
    ('语文','讲述孔融让梨的故事','孔融拿着梨走向哥哥。',True),
    ('语文','制作守株待兔动画','农夫每天守在树旁，等待兔子再次撞树。',True),
    ('语文','讲述亡羊补牢','牧羊人发现羊圈破了洞，立刻修好围栏。',True),
    ('语文','制作司马光砸缸动画','司马光搬起石头砸破水缸，救出落水的伙伴。',True),
    ('语文','讲解汉字笔顺','逐笔演示书写顺序。',False),
    ('英语','讲解语法和词汇','用例句展示一般现在时的结构。',False),
    ('语文','不要人物，只展示文本','分析诗句的押韵。',False),
    ('数学','讲解一次函数','展示公式和函数图像。',False),
    ('物理','演示实验','老师连接电路并观察电流表。',False),
    ('数学','用像素风展示函数图像','绘制函数曲线与坐标。',False),
    ('物理','科学家探索浮力的故事','科学家向学生讲述实验，展示浮力公式。',True),
])
def test_story_request_uses_simple_native_characters_without_sprite_cast(subject,prompt,narration,expected_character):
    from app.videos.direct_pipeline import html_generation_request
    from app.videos.quality import resolve_style
    snapshot={'title':'测试','prompt':prompt,'form_values':{'subject':subject},
              'film_expression':{'visual_prompt':'连续画面'},'outline':{},'style':resolve_style({'subject':subject})}
    request=html_generation_request(snapshot,[{'narration':narration}],4.)
    assert 'sprite_library' not in request
    if expected_character:
        assert '完整、可复用的整体角色' in request['animation_reference_adapter']
        assert '整体移动' in request['animation_reference_adapter']
    else:
        assert '故事演绎中的人物' not in request['animation_reference_adapter']


async def test_explicit_legacy_sprite_payload_still_embeds_runtime(monkeypatch):
    import httpx
    from app.videos.direct_html import generate_html
    from app.videos.sprite_assets import sprite_guidance
    source='<html><head></head><body><canvas></canvas><script>window.renderFrame=t=>{};</script></body></html>'
    async def response(*args,**kwargs):
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'html':source})}}]})
    monkeypatch.setattr('app.videos.model_stream.animation_response',response)
    config=type('Config',(),{'base_url':'https://example.invalid/v1','api_key':'test','model':'test'})()
    async with httpx.AsyncClient() as http:
        story=await generate_html(config,{'sprite_library':sprite_guidance()},http)
        plain=await generate_html(config,{},http)
    assert 'data-edu-characters-required="true"' in story
    assert plain==source


def test_story_request_uses_bounded_animation_references_without_pixel_assets():
    from copy import deepcopy
    from app.videos.direct_pipeline import html_generation_request
    from app.videos.quality import resolve_style
    snapshot={'title':'大禹治水','prompt':'讲述大禹带领百姓疏通河道的故事',
              'form_values':{'subject':'语文'},'style':resolve_style({'subject':'语文'}),
              'outline':{'segments':[{'narration':'先观察地形，再带领百姓疏通河道。'}]},
              'film_expression':{'visual_prompt':'连续讲述，人物不瞬移，自然转场。'}}
    targets=[{'narration':'先观察地形，再带领百姓疏通河道。','start':0.,'end':180.,
              'sentences':[{'text':'先观察地形，再带领百姓疏通河道。','start':0.,'end':180.}],
              'teacher_visual_instruction':'保留疏导而非堵水的重点'}]
    before=deepcopy((snapshot,targets))
    request=html_generation_request(snapshot,targets,180.)
    references=request['animation_design_references']
    assert len(json.dumps(references,ensure_ascii=False).encode('utf-8')) <= 9000
    assert references and all(doc['content'].strip() and doc['commit'] and doc['path'] for doc in references)
    reference_ids={d['skill_id'] for d in references}
    assert {'animation-principles','game-graphics'} <= reference_ids
    assert '2d-character-rig-animation' not in reference_ids
    assert not any(doc['path'].endswith('/pixel-art-reference.md') for doc in references)
    assert all('gsap.' not in doc['content'] and chr(96)*3 not in doc['content'] for doc in references)
    assert (snapshot,targets)==before
    assert request['teacher_request']==snapshot['prompt']
    assert request['approved_outline']==snapshot['outline'] and request['segments']==targets
    assert request['source_duration']==180. and 'sprite_library' not in request
    assert '整体移动' in request['animation_reference_adapter']


def test_mixed_story_retains_native_scientific_guidance_without_pixel_assets():
    from app.videos.direct_pipeline import html_generation_request
    from app.videos.quality import resolve_style
    snapshot={'title':'浮力的发现','prompt':'通过科学家的故事讲解浮力',
              'form_values':{'subject':'物理'},'style':resolve_style({'subject':'物理'}),
              'outline':{},'film_expression':{'visual_prompt':'人物演示与清晰公式图形并存'}}
    request=html_generation_request(snapshot,[{'narration':'科学家和学生观察物体入水，显示浮力公式。'}],20.)
    assert 'sprite_library' not in request
    assert '人物作为整体' in request['animation_reference_adapter']
    assert '公式、函数图像和实验保持清晰图形' in request['animation_reference_adapter']
    references=request['animation_design_references']
    assert any(d['skill_id']=='diagram-animation' and 'progressive disclosure' in d['content'] for d in references)
    assert len(json.dumps(references,ensure_ascii=False).encode('utf-8'))<=9000


def test_clean_science_route_keeps_its_original_design_references():
    from app.videos.direct_pipeline import html_generation_request
    from app.videos.quality import resolve_style
    from app.videos.skill_guidance import animation_guidance
    style=resolve_style({'subject':'数学'})
    snapshot={'title':'二次函数','prompt':'讲解二次函数','form_values':{'subject':'数学'},
              'style':style,'outline':{},'film_expression':{'visual_prompt':'清晰坐标与函数曲线'}}
    targets=[{'narration':'观察抛物线的顶点。','visual_prompt':'绘制函数图像'}]
    request=html_generation_request(snapshot,targets,10.)
    expected=animation_guidance({'subject':'数学','teacher_request':snapshot['prompt'],
        'whole_film_visual_prompt':snapshot['film_expression']['visual_prompt'],
        'visuals':['绘制函数图像'],'teacher_visual_instruction':[''],'narration':targets[0]['narration']},style)
    assert 'sprite_library' not in request
    assert request['animation_design_references']==expected['documents']


async def test_playback_check_rejects_injected_but_unused_required_characters(monkeypatch):
    from app.videos import direct_render
    class Frame:
        async def evaluate(self,code):return '<body></body>' if code=='document.body.innerHTML' else False
    class Page:
        frames=[None,Frame()]
        async def evaluate(self,code):return False if 'filmDiagnostics' in code else None
        async def wait_for_timeout(self,ms):pass
    async def inspect(page,t):return '<body></body>'
    async def pixels(page):return b'unchanged frame'
    monkeypatch.setattr(direct_render,'inspect',inspect)
    monkeypatch.setattr(direct_render,'pixels',pixels)
    monkeypatch.setattr(direct_render,'same_pixels',lambda first,second:first==second)
    with pytest.raises(ValueError,match='人物素材'):
        await direct_render.check_page(Page(),[],1.)
