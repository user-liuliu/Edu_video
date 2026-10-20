<script setup lang="ts">
import {computed,onMounted,onBeforeUnmount,ref} from 'vue'
import {useRoute,useRouter,onBeforeRouteLeave} from 'vue-router'
import {ElMessageBox} from 'element-plus'
import {getOutline,saveOutline,submitOutlineJob,getJob,confirmOutline,type Outline,type Segment,type Job} from '../../api/outline'
import {errorText} from '../../api/http'
import {segmentReviewState} from '../../utils/outline-review'
import CreationSteps from '../../components/workbench/CreationSteps.vue'
import OutlineGenerationProgress from '../../components/workbench/OutlineGenerationProgress.vue'
import SegmentEditor from '../../components/workbench/SegmentEditor.vue'
import EvidencePanel from '../../components/workbench/EvidencePanel.vue'
const route=useRoute(),router=useRouter(),id=String(route.params.id)
const pollInterval=1000
const data=ref<Outline>(),segments=ref<Segment[]>([]),job=ref<Job>(),connectionError=ref(false),selected=ref<string[]>([]),instruction=ref(''),error=ref(''),message=ref(''),loading=ref(true),saving=ref(false),dirty=ref(false),evidenceId=ref<string|null>(null)
let timer:ReturnType<typeof setTimeout>|undefined,disposed=false
const processing=computed(()=>job.value&&['pending','running'].includes(job.value.status))

// Match the server's reviewed content fields; ordering alone does not invalidate review.
const unsavedSegmentIds=computed(()=>{
 const saved=new Map(data.value?.segments.map(segment=>[segment.id,segment]))
 const fields=['title','objective','narration','visuals','evidence_ids','content_kind'] as const
 return new Set(segments.value.filter(segment=>{
  const original=saved.get(segment.id)
  return !original||fields.some(field=>JSON.stringify(segment[field])!==JSON.stringify(original[field]))
 }).map(segment=>segment.id))
})
const reviewCounts=computed(()=>{
 const counts={pending:0,failed:0,passed:0}
 for(const segment of segments.value)counts[segmentReviewState(segment,unsavedSegmentIds.value.has(segment.id))]++
 return counts
})
const needsReview=computed(()=>reviewCounts.value.pending+reviewCounts.value.failed>0)
const needsSave=computed(()=>dirty.value||data.value?.needs_save!==false)
const reviewWarning=computed(()=>`存在未通过审核的片段：待审核 ${reviewCounts.value.pending} 段、审核未通过 ${reviewCounts.value.failed} 段。请完成审核后再确认大纲。`)
function apply(value:Outline){data.value=value;segments.value=structuredClone(value.segments);dirty.value=false}
async function load(){try{apply(await getOutline(id));if(data.value?.job_id)await poll(data.value.job_id)}catch(e){error.value=errorText(e)}finally{loading.value=false}}
async function poll(jobId:string){if(disposed)return;try{job.value=await getJob(jobId);connectionError.value=false;if(processing.value){schedule(jobId)}else if(job.value.status==='succeeded'){apply(await getOutline(id));if(job.value.kind!=='generate')message.value=needsReview.value?'审核已完成，仍存在待处理片段，请查看原因并修改或重试':'大纲已更新，全部片段已通过AI审核，请检查后确认'}else if(job.value.status==='failed'){error.value=job.value.error_message??'任务失败，请重试';apply(await getOutline(id))}}catch(e){if(processing.value){connectionError.value=true;schedule(jobId)}else error.value=errorText(e)}}
function schedule(jobId:string){clearTimeout(timer);if(!disposed&&!document.hidden)timer=setTimeout(()=>poll(jobId),pollInterval)}
function change(index:number,value:Segment){if(processing.value||saving.value)return;segments.value[index]=value;dirty.value=true}
function move(index:number,direction:number){if(processing.value||saving.value)return;const target=index+direction;if(target<0||target>=segments.value.length)return;const [item]=segments.value.splice(index,1);segments.value.splice(target,0,item!);dirty.value=true}
function remove(index:number){if(processing.value||saving.value)return;segments.value.splice(index,1);dirty.value=true}
function add(){if(processing.value||saving.value)return;segments.value.push({id:crypto.randomUUID(),position:segments.value.length,title:'新段落',objective:'',narration:'',visuals:[{kind:'文字卡',description:''}],evidence_ids:[],content_kind:'knowledge',review_notes:[],estimated_duration_seconds:1,content_revision:1,reviewed_revision:0,review_passed:null,review_issues:[]});dirty.value=true}
async function save(showSuccess=true):Promise<boolean>{
 if(!data.value||processing.value||saving.value)return false
 saving.value=true;error.value=''
 let goReview=false
 try{
  apply(await saveOutline(id,data.value.revision,segments.value))
  if(showSuccess){
   if(needsReview.value){
    try{
     await ElMessageBox.confirm('大纲已保存，但'+reviewWarning.value,'已保存，需完成审核',{confirmButtonText:'去审核',cancelButtonText:'继续编辑',type:'warning',closeOnClickModal:false})
     goReview=true
    }catch(action){if(action!=='cancel'&&action!=='close')throw action}
   }else await ElMessageBox.alert('大纲已保存','保存成功',{confirmButtonText:'知道了',type:'success'})
  }
 }catch(e){error.value=errorText(e);return false}finally{saving.value=false}
 if(goReview)await submit('review')
 return true
}
async function submit(operation:'generate'|'review'|'rewrite'){
 if(!data.value||processing.value||saving.value)return
 if(operation==='generate'){await router.push({name:'project-edit',params:{id}});return}
 if(operation==='rewrite'&&(!selected.value.length||!instruction.value.trim())){error.value='请选择需要改写的段落并填写改写要求';return}
 if(dirty.value&&!(await save(false)))return
 saving.value=true;error.value='';message.value=''
 try{
  job.value=await submitOutlineJob(id,operation,data.value.revision,{segment_ids:selected.value,instruction:instruction.value})
  connectionError.value=false;message.value='任务已提交，关闭页面后仍会继续处理';schedule(job.value.id)
 }catch(e){error.value=errorText(e)}finally{saving.value=false}
}
async function confirm(){
 if(!data.value||processing.value||saving.value)return
 error.value=''
 if(data.value.needs_regeneration){error.value='需求或素材已变化，请返回需求页重新生成';return}
 if(needsSave.value){error.value='请先保存大纲，再确认大纲';return}
 if(needsReview.value){error.value=reviewWarning.value;return}
 saving.value=true
 try{
  await ElMessageBox.confirm('当前已保存的大纲全部片段已通过AI审核，请确认你已检查讲稿、画面和审核提示。确认后可进入视频预览并开始制作。','确认大纲',{confirmButtonText:'确认大纲',cancelButtonText:'继续编辑',type:'warning'})
  apply(await confirmOutline(id,data.value.revision));message.value='大纲已确认';await router.push({name:'project-video',params:{id}})
 }catch(e){if(e!=='cancel'&&e!=='close')error.value=errorText(e)}finally{saving.value=false}
}
function visibility(){if(!document.hidden&&job.value&&processing.value)void poll(job.value.id);else clearTimeout(timer)}
function beforeUnload(e:BeforeUnloadEvent){if(dirty.value){e.preventDefault();e.returnValue=''}}
onMounted(()=>{void load();document.addEventListener('visibilitychange',visibility);window.addEventListener('beforeunload',beforeUnload)})
onBeforeUnmount(()=>{disposed=true;clearTimeout(timer);document.removeEventListener('visibilitychange',visibility);window.removeEventListener('beforeunload',beforeUnload)})
onBeforeRouteLeave(async()=>{if(!dirty.value)return true;try{await ElMessageBox.confirm('有未保存的大纲修改，确定离开吗？','离开页面',{confirmButtonText:'离开',cancelButtonText:'继续编辑'});return true}catch{return false}})
</script>
<template><section v-loading="loading" class="outline-page"><div class="heading"><div><h1>大纲草稿</h1><p class="ev-muted">按段检查教学内容、完整讲稿与画面说明，再确认大纲。AI审核针对大纲内容，生成后仍需预览核对画面与配音。</p></div><el-button v-if="!processing" data-testid="return-requirement" @click="router.push({name:'project-edit',params:{id}})">返回需求</el-button></div><CreationSteps :active="1"/><el-alert v-if="data?.material_warnings?.length" title="参考素材有部分内容未解析，请核对大纲" type="warning" :closable="false" show-icon><p v-for="(warning,index) in data.material_warnings" :key="index">{{warning.filename}} · {{warning.location}}：{{warning.message}}</p></el-alert><el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/><OutlineGenerationProgress v-if="job&&processing" :key="job.id" :stage="job.stage" :created-at="job.created_at" :connection-error="connectionError"/><el-alert v-if="data?.status==='outline_confirmed'" title="大纲已确认，可以进入视频预览开始制作。" type="success" :closable="false"/><el-alert v-if="data?.needs_regeneration" title="需求或素材已变化，需要重新生成大纲。当前显示的是保留的旧稿。" type="warning" :closable="false"/><p v-if="message" role="status">{{message}}</p><div v-if="segments.length" class="outline-toolbar"><span>{{segments.length}} 个段落 · 预计 {{segments.reduce((n,s)=>n+s.estimated_duration_seconds,0)}} 秒（按讲稿字数估算）<span v-if="needsSave"> · 请先保存大纲</span><span v-if="needsReview"> · 待审核 {{reviewCounts.pending}} 段 · 未通过 {{reviewCounts.failed}} 段</span></span><div><el-button data-testid="save-outline" :loading="saving" :disabled="processing" @click="save()">保存大纲</el-button><el-button :disabled="processing||saving||(!needsReview)" @click="submit('review')">审核待处理片段</el-button><el-button v-if="data?.status==='outline_confirmed'||data?.status==='completed'||data?.status==='video_failed'||data?.status==='video_generating'||data?.status==='preview_ready'||data?.status==='video_exporting'" type="primary" :disabled="saving||dirty" @click="router.push({name:'project-video',params:{id}})">进入视频预览</el-button><el-button v-else type="primary" :disabled="processing||saving" @click="confirm">确认大纲</el-button></div></div><SegmentEditor v-for="(segment,index) in segments" :key="segment.id" :segment="segment" :content-changed="unsavedSegmentIds.has(segment.id)" :index="index" :count="segments.length" :selected="selected.includes(segment.id)" :disabled="processing||saving" @change="value=>change(index,value)" @move="direction=>move(index,direction)" @remove="remove(index)" @select="value=>selected=value?[...selected,segment.id]:selected.filter(id=>id!==segment.id)" @evidence="value=>evidenceId=value"/><el-button v-if="segments.length" :disabled="processing||saving" @click="add">添加段落</el-button><div v-if="segments.length" class="rewrite-card"><h2>局部改写</h2><p class="ev-muted">已选择 {{selected.length}} 个段落，只改写勾选内容；提交前自动保存当前修改。</p><el-input v-model="instruction" type="textarea" :rows="2" maxlength="2000" aria-label="局部改写要求" placeholder="例如：简洁清晰，多用生活实例；保留公式与关键概念。" :disabled="processing||saving"/><div class="rewrite-actions"><el-button :disabled="processing||saving||!selected.length||!instruction.trim()" @click="submit('rewrite')">改写选中段落</el-button><el-button v-if="job?.status==='failed'" :disabled="saving" @click="submit(job.kind==='rewrite'?'rewrite':job.kind==='review'?'review':'generate')">重试失败任务</el-button></div></div><el-empty v-if="!loading&&!segments.length&&!processing" description="还没有大纲，可返回需求页开始生成"><el-button v-if="job?.status==='failed'" type="primary" @click="submit('generate')">重新生成大纲</el-button></el-empty><EvidencePanel :project-id="id" :evidence-id="evidenceId" @close="evidenceId=null"/></section></template>
<style scoped>.outline-page{width:100%;max-width:none}.heading{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:24px}h1{font:32px var(--ev-font-display);margin:0}h2{font-size:18px;margin:0}.outline-toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:14px;padding:20px 0}.outline-toolbar>span{font-size:13px;color:var(--ev-color-muted)}.outline-toolbar>div{display:flex;gap:8px;flex-wrap:wrap}.outline-toolbar .el-button{margin:0}.el-alert{margin:15px 0}.rewrite-card{border:1px solid var(--ev-color-border);border-radius:var(--ev-radius);padding:22px;background:var(--ev-color-surface);margin:20px 0}.rewrite-actions{display:flex;gap:10px;margin-top:16px}@media(max-width:600px){.heading{align-items:flex-start}.heading .el-button{padding:10px}.outline-toolbar>div{width:100%}.rewrite-card{padding:16px}}</style>
