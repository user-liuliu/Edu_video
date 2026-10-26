<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getFormConfig, getProject, saveProject, type FormConfig, type Project, type PublicField } from '../../api/projects'
import { uploadMaterial } from '../../api/materials'
import { errorText } from '../../api/http'
import AppIcon from '../../components/AppIcon.vue'
import CreationMode from '../../components/workbench/CreationMode.vue'
import {rememberCreation,restoreCreation,creationEpoch} from '../../utils/creation-memory'
import CreationSteps from '../../components/workbench/CreationSteps.vue'
import MaterialUpload from '../../components/workbench/MaterialUpload.vue'
import {submitOutlineJob} from '../../api/outline'
import {clearPendingFiles, clearVideoDraft} from '../../utils/video-draft-cache'
import {addPendingOutlineNotification} from '../../utils/outline-job-notification'
const route=useRoute(),router=useRouter()
const ownerEpoch=creationEpoch()
const statePath=route.fullPath, projectId=route.params.id ? String(route.params.id) : undefined
const config=ref<FormConfig>(), project=ref<Project>(), prompt=ref(''), title=ref(''), values=ref<Record<string,unknown>>({}), pendingFiles=ref<File[]>([]), loading=ref(true), saving=ref(false), error=ref(''), dirty=ref(false), materialsRefreshToken=ref(0)
const cacheKey=computed(()=>`project:${String(route.params.id??'new')}`)
const hasOutline=computed(()=>['outline_ready','outline_confirmed'].includes(project.value?.status??''))
const fields=computed(()=>config.value?.fields.filter(f=>!['prompt','materials'].includes(f.key))??[])
const settingsFields=computed(()=>fields.value.filter(f=>f.key!=='web_search'))
const searchField=computed(()=>fields.value.find(f=>f.key==='web_search'))
function options(f:PublicField){return f.options.filter(o=>!o.subjects?.length||o.subjects.includes(String(values.value.subject)))}
watch(()=>values.value.subject,(subject,previous)=>{if(loading.value||previous===undefined)return;const edition=config.value?.fields.find(f=>f.key==='textbook_edition');if(edition)values.value.textbook_edition=edition.default_by_subject[String(subject)]??edition.default})
watch([prompt,title,values],()=>{if(!loading.value)dirty.value=true},{deep:true})
function isDocumentReload(){const entry=performance.getEntriesByType?.('navigation')[0] as PerformanceNavigationTiming|undefined;return entry?.type==='reload'}
async function load(){loading.value=true;error.value='';try{if(!route.params.id&&isDocumentReload()){clearVideoDraft(cacheKey.value);await clearPendingFiles(cacheKey.value)}const loaded=await getFormConfig();config.value={...loaded,fields:loaded.fields.filter(f=>String(f.key)!=='style')};values.value=Object.fromEntries(config.value.fields.map(f=>[f.key,f.default]));if(projectId){project.value=await getProject(projectId);prompt.value=project.value.prompt;title.value=project.value.title;Object.assign(values.value,project.value.form_values);delete values.value.style}const cached=restoreCreation('video',statePath);if(cached){title.value=String(cached.title);prompt.value=String(cached.prompt);values.value=cached.values as Record<string,unknown>;pendingFiles.value=(cached.files as File[])??pendingFiles.value;dirty.value=true}}catch(e){error.value=errorText(e)}finally{await nextTick();loading.value=false}}
async function uploadPendingMaterials(){if(!project.value)return;for(const file of [...pendingFiles.value]){await uploadMaterial(project.value.id,file,true);pendingFiles.value=pendingFiles.value.filter(item=>item!==file)}await refreshProject();materialsRefreshToken.value+=1}
async function save(showSuccess=true){if(saving.value)return;if(project.value?.status==='outlining'){error.value='项目正在处理中，请先等待任务完成';return;}title.value=title.value.trim();if(!title.value){error.value='请填写项目名称';return}if(project.value&&['outline_ready','outline_confirmed','failed'].includes(project.value.status)&&dirty.value){try{await ElMessageBox.confirm('修改需求或科目、年级、教材、时长、联网方式后需要重新生成大纲；原大纲会保留。尺寸和音色调整不会重写讲稿。','保存需求修改',{confirmButtonText:'保存修改',cancelButtonText:'继续编辑'});}catch{return;}}if(!prompt.value.trim()){error.value='请填写想讲什么';return}saving.value=true;error.value='';try{project.value=await saveProject({prompt:prompt.value,title:title.value,form_values:values.value,form_version:config.value?.form_version,revision:project.value?.revision},project.value?.id);await uploadPendingMaterials();dirty.value=false;if(showSuccess)ElMessage.success('已保存为草稿')}catch(e){error.value=errorText(e)}finally{saving.value=false}}
async function refreshProject(){if(project.value)project.value=await getProject(project.value.id)}
async function generate(){if(!config.value?.system_available||saving.value)return;if(hasOutline.value){try{await ElMessageBox.confirm('是否重新生成大纲','重新生成大纲',{confirmButtonText:'重新生成大纲',cancelButtonText:'取消',type:'warning'})}catch{return}}if(dirty.value||!project.value||pendingFiles.value.length)await save(false);if(error.value||dirty.value||!project.value)return;saving.value=true;error.value='';try{const job=await submitOutlineJob(project.value.id,'generate',project.value.revision,{form_version:config.value.form_version});addPendingOutlineNotification({jobId:job.id,projectId:project.value.id});await router.push({name:'project-outline',params:{id:project.value.id}})}catch(e){error.value=errorText(e)}finally{saving.value=false}}
function remember(){if(loading.value||!config.value)return;rememberCreation('video',statePath,{title:title.value,prompt:prompt.value,values:{...values.value},files:[...pendingFiles.value]},ownerEpoch)}
onMounted(()=>{void load()})

</script>
<template>
<section v-loading="loading&&!!config" class="create-page" data-testid="wide-workspace">
  <h1 class="sr-only">视频制作</h1>
  <div class="creation-welcome" aria-hidden="true">今天<span>讲</span>点啥？</div>
  <CreationMode mode="video" :disabled="saving" @switch="remember"/>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/>
  <el-alert v-if="config&&!config.system_available" title="系统暂不可用，请联系管理员。你仍可以保存草稿。" type="warning" :closable="false"/>
  <el-alert v-if="project?.needs_regeneration" title="需求或素材已变化，旧大纲已保留，请重新生成后再确认。" type="warning" :closable="false"/>
  <div v-if="loading&&!config" class="creation-loading creation-composer" role="status" aria-live="polite" aria-busy="true">
    <p>正在加载制作设置，请稍候…</p>
    <el-skeleton :rows="6" aria-hidden="true"/>
  </div>
  <div v-else-if="!config" class="creation-load-error creation-composer">
    <p>制作设置加载失败，请重试。</p>
    <el-button data-testid="retry-creation-load" type="primary" @click="load">重新加载</el-button>
  </div>
  <el-form v-if="config" :disabled="loading||saving" label-position="top" class="creation-form creation-composer" @submit.prevent="save()">
    <div class="composer-input">
      <el-form-item label="项目名称" required class="project-line"><el-input v-model="title" data-testid="project-title" maxlength="200" placeholder="请输入项目名称"/></el-form-item>
      <el-form-item :label="config.fields.find(f=>f.key==='prompt')?.label??'想讲什么'" required class="prompt-field"><el-input v-model="prompt" type="textarea" :rows="3" maxlength="20000" show-word-limit placeholder="例如：给初三学生讲解二次函数，用投篮的例子帮助理解抛物线。"/></el-form-item>
      <MaterialUpload compact v-if="config.fields.some(f=>f.key==='materials')" :project-id="project?.id" :pending-files="pendingFiles" :saving="saving" :refresh-token="materialsRefreshToken" @pending-change="files=>{pendingFiles=files}" @changed="refreshProject"/>
      <div class="composer-toolbar">
        <div v-if="searchField" class="composer-search"><AppIcon name="globe"/><span>{{searchField.label}}</span><el-switch :model-value="Boolean(values.web_search)" :aria-label="searchField.label" @update:model-value="(v: unknown)=>values.web_search=v"/></div>
        <div class="actions"><el-button data-testid="save-draft" :loading="saving" @click="save()"><AppIcon name="save"/>保存草稿</el-button><el-button type="primary" :disabled="!config.system_available||saving" @click="generate">{{hasOutline?'重新生成大纲':'生成大纲'}}<AppIcon name="arrow"/></el-button><el-button v-if="project&&project.status!=='draft'" @click="router.push({name:'project-outline',params:{id:project.id}})">查看大纲与任务</el-button></div>
      </div>
    </div>
    <section v-if="settingsFields.length" class="creation-settings" aria-label="视频设置"><h2><AppIcon name="memory"/>视频设置</h2><div class="parameter-grid creation-settings-grid"><el-form-item v-for="f in settingsFields" :key="f.key" :label="f.label"><template #label><AppIcon :name="f.key"/><span>{{f.label}}</span></template><el-select :model-value="String(values[f.key]??'')" :aria-label="f.label" @update:model-value="(v: unknown)=>values[f.key]=v"><el-option v-for="o in options(f)" :key="o.value" :value="o.value" :label="o.label"/></el-select><el-input-number v-if="f.key==='duration'&&values.duration==='custom'" v-model="values.custom_duration_minutes as number" :min="0.1" :max="60" :precision="1" aria-label="自定义分钟数"/></el-form-item></div></section>
  </el-form>
  <div class="creation-notes"><span>关闭联网时仅参考素材与模型知识。</span><span v-if="values.voice==='system:zh-CN'" role="status">系统配音离线生成，不调用配音模型。</span><el-popover placement="top" :width=320 trigger="click"><template #reference><button type="button" class="creation-help">使用说明<AppIcon name="info"/></button></template><p>关闭联网搜索后，仅使用上传素材与模型知识；无可靠依据的内容会标明“未核实出处”。</p><p v-if="values.voice==='system:zh-CN'">系统配音在服务器离线生成，不调用配音模型，不消耗配音模型额度；声音较机械。预览和导出使用同一份配音，支持简单快慢调整，不支持克隆音色或复杂情感。</p></el-popover></div>
  <CreationSteps :active="0"/>
</section>
</template>
<style scoped src="../../styles/creation.css"></style>
