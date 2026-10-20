/* Trusted renderer: model output is data, never markup or executable code. */
(() => {
  const { scene, captions } = JSON.parse(document.getElementById('scene-data').textContent);
  const svg = document.getElementById('stage');
  const ns = 'http://www.w3.org/2000/svg';
  const clamp = x => Math.max(0, Math.min(1, x));
  const smooth = x => { x=clamp(x); return x*x*(3-2*x); };
  const smoother = x => { x=clamp(x); return x*x*x*(x*(6*x-15)+10); };
  const mix = (a,b,u) => a+(b-a)*u;
  const draw = (tag, attrs={}, parent=svg, content='') => {
    const e=document.createElementNS(ns,tag);
    for(const [k,v] of Object.entries(attrs)) e.setAttribute(k,String(v));
    if(content) e.textContent=content;
    parent.appendChild(e); return e;
  };
  const text=(x,y,value,size=26,color='#453b32',parent=svg,extra={}) =>
    draw('text',{x,y,'font-size':size,fill:color,...extra},parent,value);
  const line=(x1,y1,x2,y2,color,width,parent) => draw('line',{x1,y1,x2,y2,stroke:color,'stroke-width':width,'stroke-linecap':'round'},parent);
  const groups=new Map(), parts=new Map();
  svg.style.background=scene.background;
  const sceneTitle=text(58,64,scene.title,34,'#473b30',svg,{'font-weight':'700','data-scene-title':'true'});
  line(58,89,1222,89,'#e1d5c4',2,svg);
  const defs=draw('defs',{},svg);
  const contentClip=draw('clipPath',{id:'scene-content-clip',clipPathUnits:'userSpaceOnUse'},defs);
  draw('rect',{x:0,y:110,width:1280,height:500},contentClip);
  const viewport=draw('g',{'clip-path':'url(#scene-content-clip)'},svg);
  const body=draw('g',{'data-camera-world':'true'},viewport);
  for(const n of scene.nodes){
    const g=draw('g',{'data-node-id':n.id},body);groups.set(n.id,g);
    if(n.kind==='character'){
      draw('ellipse',{cx:0,cy:200,rx:42,ry:9,fill:'#30271d',opacity:.09},g);
      const legs=[];
      for(const x of [-17,17]){
        const limb=draw('g',{},g); line(x,83,x,183,'#4c4540',17,limb);
        draw('path',{d:'M '+(x-8)+' 182 q 14 -2 25 7 q 0 9 -28 5 Z',fill:'#38332f'},limb);legs.push(limb);
      }
      draw('path',{d:'M -35 5 Q 0 -7 35 5 L 42 91 Q 0 108 -42 91 Z',fill:n.color},g);
      draw('path',{d:'M -23 1 L 0 29 L 23 1 M 0 29 L 0 92',stroke:'#fff5e7','stroke-width':3,fill:'none',opacity:.65},g);
      draw('rect',{x:-39,y:76,width:78,height:11,rx:3,fill:'#74533a'},g);
      const arms=[];
      for(const x of [-36,36]){
        const arm=draw('g',{},g);line(x,14,x,87,n.color,20,arm);line(x,85,x,110,'#e8b38e',13,arm);
        draw('circle',{cx:x,cy:110,r:7,fill:'#e8b38e','data-hand':x<0?'left':'right'},arm);arms.push(arm);
      }
      draw('rect',{x:-10,y:-18,width:20,height:27,rx:7,fill:'#e8b38e'},g);
      draw('ellipse',{cx:0,cy:-43,rx:32,ry:37,fill:'#efc29f'},g);
      draw('path',{d:'M -32 -40 Q -39 -84 0 -83 Q 39 -80 32 -39 L 26 -58 Q 5 -51 -15 -64 L -26 -36 Z',fill:'#383432'},g);
      draw('ellipse',{cx:0,cy:-86,rx:13,ry:10,fill:'#383432'},g);
      const eyes=n.facing==='left'?[-16,-3]:n.facing==='right'?[3,16]:[-11,11];
      for(const x of eyes)draw('ellipse',{cx:x,cy:-43,rx:2.4,ry:3,fill:'#3d332c'},g);
      draw('path',{d:'M -7 -25 Q 0 -20 7 -25',stroke:'#a36251','stroke-width':2,fill:'none'},g);
      if(n.text)text(0,235,n.text,23,'#63503e',g,{'text-anchor':'middle'});
      parts.set(n.id,{arms,legs});
    }else if(n.kind==='pear'){
      draw('path',{d:'M 0 -28 C -12 -29 -10 -9 -23 4 C -47 35 -20 53 0 53 C 24 53 46 35 24 6 C 9 -9 12 -28 0 -28 Z',fill:n.color,stroke:'#a88c45','stroke-width':2},g);
      draw('path',{d:'M 0 -27 Q -2 -40 5 -47',fill:'none',stroke:'#79593b','stroke-width':5},g);
      draw('path',{d:'M 4 -36 Q 25 -49 29 -30 Q 13 -26 4 -36',fill:'#6e8b55'},g);
      draw('ellipse',{cx:-10,cy:13,rx:5,ry:14,fill:'#fff3b1',opacity:.45},g);
    }else if(n.kind==='text')text(0,0,n.text,n.size,n.color,g);
    else if(n.kind==='rect')draw('rect',{x:0,y:0,width:n.width,height:n.height,rx:16,fill:n.fill==='none'?n.color:n.fill},g);
    else if(n.kind==='ellipse')draw('ellipse',{cx:n.width/2,cy:n.height/2,rx:n.width/2,ry:n.height/2,fill:n.fill==='none'?n.color:n.fill},g);
    else if(n.kind==='line')line(0,0,n.width,n.height,n.color,n.stroke_width,g);
    else if(n.kind==='path')draw('path',{d:n.path,fill:n.fill,stroke:n.color,'stroke-width':n.stroke_width,'stroke-linecap':'round','stroke-linejoin':'round'},g);
    else if(n.kind==='graph'){
      draw('rect',{width:n.width,height:n.height,rx:18,fill:'#ffffff',stroke:'#e3d9cb'},g);
      const ox=n.width/2,oy=n.height/2+25,unit=Math.min(n.width/10,(n.height-80)/8);
      for(let i=-4;i<=4;i++){
        line(ox+i*unit,60,ox+i*unit,n.height-30,'#ece7df',1,g);
        line(30,oy+i*unit,n.width-30,oy+i*unit,'#ece7df',1,g);
        if(i){text(ox+i*unit-5,oy+23,''+i,14,'#968774',g);text(ox-23,oy-i*unit+5,''+i,14,'#968774',g);}
      }
      line(25,oy,n.width-20,oy,'#978976',2,g);line(ox,n.height-20,ox,58,'#978976',2,g);
      text(n.width-28,oy-12,'x',19,'#76654f',g);text(ox+12,74,'y',19,'#76654f',g);
      const curve=draw('path',{fill:'none',stroke:n.color,'stroke-width':5,'stroke-linecap':'round'},g);
      const eq=text(25,36,'',27,n.color,g,{'font-weight':'700'});
      parts.set(n.id,{curve,eq,ox,oy,unit});
    }else if(n.kind==='circuit'){
      const w=n.width,h=n.height;
      draw('path',{d:'M 90 0 H '+w+' V '+h+' H 0 V 0 H 35',fill:'none',stroke:'#857665','stroke-width':5,'stroke-linejoin':'round'},g);
      const switchBlade=line(35,0,90,0,n.color,5,g);switchBlade.setAttribute('data-switch','closed');
      for(const cx of [w*.35,w*.7]){
        draw('circle',{cx,cy:h,r:29,fill:'#ffe7a0',stroke:'#a58342','stroke-width':3},g);
        line(cx-15,h-15,cx+15,h+15,'#a58342',2,g);line(cx-15,h+15,cx+15,h-15,'#a58342',2,g);
      }
      draw('rect',{x:-18,y:h/2-27,width:36,height:54,fill:scene.background},g);
      line(-23,h/2-8,23,h/2-8,'#705c43',4,g);line(-13,h/2+9,13,h/2+9,'#705c43',4,g);
      text(38,h/2+10,n.voltage+' V',22,'#705c43',g);
      const dots=Array.from({length:14},()=>draw('circle',{r:5,fill:n.color},g));parts.set(n.id,{dots});
    }
  }
  const subtitleGroup=draw('g',{},svg);
  draw('rect',{x:40,y:623,width:1200,height:70,rx:16,fill:'#453b32',opacity:.94},subtitleGroup);
  const subtitle=text(640,668,'',25,'#fffaf0',subtitleGroup,{'text-anchor':'middle'});
  const statesAt=t=>{
    const states=Object.fromEntries(scene.nodes.map(n=>[n.id,{...n,left_arm:0,right_arm:0,left_leg:0,right_leg:0}]));
    for(const tr of scene.tracks){
      const ks=tr.keys;let value=ks[0].value;
      if(t>=ks.at(-1).t)value=ks.at(-1).value;
      else for(let i=1;i<ks.length;i++)if(t>=ks[i-1].t&&t<ks[i].t){let u=(t-ks[i-1].t)/(ks[i].t-ks[i-1].t);if(tr.easing==='smooth')u=smooth(u);else if(tr.easing==='smoother')u=smoother(u);else if(tr.easing==='ease_in')u=u*u*u;else if(tr.easing==='ease_out')u=1-Math.pow(1-u,3);value=mix(ks[i-1].value,ks[i].value,u);break;}
      // Bound interpolated slope precision once for both the curve and label.
      states[tr.target][tr.property]=tr.property==='slope'?Number(value.toFixed(6)):value;
    }
    return states;
  };
  const radians=angle=>angle*Math.PI/180;
  const world=(s,x,y)=>{const a=radians(s.rotation);return {x:s.x+s.scale*(x*Math.cos(a)-y*Math.sin(a)),y:s.y+s.scale*(x*Math.sin(a)+y*Math.cos(a))};};
  function hand(s,side){
    const x=side==='right'?36:-36,a=radians(s[side+'_arm']);
    return world(s,x-96*Math.sin(a),14+96*Math.cos(a));
  }
  function reach(s,side,target,amount=1){
    const rest=hand(s,side),point={x:mix(rest.x,target.x,amount),y:mix(rest.y,target.y,amount)};
    const a=radians(-s.rotation),dx=(point.x-s.x)/s.scale,dy=(point.y-s.y)/s.scale;
    const x=dx*Math.cos(a)-dy*Math.sin(a)-(side==='right'?36:-36),y=dx*Math.sin(a)+dy*Math.cos(a)-14;
    s[side+'_arm']=-Math.atan2(x,y)*180/Math.PI;s[side+'_stretch']=Math.hypot(x,y)/96;
  }
  // Stable paint order is independent of the sequence of seek calls.
  scene.handoffs.forEach(a=>body.appendChild(groups.get(a.prop)));
  scene.pickups.forEach(a=>body.appendChild(groups.get(a.prop)));
  // Evaluate carriers before their carried objects, independent of array order.
  const actions=new Map([
    ...scene.pickups.map(a=>[a.prop,{...a,type:'pickup'}]),
    ...scene.handoffs.map(a=>[a.prop,{...a,type:'handoff'}])
  ]),orderedActions=[],visited=new Set();
  const visitAction=a=>{
    if(visited.has(a.prop))return;
    visited.add(a.prop);
    for(const actor of [a.giver,a.receiver])if(actions.has(actor))visitAction(actions.get(actor));
    orderedActions.push(a);
  };
  for(const a of actions.values())visitAction(a);
  const cameraAt=t=>{
    const keys=scene.camera;if(!keys.length)return {x:640,y:360,zoom:1};
    if(t<=keys[0].t)return keys[0];
    for(let i=1;i<keys.length;i++)if(t<keys[i].t){
      const a=keys[i-1],b=keys[i],u=smoother((t-a.t)/(b.t-a.t));
      return {x:mix(a.x,b.x,u),y:mix(a.y,b.y,u),zoom:mix(a.zoom,b.zoom,u)};
    }
    return keys.at(-1);
  };
  window.seek=t=>{
    t=Math.max(0,Math.min(scene.duration,Number(t)||0));
    const states=statesAt(t),before=statesAt(Math.max(0,t-.025)),after=statesAt(Math.min(scene.duration,t+.025));
    for(const n of scene.nodes)if(n.kind==='character'){
      const s=states[n.id],moving=Math.abs(after[n.id].x-before[n.id].x)>.05;
      s.gait=moving?Math.sin(t*10)*22:0;s.left_arm-=s.gait*.5;s.right_arm+=s.gait*.5;
    }
    const camera=cameraAt(t);
    body.setAttribute('transform','translate(640 360) scale('+camera.zoom+') translate('+(-camera.x)+' '+(-camera.y)+')');
    for(const a of orderedActions){
      if(a.type==='pickup'){
      const receiver=states[a.receiver],p=states[a.prop];
      const anchor=statesAt(a.start)[a.prop],offset=world({...p,x:0,y:0},a.grip_x??0,a.grip_y??20);
      if(t<a.start){
        reach(receiver,a.hand,{x:p.x+offset.x,y:p.y+offset.y},smooth((t-a.start+.7)/.7));
      }else{
        const grip=hand(receiver,a.hand),u=smoother(clamp((t-a.start)/(a.end-a.start)));
        p.x=mix(anchor.x,grip.x-offset.x,u);p.y=mix(anchor.y,grip.y-offset.y,u)-Math.sin(Math.PI*u)*18;
        reach(receiver,a.hand,{x:p.x+offset.x,y:p.y+offset.y});
      }
      }else{
      const giver=states[a.giver],receiver=states[a.receiver],right=receiver.x>giver.x;
      const p=states[a.prop],side=right?'right':'left',other=right?'left':'right';
      const offset=world({...p,x:0,y:0},a.grip_x??0,a.grip_y??20);
      if(t<a.start){
        reach(giver,side,{x:p.x+offset.x,y:p.y+offset.y},smooth((t-a.start+.6)/.6));
        continue;
      }
      const u=clamp((t-a.start)/(a.end-a.start));
      const from=statesAt(a.start)[a.prop],to=hand(receiver,other);
      p.x=mix(from.x,to.x-offset.x,smooth(u));p.y=mix(from.y,to.y-offset.y,smooth(u))-Math.sin(Math.PI*u)*20;
      const grip={x:p.x+offset.x,y:p.y+offset.y};
      reach(giver,side,grip,1-smooth((u-.5)*2));
      reach(receiver,other,grip,smooth(u*2));
      }
    }
    const strokeReveal=(element,progress)=>{
      if(!element)return;
      if(progress>=1){
        element.removeAttribute('pathLength');element.removeAttribute('stroke-dasharray');
        element.removeAttribute('stroke-dashoffset');element.removeAttribute('stroke-opacity');
      }else{
        element.setAttribute('pathLength','1');element.setAttribute('stroke-dasharray','1 1');
        element.setAttribute('stroke-dashoffset',String(1-clamp(progress)));
        element.setAttribute('stroke-opacity',progress<=0?'0':'1');
      }
    };
    for(const n of scene.nodes){
      const s=states[n.id],g=groups.get(n.id),p=parts.get(n.id);
      g.setAttribute('transform','translate('+s.x+' '+s.y+') rotate('+s.rotation+') scale('+s.scale+')');g.setAttribute('opacity',s.opacity);
      if(n.kind==='path'||n.kind==='line')strokeReveal(g.firstElementChild,s.draw_progress??1);
      if(n.kind==='character'){
        for(const [index,side,x] of [[0,'left',-36],[1,'right',36]])
          p.arms[index].setAttribute('transform','translate('+x+' 14) rotate('+s[side+'_arm']+') scale(1 '+(s[side+'_stretch']??1)+') translate('+(-x)+' -14)');
        p.legs[0].setAttribute('transform','rotate('+(s.left_leg+s.gait)+' -17 83)');
        p.legs[1].setAttribute('transform','rotate('+(s.right_leg-s.gait)+' 17 83)');
      }else if(n.kind==='graph'){
        // Analytic clipping avoids quantized endpoints as the line rotates.
        let lo=-4,hi=4;
        if(s.slope!==0){const a=(-3.65-s.intercept)/s.slope,b=(3.65-s.intercept)/s.slope;lo=Math.max(lo,Math.min(a,b));hi=Math.min(hi,Math.max(a,b));}
        const d=lo<=hi?'M '+(p.ox+lo*p.unit)+','+(p.oy-(s.slope*lo+s.intercept)*p.unit)+' L '+(p.ox+hi*p.unit)+','+(p.oy-(s.slope*hi+s.intercept)*p.unit):'';
        p.curve.setAttribute('d',d.trim());
        strokeReveal(p.curve,s.draw_progress??1);
        const animated=scene.tracks.some(tr=>tr.target===n.id&&tr.property==='slope'&&t>tr.keys[0].t&&t<tr.keys.at(-1).t);
        const displaySlope=animated?Number(s.slope.toFixed(2)):s.slope;
        // Shorten the readout without rounding geometry or claiming exact equality.
        p.eq.textContent='y '+(displaySlope===s.slope?'= ':'≈ ')+displaySlope+'x'+(s.intercept>=0?' + ':' − ')+Math.abs(s.intercept);
      }else if(n.kind==='circuit'){
        const perimeter=2*(n.width+n.height);
        p.dots.forEach((dot,i)=>{let d=(i*perimeter/p.dots.length+t*60)%perimeter,x,y;if(d<n.width){x=d;y=0;}else if((d-=n.width)<n.height){x=n.width;y=d;}else if((d-=n.height)<n.width){x=n.width-d;y=n.height;}else{x=0;y=n.height-(d-n.width);}dot.setAttribute('cx',x);dot.setAttribute('cy',y);});
      }
    }
    const titleKeys=scene.title_opacity??[];let titleOpacity=titleKeys[0]?.value??1;
    if(titleKeys.length){
      if(t>=titleKeys.at(-1).t)titleOpacity=titleKeys.at(-1).value;
      else for(let i=1;i<titleKeys.length;i++)if(t>=titleKeys[i-1].t&&t<titleKeys[i].t){
        titleOpacity=mix(titleKeys[i-1].value,titleKeys[i].value,smoother((t-titleKeys[i-1].t)/(titleKeys[i].t-titleKeys[i-1].t)));break;
      }
    }
    sceneTitle.setAttribute('opacity',titleOpacity);
    const c=captions.find(c=>t>=c.start&&t<c.end);subtitle.textContent=c?c.text:'';
    subtitleGroup.setAttribute('opacity',c?'1':'0');
    subtitle.setAttribute('font-size','25');
    const captionWidth=subtitle.getComputedTextLength();
    if(captionWidth>1120)subtitle.setAttribute('font-size',String(25*1120/captionWidth));
    window.currentSceneTime=t;
  };
  window.sceneReady=document.fonts.ready.then(()=>{window.seek(0);return true;});
  // Sandboxed preview: the parent owns the audio clock; no autonomous timer.
  let previewChannel=null;
  window.addEventListener('message',event=>{
    if(window.parent===window||event.source!==window.parent)return;
    const data=event.data;
    if(!data||typeof data!=='object')return;
    if(data.type==='edu-preview:init'&&typeof data.channel==='string'&&data.channel.length<=128){
      previewChannel=data.channel;
      window.sceneReady.then(()=>window.parent.postMessage({type:'edu-preview:ready',channel:previewChannel},'*'));
    }else if(data.type==='edu-preview:seek'&&data.channel===previewChannel&&previewChannel&&Number.isFinite(data.time)){
      window.seek(Math.max(0,Math.min(scene.duration,data.time)));
    }
  });
})();
