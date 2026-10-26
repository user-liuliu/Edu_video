<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue'
import {onBeforeRouteLeave,useRoute,useRouter} from 'vue-router'
import {ElMessageBox} from 'element-plus'
import CreationSteps from '../../components/workbench/CreationSteps.vue'
import OutlineGenerationProgress from '../../components/workbench/OutlineGenerationProgress.vue'
import {getPptConfig,savePptOutline,confirmPptOutline,startPptJob,type PptSlide} from '../../api/presentations'
import {usePptProject} from '../../composables/usePptProject'
import {errorText} from '../../api/http'
const route=useRoute(),router=useRouter(),{project,error,loading,connectionError,load}=usePptProject()
const slides=ref<PptSlide[]>([]),selected=ref<string[]>([]),instruction=ref(''),layouts=ref<Record<string,string>>({}),saving=ref(false),reviewAvailable=ref(true),baseline=ref(''),reviewedBefore=ref(false)
const dirty=computed(()=>JSON.stringify(slides.value)!==baseline.value)
const knowledgeChecked=computed(()=>!dirty.value&&project.value?.outline?.review?.status==='passed')
const outlineConfirmed=computed(()=>Boolean(project.value)&&!dirty.value&&project.value?.confirmed_revision===project.value?.revision)
const busy=computed(()=>saving.value||['pending','running'].includes(project.value?.job?.status??''))
watch(()=>project.value?.revision,()=>{if(!project.value)return;if(project.value.outline?.review)reviewedBefore.value=true;slides.value=JSON.parse(JSON.stringify(project.value.outline?.slides??[]));baseline.value=JSON.stringify(slides.value);selected.value=selected.value.filter(id=>slides.value.some(s=>s.id===id))})
async function refresh(){await load(String(route.params.id))}
onMounted(async()=>{try{const config=await getPptConfig();layouts.value=config.layouts;reviewAvailable.value=config.review_available!==false}catch(e){error.value=errorText(e)}await refresh()})
async function save(){if(!project.value||busy.value)return false;saving.value=true;error.value='';try{project.value=await savePptOutline(project.value,slides.value);return true}catch(e){error.value=errorText(e);return false}finally{saving.value=false}}
function add(){if(slides.value.length<40)slides.value.push({id:crypto.randomUUID(),layout:'image-text',title:'新页面',content:'请填写此页的教学内容。',slots:{}})}
function remove(index:number){const old=slides.value.splice(index,1)[0];selected.value=selected.value.filter(id=>id!==old?.id)}
function move(index:number,direction:number){const to=index+direction;if(to<0||to>=slides.value.length)return;const a=slides.value.splice(index,1)[0];if(a)slides.value.splice(to,0,a)}
async function submit(kind:'rewrite'|'outline'|'check'){if(!project.value||busy.value||(kind==='check'&&knowledgeChecked.value))return;if(dirty.value&&!await save())return;if(kind==='rewrite'&&(!selected.value.length||!instruction.value.trim())){error.value='请选择页面并填写修改要求';return}saving.value=true;error.value='';try{await startPptJob(project.value,kind,kind==='rewrite'?{slide_ids:selected.value,instruction:instruction.value}:{});await refresh()}catch(e){error.value=errorText(e)}finally{saving.value=false}}
async function confirm(){
 if(!project.value||busy.value||!knowledgeChecked.value)return
 saving.value=true;error.value=''
 try{
  await ElMessageBox.confirm('请确认你已检查逐页教学内容、知识点和公式。确认后进入 PPT 预览，点击“开始生成 PPT”后才会制作课件。','确认大纲',{confirmButtonText:'确认大纲',cancelButtonText:'继续编辑',type:'warning',closeOnClickModal:false})
  project.value=await confirmPptOutline(project.value)
  await router.push({name:'ppt-preview',params:{id:project.value.id}})
 }catch(e){if(e!=='cancel'&&e!=='close')error.value=errorText(e)}finally{saving.value=false}
}
watch(()=>project.value?.job,async job=>{if(job&&['render','revise'].includes(job.kind)&&['pending','running'].includes(job.status)&&project.value)await router.replace({name:'ppt-preview',params:{id:project.value.id}})})
onBeforeRouteLeave(async()=>{if(!dirty.value)return true;try{await ElMessageBox.confirm('大纲尚未保存，确定离开？','未保存的大纲',{confirmButtonText:'离开',cancelButtonText:'继续编辑'});return true}catch{return false}})
</script>
<template><section v-loading="loading" class="ppt-workspace">
<header class="ppt-heading"><div><h1>大纲草稿</h1><p class="ev-muted">{{project?.title}} · 按页检查教学内容、知识点与公式，再确认大纲。确认后可进入 PPT 预览并开始制作。</p></div><el-button v-if="project" @click="router.push({name:'ppt-edit',params:{id:project.id}})">返回需求</el-button></header>
<CreationSteps mode="ppt" :active="1"/>
<el-alert v-if="outlineConfirmed" title="大纲已确认，可以进入 PPT 预览开始制作。" type="success" :closable="false"/>
<el-alert v-if="!reviewAvailable" title="内部质检服务暂不可用，仍可制作课件；系统会采用简洁版式兜底，使用前请由教师确认内容。" type="warning" :closable="false"/>
<el-alert v-if="error" :title="error" type="error" :closable="false"/>
<OutlineGenerationProgress v-if="project?.job&&['pending','running'].includes(project.job.status)" :key="project.job.id" :stage="project.job.stage" :created-at="project.job.created_at" :connection-error="connectionError" label="PPT 大纲生成进度"/>
<el-alert v-if="project?.job?.status==='failed'" :title="project.job.error_message??'生成失败，请重试'" type="error" :closable="false"/>
<div v-if="project?.warnings.length" class="ppt-warnings"><p v-for="(w,i) in project.warnings" :key="i">{{w.filename}} {{w.location}} {{w.message}}</p></div>
<section v-if="slides.length" class="ppt-warnings" data-testid="knowledge-review" aria-label="大纲知识核查">
<h2>知识点与公式核查</h2>
<p>{{dirty?'大纲已修改，请重新审查后确认大纲，审查时会自动保存修改。':knowledgeChecked?'已审查，请确认大纲后进入 PPT 预览；修改大纲后需要重新审查。':'请先核查知识点与公式，再确认大纲。'}}</p>
<p>只检查知识点、公式、计算、例题答案和必要条件，不审核配图或美观。</p>
<template v-if="!dirty&&project?.outline?.review">
<div v-for="(change,index) in project.outline.review.changes" :key="index"><strong>{{change.message}}</strong><p v-if="change.title_before!==change.title_after">标题：{{change.title_before}} → {{change.title_after}}</p><p>修正前：{{change.before}}</p><p>修正后：{{change.after}}</p></div>
<p v-for="(issue,index) in project.outline.review.issues" :key="index">{{issue.message}}；建议：{{issue.repair}}</p>
</template>
</section>
<div v-if="slides.length" class="ppt-actions" role="group" aria-label="大纲操作"><span>{{slides.length}} 页{{dirty?' · 有未保存修改':''}}</span><el-button :disabled="busy||!dirty" @click="save">保存大纲</el-button><el-button data-testid="review-outline" :disabled="busy||knowledgeChecked" @click="submit('check')">{{knowledgeChecked?'已审查':dirty||reviewedBefore?'重新审查':'核查知识点和公式'}}</el-button><el-button v-if="outlineConfirmed" type="primary" :disabled="busy" @click="router.push({name:'ppt-preview',params:{id:project!.id}})">进入 PPT 预览</el-button><el-button v-else type="primary" :disabled="busy||!knowledgeChecked" @click="confirm">确认大纲</el-button></div>
<div class="outline-pages"><article v-for="(slide,index) in slides" :key="slide.id" class="outline-page"><div class="page-controls"><label><input v-model="selected" type="checkbox" :value="slide.id" :aria-label="`选择第 ${index+1} 页`" :disabled="busy"/>第 {{index+1}} 页</label><div><el-button :disabled="busy||index===0" :aria-label="`上移第 ${index+1} 页`" @click="move(index,-1)">上移</el-button><el-button :disabled="busy||index===slides.length-1" :aria-label="`下移第 ${index+1} 页`" @click="move(index,1)">下移</el-button><el-button text type="danger" :disabled="busy||slides.length===1" @click="remove(index)">删除</el-button></div></div><el-form label-position="top" :disabled="busy"><div class="outline-fields"><el-form-item label="页面标题"><el-input v-model="slide.title" maxlength="80" :aria-label="`第 ${index+1} 页标题`"/></el-form-item><el-form-item label="版式"><el-select v-model="slide.layout" :aria-label="`第 ${index+1} 页版式`"><el-option v-for="(name,id) in layouts" :key="id" :label="name" :value="id"/></el-select></el-form-item></div><el-form-item label="本页内容"><el-input v-model="slide.content" type="textarea" :rows="4" maxlength="3000" show-word-limit :aria-label="`第 ${index+1} 页内容`"/></el-form-item></el-form></article></div>
<div v-if="slides.length" class="ppt-actions"><el-button :disabled="busy||slides.length>=40" @click="add">添加页面</el-button></div>
<section v-if="slides.length" class="ppt-rewrite" aria-label="选页修改"><label for="ppt-outline-instruction">已选择 {{selected.length}} 页 · 描述你想怎样调整</label><el-input id="ppt-outline-instruction" v-model="instruction" aria-label="修改要求" type="textarea" :rows="2" maxlength="4000" :disabled="busy" placeholder="例如：增加生活实例，让内容更适合初中生。"/><el-button data-testid="rewrite-pages" type="primary" :disabled="busy||!selected.length||!instruction.trim()" @click="submit('rewrite')">修改所选页面大纲</el-button></section>
<el-empty v-if="!loading&&!slides.length&&!busy" description="尚未生成大纲"><el-button v-if="project" type="primary" @click="submit('outline')">生成大纲</el-button></el-empty>
</section></template>
<style scoped src="../../styles/ppt-workspace.css"></style>
