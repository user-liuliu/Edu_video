<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getFormConfig, getProject, saveProject, type FormConfig, type Project, type PublicField } from '../../api/projects'
import { uploadMaterial } from '../../api/materials'
import { errorText } from '../../api/http'
import CreationSteps from '../../components/workbench/CreationSteps.vue'
import MaterialUpload from '../../components/workbench/MaterialUpload.vue'
import {submitOutlineJob} from '../../api/outline'
import {clearPendingFiles, clearVideoDraft, readPendingFiles, writePendingFiles} from '../../utils/video-draft-cache'
import {addPendingOutlineNotification} from '../../utils/outline-job-notification'
const route=useRoute(),router=useRouter()
const config=ref<FormConfig>(), project=ref<Project>(), prompt=ref(''), title=ref(''), values=ref<Record<string,unknown>>({}), pendingFiles=ref<File[]>([]), loading=ref(true), saving=ref(false), error=ref(''), dirty=ref(false), materialsRefreshToken=ref(0)
const cacheKey=computed(()=>`project:${String(route.params.id??'new')}`)
const hasOutline=computed(()=>['outline_ready','outline_confirmed'].includes(project.value?.status??''))
const fields=computed(()=>config.value?.fields.filter(f=>!['prompt','materials'].includes(f.key))??[])
function options(f:PublicField){return f.options.filter(o=>!o.subjects?.length||o.subjects.includes(String(values.value.subject)))}
watch(()=>values.value.subject,(subject,previous)=>{if(loading.value||previous===undefined)return;const edition=config.value?.fields.find(f=>f.key==='textbook_edition');if(edition)values.value.textbook_edition=edition.default_by_subject[String(subject)]??edition.default})
watch([prompt,title,values],()=>{if(!loading.value)dirty.value=true},{deep:true})
function isDocumentReload(){const entry=performance.getEntriesByType?.('navigation')[0] as PerformanceNavigationTiming|undefined;return entry?.type==='reload'}
async function load(){loading.value=true;try{if(!route.params.id&&isDocumentReload()){clearVideoDraft(cacheKey.value);await clearPendingFiles(cacheKey.value)}config.value=await getFormConfig();values.value=Object.fromEntries(config.value.fields.map(f=>[f.key,f.default]));if(route.params.id){project.value=await getProject(String(route.params.id));prompt.value=project.value.prompt;title.value=project.value.title;Object.assign(values.value,project.value.form_values)}pendingFiles.value=await readPendingFiles(cacheKey.value)}catch(e){error.value=errorText(e)}finally{loading.value=false}}
async function uploadPendingMaterials(){if(!project.value)return;for(const file of [...pendingFiles.value]){await uploadMaterial(project.value.id,file,true);pendingFiles.value=pendingFiles.value.filter(item=>item!==file);await writePendingFiles(cacheKey.value,pendingFiles.value)}await refreshProject();materialsRefreshToken.value+=1}
async function save(showSuccess=true){if(saving.value)return;if(project.value?.status==='outlining'){error.value='项目正在处理中，请先等待任务完成';return;}title.value=title.value.trim();if(!title.value){error.value='请填写项目名称';return}if(project.value&&['outline_ready','outline_confirmed','failed'].includes(project.value.status)&&dirty.value){try{await ElMessageBox.confirm('修改需求或科目、年级、教材、时长、风格、联网方式后需要重新生成大纲；原大纲会保留。尺寸和音色调整不会重写讲稿。','保存需求修改',{confirmButtonText:'保存修改',cancelButtonText:'继续编辑'});}catch{return;}}if(!prompt.value.trim()){error.value='请填写想讲什么';return}saving.value=true;error.value='';try{project.value=await saveProject({prompt:prompt.value,title:title.value,form_values:values.value,form_version:config.value?.form_version,revision:project.value?.revision},project.value?.id);await uploadPendingMaterials();dirty.value=false;if(showSuccess)ElMessage.success('已保存为草稿')}catch(e){error.value=errorText(e)}finally{saving.value=false}}
async function refreshProject(){if(project.value)project.value=await getProject(project.value.id)}
async function generate(){if(!config.value?.system_available||saving.value)return;if(hasOutline.value){try{await ElMessageBox.confirm('是否重新生成大纲','重新生成大纲',{confirmButtonText:'重新生成大纲',cancelButtonText:'取消',type:'warning'})}catch{return}}if(dirty.value||!project.value||pendingFiles.value.length)await save(false);if(error.value||dirty.value||!project.value)return;saving.value=true;error.value='';try{const job=await submitOutlineJob(project.value.id,'generate',project.value.revision,{form_version:config.value.form_version});addPendingOutlineNotification({jobId:job.id,projectId:project.value.id});await router.push({name:'project-outline',params:{id:project.value.id}})}catch(e){error.value=errorText(e)}finally{saving.value=false}}
onMounted(()=>{void load()})
onBeforeUnmount(()=>{void writePendingFiles(cacheKey.value,pendingFiles.value)})
</script>
<template>
<section v-loading="loading" class="create-page" data-testid="wide-workspace"><h1>视频制作</h1><p class="intro">从一个教学想法开始，先整理需求，再生成分段大纲。</p><CreationSteps :active="0"/>
<el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/>
<el-alert v-if="config&&!config.system_available" title="系统暂不可用，请联系管理员。你仍可以保存草稿。" type="warning" :closable="false"/>
<el-alert v-if="project?.needs_regeneration" title="需求或素材已变化，旧大纲已保留，请重新生成后再确认。" type="warning" :closable="false"/>
<el-form v-if="config" :disabled="saving" label-position="top" class="creation-form" @submit.prevent="save()">
<el-form-item label="项目名称" required><el-input v-model="title" data-testid="project-title" maxlength="200" placeholder="请输入项目名称"/></el-form-item>
<el-form-item :label="config.fields.find(f=>f.key==='prompt')?.label??'想讲什么'" required><el-input v-model="prompt" type="textarea" :rows="5" maxlength="20000" show-word-limit placeholder="例如：给初三学生讲解二次函数，用投篮的例子帮助理解抛物线。"/></el-form-item>
<MaterialUpload v-if="config.fields.some(f=>f.key==='materials')" :project-id="project?.id" :pending-files="pendingFiles" :saving="saving" :refresh-token="materialsRefreshToken" @pending-change="files=>{pendingFiles=files;void writePendingFiles(cacheKey,files)}" @changed="refreshProject"/>
<div class="parameter-grid"><el-form-item v-for="f in fields" :key="f.key" :label="f.label"><el-switch v-if="f.key==='web_search'" :model-value="Boolean(values[f.key])" :aria-label="f.label" @update:model-value="(v: unknown)=>values[f.key]=v"/><el-select v-else :model-value="String(values[f.key]??'')" :aria-label="f.label" @update:model-value="(v: unknown)=>values[f.key]=v"><el-option v-for="o in options(f)" :key="o.value" :value="o.value" :label="o.label"/></el-select><el-input-number v-if="f.key==='duration'&&values.duration==='custom'" v-model="values.custom_duration_minutes as number" :min="0.1" :max="60" :precision="1" aria-label="自定义分钟数"/></el-form-item></div>
<p class="ev-muted">关闭联网搜索后，仅使用上传素材与模型知识；无可靠依据的内容会标明“未核实出处”。</p>
<div class="actions"><el-button data-testid="save-draft" :loading="saving" @click="save()">保存草稿</el-button><el-button type="primary" :disabled="!config.system_available||saving" @click="generate">{{hasOutline?'重新生成大纲':'生成大纲'}}</el-button><el-button v-if="project&&project.status!=='draft'" @click="router.push({name:'project-outline',params:{id:project.id}})">查看大纲与任务</el-button></div>
</el-form></section>
</template>
<style scoped>.create-page{width:100%;max-width:none}h1{font:32px var(--ev-font-display);margin:0}.intro{color:var(--ev-color-muted);margin:10px 0 26px}.creation-form{width:100%;background:var(--ev-color-surface);border:1px solid var(--ev-color-border);border-radius:var(--ev-radius);padding:26px;margin-top:18px}.parameter-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0 20px}.material-area{border:1px dashed var(--ev-color-border);border-radius:var(--ev-radius);padding:18px;margin:0 0 22px}.actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:10px;margin-top:24px;padding-top:20px;border-top:1px solid var(--ev-color-border)}.actions .el-button{margin-left:0}.el-alert{margin-bottom:12px}@media(max-width:960px){.parameter-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:720px){.parameter-grid{grid-template-columns:1fr 1fr}.creation-form{padding:18px}.actions{justify-content:flex-start}}@media(max-width:480px){.parameter-grid{grid-template-columns:1fr}}</style>
