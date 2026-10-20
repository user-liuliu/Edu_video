/** Add a render acknowledgement to frozen previews without changing their assets. */
export function preparePreviewHtml(html:string):string {
 const bridge=`<script>(()=>{
 let drawing=false,latest=null,firstFrame=true;
 async function draw(){
  if(drawing)return;drawing=true;
  try{while(latest){
   const request=latest;latest=null;
   try{
    dispatchEvent(new Event('resize'));
    if(typeof window.seek!=='function')throw Error('动画播放接口未就绪');
    await window.seek(request.time);
    if(firstFrame){await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));firstFrame=false;}
    parent.postMessage({type:'edu-preview:rendered',channel:request.channel,request:request.request,time:request.time},'*');
   }catch(error){parent.postMessage({type:'edu-preview:render-error',channel:request.channel,request:request.request},'*');}
  }}finally{drawing=false;}
 }
 addEventListener('message',event=>{
  if(event.source!==parent||event.data?.type!=='edu-preview:render'||!Number.isFinite(event.data.time))return;
  latest=event.data;void draw();
 });
})();<`+`/script>`
 // Append after the frozen document: its runtime contains literal </body> strings.
 return html+bridge
}
