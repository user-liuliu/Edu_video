const payload=JSON.parse(document.getElementById('payload').textContent);
const film=document.getElementById('film'),caption=document.getElementById('caption'),stage=document.getElementById('stage');
const token=crypto.randomUUID?crypto.randomUUID():String(Math.random());
let readyResolve,readyReject,id=0,channel='',pending=new Map();
window.filmDiagnostics=[];
window.sceneReady=new Promise((resolve,reject)=>{readyResolve=resolve;readyReject=reject;});
function fail(message){window.filmDiagnostics.push(String(message).slice(0,400));readyReject(Error(message));for(const entry of pending.values()){clearTimeout(entry.timer);entry.reject(Error(message));}pending.clear();}
const loadTimer=setTimeout(()=>fail('动画初始化超时'),10000);
function resize(){const scale=Math.min(innerWidth/1280,innerHeight/720);stage.style.width='1280px';stage.style.height='720px';stage.style.transform='translate(-50%,-50%) scale('+scale+')';}
addEventListener('resize',resize);resize();
function sourceAt(t){const c=payload.clock;if(t>=c[c.length-1].t)return c[c.length-1].source;for(let i=1;i<c.length;i++){const a=c[i-1],b=c[i];if(t<=b.t)return a.source+(b.source-a.source)*(Math.max(a.t,t)-a.t)/(b.t-a.t);}return 0;}
addEventListener('message',event=>{
 if(event.source===film.contentWindow&&event.data?.token===token){
  const d=event.data;
  if(d.type==='direct:ready'){clearTimeout(loadTimer);readyResolve(true);}
  if(d.type==='direct:done'){const entry=pending.get(d.id);if(entry){clearTimeout(entry.timer);pending.delete(d.id);window.lastSceneDom=d.dom;entry.resolve();}}
  if(d.type==='direct:error')fail(d.message);
 }
 if(event.source===parent&&event.data?.type==='edu-preview:init'){
  channel=event.data.channel;window.sceneReady.then(()=>parent.postMessage({type:'edu-preview:ready',channel},'*')).catch(error=>parent.postMessage({type:'edu-preview:error',channel,message:error.message},'*'));
 }
 if(event.source===parent&&event.data?.type==='edu-preview:seek'&&event.data.channel===channel){
  window.seek(event.data.time).catch(error=>parent.postMessage({type:'edu-preview:error',channel,message:error.message},'*'));
 }
});
window.seek=async function(t,inspect=false){
 await window.sceneReady;
 if(window.filmDiagnostics.length)throw Error(window.filmDiagnostics.join(';'));
 if(!Number.isFinite(t))throw Error('无效动画时间');
 t=Math.max(0,Math.min(payload.duration,t));window.currentSceneTime=t;
 caption.textContent=payload.captions.find(c=>c.start<=t&&t<c.end)?.text??'';
 const request=++id;
 await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(request);reject(Error('动画定位超时'));},5000);pending.set(request,{resolve,reject,timer});film.contentWindow.postMessage({type:'direct:seek',token,id:request,source:sourceAt(t),inspect},'*');});
};
const bridge='('+function(secret){
 const report=message=>parent.postMessage({type:'direct:error',token:secret,message:String(message).slice(0,300)},'*');
 addEventListener('error',e=>report(e.message));
 addEventListener('unhandledrejection',e=>report(e.reason));
 addEventListener('load',async()=>{
  if(typeof window.renderFrame!=='function'){report('缺少renderFrame');return;}
  try{
   if(window.EduSprites)await window.EduSprites.ready;
   await Promise.all(Array.from(document.images,img=>img.decode()));
  }catch(error){report('动画素材加载失败：'+error.message);return;}
  addEventListener('message',e=>{
   if(e.source!==parent||e.data?.type!=='direct:seek'||e.data.token!==secret)return;
   try{
    const result=window.renderFrame(e.data.source);
    if(result&&typeof result.then==='function')throw Error('renderFrame必须同步执行');
    document.body.getBoundingClientRect();
    if(document.getAnimations().some(a=>a.playState==='running'))throw Error('动画必须由绝对时钟驱动');
    parent.postMessage({type:'direct:done',token:secret,id:e.data.id,dom:e.data.inspect?document.body.innerHTML:null},'*');
   }catch(error){report(error.message);}
  });
  parent.postMessage({type:'direct:ready',token:secret},'*');
 });
}.toString()+')('+JSON.stringify(token)+');';
const script='<script>'+bridge+'<'+ '/script>';
film.srcdoc=/<\/body\s*>/i.test(payload.html)?payload.html.replace(/<\/body\s*>/i,()=>script+'</body>'):payload.html+script;
