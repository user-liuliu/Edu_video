<script setup lang="ts">
import {computed,nextTick,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {onBeforeRouteLeave,useRoute,useRouter} from 'vue-router'
import {ElMessage,ElMessageBox} from 'element-plus'
import PptTextEditor from '../../components/workbench/PptTextEditor.vue'
import CreationSteps from '../../components/workbench/CreationSteps.vue'
import OutlineGenerationProgress from '../../components/workbench/OutlineGenerationProgress.vue'
import {startPptJob,getPptVersion,pptExportUrl,pptPreviewUrl,pptPageApproved,type PptProject,type PptPage,type PptReviewIssue} from '../../api/presentations'
import {usePptProject} from '../../composables/usePptProject'
import {errorText} from '../../api/http'
import {getCreditBalance,notifyCreditsChanged,type CreditBalance} from '../../api/credits'
const route=useRoute(),router=useRouter(),{project:liveProject,error,loading,connectionError,load}=usePptProject()
const credits=ref<CreditBalance>(),creditsError=ref('')
let creditSequence=0,creditDisposed=false
async function refreshCredits(){const seq=++creditSequence;try{const value=await getCreditBalance();if(!creditDisposed&&seq===creditSequence){credits.value=value;creditsError.value=''}}catch{if(!creditDisposed&&seq===creditSequence){credits.value=undefined;creditsError.value='积分余额暂时无法读取'}}}
async function requireCredits(){const seq=++creditSequence,value=await getCreditBalance();if(!creditDisposed&&seq===creditSequence){credits.value=value;creditsError.value=''}const cost=value.ppt_cost??10;if(value.available<cost)throw new Error('积分不足，本次生成需要 '+cost+' 积分，当前可用 '+value.available+' 积分，请先兑换积分')}
onBeforeUnmount(()=>{creditDisposed=true})
const textEditing=ref(false),textDirty=ref(false),textSaving=ref(false)
const historical=ref<PptProject>(),selectedVersion=ref('current'),versionLoading=ref(false),versionError=ref('')
const project=computed(()=>historical.value??liveProject.value)
const versionNumber=computed(()=>historical.value?.revision)
let versionRequest=0
async function changeVersion(){
  const request=++versionRequest
  revisionOpen.value=false;selected.value=[];active.value=0;versionError.value=''
  if(selectedVersion.value==='current'){historical.value=undefined;versionLoading.value=false;return}
  if(!liveProject.value)return
  versionLoading.value=true
  try{const snapshot=await getPptVersion(liveProject.value.id,Number(selectedVersion.value));if(request===versionRequest)historical.value=snapshot}
  catch(e){if(request===versionRequest){versionError.value=errorText(e);selectedVersion.value=historical.value?String(historical.value.revision):'current'}}
  finally{if(request===versionRequest)versionLoading.value=false}
}
const selected=ref<string[]>([]),active=ref(0),instruction=ref(''),saving=ref(false),revisionOpen=ref(false),revisionPanel=ref<HTMLElement>(),editButton=ref<{ $el:HTMLButtonElement }>()
const jobActive=computed(()=>['pending','running'].includes(liveProject.value?.job?.status??''))
const busy=computed(()=>saving.value||jobActive.value||versionLoading.value||textEditing.value)
const outlineConfirmed=computed(()=>Boolean(project.value)&&project.value!.confirmed_revision===project.value!.revision)
const failedRender=computed(()=>project.value?.job?.kind==='render'&&project.value.job.status==='failed')
const hasPages=computed(()=>Boolean(project.value?.pages.length))
const statusPages=computed(()=>hasPages.value?project.value!.pages:project.value?.outline?.slides??[])
const current=computed(()=>project.value?.pages[active.value])
function pageApproved(page:PptPage){return pptPageApproved(page)}
function pageDelivered(page:PptPage){return page.delivery?.version==='ppt-delivery-1'}
const verifiedDelivery=computed(()=>hasPages.value&&project.value!.pages.some(pageDelivered)&&project.value!.pages.every(p=>pageDelivered(p)||pageApproved(p)))
const partialDelivery=computed(()=>!verifiedDelivery.value&&hasPages.value&&project.value?.rendered_revision===project.value?.revision&&approvedCount.value>0&&approvedCount.value<(project.value?.pages.length??0))
function pageVisible(page:PptPage){return partialDelivery.value?pageApproved(page):canPreview.value}
const canPreview=computed(()=>hasPages.value&&project.value!.pages.every(p=>pageDelivered(p)||!p.review||pageApproved(p)))
const approvedCount=computed(()=>project.value?.pages.filter(pageApproved).length??0)
const canExport=computed(()=>(canPreview.value||(partialDelivery.value&&approvedCount.value>0))&&(!busy.value||Boolean(historical.value)&&!versionLoading.value)&&project.value?.rendered_revision===project.value?.revision)
const missingPages=computed(()=>project.value?.pages.flatMap((p,i)=>pageApproved(p)?[]:[i+1]).join('、')??'')
const issueLabels:Record<PptReviewIssue['category'],string>={teaching:'教学一致性',readability:'文字可读性',visual:'优化建议',file:'文件可用性',generation:'页面制作异常',service:'模型服务异常'}
function reviewLabel(page:PptPage){
  if(pageDelivered(page))return '已生成'
  if(!hasPages.value)return busy.value?'等待生成与审核':'尚未生成与审核'
  switch(page.review?.status){case 'passed':return page.review.issues.length?'审核通过 · 有优化建议':'审核通过';case 'needs_attention':return page.review.issues.some(i=>['generation','service'].includes(i.category))?'生成异常，待补齐':'仍需检查';case 'pending':return '等待内容与可用性检查';default:return '尚无审核记录'}
}
function reviewType(page:PptPage){if(pageDelivered(page))return 'info';return page.review?.status==='passed'?'success':page.review?.status==='needs_attention'?'warning':'info'}
async function refresh(){await load(String(route.params.id))}
onMounted(()=>{void refresh();void refreshCredits()})
watch(()=>liveProject.value?.job?.status,(status,prior)=>{if(prior&&['pending','running'].includes(prior)&&status&&!['pending','running'].includes(status)){notifyCreditsChanged();void refreshCredits()}})
watch(()=>project.value?.revision,()=>{
  if(active.value>=statusPages.value.length)active.value=0
  selected.value=selected.value.filter(id=>project.value?.pages.some(p=>p.id===id))
})
async function revealRevision(){
  revisionOpen.value=true
  await nextTick()
  revisionPanel.value?.scrollIntoView?.({block:'nearest'})
  revisionPanel.value?.querySelector<HTMLTextAreaElement>('textarea')?.focus({preventScroll:true})
}
function openRevision(){
  if(!current.value||busy.value||historical.value)return
  selected.value=[current.value.id]
  instruction.value=''
  void revealRevision()
}
async function closeRevision(){
  revisionOpen.value=false
  await nextTick()
  editButton.value?.$el.focus()
}
function useSuggestions(){
  if(!current.value||busy.value||!current.value.review?.issues.length)return
  selected.value=[current.value.id]
  instruction.value=current.value.review.issues.map(i=>`${i.message}：${i.repair}`).join('\n').slice(0,4000)
  void revealRevision()
}
async function submit(kind:'render'|'revise'){
  if(!liveProject.value||busy.value||historical.value)return
  if(kind==='render'&&!outlineConfirmed.value){error.value='请先返回大纲页确认当前大纲';return}
  if(kind==='revise'&&(!selected.value.length||!instruction.value.trim()))return
  saving.value=true;error.value=''
  try{
    await requireCredits()
    const job=await startPptJob(liveProject.value,kind,kind==='revise'?{slide_ids:selected.value,instruction:instruction.value}:{})
    liveProject.value={...liveProject.value,job,status:'generating'}
    notifyCreditsChanged();void refreshCredits()
    await refresh()
  }catch(e){error.value=errorText(e)}finally{saving.value=false}
}

async function cancelTextEditing(){
 if(textSaving.value)return
 if(textDirty.value){try{await ElMessageBox.confirm('未保存的文字修改将丢失，确定取消？','取消编辑',{confirmButtonText:'放弃修改',cancelButtonText:'继续编辑',type:'warning'})}catch{return}}
 textEditing.value=false;textDirty.value=false
}
function savedText(p:PptProject){liveProject.value=p;textEditing.value=false;textDirty.value=false;ElMessage.success('文字修改已保存为新版本')}
onBeforeRouteLeave(async()=>{if(textSaving.value)return false;if(!textDirty.value)return true;try{await ElMessageBox.confirm('文字修改尚未保存，确定离开？','未保存的文字修改',{confirmButtonText:'离开',cancelButtonText:'继续编辑',type:'warning'});return true}catch{return false}})
</script>
<template>
<section v-loading="loading||versionLoading" class="ppt-workspace ppt-preview-page">
  <header class="ppt-heading">
    <div><h1>PPT 预览</h1><p class="ev-muted">{{project?.title}} · {{project?.template_name??'简洁教学 · 清蓝'}} · 16:9 · {{statusPages.length}} 页</p></div>
    <el-button v-if="project" :disabled="busy" @click="router.push({name:'ppt-outline',params:{id:project.id}})">返回大纲</el-button>
  </header>
  <CreationSteps mode="ppt" :active="2"/>
  <div v-if="liveProject&&!historical" class="ppt-credit-notice" role="note"><span>生成 PPT 或 AI 修改版，每次成功扣 <strong>{{credits?.ppt_cost??10}} 积分</strong> · 失败不收费 · 大纲、手动编辑和下载不扣费</span><span v-if="credits">当前可用 {{credits.available}} 积分</span><span v-else-if="creditsError">{{creditsError}}</span><RouterLink to="/account/balance">查看余额 / 兑换积分</RouterLink></div>
  <div v-if="liveProject?.versions?.length" class="ppt-version-bar">
    <label for="ppt-version-select">课件版本</label>
    <select id="ppt-version-select" v-model="selectedVersion" aria-label="课件版本" :disabled="textEditing" @change="changeVersion">
      <option value="current">当前版本</option>
      <option v-for="version in liveProject.versions" :key="version.revision" :value="String(version.revision)">历史版本 {{version.revision}} · {{version.page_count}} 页</option>
    </select>
    <span v-if="historical" class="ev-muted">正在查看历史版本 {{historical.revision}}，可预览和下载。</span>
  </div>
  <el-alert v-if="versionError" :title="versionError" type="error" :closable="false"/>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <div v-if="error" class="ppt-actions"><el-button :disabled="loading||saving" @click="refresh">重新加载</el-button></div>
  <div v-if="!historical&&jobActive&&project?.job" data-testid="review-progress">
    <OutlineGenerationProgress :key="project.job.id" :stage="project.job.stage" :created-at="project.job.created_at" :connection-error="connectionError" label="PPT 生成与审核进度"/>
    <p v-if="hasPages" class="ev-muted">当前预览与审核记录来自上一版，本次任务完成后自动更新。</p>
  </div>
  <p v-if="hasPages&&!canPreview&&!partialDelivery" class="ev-muted">正在等待审核通过后开放预览，未通过的页面不会作为成品提供下载。</p>
  <el-alert v-if="project?.job?.status==='failed'" :title="project.job.error_message??'生成或审核失败，请重试'" type="error" :closable="false"/>
  <p v-if="project?.job?.status==='failed'&&hasPages" class="ev-muted">本次任务未发布新页面，上一版课件与审核记录已保留。你可以重新选择页面并提交修改。</p>
  <div v-if="project&&!historical&&!busy&&outlineConfirmed&&!partialDelivery&&statusPages.length" class="ppt-generation-actions">
    <el-button :type="hasPages?undefined:'primary'" @click="submit('render')">{{hasPages?'重新生成整份 PPT':failedRender?'重新生成并审核':'开始生成 PPT'}}</el-button>
    <span class="ev-muted">{{hasPages?'当前展示已生成的课件，修改后可重新预览。':'大纲已确认，开始生成后会自动制作与审核。'}}</span>
  </div>
  <template v-if="statusPages.length">
    <section v-if="partialDelivery" class="ppt-review-summary" aria-label="部分课件恢复" data-testid="partial-recovery">
      <p>已完成 {{approvedCount}} / {{statusPages.length}} 页，部分版缺少原第 {{missingPages}} 页。通过的页面已保留，补齐时不会重复生成。</p>
      <el-button v-if="!historical" :disabled="busy" type="primary" @click="submit('render')">自动补齐未通过页面</el-button>
    </section>
    <div class="ppt-preview-layout">
      <div class="ppt-player-column">
        <div v-if="current&&project" class="ppt-slide-preview">
          <PptTextEditor v-if="textEditing&&liveProject" :key="liveProject.revision+current.id" :project-id="liveProject.id" :slide-id="current.id" :revision="liveProject.revision" @dirty="textDirty=$event" @saving="textSaving=$event" @saved="savedText" @cancel="cancelTextEditing"/>
          <img v-else-if="pageVisible(current)" :src="pptPreviewUrl(project,current.id,versionNumber)" :alt="`第 ${active+1} 页：${current.title}`"/>
          <div v-else class="ppt-preview-pending" role="status"><h2>{{reviewLabel(current)}}</h2><p>此页暂未开放成品预览，请查看下方审核详情与处理建议。</p></div>
          <div class="ppt-preview-pager"><p>{{active+1}} / {{project.pages.length}} · {{current.title}}</p><div class="ppt-actions"><el-button :disabled="textEditing||active===0" @click="active--">上一页</el-button><el-button :disabled="textEditing||active===project.pages.length-1" @click="active++">下一页</el-button></div></div>
          <div class="ppt-player-actions">
            <el-button v-if="!historical&&current.renderer==='ppt-master-6.7.0'&&!textEditing" :disabled="busy" @click="revisionOpen=false;textEditing=true">直接编辑文字</el-button>
            <el-button v-if="!historical&&!textEditing" ref="editButton" :disabled="busy" @click="openRevision">修改这一页</el-button>
            <a v-if="canExport&&!textEditing" class="ppt-download" :href="pptExportUrl(project.id,partialDelivery,versionNumber)">{{partialDelivery?'下载已通过部分 PPTX':'满意，下载 PPTX'}}</a>
            <p v-if="!historical&&!textEditing" class="ev-muted">基于当前页面修改指定内容与样式，其他页面保持原样；教学结构的调整请返回大纲。</p>
          </div>
          <details v-if="!canPreview" :key="current.id" class="ppt-page-review" data-testid="page-review" aria-label="当前页面审核" :open="!pageDelivered(current)&&Boolean(current.review&&(current.review.status!=='passed'||current.review.issues.length))">
            <summary>{{pageDelivered(current)?'制作记录':'本页审核'}}：{{!historical&&busy?'上一版 · ':''}}{{reviewLabel(current)}} · 查看详情</summary>
            <p v-if="pageDelivered(current)" class="ev-muted">系统已尝试质检、自动修改与版式整理，并验证完整课件文件。使用前请由教师确认内容。</p>
            <template v-else>
            <div class="ppt-review-heading"><h2>第 {{active+1}} 页{{!historical&&busy?' · 上一版审核':''}}</h2><el-tag :type="reviewType(current)">{{reviewLabel(current)}}</el-tag></div>
            <p v-if="current.review" class="ev-muted">已自动修复 {{current.review.repairs}} 次<span v-if="current.review.rebuilds">，简化重建 {{current.review.rebuilds}} 次</span>{{current.review.status==='needs_attention'?' · 已根据审核意见自动处理，可继续自动补齐。':''}}</p>
            <p v-else class="ev-muted">此页可继续预览与下载；重新生成后才会产生审核记录。</p>
            <p v-if="current.review?.status==='passed'&&current.review.issues.length" class="ev-muted">以下为优化建议，不影响预览和下载。</p>
            <ul v-if="current.review?.issues.length" class="ppt-review-issues"><li v-for="(issue,index) in current.review.issues" :key="index"><strong>{{issueLabels[issue.category]}}：{{issue.message}}</strong><p>修改建议：{{issue.repair}}</p></li></ul>
            <el-button v-if="!historical&&current.review?.issues.length" :disabled="busy" @click="useSuggestions">采用本页修改建议</el-button>
            </template>
          </details>
        </div>
        <div v-else class="ppt-preview-pending" role="status">
          <h2>{{busy?'正在制作与审核课件':!outlineConfirmed?'请先确认大纲':failedRender?'课件制作未完成':'大纲已确认，课件尚未生成'}}</h2>
          <p>{{busy?'任务完成后将在此显示整份课件和逐页审核结果。':!outlineConfirmed?'请先返回大纲页确认当前大纲，再开始制作课件。':failedRender?'可以重试制作与审核，或返回大纲调整内容。':'点击“开始生成 PPT”后，才会制作页面并进行自动审核。'}}</p>
          <p v-if="statusPages[active]" class="ev-muted">第 {{active+1}} 页 · {{statusPages[active]?.title}}</p>
        </div>
      </div>
      <aside class="ppt-contents" aria-label="课件页面" data-testid="page-status-list">
        <div class="ppt-contents-heading"><h2>课件内容</h2><span>共 {{statusPages.length}} 页</span></div>
        <div class="ppt-page-list">
          <button v-for="(slide,index) in statusPages" :key="slide.id" type="button" :disabled="textEditing" :class="{active:index===active}" :aria-label="`预览第 ${index+1} 页：${slide.title}`" :aria-pressed="index===active" :aria-describedby="canPreview?undefined:`ppt-page-status-${index}`" @click="active=index">
            <span class="ppt-page-number">{{index+1}}</span><span class="ppt-page-copy"><strong>第 {{index+1}} 页 · {{slide.title}}</strong><span class="ppt-page-excerpt">{{slide.content}}</span><el-tag v-if="!canPreview" :id="`ppt-page-status-${index}`" :type="hasPages?reviewType(slide):'info'" size="small" effect="plain">{{!historical&&busy&&hasPages?'上一版 · ':''}}{{reviewLabel(slide)}}</el-tag></span>
          </button>
        </div>
      </aside>
    </div>
    <section v-if="!historical&&hasPages&&revisionOpen" ref="revisionPanel" class="ppt-rewrite" aria-label="修改课件页面">
      <h2>修改课件页面</h2><p class="ev-muted">已选中当前页，也可以同时选择其他页面。将基于原页面直接修改，并自动核对修改结果。</p>
      <div class="ppt-revision-selection"><label v-for="(slide,index) in project!.pages" :key="slide.id"><input v-model="selected" type="checkbox" :value="slide.id" :disabled="busy" :aria-label="`选择第 ${index+1} 页`"/>第 {{index+1}} 页 · {{slide.title}}</label></div>
      <label for="ppt-page-instruction">已选择 {{selected.length}} 页 · 页面修改要求</label>
      <el-input id="ppt-page-instruction" v-model="instruction" aria-label="修改要求" type="textarea" :rows="3" :disabled="busy" maxlength="4000" placeholder="例如：精简文字，突出关键结论，增加课堂提问。"/>
      <div class="ppt-revision-actions"><el-button type="primary" :disabled="busy||!selected.length||!instruction.trim()" @click="submit('revise')">修改所选课件页面</el-button><el-button :disabled="busy" @click="closeRevision">取消</el-button></div>
    </section>
    <p v-if="hasPages" class="ev-muted ppt-preview-footer">下载后，文字与基础图形可在 PowerPoint / WPS 中继续编辑。</p>
  </template>
  <el-empty v-else-if="!loading&&!busy&&project" description="课件尚未生成，或大纲已更新"><el-button v-if="project" @click="router.push({name:'ppt-outline',params:{id:project.id}})">返回大纲生成</el-button></el-empty>
</section>
</template>
<style scoped src="../../styles/ppt-workspace.css"></style>
<style scoped src="../../styles/ppt-preview.css"></style>
