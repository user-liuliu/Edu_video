<script setup lang="ts">
import {computed,nextTick,onBeforeUnmount,onMounted,ref} from 'vue'
import {getPptEditor,savePptText,type PptTextBlock,type PptTextPatch,type PptTextAddition,type PptProject,type PptCanvasObject,type PptObjectMove} from '../../api/presentations'
import {errorText} from '../../api/http'
const props=defineProps<{projectId:string;slideId:string;revision:number}>()
const emit=defineEmits<{saved:[PptProject];cancel:[];dirty:[boolean];saving:[boolean]}>()
const loading=ref(true),saving=ref(false),error=ref(''),blocks=ref<PptTextBlock[]>([]),original=ref<PptTextBlock[]>([]),selected=ref(''),svg=ref(''),host=ref<HTMLElement>(),history=ref<{blocks:PptTextBlock[];offsets:Record<string,{dx:number;dy:number}>}[]>([])
const adding=ref(false),moveMode=ref(false),objects=ref<PptCanvasObject[]>([]),offsets=ref<Record<string,{dx:number;dy:number}>>({}),selectedObject=ref(''),dragging=ref(false)
let suppressClick=false
let drag:{id:number;x:number;y:number;key:string;start:{dx:number;dy:number};snapshot:ReturnType<typeof snapshot>;active:boolean;scaleX:number;scaleY:number}|undefined
const moves=computed<PptObjectMove[]>(()=>Object.entries(offsets.value).filter(([,o])=>o.dx!==0||o.dy!==0).map(([key,o])=>({key,...o})))
let resizing:{id:number;handle:string;x:number;y:number;box:{x:number;y:number;width:number;height:number};block:PptTextBlock;snapshot:ReturnType<typeof snapshot>;active:boolean;scaleX:number;scaleY:number}|undefined
const frameHandles=['nw','n','ne','e','se','s','sw','w']
const selectedItem=computed(()=>objects.value.find(o=>o.key===selectedObject.value))
let newBoxNumber=0
const selection=ref<{x:number;y:number;width:number;height:number}>(),typing=ref(false),input=ref<HTMLTextAreaElement>()
let source='',disposed=false
const current=computed(()=>blocks.value.find(b=>b.key===selected.value))
const patches=computed<PptTextPatch[]>(()=>original.value.flatMap(old=>{const b=blocks.value.find(b=>b.key===old.key);if(!b)return [];const p:PptTextPatch={key:b.key};for(const k of ['text','font_size','color','bold','x','y','width','height'] as const){if(b[k]!==old[k])Object.assign(p,{[k]:b[k]})}const obj=objects.value.find(o=>o.text_key===b.key),delta=obj?effectiveOffset(obj):{dx:0,dy:0};if(p.x!==undefined)p.x=Math.round((p.x+delta.dx)*100)/100;if(p.y!==undefined)p.y=Math.round((p.y+delta.dy)*100)/100;return Object.keys(p).length>1?[p]:[]}))
const additions=computed<PptTextAddition[]>(()=>blocks.value.filter(b=>b.key.startsWith('new-')).map(b=>({key:b.key,text:b.text,x:b.x,y:b.y,width:b.width??400,...(b.height?{height:b.height}:{}),font_size:b.font_size,color:b.color,bold:b.bold})))
const dirty=computed(()=>patches.value.length>0||additions.value.length>0||moves.value.length>0)
const overlayStyle=computed(()=>selection.value?{left:selection.value.x/12.8+'%',top:selection.value.y/7.2+'%',width:selection.value.width/12.8+'%',height:selection.value.height/7.2+'%'}:{})
const inputStyle=computed(()=>({...overlayStyle.value,fontSize:(current.value?.font_size??28)/12.8+'cqw',color:current.value?.color,fontWeight:current.value?.bold?'700':'400'}))
function safeSvg(value:string){
 const doc=new DOMParser().parseFromString(value,'image/svg+xml'),root=doc.documentElement
 if(root.localName!=='svg'||doc.querySelector('parsererror')||value.length>3_000_000)throw new Error('页面数据无法编辑')
 const tags=new Set(['svg','g','defs','marker','path','rect','circle','ellipse','line','polyline','polygon','text','tspan','image'])
 const attrs=new Set(['xmlns','id','fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','stroke-miterlimit','opacity','fill-opacity','stroke-opacity','transform','fill-rule','clip-rule','width','height','viewBox','data-pptx-page-role','data-pptx-role','data-pptx-bounds','data-pptx-frame','x','y','x1','y1','x2','y2','rx','ry','r','cx','cy','d','points','font-family','font-size','font-weight','font-style','text-anchor','dominant-baseline','dx','dy','letter-spacing','href','preserveAspectRatio','marker-start','marker-mid','marker-end','markerWidth','markerHeight','refX','refY','orient','markerUnits','xml:space'])
 for(const node of [root,...root.querySelectorAll('*')]){
  if(!tags.has(node.localName)||node.namespaceURI!=='http://www.w3.org/2000/svg')throw new Error('页面包含不支持的元素')
  for(const a of [...node.attributes]){
   if(!attrs.has(a.name)||a.name.toLowerCase().startsWith('on'))throw new Error('页面包含不支持的属性')
   if(a.name==='href'&&(node.localName!=='image'||!/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(a.value)))throw new Error('页面图片无法编辑')
   if(/javascript:|https?:|url\(/i.test(a.value)&&!(a.name==='xmlns'||/^marker-(start|mid|end)$/.test(a.name)&&/^url\(#[-A-Za-z0-9_]+\)$/.test(a.value)))throw new Error('页面包含外部内容')
  }
 }
 return root
}
function textNodes(root:Element){return [...root.querySelectorAll<SVGTextElement>('text')].filter(t=>!t.closest('defs,marker'))}
function measure(value:string,size:number){return [...value].reduce((n,c)=>n+size*(/[\u1100-\u115F\u2329\u232A\u2E80-\uA4CF\uAC00-\uD7A3\uF900-\uFAFF\uFE10-\uFE19\uFE30-\uFE6F\uFF01-\uFF60\uFFE0-\uFFE6\u{1F300}-\u{1FAFF}]/u.test(c)?1:.62),0)}
function wrapped(b:PptTextBlock,old:PptTextBlock){
 const original=Math.max(...old.text.split('\n').map(t=>measure(t,old.font_size)),old.font_size)
 const anchor=b.anchor??'start',edge=anchor==='start'?1280-b.x-24:anchor==='end'?b.x-24:2*Math.min(b.x-24,1280-b.x-24)
 const width=b.width??Math.min(Math.max(original*1.05,b.font_size*5),edge),lines:string[]=[]
 for(const paragraph of b.text.split('\n')){let line='';for(const c of paragraph){if(line&&measure(line+c,b.font_size)>width){lines.push(line);line=''}line+=c}lines.push(line)}
 return lines
}
function parentDelta(node:Element,dx:number,dy:number){
 const parents:Element[]=[];for(let parent=node.parentElement;parent;parent=parent.parentElement)parents.unshift(parent)
 let a=1,b=0,c=0,d=1
 for(const parent of parents)for(const match of (parent.getAttribute('transform')??'').matchAll(/(translate|scale|rotate)\(([^)]*)\)/g)){
  const v=match[2]!.trim().split(/[ ,]+/).map(Number);let p=1,q=0,r=0,t=1
  if(match[1]==='scale'){p=v[0]!;t=v[1]??p}else if(match[1]==='rotate'){const rad=v[0]!*Math.PI/180;p=t=Math.cos(rad);q=Math.sin(rad);r=-q}
  const next=[a*p+c*q,b*p+d*q,a*r+c*t,b*r+d*t];[a,b,c,d]=next as [number,number,number,number]
 }
 const det=a*d-b*c;return {dx:(d*dx-c*dy)/det,dy:(a*dy-b*dx)/det}
}
function rebuild(){
 const root=safeSvg(source),nodes=textNodes(root)
 for(const obj of objects.value){let node:Element|undefined=root;for(const index of obj.path)node=node?.children[index];if(!node)continue;node.setAttribute('data-object-key',obj.key);node.setAttribute('tabindex','0');if(!obj.text_key){node.setAttribute('role','button');node.setAttribute('aria-label','移动'+obj.label)}const offset=offsets.value[obj.key];if(offset&&(offset.dx||offset.dy)){const current=node.getAttribute('transform')??'';const local=parentDelta(node,offset.dx,offset.dy);node.setAttribute('transform','translate('+local.dx+' '+local.dy+') '+current)}}
 for(const b of blocks.value.filter(b=>b.key.startsWith('new-'))){const node=root.ownerDocument.createElementNS('http://www.w3.org/2000/svg','text');node.setAttribute('font-family','Microsoft YaHei, Arial');node.setAttribute('x',String(b.x));node.setAttribute('y',String(b.y));root.append(node);nodes.push(node)}
 for(const [i,node] of nodes.entries()){
  const b=blocks.value[i];if(!b)continue
  const isNew=b.key.startsWith('new-'),old=original.value.find(o=>o.key===b.key)??{...b,text:''}
  const geometry=isNew||b.x!==old.x||b.y!==old.y||b.width!==old.width||b.height!==old.height
  if(geometry){node.setAttribute('x',String(b.x));node.setAttribute('y',String(b.y))}
  if(geometry||b.text!==old.text||b.font_size!==old.font_size||b.bold!==old.bold){
   node.replaceChildren();const lines=wrapped(b,old)
   for(const [line,text] of lines.entries()){const span=root.ownerDocument.createElementNS(root.namespaceURI,'tspan');span.setAttribute('x',String(b.x));span.setAttribute('y',String(b.y+line*b.font_size*1.35));span.textContent=text;node.append(span)}
  }
  for(const [name,key] of [['font-size','font_size'],['fill','color'],['font-weight','bold']] as const){
   if(isNew||b[key]!==old[key]||b.text!==old.text){const value=key==='bold'?(b.bold?'700':'400'):String(b[key]);node.setAttribute(name,value);node.querySelectorAll('tspan').forEach(s=>s.setAttribute(name,value))}
  }
  if(b.editable){node.setAttribute('data-text-key',b.key);node.setAttribute('tabindex','0');node.setAttribute('role','button');node.setAttribute('aria-label','编辑文字：'+b.text.slice(0,36));node.setAttribute('aria-pressed',String(b.key===selected.value))}
 }
 svg.value=new XMLSerializer().serializeToString(root)
 void nextTick(updateSelection)
}
function textRect(b:PptTextBlock){
 const obj=objects.value.find(o=>o.text_key===b.key),old=original.value.find(o=>o.key===b.key)??b
 const width=b.width??obj?.bounds[2]??Math.max(...old.text.split('\n').map(t=>measure(t,old.font_size)),old.font_size*5)
 const height=b.height??Math.max(obj?.bounds[3]??0,wrapped({...b,width},old).length*b.font_size*1.35+b.font_size*.1)
 return {x:b.x-((b.anchor??'start')==='end'?width:b.anchor==='middle'?width/2:0),y:b.y-b.font_size,width,height}
}
function updateSelection(){
 const b=current.value
 if(b){const obj=objects.value.find(o=>o.text_key===b.key),delta=obj?effectiveOffset(obj):{dx:0,dy:0},box=textRect(b);selection.value={...box,x:box.x+delta.dx,y:box.y+delta.dy};return}
 const obj=selectedItem.value
 if(obj){const [x,y,width,height]=obj.bounds,offset=effectiveOffset(obj);selection.value={x:x+offset.dx,y:y+offset.dy,width,height}}
 else selection.value=undefined
}
function choose(key:string,edit=false){if(saving.value)return;adding.value=false;selected.value=key;selectedObject.value=objects.value.find(o=>o.text_key===key)?.key??'';typing.value=edit;host.value?.querySelectorAll('[data-text-key]').forEach(node=>node.setAttribute('aria-pressed',String(node.getAttribute('data-text-key')===key)));void nextTick(updateSelection);if(edit)void nextTick(()=>input.value?.focus())}
function snapshot(){return {blocks:blocks.value.map(b=>({...b})),offsets:Object.fromEntries(Object.entries(offsets.value).map(([k,v])=>[k,{...v}]))}}
function remember(){history.value.push(snapshot());if(history.value.length>60)history.value.shift()}
function placeBox(event:MouseEvent){
 const canvas=event.currentTarget as HTMLElement,rect=canvas.getBoundingClientRect()
 const x=rect.width?Math.max(24,Math.min(856,(event.clientX-rect.left)*1280/rect.width)):64
 const y=rect.height?Math.max(48,Math.min(640,(event.clientY-rect.top)*720/rect.height)):360
 remember();const key='new-'+(++newBoxNumber)
 blocks.value.push({key,text:'输入文字',x:Math.round(x),y:Math.round(y),width:400,font_size:28,color:'#173359',bold:false,editable:true,anchor:'start'})
 adding.value=false;choose(key,true);emit('dirty',true);void nextTick(()=>input.value?.select())
}
function clicked(event:MouseEvent){
 if(suppressClick){suppressClick=false;return}
 if((event.target as Element)?.closest?.('[data-text-frame]'))return
 if((event.target as Element)?.closest?.('textarea,input,select')||saving.value)return
 if(adding.value){placeBox(event);return}
 const target=(event.target as Element)?.closest?.('[data-text-key]')
 if(target)choose(target.getAttribute('data-text-key')!,false)
 else if((event.target as Element)?.closest?.('[data-object-key]'))selectObject((event.target as Element).closest('[data-object-key]')!.getAttribute('data-object-key')!)
 else{typing.value=false;selected.value='';selectedObject.value='';selection.value=undefined;rebuild()}
}
function doubleClicked(event:MouseEvent){if(suppressClick||saving.value)return;const key=(event.target as Element).closest('[data-text-key]')?.getAttribute('data-text-key');if(key)choose(key,true)}
function keyboard(event:KeyboardEvent){const target=event.target as Element;if(target.closest('textarea,input,select')||event.isComposing)return;
 const objectKey=target.closest('[data-object-key]')?.getAttribute('data-object-key')??selectedObject.value
 if(objectKey&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();selectedObject.value=objectKey;typing.value=false;remember();const step=event.shiftKey?10:1,previous=offsets.value[objectKey]??{dx:0,dy:0};moveObject(objectKey,previous.dx+(event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0),previous.dy+(event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0));rebuild();void nextTick(()=>host.value?.querySelector<SVGElement>('[data-object-key="'+objectKey+'"]')?.focus());emit('dirty',dirty.value);return}
const key=target.closest('[data-text-key]')?.getAttribute('data-text-key');if(key&&(event.key==='Enter'||event.key===' ')){event.preventDefault();choose(key,true)}}
function effectiveOffset(obj:PptCanvasObject,excludeSelf=false){
 let dx=0,dy=0
 for(const candidate of objects.value){if(excludeSelf&&candidate.key===obj.key)continue;if(candidate.path.length<=obj.path.length&&candidate.path.every((v,i)=>v===obj.path[i])){const o=offsets.value[candidate.key];if(o){dx+=o.dx;dy+=o.dy}}}
 return {dx,dy}
}
function selectObject(key:string){selectedObject.value=key;const obj=objects.value.find(o=>o.key===key);selected.value=obj?.text_key??'';typing.value=false;adding.value=false;rebuild();void nextTick(()=>host.value?.querySelector<SVGElement>('[data-object-key="'+key+'"]')?.focus())}
function moveObject(key:string,dx:number,dy:number){
 const obj=objects.value.find(o=>o.key===key);if(!obj)return
 const block=blocks.value.find(b=>b.key===obj.text_key),box=block?textRect(block):undefined
 const [x,y,width,height]=box?[box.x,box.y,box.width,box.height]:obj.bounds,parent=effectiveOffset(obj,true)
 offsets.value[key]={dx:Math.round(Math.max(-x-parent.dx,Math.min(1280-x-width-parent.dx,dx))*100)/100,dy:Math.round(Math.max(-y-parent.dy,Math.min(720-y-height-parent.dy,dy))*100)/100}
}
function pointerDown(event:PointerEvent){
 const target=event.target as Element
 if(target.closest('[data-text-frame]'))return
 if(saving.value||adding.value||target.closest('textarea,input,select')||event.button!==0)return
 let key=target.closest('[data-object-key]')?.getAttribute('data-object-key')
 const selectedGroup=selectedItem.value
 if(selectedGroup?.kind==='group'){const candidate=objects.value.find(o=>o.key===key);if(candidate&&selectedGroup.path.every((v,i)=>v===candidate.path[i]))key=selectedGroup.key}
 const newKey=target.closest('[data-text-key]')?.getAttribute('data-text-key')
 if(!key&&!newKey?.startsWith('new-'))return
 const canvas=event.currentTarget as HTMLElement,rect=canvas.getBoundingClientRect()
 drag={id:event.pointerId,x:event.clientX,y:event.clientY,key:key??newKey!,start:key?{...(offsets.value[key]??{dx:0,dy:0})}:{dx:0,dy:0},snapshot:snapshot(),active:false,scaleX:rect.width?1280/rect.width:1,scaleY:rect.height?720/rect.height:1}
}
function pointerMove(event:PointerEvent){
 if(resizing){resizeMove(event);return}
 if(!drag||event.pointerId!==drag.id)return
 const dx=(event.clientX-drag.x)*drag.scaleX,dy=(event.clientY-drag.y)*drag.scaleY
 if(!drag.active&&Math.hypot(event.clientX-drag.x,event.clientY-drag.y)<4)return
 if(!drag.active){(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);remember();drag.active=true;dragging.value=true;typing.value=false;selectedObject.value=drag.key;selected.value=objects.value.find(o=>o.key===drag!.key)?.text_key??drag.key}
 event.preventDefault()
 if(drag.key.startsWith('new-')){const block=blocks.value.find(b=>b.key===drag!.key),old=drag.snapshot.blocks.find(b=>b.key===drag!.key);if(block&&old){block.x=Math.round(Math.max(24,Math.min(1256-(block.width??400),old.x+dx)));block.y=Math.round(Math.max(block.font_size,Math.min(696-block.font_size*.45,old.y+dy)))}}
 else moveObject(drag.key,drag.start.dx+dx,drag.start.dy+dy)
 rebuild();emit('dirty',dirty.value)
}
function pointerUp(event:PointerEvent,cancel=false){
 if(resizing){resizeUp(event,cancel);return}
 if(!drag||event.pointerId!==drag.id)return
 const canvas=event.currentTarget as HTMLElement
 if(cancel&&drag.active){blocks.value=drag.snapshot.blocks;offsets.value=drag.snapshot.offsets;history.value.pop();rebuild();emit('dirty',dirty.value)}
 suppressClick=drag.active&&!cancel;drag=undefined;dragging.value=false
 if(canvas.hasPointerCapture?.(event.pointerId))canvas.releasePointerCapture(event.pointerId)
}
function startResize(event:PointerEvent,handle:string){
 if(!current.value?.editable||saving.value||!selection.value||event.button!==0)return
 event.preventDefault();const canvas=host.value?.parentElement,rect=canvas?.getBoundingClientRect();if(!canvas||!rect)return
 resizing={id:event.pointerId,handle,x:event.clientX,y:event.clientY,box:{...selection.value},block:{...current.value},snapshot:snapshot(),active:false,scaleX:rect.width?1280/rect.width:1,scaleY:rect.height?720/rect.height:1}
 typing.value=false
}
function resizeMove(event:PointerEvent){
 if(!resizing||event.pointerId!==resizing.id||!current.value)return
 const state=resizing,dx=(event.clientX-state.x)*state.scaleX,dy=(event.clientY-state.y)*state.scaleY
 if(!state.active&&Math.hypot(event.clientX-state.x,event.clientY-state.y)<2)return
 if(!state.active){(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);remember();state.active=true;dragging.value=true}
 event.preventDefault()
 const old=state.box,minWidth=80,minHeight=24
 let left=old.x,top=old.y,right=old.x+old.width,bottom=old.y+old.height
 if(state.handle.includes('w'))left=Math.max(0,right-1200,Math.min(right-minWidth,old.x+dx))
 if(state.handle.includes('e'))right=Math.min(1280,left+1200,Math.max(left+minWidth,right+dx))
 if(state.handle.includes('n'))top=Math.max(0,Math.min(bottom-minHeight,old.y+dy))
 if(state.handle.includes('s'))bottom=Math.min(720,Math.max(top+minHeight,bottom+dy))
 const obj=objects.value.find(o=>o.text_key===state.block.key),delta=obj?effectiveOffset(obj):{dx:0,dy:0},width=right-left,height=bottom-top
 const anchor=state.block.anchor??'start'
 Object.assign(current.value,{x:Math.round((left-delta.dx+(anchor==='end'?width:anchor==='middle'?width/2:0))*100)/100,y:Math.round((top-delta.dy+state.block.font_size)*100)/100,width:Math.round(width*100)/100,height:Math.round(height*100)/100})
 error.value='';rebuild();emit('dirty',dirty.value)
}
function resizeUp(event:PointerEvent,cancel=false){
 if(!resizing||event.pointerId!==resizing.id)return
 if(cancel&&resizing.active){blocks.value=resizing.snapshot.blocks;offsets.value=resizing.snapshot.offsets;history.value.pop();rebuild();emit('dirty',dirty.value)}
 suppressClick=resizing.active&&!cancel;resizing=undefined;dragging.value=false
 const canvas=event.currentTarget as HTMLElement;if(canvas.hasPointerCapture?.(event.pointerId))canvas.releasePointerCapture(event.pointerId)
}
function startFrameMove(event:PointerEvent){
 if(!current.value||saving.value||event.button!==0)return
 event.preventDefault();const b=current.value,obj=objects.value.find(o=>o.text_key===b.key),canvas=host.value?.parentElement,rect=canvas?.getBoundingClientRect();if(!rect)return
 const key=obj?.key??b.key;typing.value=false
 drag={id:event.pointerId,x:event.clientX,y:event.clientY,key,start:{...(offsets.value[key]??{dx:0,dy:0})},snapshot:snapshot(),active:false,scaleX:rect.width?1280/rect.width:1,scaleY:rect.height?720/rect.height:1}
}
function frameKey(event:KeyboardEvent,handle:string){
 if(!current.value||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return
 event.preventDefault();event.stopPropagation();const b=current.value,box=textRect(b),step=event.shiftKey?10:1
 const delta=event.key==='ArrowLeft'||event.key==='ArrowUp'?-step:step
 if(handle==='move'){
  const obj=objects.value.find(o=>o.text_key===b.key);remember();if(obj){const old=offsets.value[obj.key]??{dx:0,dy:0};moveObject(obj.key,old.dx+(event.key.includes('Left')||event.key.includes('Right')?delta:0),old.dy+(event.key.includes('Up')||event.key.includes('Down')?delta:0))}else{b.x=Math.max(24,Math.min(1256-box.width,b.x+(event.key.includes('Left')||event.key.includes('Right')?delta:0)));b.y=Math.max(b.font_size,Math.min(720-box.height+b.font_size,b.y+(event.key.includes('Up')||event.key.includes('Down')?delta:0)))}
 }else if(event.key.includes('Left')||event.key.includes('Right')){change('width',Math.max(80,Math.min(1280-box.x,Math.min(1200,box.width+delta))));return}
 else{change('height',Math.max(24,Math.min(720-box.y,box.height+delta)));return}
 rebuild();emit('dirty',dirty.value)
}
function change(key:'text'|'font_size'|'color'|'bold'|'x'|'y'|'width'|'height',value:string|number|boolean){
 if(!current.value||saving.value||current.value[key]===value)return
 remember()
 Object.assign(current.value,{[key]:value});error.value='';rebuild();emit('dirty',dirty.value)
}
function undo(){const previous=history.value.pop();if(previous){blocks.value=previous.blocks;offsets.value=previous.offsets;error.value='';rebuild();emit('dirty',dirty.value)}}
async function save(){
 if(!dirty.value||saving.value)return;saving.value=true;emit('saving',true);error.value=''
 try{const p=await savePptText(props.projectId,props.slideId,props.revision,patches.value,additions.value,moves.value);if(!disposed){emit('dirty',false);emit('saved',p)}}catch(e){if(!disposed)error.value=errorText(e)}finally{saving.value=false;emit('saving',false)}
}
function beforeUnload(e:BeforeUnloadEvent){if(dirty.value){e.preventDefault();e.returnValue=''}}
onMounted(async()=>{window.addEventListener('beforeunload',beforeUnload);try{const data=await getPptEditor(props.projectId,props.slideId,props.revision);if(disposed)return;source=data.svg;safeSvg(source);objects.value=data.objects??[];blocks.value=data.blocks.map(b=>({...b}));original.value=data.blocks.map(b=>({...b}));rebuild()}catch(e){error.value=errorText(e)}finally{loading.value=false}})
onBeforeUnmount(()=>{disposed=true;window.removeEventListener('beforeunload',beforeUnload)})
</script>
<template>
<section class="ppt-text-editor" aria-label="直接编辑课件文字" :aria-busy="loading||saving">
 <div class="ppt-editor-toolbar" role="toolbar" aria-label="课件编辑工具">
  <el-button data-testid="move-mode" :type="moveMode?'primary':'default'" :aria-pressed="moveMode" :disabled="saving||loading" @click="typing=false;adding=false;moveMode=!moveMode">{{moveMode?'移动模式':'移动对象'}}</el-button>
  <el-button data-testid="add-text-box" :type="adding?'primary':'default'" :disabled="loading||saving" :aria-pressed="adding" @click="typing=false;adding=!adding">添加文本框</el-button>
  <label class="ppt-editor-picker"><span class="sr-only">选择文字</span><select aria-label="选择编辑文字" :value="selected" :disabled="saving||loading" @change="choose(($event.target as HTMLSelectElement).value,true)"><option value="">点击选择，双击编辑</option><option v-for="b in blocks.filter(b=>b.editable)" :key="b.key" :value="b.key">{{b.text.slice(0,24)}}</option></select></label>
  <label>字号<input aria-label="文字字号" type="number" min="18" max="72" :value="current?.font_size??28" :disabled="saving||!current" @input="change('font_size',Number(($event.target as HTMLInputElement).value))"/></label>
  <label>颜色<input aria-label="文字颜色" type="color" :value="current?.color??'#173359'" :disabled="saving||!current" @input="change('color',($event.target as HTMLInputElement).value)"/></label>
  <el-button class="ppt-editor-bold" aria-label="文字加粗" :type="current?.bold?'primary':'default'" :aria-pressed="current?.bold??false" :disabled="saving||!current" @click="change('bold',!current?.bold)"><strong>B</strong></el-button>
  <el-button data-testid="undo-text-edit" :disabled="!history.length||saving" @click="typing=false;undo()">撤销</el-button>
  <span class="ppt-editor-toolbar-space"/>
  <el-button data-testid="save-text-edit" type="primary" :disabled="!dirty||loading||saving" :loading="saving" @click="save">{{saving?'保存中':'保存'}}</el-button>
  <el-button data-testid="cancel-text-edit" :disabled="saving" @click="emit('cancel')">退出编辑</el-button>
 </div>
 <div class="ppt-editor-position ppt-editor-text-properties" aria-label="文本框大小"><template v-if="current?.editable">
  <span>文本框</span><template v-if="current.key.startsWith('new-')"><label>横向<input aria-label="文本框横坐标" type="number" :value="current.x" :disabled="saving" @input="change('x',Number(($event.target as HTMLInputElement).value))"/></label><label>纵向<input aria-label="文本框纵坐标" type="number" :value="current.y" :disabled="saving" @input="change('y',Number(($event.target as HTMLInputElement).value))"/></label></template>
  <label>宽度<input aria-label="文本框宽度" type="number" min="80" max="1200" :value="Math.round((current.width??textRect(current).width)*100)/100" :disabled="saving" @input="change('width',Number(($event.target as HTMLInputElement).value))"/></label><label>高度<input aria-label="文本框高度" type="number" min="24" max="720" :value="Math.round((current.height??textRect(current).height)*100)/100" :disabled="saving" @input="change('height',Number(($event.target as HTMLInputElement).value))"/></label><el-button :disabled="saving" @click="typing=true;nextTick(()=>input?.focus())">编辑文字</el-button>
 </template></div>
 <div class="ppt-editor-position" v-if="objects.length"><label>选择对象<select aria-label="选择移动对象" :value="selectedObject" :disabled="saving" @change="selectObject(($event.target as HTMLSelectElement).value)"><option value="">点击或拖动画面对象</option><option v-for="o in objects" :key="o.key" :value="o.key">{{o.kind==='group'?'组合：':o.kind==='image'?'图片：':o.kind==='text'?'文字：':'图形：'}}{{o.label}}</option></select></label><span>拖动调整位置 · 方向键微调，Shift 加速</span></div>
 <p v-if="loading" role="status">正在加载页面…</p>
 <div v-if="svg" class="ppt-editor-canvas" :class="{'is-adding':adding,'is-moving':moveMode,'is-dragging':dragging}" @pointerdown="pointerDown" @pointermove="pointerMove" @pointerup="pointerUp($event)" @pointercancel="pointerUp($event,true)" @lostpointercapture="pointerUp($event,true)" @click="clicked" @dblclick="doubleClicked" @keydown="keyboard">
  <div ref="host" class="ppt-editor-svg" v-html="svg"/>
  <div v-if="selection&&!adding" :class="['ppt-text-selection',{'is-text-frame':current?.editable}]" :style="overlayStyle" :aria-hidden="current?.editable?undefined:true" :data-text-frame="current?.editable?'true':undefined" @dblclick.stop="current?.editable&&choose(current.key,true)">
   <template v-if="current?.editable">
    <div v-for="edge in ['top','right','bottom','left']" :key="edge" :class="['ppt-frame-edge','edge-'+edge]" @pointerdown.stop="startFrameMove" @click.stop/>
    <button class="ppt-frame-move" type="button" data-testid="text-move-handle" aria-label="移动文本框" :disabled="saving" @pointerdown.stop="startFrameMove" @keydown="frameKey($event,'move')" @click.stop>↔</button>
    <button v-for="handle in frameHandles" :key="handle" type="button" :class="['ppt-frame-handle','handle-'+handle]" :data-resize-handle="handle" :data-testid="handle==='se'?'text-resize-corner':handle==='e'?'text-resize-width':undefined" :aria-label="'调整文本框大小 '+handle" :disabled="saving" @pointerdown.stop="startResize($event,handle)" @keydown="frameKey($event,handle)" @click.stop/>
   </template>
  </div>
  <textarea v-if="typing&&current" ref="input" class="ppt-text-overlay" aria-label="画面原位文字输入" :value="current.text" :style="inputStyle" :disabled="saving" maxlength="2000" @click.stop @dblclick.stop @input="change('text',($event.target as HTMLTextAreaElement).value)" @keydown.esc.stop="typing=false" @blur="typing=false"/>
 </div>
 <div class="ppt-editor-status" role="status"><span>{{adding?'点击画面空白处放置文本框':dirty?'有未保存修改 · 保存后生成新版本，旧版保留':'点击选中文本框，拖动边框移动，拖动控制点调整大小；双击编辑文字'}}</span></div>
 <p v-if="error" class="ppt-editor-error" role="alert">{{error}}</p>
</section>
</template>
<style scoped src="../../styles/ppt-text-editor.css"></style>
