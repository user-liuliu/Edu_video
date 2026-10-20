"""Build a standalone, offline animated catalog through the production packager."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.videos.sprite_assets import assemble_sprites,load_bundle


def create():
    manifest,_,_=load_bundle()
    labels={'idle':'待机','walk':'行走','run':'跑步','wave':'挥手','nod':'点头','talk':'说话','pickup':'拾取','carry':'端物行走','sit':'坐下','jump':'跳跃','work':'劳动手势'}
    action_options=''.join(f'<option value="{key}">{label}</option>' for key,label in labels.items())
    character_options=''.join(f'<option value="{key}">{item["description"]}</option>' for key,item in manifest['characters'].items())
    template='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>原创像素角色库</title><style>
    :root{color-scheme:light;font-family:system-ui,"Microsoft YaHei",sans-serif;color:#49343d;background:#f4eddd}*{box-sizing:border-box}body{margin:0;padding:26px;max-width:1400px;margin:auto}h1{font-size:27px;margin:0 0 9px}p{margin:0 0 22px;color:#75675f;line-height:1.6}.toolbar{display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:16px;background:#e1e4cd;border:1px solid #cdcbb2;border-radius:12px;margin-bottom:20px}select,button,input{font:inherit}select,button{border:1px solid #b8ac93;border-radius:7px;padding:9px 12px;background:#fff8e8;color:#49343d}button{cursor:pointer}canvas{display:block;image-rendering:pixelated;max-width:100%;height:auto;background:#e1e4cd;border-radius:12px;border:1px solid #cdcbb2}h2{font-size:20px;margin:25px 0 12px}.note{font-size:13px;margin-top:12px}#time{min-width:75px}label{display:flex;gap:8px;align-items:center}a{color:#456d70}</style></head><body>
    <h1>原创像素人物 · 暖色乡村 RPG</h1><p>20 种原创角色，四方向移动，11 种动态动作。每个角色均为透明 PNG 图集，可由本地绘画源文件重新生成。</p>
    <div class="toolbar"><label>动作<select id="action">__ACTIONS__</select></label><label>朝向<select id="direction"><option value="down">正面</option><option value="left">左侧</option><option value="right">右侧</option><option value="up">背面</option></select></label><button id="play">暂停</button><button id="restart">重播动作</button><label>时间<input id="seek" type="range" min="0" max="12" value="0" step="0.01"></label><span id="time">0.00s</span></div>
    <canvas id="cast" width="1280" height="800"></canvas>
    <h2>单个角色 · 全部动作</h2><div class="toolbar"><label>角色<select id="character">__CHARACTERS__</select></label></div>
    <canvas id="actions" width="1280" height="300"></canvas>
    <p class="note">动作说明：坐下需要配套座椅；拾取、端物和劳动为通用身体动作，道具通过每帧手部连接点挂接。跳跃已包含离地位移。点头、拾取、坐下、跳跃播放后保持末帧，点击重播可重新查看。</p>
    <p class="note">风格参考温暖乡村像素 RPG；人物、服装及环境图像均为新绘，无星露谷或 LPC 游戏图像。此页离线可用；生产动画依然由 renderFrame(t) 的绝对时间驱动。</p>
    <script>
    const characters=__DATA__,labels=__LABELS__;
    const cast=document.getElementById('cast'),ctx=cast.getContext('2d'),ac=document.getElementById('actions'),ax=ac.getContext('2d');
    const actionSelect=document.getElementById('action'),directionSelect=document.getElementById('direction'),characterSelect=document.getElementById('character');
    const seek=document.getElementById('seek'),time=document.getElementById('time'),play=document.getElementById('play');
    let playing=true,current=0,last=0;
    window.catalogDiagnostics=[];
    function background(c,w,h){c.fillStyle='#e1e4cd';c.fillRect(0,0,w,h);c.imageSmoothingEnabled=false;c.textAlign='center';c.fillStyle='#49343d';c.font='17px system-ui,Microsoft YaHei';}
    window.renderFrame=function(t){
      background(ctx,1280,800);background(ax,1280,300);
      const direction=directionSelect.value,action=actionSelect.value;
      characters.forEach((c,index)=>{
        const x=128+(index%5)*256,y=155+Math.floor(index/5)*195;
        const a=EduSprites.actor({variant:c.key,x,y,scale:3,direction,...EduSprites.animate(action,t)});
        EduSprites.drawActor(ctx,a);
        if(action==='carry'){const h=EduSprites.anchor(a,'hand');EduSprites.drawAsset(ctx,'basket',{x:h.x-19,y:h.y-24,width:36,height:36});}
        ctx.fillStyle='#49343d';ctx.fillText(c.description.split('：')[0],x,y+27);
      });
      Object.keys(labels).forEach((action,index)=>{
        const x=58+index*116,y=220;const a=EduSprites.actor({variant:characterSelect.value,x,y,scale:3,direction,...EduSprites.animate(action,t)});
        EduSprites.drawActor(ax,a);ax.fillStyle='#49343d';ax.fillText(labels[action],x,260);
      });
    };
    window.seekCatalog=t=>{current=Math.max(0,Math.min(12,t));seek.value=current;time.textContent=current.toFixed(2)+'s';window.renderFrame(current);};
    function tick(now){if(playing){current+=(now-last)/1000;if(current>12)current=0;window.seekCatalog(current);}last=now;requestAnimationFrame(tick);}
    actionSelect.onchange=()=>window.seekCatalog(0);directionSelect.onchange=()=>window.seekCatalog(current);characterSelect.onchange=()=>window.seekCatalog(current);
    seek.oninput=()=>{playing=false;play.textContent='播放';window.seekCatalog(Number(seek.value));};
    play.onclick=()=>{playing=!playing;play.textContent=playing?'暂停':'播放';};
    document.getElementById('restart').onclick=()=>window.seekCatalog(0);
    window.catalogReady=EduSprites.ready.then(()=>{window.seekCatalog(0);last=performance.now();requestAnimationFrame(tick);});
    </script></body></html>'''
    html=template.replace('__ACTIONS__',action_options).replace('__CHARACTERS__',character_options).replace('__DATA__',json.dumps(list(manifest['characters'].values()),ensure_ascii=False)).replace('__LABELS__',json.dumps(labels,ensure_ascii=False))
    output=Path(__file__).with_name('catalog.html');output.write_text(assemble_sprites(html,enabled=True),encoding='utf-8')
    print(json.dumps({'catalog':str(output),'bytes':output.stat().st_size,'characters':len(manifest['characters'])}))


if __name__=='__main__':create()
