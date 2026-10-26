<script setup lang="ts">
import {onMounted,ref,watch} from 'vue'
import {useRouter} from 'vue-router'
import {ElMessageBox} from 'element-plus'
import {listPpts,deletePpt,pptExportUrl,pptPageApproved,pptPageDelivered,type PptProject} from '../../api/presentations'
import {errorText} from '../../api/http'
import PptCover from './PptCover.vue'
const props=defineProps<{drafts:boolean}>(),router=useRouter(),items=ref<PptProject[]>([]),total=ref(0),page=ref(1),error=ref(''),loading=ref(false)
const labels:Record<string,string>={draft:'草稿',generating:'正在处理',outline_ready:'大纲待确认',outline_confirmed:'大纲已确认',ready:'课件已生成',partial_ready:'部分页面已完成',failed:'任务失败'}
async function load(){loading.value=true;try{const data=await listPpts(props.drafts?'drafts':'completed',page.value);items.value=data.items;total.value=data.total;error.value=''}catch(e){error.value=errorText(e)}finally{loading.value=false}}
function partial(p:PptProject){const available=(s:PptProject['pages'][number])=>pptPageDelivered(s)||pptPageApproved(s);return p.rendered_revision===p.revision&&p.pages.some(available)&&p.pages.some(s=>!available(s))}
function open(p:PptProject){void router.push({name:p.pages.length?'ppt-preview':p.outline||p.job?'ppt-outline':'ppt-edit',params:{id:p.id}})}
async function remove(p:PptProject){try{await ElMessageBox.confirm('确定删除“'+p.title+'”？','删除课件',{confirmButtonText:'删除',cancelButtonText:'取消',type:'warning'})}catch{return}try{await deletePpt(p);await load()}catch(e){error.value=errorText(e)}}
onMounted(load);watch(()=>props.drafts,()=>{page.value=1;void load()})
</script>
<template>
 <section v-loading="loading" class="project-list-page">
  <header class="heading">
   <div><h1>{{drafts?'PPT 草稿':'我的 PPT'}}</h1><p class="ev-muted">{{drafts?'尚未确认导出的课件保存在这里，生成后可继续预览和修改。':'满意并成功导出的课件保存在这里，支持继续预览、修改和下载。'}}</p></div>
  </header>
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <el-empty v-if="!loading&&!items.length" :description="drafts?'还没有 PPT 草稿':'还没有已完成的 PPT'"/>
  <div class="projects">
   <article v-for="p in items" :key="p.id">
    <div class="project-cover" aria-hidden="true"><PptCover :project="p"/></div>
    <div class="project-info">
     <div class="project-meta"><span class="status">{{p.status==='ready'&&!drafts?'已导出':labels[p.status]??p.status}}</span><span class="page-count">{{p.outline?.slides.length??p.pages.length}} 页</span></div>
     <h2>{{p.title}}</h2>
     <p class="summary">{{p.prompt}}</p>
     <small class="ev-muted">更新于 {{new Date(p.updated_at).toLocaleString('zh-CN')}}</small>
     <div class="actions">
      <div class="project-open-actions"><el-button @click="open(p)">{{p.pages.length?'查看课件':'继续编辑'}}</el-button><a v-if="p.pages.length" class="project-download" :href="pptExportUrl(p.id,partial(p))">{{partial(p)?'下载已通过部分':'下载 PPTX'}}</a></div>
      <el-button text type="danger" :disabled="p.status==='generating'" @click="remove(p)">删除</el-button>
     </div>
    </div>
   </article>
  </div>
  <el-pagination v-if="total>20" v-model:current-page="page" :total="total" :page-size="20" layout="prev,pager,next" @current-change="load"/>
 </section>
</template>
<style scoped src="../../styles/project-list.css"></style>
