/* Original pixel cast. Rendering and motion are pure functions of source time. */
(function (global) {
 'use strict';
 const clamp=n=>Math.max(0,Math.min(1,n));
 const smooth=n=>{n=clamp(n);return n*n*(3-2*n);};
 const directions={up:0,left:1,down:2,right:3};
 const poses={neutral:0,hands_front:1,raised_arms:2};
 const defaults={idle:[3,true,3],walk:[8,true,9],run:[8,true,12],pose:[3,false,1],wave:[6,true,7],nod:[4,false,6],talk:[4,true,5],pickup:[6,false,7],carry:[8,true,8],sit:[4,false,5],jump:[6,false,8],work:[6,true,7]};
 let images={},catalog={},characters={},aliases={},contacts={};
 let actions=Object.fromEntries(Object.entries(defaults).map(([key,[frames,loop,fps]],i)=>[key,{frames,loop,fps,row:i*4}]));
 let drawnCharacters=0;
 const api={ready:Promise.resolve(),usage:()=>({drawnCharacters})};
 function characterVariant(value){
  const requested=aliases[value.variant]||value.variant;
  if(!Object.keys(characters).length)return requested||'farmer_m';
  if(Object.hasOwn(characters,requested))return requested;
  const fallback=aliases[value.fallback_variant]||value.fallback_variant;
  if(Object.hasOwn(characters,fallback))return fallback;
  const candidates=Object.entries(characters);
  const score=spec=>(spec.age===value.age?100:0)+(spec.outfit===value.outfit?20:0)+(spec.hairstyle===value.hairstyle?4:0)+(spec.cloth===value.cloth?2:0);
  return candidates.reduce((best,item)=>score(item[1])>score(best[1])?item:best,candidates[0])[0];
 }
 function pose(name='neutral'){
  if(!Object.hasOwn(poses,name))throw Error('未知独立姿态：'+name);
  return {action:'pose',frame:poses[name],pose:name};
 }
 function animate(action,t,options={}){
  const spec=actions[action];
  if(!spec||action==='pose'||!Number.isFinite(t))throw Error('动画动作或时间无效：'+action);
  const start=options.start===undefined?0:options.start;
  const fps=options.fps===undefined?spec.fps:options.fps;
  if(!Number.isFinite(start)||!Number.isFinite(fps)||fps<=0)throw Error('动作时间或帧率无效');
  const value=Math.max(0,Math.floor((t-start)*fps));
  return {action,frame:spec.loop?value%spec.frames:Math.min(spec.frames-1,value)};
 }
 function travel(route,t){
  const {points,start,end}=route;
  if(!Array.isArray(points)||points.length<2||!Number.isFinite(start)||!Number.isFinite(end)||end<=start||!Number.isFinite(t)||points.some(p=>!Number.isFinite(p.x)||!Number.isFinite(p.y)))throw Error('移动路径或时间无效');
  const segments=points.slice(1).map((p,i)=>({a:points[i],b:p,length:Math.hypot(p.x-points[i].x,p.y-points[i].y)})).filter(s=>s.length>0);
  const total=segments.reduce((a,b)=>a+b.length,0);
  if(total<=0)throw Error('移动路径长度必须大于零');
  const u=clamp((t-start)/(end-start)),distance=total*(route.ease===false?u:smooth(u));
  let remaining=distance,index=0;
  while(index<segments.length-1&&remaining>=segments[index].length){remaining-=segments[index].length;index++;}
  const {a,b,length}=segments[index],dx=b.x-a.x,dy=b.y-a.y;
  const f=clamp(remaining/length);
  const direction=Math.abs(dx)>=Math.abs(dy)?(dx>=0?'right':'left'):(dy>=0?'down':'up');
  const active=t>start&&t<end;
  const stride=Number.isFinite(route.stride)&&route.stride>0?route.stride:32;
  const frame=active?Math.floor(distance/stride*8)%8:0;
  const requested=['run','carry'].includes(route.action)?route.action:'walk';
  return {x:a.x+dx*f,y:a.y+dy*f,direction:active?direction:(t<=start?route.startDirection:route.endDirection)||direction,action:active?requested:'idle',frame,distance};
 }
 function actor(value){
  const result={variant:'farmer_m',x:0,y:0,scale:1,direction:'down',action:'idle',frame:0,...value};
  result.variant=characterVariant(value||{});
  if(!Number.isFinite(result.x)||!Number.isFinite(result.y)||!Number.isFinite(result.scale)||result.scale<=0||!Object.hasOwn(directions,result.direction))throw Error('人物位置、比例或朝向无效');
  if(result.pose)Object.assign(result,pose(result.pose));
  const spec=actions[result.action];
  if(!spec)throw Error('素材没有此动作，请用独立绘制表达：'+result.action);
  if(!Number.isFinite(result.frame))throw Error('人物帧无效');
  const n=Math.floor(result.frame);
  result.frame=spec.loop?((n%spec.frames)+spec.frames)%spec.frames:Math.max(0,Math.min(spec.frames-1,n));
  return result;
 }
 function anchor(value,name='hand'){
  const a=actor(value),key=aliases[a.variant]||a.variant,spec=characters[key];
  if(name==='foot')return {x:a.x,y:a.y};
  const origin=spec&&spec.foot_origin||[32,60];
  if(['hand','leftHand','rightHand'].includes(name)){
   const points=spec&&contacts[spec.age]&&contacts[spec.age][a.action];
   if(points){
    const point=points[directions[a.direction]][a.frame][name==='leftHand'?0:1];
    return {x:a.x+(point[0]-origin[0])*a.scale,y:a.y+(point[1]-origin[1])*a.scale};
   }
   return {x:a.x+(name==='leftHand'?-6:6)*a.scale,y:a.y-16*a.scale};
  }
  if(name==='head')return {x:a.x,y:a.y-(spec&&spec.age==='child'?24:32)*a.scale};
  if(name==='center')return {x:a.x,y:a.y-18*a.scale};
  throw Error('未知人物连接点：'+name);
 }
 function transfer(donor,receiver,t,options){
  const {start,end}=options;
  if(!Number.isFinite(t)||!Number.isFinite(start)||!Number.isFinite(end)||end<=start)throw Error('递交时间无效');
  const a=anchor(donor,options.from||'hand'),b=anchor(receiver,options.to||'hand'),p=smooth((t-start)/(end-start));
  return {x:a.x+(b.x-a.x)*p,y:a.y+(b.y-a.y)*p-Math.sin(Math.PI*p)*(options.lift||0)};
 }
 function configure(bundle){
  catalog=bundle.catalog;characters=bundle.characters||{};actions=bundle.actions||actions;
  aliases=bundle.aliases||{};contacts=bundle.contacts||{};images={};drawnCharacters=0;
  api.ready=Promise.all(Object.entries(bundle.images).map(([key,url])=>{
   const img=new global.Image();images[key]=img;img.src=url;
   return img.decode().then(()=>{const spec=catalog[key];if(img.naturalWidth!==spec.width||img.naturalHeight!==spec.height)throw Error('素材尺寸不符：'+key);});
  }));
  return api.ready;
 }
 function drawActor(ctx,value){
  const a=actor(value),key=aliases[a.variant]||a.variant,img=images[key],spec=actions[a.action];
  if(!img||!img.complete||!img.naturalWidth)throw Error('人物素材未就绪：'+key);
  const cell=characters[key].cell,origin=characters[key].foot_origin;
  ctx.save();ctx.imageSmoothingEnabled=false;
  ctx.drawImage(img,a.frame*cell,(spec.row+directions[a.direction])*cell,cell,cell,Math.round(a.x-origin[0]*a.scale),Math.round(a.y-origin[1]*a.scale),cell*a.scale,cell*a.scale);
  if(visibleDraw(ctx,a,cell,origin))drawnCharacters++;
  ctx.restore();return a;
 }
 function visibleDraw(ctx,a,cell,origin){
  const canvas=ctx.canvas;
  if(!canvas||!canvas.isConnected||ctx.globalAlpha<=0)return false;
  const rect=canvas.getBoundingClientRect();
  if(rect.width<=0||rect.height<=0||rect.right<=0||rect.bottom<=0||rect.left>=global.innerWidth||rect.top>=global.innerHeight)return false;
  if(global.getComputedStyle){
   for(let node=canvas;node&&node.nodeType===1;node=node.parentElement){
    const style=global.getComputedStyle(node);
    if(style.display==='none'||style.visibility==='hidden'||Number(style.opacity)===0)return false;
   }
  }
  const m=ctx.getTransform(),x=Math.round(a.x-origin[0]*a.scale),y=Math.round(a.y-origin[1]*a.scale),size=cell*a.scale;
  const corners=[[x,y],[x+size,y],[x,y+size],[x+size,y+size]].map(([X,Y])=>({x:m.a*X+m.c*Y+m.e,y:m.b*X+m.d*Y+m.f}));
  return Math.max(...corners.map(p=>p.x))>0&&Math.min(...corners.map(p=>p.x))<canvas.width&&Math.max(...corners.map(p=>p.y))>0&&Math.min(...corners.map(p=>p.y))<canvas.height;
 }
 function drawAsset(ctx,key,options){
  const img=images[key],spec=catalog[key];
  if(!img||!img.complete||!img.naturalWidth||!spec||spec.kind==='character')throw Error('环境素材未就绪：'+key);
  const source=options.source||[0,0,spec.width,spec.height];
  ctx.save();ctx.imageSmoothingEnabled=false;
  ctx.drawImage(img,...source,options.x,options.y,options.width||source[2],options.height||source[3]);ctx.restore();
 }
 Object.assign(api,{pose,animate,travel,actor,anchor,transfer,configure,drawActor,drawAsset});
 global.EduSprites=api;
})(window);
