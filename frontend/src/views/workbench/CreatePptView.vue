<script setup lang="ts">
import {onMounted,onBeforeUnmount,ref,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {ElMessage} from 'element-plus'
import AppIcon from '../../components/AppIcon.vue'
import CreationMode from '../../components/workbench/CreationMode.vue'
import CreationSteps from '../../components/workbench/CreationSteps.vue'
import MaterialUpload from '../../components/workbench/MaterialUpload.vue'
import {getPptConfig,getPpt,savePpt,startPptJob,pptMaterialApi,type PptProject,type PptConfig} from '../../api/presentations'
import {errorText} from '../../api/http'
import {rememberCreation,restoreCreation,creationEpoch} from '../../utils/creation-memory'
const route=useRoute(),router=useRouter()
let statePath=route.fullPath
const ownerEpoch=creationEpoch()
const project=ref<PptProject>(),config=ref<PptConfig>(),title=ref(''),prompt=ref(''),style=ref('auto'),webSearch=ref(false),pendingFiles=ref<File[]>([]),saving=ref(false),loading=ref(true),error=ref(''),refreshToken=ref(0)
async function load(){statePath=route.fullPath;loading.value=true;error.value='';try{config.value=await getPptConfig();if(route.params.id)project.value=await getPpt(String(route.params.id));else project.value=undefined;title.value=project.value?.title??'';prompt.value=project.value?.prompt??'';style.value=project.value?.style??'auto';webSearch.value=project.value?.web_search??config.value.search_default;const saved=restoreCreation('ppt',route.fullPath);if(saved){title.value=String(saved.title);prompt.value=String(saved.prompt);style.value=String(saved.style);webSearch.value=Boolean(saved.webSearch);pendingFiles.value=(saved.files as File[])??[]}if(!config.value.search_available)webSearch.value=false;else if(!config.value.search_visible)webSearch.value=config.value.search_default}catch(e){error.value=errorText(e)}finally{loading.value=false}}
function remember(){if(loading.value||!config.value)return;rememberCreation('ppt',statePath,{title:title.value,prompt:prompt.value,style:style.value,webSearch:webSearch.value,files:[...pendingFiles.value]},ownerEpoch)}
async function refresh(){if(project.value)project.value=await getPpt(project.value.id)}
async function save(show=true){if(saving.value)return false;error.value='';if(!title.value.trim()||!prompt.value.trim()){error.value='请填写项目名称和教学需求';return false}saving.value=true;try{const old=project.value;if(!old||old.title!==title.value.trim()||old.prompt!==prompt.value.trim()||old.style!==style.value||old.web_search!==webSearch.value){project.value=await savePpt({title:title.value,prompt:prompt.value,style:style.value,web_search:webSearch.value,revision:old?.revision},old?.id)}for(const file of [...pendingFiles.value]){await pptMaterialApi.upload(project.value!,file);pendingFiles.value=pendingFiles.value.filter(f=>f!==file);await refresh()}refreshToken.value++;if(project.value){statePath='/presentations/'+project.value.id+'/edit';remember();if(route.path!==statePath)await router.replace(statePath)}if(show)ElMessage.success('已保存为草稿');return true}catch(e){error.value=errorText(e);return false}finally{saving.value=false}}
async function generate(){if(!await save(false)||!project.value)return;saving.value=true;try{await startPptJob(project.value,'outline');await router.push({name:'ppt-outline',params:{id:project.value.id}})}catch(e){error.value=errorText(e)}finally{saving.value=false}}
onMounted(load);watch(()=>route.params.id,load);onBeforeUnmount(remember)
</script>
<template>
<section v-loading="loading&&!!config" class="create-page" data-testid="wide-workspace">
  <h1 class="sr-only">PPT 制作</h1><div class="creation-welcome" aria-hidden="true">今天<span>讲</span>点啥？</div>
  <CreationMode mode="ppt" :disabled="saving" @switch="remember"/>
  <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon/>
  <el-alert v-if="config&&!config.system_available" title="大纲模型尚未配置，请联系管理员。你仍可以保存草稿。" type="warning" :closable="false"/>
  <div v-if="loading&&!config" class="creation-loading creation-composer" role="status" aria-live="polite" aria-busy="true">
    <p>正在加载制作设置，请稍候…</p>
    <el-skeleton :rows="6" aria-hidden="true"/>
  </div>
  <div v-else-if="!config" class="creation-load-error creation-composer">
    <p>制作设置加载失败，请重试。</p>
    <el-button data-testid="retry-creation-load" type="primary" @click="load">重新加载</el-button>
  </div>
  <el-form v-if="config" :disabled="loading||saving||project?.status==='generating'" label-position="top" class="creation-form creation-composer" @submit.prevent="save()">
    <div class="composer-input">
      <el-form-item label="项目名称" required class="project-line"><el-input v-model="title" data-testid="project-title" maxlength="200" placeholder="请输入项目名称"/></el-form-item>
      <el-form-item label="想讲什么" required class="prompt-field"><el-input v-model="prompt" type="textarea" :rows="3" maxlength="20000" show-word-limit placeholder="例如：给初三学生制作一份二次函数课件，用投篮的例子帮助理解抛物线。"/></el-form-item>
      <MaterialUpload compact kind="ppt" :project-id="project?.id" :project-revision="project?.revision" :pending-files="pendingFiles" :saving="saving" :refresh-token="refreshToken" @pending-change="files=>pendingFiles=files" @changed="refresh"/>
      <div class="composer-toolbar"><div v-if="config.search_visible&&config.search_available" class="composer-search"><AppIcon name="globe"/><span>联网搜索</span><el-switch v-model="webSearch" aria-label="联网搜索" :disabled="!config.search_available"/></div><div class="actions"><el-button data-testid="save-draft" :loading="saving" @click="save()"><AppIcon name="save"/>保存草稿</el-button><el-button type="primary" :disabled="!config.system_available||saving||project?.status==='generating'" @click="generate">生成 PPT 大纲<AppIcon name="arrow"/></el-button><el-button v-if="project?.outline||project?.job" @click="router.push({name:'ppt-outline',params:{id:project!.id}})">查看大纲与任务</el-button></div></div>
    </div>
    <section class="creation-settings" aria-label="PPT 设置"><h2><AppIcon name="memory"/>PPT 设置</h2><div class="parameter-grid creation-settings-grid"><el-form-item label="课件风格"><el-select v-model="style" aria-label="课件风格"><el-option value="auto" label="自动推荐"/><el-option v-for="t in config.templates" :key="t.id" :value="t.id" :label="t.name"/></el-select></el-form-item></div></section>
  </el-form>
  <div class="creation-notes"><span>关闭联网时仅参考素材与模型知识。</span><span>课件固定为 16:9，可导出整份可编辑 PPTX。</span></div>
  <CreationSteps :active="0" mode="ppt"/>
</section>
</template>
<style scoped src="../../styles/creation.css"></style>
