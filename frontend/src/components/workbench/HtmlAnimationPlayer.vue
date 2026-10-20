<script setup lang="ts">
import {computed,nextTick,onBeforeUnmount,onMounted,ref} from 'vue'
import type {VideoSegment} from '../../api/videos'
import {errorText} from '../../api/http'
import {preparePreviewHtml} from '../../utils/preview-frame'
const props=defineProps<{segments:VideoSegment[];duration:number;aspectRatio?:string;htmlUrl?:string|null;audioUrl?:string|null}>()
const emit=defineEmits<{time:[number]}>()
const frame=ref<HTMLIFrameElement>(),audio=ref<HTMLAudioElement>(),srcdoc=ref(''),time=ref(0),playing=ref(false),loading=ref(true),ready=ref(false),error=ref('')
const ratio=computed(()=>props.aspectRatio??'16 / 9')
let epoch=0,playAttempt=0,disposed=false,controller:AbortController|undefined,blobUrl='',channel='',raf=0,playIntent=false,readyTimeout:ReturnType<typeof setTimeout>|undefined,readyRetry:ReturnType<typeof setInterval>|undefined
let renderRequest=0,pendingRender=0,renderedTime=-1,renderTimeout:ReturnType<typeof setTimeout>|undefined
let settleReady:((value:boolean)=>void)|undefined,frameReady:Promise<boolean>=Promise.resolve(false)
function postTime(){
 if(pendingRender)return
 pendingRender=++renderRequest
 frame.value?.contentWindow?.postMessage({type:'edu-preview:render',channel,request:pendingRender,time:Math.max(0,time.value)},'*')
 renderTimeout=setTimeout(()=>{if(!disposed){pendingRender=0;ready.value=false;pause();error.value='动画画面加载失败，请重新加载';loading.value=false;settleReady?.(false)}},12000)
}
function pause(){++playAttempt;playIntent=false;playing.value=false;audio.value?.pause();cancelAnimationFrame(raf)}
function tick(){
 if(disposed||!playing.value)return
 const el=audio.value,segment=props.segments[0]
 if(el&&segment){time.value=Math.min(props.duration,el.currentTime);emit('time',time.value);postTime()}
 raf=requestAnimationFrame(tick)
}
function updateTime(){const segment=props.segments[0];if(segment&&audio.value){time.value=Math.min(props.duration,audio.value.currentTime);emit('time',time.value);postTime()}}
function cleanup(){
 controller?.abort();clearTimeout(readyTimeout);clearTimeout(renderTimeout);pendingRender=0;renderedTime=-1;clearInterval(readyRetry);settleReady?.(false);settleReady=undefined
 audio.value?.pause();audio.value?.removeAttribute('src');audio.value?.load()
 if(blobUrl)URL.revokeObjectURL(blobUrl);blobUrl=''
}
async function startAudio(token:number){
 if(token!==epoch||disposed||!playIntent||!ready.value||!audio.value)return
 const el=audio.value,attempt=++playAttempt
 try{await el.play();if(attempt!==playAttempt){if(el!==audio.value)el.pause();return}if(token!==epoch||disposed||!playIntent){el.pause();return}playing.value=true;cancelAnimationFrame(raf);tick()}
 catch{if(attempt===playAttempt&&token===epoch&&!disposed){pause();error.value='无法播放配音，请点击播放重试'}}
}
async function loadFilm(at:number,resume=false){
 const token=++epoch;pause();cleanup();time.value=at;emit('time',at);ready.value=false;loading.value=true;error.value='';srcdoc.value=''
 playIntent=resume;channel=crypto.randomUUID();controller=new AbortController();const signal=controller.signal
 const segment={html_url:props.htmlUrl,audio_url:props.audioUrl}
 if(!segment?.html_url||!segment.audio_url){error.value='预览资源不完整，请重新生成预览';loading.value=false;return}
 try{
  const [htmlResponse,audioResponse]=await Promise.all([fetch(segment.html_url,{signal,credentials:'same-origin'}),fetch(segment.audio_url,{signal,credentials:'same-origin'})])
  if(!htmlResponse.ok||!audioResponse.ok)throw new Error('预览资源加载失败，请重试；若资源已失效，请重新生成预览')
  const [html,blob]=await Promise.all([htmlResponse.text(),audioResponse.blob()])
  if(token!==epoch||disposed)return
  frameReady=new Promise(resolve=>{settleReady=resolve;readyTimeout=setTimeout(()=>resolve(false),12000)})
  blobUrl=URL.createObjectURL(blob);srcdoc.value=preparePreviewHtml(html);await nextTick()
  if(token!==epoch||disposed)return
  initializeFrame();readyRetry=setInterval(initializeFrame,250)
  if(audio.value){audio.value.src=blobUrl;audio.value.load()}
  const connected=await frameReady
  if(token!==epoch||disposed)return
  if(!connected)throw new Error('动画加载超时，请重试')
  clearTimeout(readyTimeout);clearInterval(readyRetry);ready.value=true;loading.value=false;setAudioPosition()
  if(playIntent)await startAudio(token)
 }catch(e){if(token===epoch&&!disposed&&!(e instanceof DOMException&&e.name==='AbortError')){clearInterval(readyRetry);clearTimeout(readyTimeout);clearTimeout(renderTimeout);pendingRender=0;settleReady=undefined;error.value=errorText(e);loading.value=false;pause()}}
}
function setAudioPosition(){if(audio.value){try{audio.value.currentTime=Math.max(0,time.value)}catch{/* metadata will retry */}}}
function initializeFrame(){if(!disposed&&settleReady)frame.value?.contentWindow?.postMessage({type:'edu-preview:init',channel},'*')}
function message(event:MessageEvent){
 if(event.source!==frame.value?.contentWindow||event.data?.channel!==channel)return
 if(event.data?.type==='edu-preview:error'||(event.data?.type==='edu-preview:render-error'&&event.data.request===pendingRender)){clearInterval(readyRetry);clearTimeout(renderTimeout);pendingRender=0;ready.value=false;pause();error.value='动画运行失败，请重新加载预览';loading.value=false;settleReady?.(false);return}
 if(event.data?.type==='edu-preview:ready'&&settleReady){clearInterval(readyRetry);postTime()}
 if(event.data?.type==='edu-preview:rendered'&&pendingRender&&event.data.request===pendingRender){
  clearTimeout(renderTimeout);pendingRender=0;renderedTime=event.data.time
  settleReady?.(true);settleReady=undefined
  if(Number.isFinite(renderedTime)&&Math.abs(renderedTime-time.value)>.001)postTime()
 }
}
function seek(value:number,resume=false){
 if(!Number.isFinite(value)||!props.segments.length)return
 const at=Math.max(0,Math.min(props.duration,value))
 if(!ready.value){void loadFilm(at,resume);return}
 pause();time.value=at;emit('time',at);setAudioPosition();postTime();playIntent=resume;if(resume)void startAudio(epoch)
}
async function toggle(){if(playing.value){pause();return}if(!ready.value)return;error.value='';if(time.value>=props.duration-.01){seek(0,true);return}playIntent=true;await startAudio(epoch)}
function ended(){time.value=props.duration;emit('time',time.value);postTime();pause()}
function visibility(){if(document.hidden)pause()}
function mediaError(){if(audio.value?.getAttribute('src')&&!loading.value){pause();error.value='配音加载失败，请重试'}}
function retry(){void loadFilm(time.value,false)}
function format(value:number){return Math.floor(value/60)+':'+String(Math.floor(value%60)).padStart(2,'0')}
onMounted(()=>{window.addEventListener('message',message);document.addEventListener('visibilitychange',visibility);void loadFilm(0)})
onBeforeUnmount(()=>{disposed=true;++epoch;pause();cleanup();window.removeEventListener('message',message);document.removeEventListener('visibilitychange',visibility)})
defineExpose({pause,seek,currentTime:time})
</script>
<template>
 <div class="html-player" :aria-busy="loading">
  <div class="animation-stage" :style="{aspectRatio:ratio}">
   <iframe ref="frame" :key="channel" :srcdoc="srcdoc" title="教学动画" sandbox="allow-scripts" referrerpolicy="no-referrer" @load="initializeFrame"/>
   <div v-if="loading" class="loading-layer" role="status"><span class="spinner"/>正在加载动画和配音…</div>
  </div>
  <audio ref="audio" :key="channel" preload="auto" @loadedmetadata="setAudioPosition" @timeupdate="updateTime" @ended="ended" @error="mediaError"/>
  <div class="playback-controls">
   <button type="button" class="play-toggle" :disabled="!ready||loading" @click="toggle">{{playing?'暂停':'播放'}}</button>
   <span class="clock">{{format(time)}} / {{format(duration)}}</span>
   <input type="range" min="0" :max="duration" step="0.01" :value="time" aria-label="播放位置" :aria-valuetext="format(time)" @input="seek(Number(($event.target as HTMLInputElement).value))"/>
  </div>
  <div v-if="error" class="player-error" role="alert">{{error}}<button type="button" @click="retry">重新加载</button></div>
 </div>
</template>
<style scoped>
.html-player{width:100%;min-width:0}.animation-stage{position:relative;background:var(--ev-color-surface-muted);width:100%;max-height:70vh;margin:auto}.animation-stage iframe{display:block;width:100%;height:100%;position:absolute;inset:0;border:0}.loading-layer{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;gap:12px;background:var(--ev-color-surface-muted);color:var(--ev-color-muted)}.spinner{width:20px;height:20px;border:2px solid var(--ev-color-border);border-top-color:var(--ev-color-primary);border-radius:50%;animation:spin 1s linear infinite}.playback-controls{display:flex;align-items:center;gap:16px;padding:12px 16px;border-top:1px solid var(--ev-color-border);background:var(--ev-color-surface)}.play-toggle,.player-error button{min-height:44px;padding:0 16px;border:1px solid var(--ev-color-border);border-radius:var(--ev-radius);background:var(--ev-color-surface);color:var(--ev-color-primary-dark);font:inherit;font-weight:600;cursor:pointer}.play-toggle:disabled{opacity:.5;cursor:wait}.clock{font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap}.playback-controls input{flex:1;min-width:50px;accent-color:var(--ev-color-primary);height:32px;cursor:pointer}.player-error{padding:12px 16px;color:var(--el-color-danger);display:flex;align-items:center;gap:12px;flex-wrap:wrap}.player-error button{margin-left:auto}:focus-visible{outline:2px solid var(--ev-color-primary);outline-offset:3px}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:600px){.playback-controls{gap:8px;padding:8px;flex-wrap:wrap}.playback-controls input{flex-basis:100%}}@media(prefers-reduced-motion:reduce){.spinner{animation:none}}
</style>
