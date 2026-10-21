<script setup lang="ts">
import {onBeforeUnmount,onMounted,ref} from 'vue'
import AppIcon from '../AppIcon.vue'
import {listVideos} from '../../api/videos'
import {preparePreviewHtml} from '../../utils/preview-frame'

const props=defineProps<{projectId:string;title:string}>()
const root=ref<HTMLElement>(),frame=ref<HTMLIFrameElement>()
const frameScale=ref(.2)
const mediaUrl=ref(''),srcdoc=ref(''),ready=ref(false),loading=ref(false)
let disposed=false,started=false,observer:IntersectionObserver|undefined,controller:AbortController|undefined
let resizeObserver:ResizeObserver|undefined
let timeout:ReturnType<typeof setTimeout>|undefined
const channel=crypto.randomUUID()
function loaded(){if(disposed)return;ready.value=true;loading.value=false;clearTimeout(timeout)}
function failed(){if(disposed)return;loading.value=false;ready.value=false;mediaUrl.value='';srcdoc.value='';controller?.abort();clearTimeout(timeout)}
async function load(){
 if(started||disposed)return
 started=true;loading.value=true;timeout=setTimeout(failed,15000)
 try{
  const versions=await listVideos(props.projectId)
  if(disposed||!loading.value)return
  // Match the preview page: skip failed/running revisions, prefer an exported MP4.
  const version=versions.find(v=>['preview_ready','succeeded'].includes(v.status)&&(v.media_url||v.html_url))
  if(!version){failed();return}
  if(version.media_url){mediaUrl.value=version.media_url;return}
  controller=new AbortController()
  const response=await fetch(version.html_url!,{credentials:'same-origin',signal:controller.signal})
  if(!response.ok)throw new Error('cover unavailable')
  const html=await response.text()
  if(!disposed&&loading.value)srcdoc.value=preparePreviewHtml(html)
 }catch{failed()}
}
function initialize(){frame.value?.contentWindow?.postMessage({type:'edu-preview:init',channel},'*')}
function message(event:MessageEvent){
 if(disposed||event.source!==frame.value?.contentWindow||event.data?.channel!==channel)return
 if(event.data.type==='edu-preview:ready')frame.value?.contentWindow?.postMessage({type:'edu-preview:render',channel,request:1,time:0},'*')
 if(event.data.type==='edu-preview:rendered'&&event.data.request===1)loaded()
 if(['edu-preview:error','edu-preview:render-error'].includes(event.data.type))failed()
}
onMounted(()=>{
 window.addEventListener('message',message)
 const resize=()=>{const box=root.value?.getBoundingClientRect();if(box&&box.width&&box.height)frameScale.value=Math.min(box.width/1280,box.height/720)}
 resize()
 if(typeof ResizeObserver!=='undefined'){resizeObserver=new ResizeObserver(resize);if(root.value)resizeObserver.observe(root.value)}
 if(typeof IntersectionObserver==='undefined'){void load();return}
 observer=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)){observer?.disconnect();void load()}},{rootMargin:'160px'})
 if(root.value)observer.observe(root.value)
})
onBeforeUnmount(()=>{disposed=true;observer?.disconnect();resizeObserver?.disconnect();controller?.abort();clearTimeout(timeout);window.removeEventListener('message',message)})
</script>
<template>
 <div ref="root" class="video-cover" :aria-busy="loading" aria-hidden="true">
  <video v-if="mediaUrl" :src="mediaUrl" muted playsinline preload="metadata" tabindex="-1" :class="{ready}" @loadedmetadata="($event.target as HTMLVideoElement).currentTime=0" @loadeddata="loaded" @error="failed"/>
  <div v-else-if="srcdoc" class="cover-frame" :class="{ready}"><iframe ref="frame" :srcdoc="srcdoc" :title="title+'首帧'" tabindex="-1" sandbox="allow-scripts" referrerpolicy="no-referrer" :style="{transform:'translate(-50%,-50%) scale('+frameScale+')'}" @load="initialize"/></div>
  <div v-if="!ready" class="cover-placeholder" :class="{'is-loading':loading}"><AppIcon name="videos"/></div>
 </div>
</template>
<style scoped>
.video-cover{position:relative;width:100%;height:100%;overflow:hidden;isolation:isolate;background:#f0f5fc}.video-cover video,.cover-frame{position:absolute;inset:0;width:100%;height:100%;opacity:0;transition:opacity .2s ease;pointer-events:none}.video-cover video{object-fit:contain;background:#f0f5fc}.video-cover .ready{opacity:1}.cover-frame iframe{position:absolute;left:50%;top:50%;width:1280px;height:720px;border:0;transform-origin:center;pointer-events:none}.cover-placeholder{position:absolute;inset:0;display:grid;place-items:center;color:#7297bf}.cover-placeholder .app-icon{width:44px;height:44px;stroke-width:1}.is-loading{animation:cover-pulse 1.6s ease-in-out infinite}@keyframes cover-pulse{50%{opacity:.45}}@media(prefers-reduced-motion:reduce){.is-loading{animation:none}}
</style>
