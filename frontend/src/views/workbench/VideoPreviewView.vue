<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {getOutline,type Outline} from '../../api/outline'
import {listVideos,submitVideo,reviseVideo,exportVideo,type VideoVersion} from '../../api/videos'
import {errorText} from '../../api/http'
import {getCreditBalance,notifyCreditsChanged,type CreditBalance} from '../../api/credits'
import {addPendingOutlineNotification} from '../../utils/outline-job-notification'
import HtmlAnimationPlayer from '../../components/workbench/HtmlAnimationPlayer.vue'
import CreationSteps from '../../components/workbench/CreationSteps.vue'
import OutlineGenerationProgress from '../../components/workbench/OutlineGenerationProgress.vue'
const route=useRoute(),router=useRouter(),id=String(route.params.id)
const outline=ref<Outline>(),versions=ref<VideoVersion[]>([]),displayedId=ref(''),loading=ref(true),submitting=ref(false),error=ref(''),connectionError=ref(false),player=ref<HTMLVideoElement>(),revisionOpen=ref(false),selected=ref<string[]>([]),instruction=ref('')
const revisionMode=ref<'visual'|'voice'>('visual')
const credits=ref<CreditBalance>(),creditsError=ref('')
let creditSequence=0
async function refreshCredits(){
 const seq=++creditSequence
 try{const value=await getCreditBalance();if(!disposed&&seq===creditSequence){credits.value=value;creditsError.value=''}}
 catch{if(!disposed&&seq===creditSequence){credits.value=undefined;creditsError.value='积分余额暂时无法读取'}}
}
async function requireCredits(){
 const seq=++creditSequence,value=await getCreditBalance()
 if(!disposed&&seq===creditSequence){credits.value=value;creditsError.value=''}
 if(value.available<value.video_cost)throw new Error(`积分不足，本次生成需要 ${value.video_cost} 积分，当前可用 ${value.available} 积分，请先兑换积分`)
}

const htmlPlayer=ref<InstanceType<typeof HtmlAnimationPlayer>>(),htmlTime=ref(0)
const mediaFailed=ref(false)
let manualSelection=false
let timer:ReturnType<typeof setTimeout>|undefined,disposed=false
const latest=computed(()=>versions.value[0])
const active=computed(()=>versions.value.find(v=>['queued','running'].includes(v.status)||['pending','running'].includes(v.export_status??'')))
const activeJob=computed(()=>active.value?.export_job&&['pending','running'].includes(active.value.export_job.status)?active.value.export_job:active.value?.job)
const displayed=computed(()=>versions.value.find(v=>v.id===displayedId.value)??versions.value.find(v=>['preview_ready','succeeded'].includes(v.status)))
const confirmed=computed(()=>outline.value&&!outline.value.needs_regeneration&&!outline.value.needs_save&&['outline_confirmed','completed','video_failed','preview_ready'].includes(outline.value.status))
const canRevise=computed(()=>!!displayed.value&&['preview_ready','succeeded'].includes(displayed.value.status)&&displayed.value.outline_revision===outline.value?.revision&&confirmed.value&&!active.value&&!submitting.value)
const hasHtml=computed(()=>!displayed.value?.media_url&&!!displayed.value?.segments.length&&(displayed.value.html_url&&displayed.value.audio_url)&&['preview_ready','succeeded'].includes(displayed.value.status))
function schedule(){clearTimeout(timer);if(!disposed&&active.value&&!document.hidden)timer=setTimeout(()=>load(false),1000)}
async function load(initial=true){
 try{
  const [nextOutline,nextVersions]=await Promise.all([getOutline(id),listVideos(id)])
  if(disposed)return
  const prior=versions.value[0]
  if(prior&&['queued','running'].includes(prior.status)&&!nextVersions.some(v=>v.id===prior.id&&['queued','running'].includes(v.status))){notifyCreditsChanged();void refreshCredits()}
  outline.value=nextOutline;versions.value=nextVersions;connectionError.value=false
  const newest=nextVersions[0]
  const best=nextVersions.find(v=>['preview_ready','succeeded'].includes(v.status))??newest
  if(!displayedId.value||!nextVersions.some(v=>v.id===displayedId.value)||(!manualSelection&&prior&&['queued','running'].includes(prior.status)&&newest?.id===prior.id&&['preview_ready','succeeded'].includes(newest.status))){pause();displayedId.value=best?.id??'';htmlTime.value=0}
  for(const v of nextVersions){
   if(['queued','running'].includes(v.status))addPendingOutlineNotification({jobId:v.job.id,projectId:id})
   if(v.export_job&&['pending','running'].includes(v.export_job.status))addPendingOutlineNotification({jobId:v.export_job.id,projectId:id})
  }
 }catch(e){if(active.value)connectionError.value=true;else error.value=errorText(e)}
 finally{if(initial)loading.value=false;schedule()}
}
async function generate(retry?:string){
 if(!outline.value||submitting.value||active.value)return
 submitting.value=true;error.value=''
 try{await requireCredits();const value=await submitVideo(id,outline.value.revision,retry);versions.value=[value,...versions.value];notifyCreditsChanged();void refreshCredits();schedule()}
 catch(e){error.value=errorText(e)}finally{submitting.value=false}
}
function pause(){player.value?.pause();htmlPlayer.value?.pause()}
function chooseVersion(value:string){pause();mediaFailed.value=false;manualSelection=true;htmlTime.value=0;displayedId.value=value;revisionOpen.value=false;selected.value=[];instruction.value=''}
function reloadMedia(){pause();mediaFailed.value=false;player.value?.load()}
function findCurrent(){
 const t=hasHtml.value?htmlTime.value:(player.value?.currentTime??0)
 // Media time is quantized; concat boundaries can differ by floating point noise.
 // Search backwards so a shared boundary belongs to the following segment.
 return displayed.value?.segments.slice().reverse().find(s=>s.start!==null&&s.end!==null&&s.start<=t+0.000001&&t<=s.end+0.000001)
}
function openRevision(){if(!canRevise.value)return;pause();const segment=findCurrent();selected.value=segment?[segment.id]:[];revisionOpen.value=true;revisionMode.value='visual';instruction.value=''}
function seek(start:number|null){if(start===null)return;if(hasHtml.value){htmlTime.value=start;htmlPlayer.value?.seek(start)}else if(player.value){player.value.pause();player.value.currentTime=start}}
async function revise(){
 if(!canRevise.value||!displayed.value||!outline.value||!selected.value.length||!instruction.value.trim())return
 submitting.value=true;error.value=''
 try{await requireCredits();const value=await reviseVideo(id,displayed.value.id,outline.value.revision,selected.value,instruction.value.trim(),revisionMode.value);versions.value=[value,...versions.value];revisionOpen.value=false;notifyCreditsChanged();void refreshCredits();schedule()}
 catch(e){error.value=errorText(e)}finally{submitting.value=false}
}
async function exportMp4(){
 if(!displayed.value||submitting.value||active.value)return
 submitting.value=true;error.value=''
 try{const job=await exportVideo(id,displayed.value.id);displayed.value.export_job=job;displayed.value.export_status=job.status;schedule()}catch(e){error.value=errorText(e)}finally{submitting.value=false}
}
function versionLabel(v:VideoVersion){return '第 '+v.number+' 版 · '+(v.export_status==='running'||v.export_status==='pending'?'导出中':{queued:'排队中',running:'制作中',preview_ready:'可预览',succeeded:'已完成',failed:'失败'}[v.status])}
function formatTime(value:number|null){if(value===null)return '待生成';return Math.floor(value/60)+':'+String(Math.floor(value%60)).padStart(2,'0')}
function visibility(){if(document.hidden)pause();if(!document.hidden&&active.value)void load(false);else clearTimeout(timer)}
onMounted(()=>{void refreshCredits();void load();document.addEventListener('visibilitychange',visibility)})
onBeforeUnmount(()=>{disposed=true;pause();clearTimeout(timer);document.removeEventListener('visibilitychange',visibility)})
</script>
<template>
 <section class="preview-page" v-loading="loading">
  <div class="heading"><div><h1>视频预览</h1><p class="ev-muted">{{outline?.title}} · 先播放动画和配音，满意后导出 MP4；可按教学片段调整画面。</p></div><el-button @click="router.push({name:'project-outline',params:{id}})">返回大纲</el-button></div>
  <CreationSteps :active="2"/>
  <p class="ev-muted">请播放预览，核对画面、讲解与声音是否一致；大纲通过 AI 审核后，实际画面与配音仍需由教师检查，满意后再导出 MP4。</p>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/>
  <OutlineGenerationProgress v-if="activeJob" :key="activeJob.id" :stage="activeJob.stage" :created-at="activeJob.created_at" :connection-error="connectionError" :label="active?.export_status==='running'||active?.export_status==='pending'?'视频导出进度':'动画预览生成进度'"/>
  <el-alert v-if="latest?.status==='failed'" :title="latest.job.error_message??'视频生成失败，请重试'" type="error" :closable="false" show-icon/>
  <div v-if="confirmed&&!active" class="credit-notice"><span>每次成功生成扣 <strong>{{credits?.video_cost??10}} 积分</strong> · 失败不收费 · 导出不重复扣费</span><span v-if="credits">当前可用 {{credits.available}} 积分</span><span v-else-if="creditsError">{{creditsError}}</span><RouterLink to="/account/balance">查看余额 / 兑换积分</RouterLink></div>
  <div v-if="!active" class="generation-actions">
   <template v-if="confirmed"><el-button v-if="latest?.status==='failed'" type="primary" :loading="submitting" @click="generate(latest.id)">重试失败任务</el-button><el-button v-if="latest?.status==='failed'" :loading="submitting" @click="generate()">重新生成完整视频</el-button><el-button v-else type="primary" :loading="submitting" @click="generate()">{{versions.length?'重新生成视频':'生成视频'}}</el-button></template>
   <p v-else class="ev-muted">请先保存并确认大纲，再生成视频。</p>
  </div>
  <div v-if="versions.length" class="version-bar"><label for="video-version">视频版本</label><el-select id="video-version" :model-value="displayed?.id" aria-label="视频版本" @update:model-value="chooseVersion"><el-option v-for="v in versions" :key="v.id" :value="v.id" :label="versionLabel(v)"/></el-select><span v-if="displayed?.id!==latest?.id" class="ev-muted">当前查看历史版本</span></div>
  <template v-if="displayed&&(hasHtml||displayed.media_url)">
   <el-alert v-if="displayed.duration_notice" :title="displayed.duration_notice" type="warning" :closable="false" show-icon/>
   <el-alert v-if="displayed.export_status==='failed'" :title="displayed.export_job?.error_message??'MP4导出失败，动画预览已保留，可重试导出'" type="error" :closable="false" show-icon/>
   <div v-if="mediaFailed" class="media-error" role="alert">视频加载失败，请检查连接后重试。<el-button @click="reloadMedia">重新加载视频</el-button></div>
   <div class="preview-workspace"><div class="player-column"><div class="player-card"><HtmlAnimationPlayer v-if="hasHtml" ref="htmlPlayer" :key="displayed.id" :html-url="displayed.html_url" :audio-url="displayed.audio_url" :segments="displayed.segments" :duration="displayed.duration??0" :aspect-ratio="displayed.aspect_ratio?.replace(':',' / ')" @time="htmlTime=$event"/><video v-else ref="player" :key="displayed.id" :src="displayed.media_url??undefined" controls playsinline preload="metadata" aria-label="教学视频" @error="mediaFailed=true" @loadeddata="mediaFailed=false"><p>浏览器无法播放，请下载视频。</p></video></div>
   <div class="player-actions"><el-button :disabled="!canRevise" @click="openRevision">修改这一段</el-button><el-button v-if="hasHtml&&!displayed.media_url" type="primary" :disabled="!!active" :loading="submitting" @click="exportMp4">{{displayed.export_status==='failed'?'重试导出MP4':'满意，导出MP4'}}</el-button><a v-if="displayed.media_url" class="download-link" :href="displayed.media_url+'?download=1'" download>下载 MP4</a><span class="ev-muted">暂停视频后选择修改范围，可调整画面或重做配音；讲稿内容修改请返回大纲。</span></div>
   </div><section class="content-card chapters-card"><h2>教学内容</h2><ol class="teaching-list"><li v-for="s in displayed.segments" :key="s.id"><el-button text @click="seek(s.start)">{{formatTime(s.start)}}—{{formatTime(s.end)}} · {{s.title}}</el-button><p>{{s.narration}}</p></li></ol></section></div>
   <section v-if="revisionOpen" class="content-card revision-card"><h2>修改教学片段</h2><div class="revision-modes" role="radiogroup" aria-label="修改类型"><label><input v-model="revisionMode" type="radio" value="visual" :disabled="submitting"/>调整画面</label><label><input v-model="revisionMode" type="radio" value="voice" :disabled="submitting"/>重做配音</label></div><p v-if="revisionMode==='voice'" class="ev-muted">保留讲稿与画面设计，重新生成所选片段的配音并自动校时。未选片段保持原样。</p><p v-if="displayed.playback_mode==='whole_html'&&revisionMode==='visual'" class="ev-muted">为保持前后连贯，将按所选片段的要求重新生成整片画面，复用原配音。</p><p class="ev-muted">选择一个或多个完整教学片段。需要修改讲稿或知识点时，请返回大纲编辑并重新审核。</p><div class="segment-selection"><label v-for="s in displayed.segments" :key="s.id"><input v-model="selected" type="checkbox" :value="s.id" :aria-label="'修改片段 '+s.id" :disabled="submitting"/>{{formatTime(s.start)}}—{{formatTime(s.end)}} · {{s.title}}</label></div><label for="visual-instruction">{{revisionMode==='voice'?'配音表现要求':'画面修改要求'}}</label><el-input id="visual-instruction" v-model="instruction" aria-label="画面修改要求" type="textarea" :rows="3" maxlength="2000" :disabled="submitting" :placeholder="revisionMode==='voice'?'例如：语气自然清晰，重点稍作停顿。':'例如：把图像变化放慢一些，突出斜率的变化。'"/><p class="revision-cost">生成修改版成功后同样扣 {{credits?.video_cost??10}} 积分，失败不收费。</p><div class="revision-actions"><el-button type="primary" :loading="submitting" :disabled="!selected.length||!instruction.trim()||!canRevise" @click="revise">生成修改版</el-button><el-button :disabled="submitting" @click="revisionOpen=false">取消</el-button></div></section>
  </template>
  <el-empty v-else-if="!loading&&!active" description="动画预览将在这里展示，先检查配音和画面，再导出 MP4。"/>
 </section>
</template>
<style scoped>
.preview-page{width:100%;min-width:0}.heading{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:24px}h1{font:600 28px/1.4 var(--ev-font-display);margin:0}h2{font-size:16px;margin:0 0 16px}.el-alert{margin:16px 0}.generation-actions,.version-bar,.player-actions{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:20px 0}.version-bar .el-select{width:240px;max-width:100%}.version-bar label,.revision-card>label{font-weight:600}.player-card{border:1px solid var(--ev-color-border);border-radius:var(--ev-radius);overflow:hidden;background:var(--ev-color-surface-muted);display:grid;place-items:center}.player-card video{display:block;width:100%;max-height:70vh;min-height:220px}.download-link{display:inline-flex;align-items:center;min-height:44px;color:var(--ev-color-primary-dark);font-weight:600}.content-card{padding:24px;background:var(--ev-color-surface);border:1px solid var(--ev-color-border);border-radius:var(--ev-radius);margin:24px 0}.teaching-list{padding-left:24px;margin:0}.teaching-list li{padding:12px 0;border-bottom:1px solid var(--ev-color-border)}.teaching-list li:last-child{border:0}.teaching-list .el-button{white-space:normal;height:auto;min-height:40px;text-align:left}.teaching-list p{margin:4px 0;line-height:1.7;overflow-wrap:anywhere;color:var(--ev-color-muted)}.segment-selection{display:grid;gap:8px;margin:16px 0}.segment-selection label{display:flex;align-items:center;gap:12px;min-height:44px}.segment-selection input{width:18px;height:18px;accent-color:var(--ev-color-primary)}.revision-card .el-textarea{margin-top:12px}.revision-modes{display:flex;gap:24px;margin:16px 0}.revision-modes label{display:flex;align-items:center;gap:8px;min-height:44px}.revision-modes input{accent-color:var(--ev-color-primary)}.revision-actions{display:flex;gap:12px;margin-top:20px}@media(max-width:600px){.heading{align-items:flex-start}.content-card{padding:16px}.player-actions{align-items:flex-start}.player-actions>span{width:100%}.version-bar{gap:12px}}:focus-visible{outline:2px solid var(--ev-color-primary);outline-offset:3px}
.preview-workspace{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:24px;align-items:start}.player-column{min-width:0}.chapters-card{margin:0;border:0;border-left:1px solid var(--ev-color-border);border-radius:0;padding:0 0 0 22px;max-height:76vh;overflow-y:auto}.chapters-card h2{font-size:14px;font-weight:500;margin:0 0 12px}.teaching-list{padding:0;list-style:none}.teaching-list li:first-child{padding-top:0}.teaching-list .el-button{padding:6px 0;justify-content:flex-start;font-size:12px;max-width:100%}.teaching-list .el-button:deep(span){display:block;overflow-wrap:anywhere;line-height:1.8}.teaching-list p{font-size:12px;line-height:1.9}.revision-card{background:var(--ev-color-surface-muted)}@media(max-width:1100px){.preview-workspace{grid-template-columns:minmax(0,1fr) 220px;gap:20px}}@media(max-width:900px){.preview-workspace{grid-template-columns:1fr}.chapters-card{max-height:none;border-left:0;border-top:1px solid var(--ev-color-border);padding:20px 0 0;margin:0 0 24px}.teaching-list{display:grid;grid-template-columns:1fr 1fr;gap:0 22px}.teaching-list li:first-child{padding-top:12px}}@media(max-width:650px){.teaching-list{grid-template-columns:1fr}}
.credit-notice{display:flex;align-items:center;gap:10px 20px;flex-wrap:wrap;margin:20px 0 8px;padding:14px 17px;background:#f2f6ff;border:1px solid #dfe8fa;border-radius:9px;font-size:12px;line-height:1.8;color:#52698c}.credit-notice strong{font-weight:600;color:#2b4b7e}.credit-notice a{color:var(--ev-color-primary-dark);margin-left:auto;min-height:32px;display:inline-flex;align-items:center}.revision-cost{font-size:12px;color:var(--ev-color-muted);margin-top:16px}@media(max-width:650px){.credit-notice{gap:8px}.credit-notice>span:first-child{width:100%}.credit-notice a{margin-left:0}}
</style>
