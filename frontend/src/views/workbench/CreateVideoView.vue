<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getFormConfig, getProject, saveProject, type FormConfig, type Project, type PublicField } from '../../api/projects'
import { uploadMaterial } from '../../api/materials'
import { errorText } from '../../api/http'
import AppIcon from '../../components/AppIcon.vue'
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
const settingsFields=computed(()=>fields.value.filter(f=>f.key!=='web_search'))
const searchField=computed(()=>fields.value.find(f=>f.key==='web_search'))
function options(f:PublicField){return f.options.filter(o=>!o.subjects?.length||o.subjects.includes(String(values.value.subject)))}
watch(()=>values.value.subject,(subject,previous)=>{if(loading.value||previous===undefined)return;const edition=config.value?.fields.find(f=>f.key==='textbook_edition');if(edition)values.value.textbook_edition=edition.default_by_subject[String(subject)]??edition.default})
watch([prompt,title,values],()=>{if(!loading.value)dirty.value=true},{deep:true})
function isDocumentReload(){const entry=performance.getEntriesByType?.('navigation')[0] as PerformanceNavigationTiming|undefined;return entry?.type==='reload'}
async function load(){loading.value=true;try{if(!route.params.id&&isDocumentReload()){clearVideoDraft(cacheKey.value);await clearPendingFiles(cacheKey.value)}const loaded=await getFormConfig();config.value={...loaded,fields:loaded.fields.filter(f=>String(f.key)!=='style')};values.value=Object.fromEntries(config.value.fields.map(f=>[f.key,f.default]));if(route.params.id){project.value=await getProject(String(route.params.id));prompt.value=project.value.prompt;title.value=project.value.title;Object.assign(values.value,project.value.form_values);delete values.value.style}pendingFiles.value=await readPendingFiles(cacheKey.value)}catch(e){error.value=errorText(e)}finally{loading.value=false}}
async function uploadPendingMaterials(){if(!project.value)return;for(const file of [...pendingFiles.value]){await uploadMaterial(project.value.id,file,true);pendingFiles.value=pendingFiles.value.filter(item=>item!==file);await writePendingFiles(cacheKey.value,pendingFiles.value)}await refreshProject();materialsRefreshToken.value+=1}
async function save(showSuccess=true){if(saving.value)return;if(project.value?.status==='outlining'){error.value='项目正在处理中，请先等待任务完成';return;}title.value=title.value.trim();if(!title.value){error.value='请填写项目名称';return}if(project.value&&['outline_ready','outline_confirmed','failed'].includes(project.value.status)&&dirty.value){try{await ElMessageBox.confirm('修改需求或科目、年级、教材、时长、联网方式后需要重新生成大纲；原大纲会保留。尺寸和音色调整不会重写讲稿。','保存需求修改',{confirmButtonText:'保存修改',cancelButtonText:'继续编辑'});}catch{return;}}if(!prompt.value.trim()){error.value='请填写想讲什么';return}saving.value=true;error.value='';try{project.value=await saveProject({prompt:prompt.value,title:title.value,form_values:values.value,form_version:config.value?.form_version,revision:project.value?.revision},project.value?.id);await uploadPendingMaterials();dirty.value=false;if(showSuccess)ElMessage.success('已保存为草稿')}catch(e){error.value=errorText(e)}finally{saving.value=false}}
async function refreshProject(){if(project.value)project.value=await getProject(project.value.id)}
async function generate(){if(!config.value?.system_available||saving.value)return;if(hasOutline.value){try{await ElMessageBox.confirm('是否重新生成大纲','重新生成大纲',{confirmButtonText:'重新生成大纲',cancelButtonText:'取消',type:'warning'})}catch{return}}if(dirty.value||!project.value||pendingFiles.value.length)await save(false);if(error.value||dirty.value||!project.value)return;saving.value=true;error.value='';try{const job=await submitOutlineJob(project.value.id,'generate',project.value.revision,{form_version:config.value.form_version});addPendingOutlineNotification({jobId:job.id,projectId:project.value.id});await router.push({name:'project-outline',params:{id:project.value.id}})}catch(e){error.value=errorText(e)}finally{saving.value=false}}
onMounted(()=>{void load()})
onBeforeUnmount(()=>{void writePendingFiles(cacheKey.value,pendingFiles.value)})
</script>
<template>
<section v-loading="loading" class="create-page" data-testid="wide-workspace">
  <h1 class="sr-only">视频制作</h1>
  <div class="creation-welcome" aria-hidden="true">今天<span>讲</span>点啥？</div>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/>
  <el-alert v-if="config&&!config.system_available" title="系统暂不可用，请联系管理员。你仍可以保存草稿。" type="warning" :closable="false"/>
  <el-alert v-if="project?.needs_regeneration" title="需求或素材已变化，旧大纲已保留，请重新生成后再确认。" type="warning" :closable="false"/>
  <el-form v-if="config" :disabled="saving" label-position="top" class="creation-form creation-composer" @submit.prevent="save()">
    <div class="composer-input">
      <el-form-item label="项目名称" required class="project-line"><el-input v-model="title" data-testid="project-title" maxlength="200" placeholder="请输入项目名称"/></el-form-item>
      <el-form-item :label="config.fields.find(f=>f.key==='prompt')?.label??'想讲什么'" required class="prompt-field"><el-input v-model="prompt" type="textarea" :rows="3" maxlength="20000" show-word-limit placeholder="例如：给初三学生讲解二次函数，用投篮的例子帮助理解抛物线。"/></el-form-item>
      <MaterialUpload compact v-if="config.fields.some(f=>f.key==='materials')" :project-id="project?.id" :pending-files="pendingFiles" :saving="saving" :refresh-token="materialsRefreshToken" @pending-change="files=>{pendingFiles=files;void writePendingFiles(cacheKey,files)}" @changed="refreshProject"/>
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
<style scoped>
.create-page{width:100%;max-width:1180px!important;padding-top:0}
.creation-welcome{display:flex;align-items:center;justify-content:center;gap:4px;margin:0 0 10px;min-height:50px;font-family:"STKaiti","KaiTi","Noto Serif SC",serif;font-size:clamp(30px,3.4vw,46px);line-height:1.2;letter-spacing:.06em;color:var(--ev-color-text)}
.creation-welcome span{display:inline-grid;place-items:center;width:1.35em;height:1.35em;margin:0 3px;color:var(--ev-color-primary);border-radius:50%;background:linear-gradient(140deg,#f5f8ff,#edf2ff);box-shadow:2px 4px 12px #31569418;font-size:1.12em}
.creation-composer{width:100%;border:1px solid #dfe5ee;border-radius:18px;background:var(--ev-color-surface);box-shadow:var(--ev-shadow-sm);overflow:hidden}
.creation-composer:focus-within{border-color:#adc8ee;box-shadow:0 4px 20px #285bb508}
.composer-input{padding:0 22px}
.project-line{display:flex;align-items:center;gap:14px;padding:7px 0;border-bottom:1px solid #f0f2f6;margin:0}
.project-line :deep(.el-form-item__label){height:auto;line-height:1.6;flex:none;padding:0;color:var(--ev-color-muted)}
.project-line :deep(.el-form-item__content){flex:1;min-width:0}
.project-line :deep(.el-input__wrapper){box-shadow:none;background:transparent;padding-left:0;min-height:34px}
.project-line :deep(.el-input__inner){font-size:14px;font-weight:500}
.prompt-field{padding-top:10px;margin-bottom:6px}
.prompt-field :deep(.el-form-item__label){font-size:12px;margin-bottom:2px}
.prompt-field :deep(.el-textarea__inner){box-shadow:none;padding:4px 0 20px;font-size:15px;line-height:1.7;min-height:82px!important;height:clamp(82px,calc(100dvh - 720px),156px);resize:vertical}
.prompt-field :deep(.el-input__count){right:0;color:var(--ev-color-muted);font-size:11px}
.composer-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:4px 0 10px}
.composer-search{display:flex;align-items:center;gap:8px;color:var(--ev-color-muted);font-size:12px}
.composer-search>.app-icon{width:17px;height:17px}
.composer-search :deep(.el-switch){height:32px}
.actions{display:flex;flex-wrap:wrap;gap:9px;margin-left:auto}.actions .el-button{margin:0}.actions .app-icon{width:17px;height:17px}
.creation-settings{padding:12px 22px 14px;border-top:1px solid #e8edf5;background:#fafbfd}
.creation-settings h2{display:flex;align-items:center;gap:8px;color:var(--ev-color-muted);font-size:12px;font-weight:500;margin:0 0 10px}
.creation-settings h2>.app-icon{width:16px;height:16px}
.creation-settings-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px 18px}
.creation-settings-grid .el-form-item{min-width:0;margin:0}
.creation-settings-grid :deep(.el-form-item__label){display:flex;align-items:center;gap:7px;font-size:12px;padding:0;margin-bottom:5px;height:auto;line-height:1.5}
.creation-settings-grid :deep(.el-form-item__label .app-icon){width:16px;height:16px;color:#7188a7}
.creation-settings-grid :deep(.el-select){width:100%;min-width:0}
.creation-settings-grid :deep(.el-select__wrapper){font-size:13px;min-height:36px}
.creation-settings-grid :deep(.el-input-number){width:100%;margin-top:8px}
.creation-notes{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:2px 12px;margin:6px 3px;color:var(--ev-color-muted);font-size:11px;line-height:1.6}.creation-help{display:inline-flex;align-items:center;gap:4px;min-height:28px;border:0;padding:2px 4px;border-radius:5px;background:transparent;color:var(--ev-color-primary-dark);font:inherit;cursor:pointer}.creation-help .app-icon{width:14px;height:14px}.creation-help:hover{background:var(--ev-color-surface-muted)}
.create-page>.creation-steps{justify-content:center;border-bottom:0;margin:8px 0 0}
.create-page>:deep(.creation-steps li){padding-bottom:8px}
.composer-input :deep(.materials){margin-bottom:4px}
.composer-input :deep(.materials .file-button){min-height:32px;padding-top:4px;padding-bottom:4px}
.composer-input :deep(.materials>p){line-height:1.5;margin:2px 0 4px}
.composer-input :deep(.materials ul){max-height:128px;overflow-y:auto;overscroll-behavior:contain}
.el-alert{margin-bottom:10px}
@media(min-width:651px) and (max-width:900px){.creation-settings-grid{grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}.creation-settings{padding-left:16px;padding-right:16px}.creation-settings-grid :deep(.el-form-item__label){gap:4px}.creation-settings-grid :deep(.el-form-item__label .app-icon){width:14px;height:14px}}
@media(min-width:651px) and (max-height:760px){.creation-welcome{font-size:32px;min-height:48px;margin-bottom:8px}}
@media(min-width:1700px){.create-page{max-width:1320px!important}}
@media(max-width:650px){.creation-welcome{min-height:48px;font-size:30px;margin-bottom:14px}.composer-input{padding:0 16px}.creation-composer{border-radius:15px}.project-line{gap:9px}.project-line :deep(.el-input__inner){font-size:16px}.prompt-field :deep(.el-textarea__inner){font-size:16px;height:108px}.creation-settings{padding:14px 16px}.creation-settings-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:14px 12px}.creation-settings-grid :deep(.el-select__wrapper){min-height:44px}.composer-toolbar{gap:8px;padding-bottom:14px}.composer-search{font-size:11px;gap:6px}.actions{gap:6px}.actions .el-button{padding:10px;font-size:12px}.creation-notes p{font-size:11px}.create-page>.creation-steps{gap:12px}}
</style>
