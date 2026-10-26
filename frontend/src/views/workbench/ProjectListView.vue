<script setup lang="ts">
import PptList from '../../components/workbench/PptList.vue'
import AppIcon from '../../components/AppIcon.vue'
import ProjectCover from '../../components/workbench/ProjectCover.vue'
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { listProjects, deleteProject, type Project } from '../../api/projects'
import { errorText } from '../../api/http'
const route=useRoute(),router=useRouter(),items=ref<Project[]>([]),total=ref(0),page=ref(1),error=ref(''),loading=ref(false)
const labels:Record<string,string>={draft:'草稿',outlining:'正在生成大纲',outline_ready:'大纲待确认',outline_confirmed:'大纲已确认',failed:'任务失败',video_generating:'正在制作视频',preview_ready:'动画预览已就绪',video_exporting:'正在导出MP4',video_failed:'视频制作失败',completed:'视频已完成'}
const isDrafts=()=>route.name==='project-drafts'
async function load(){loading.value=true;error.value='';try{const data=await listProjects(isDrafts()?'drafts':'completed',page.value);items.value=data.items;total.value=data.total}catch(e){error.value=errorText(e)}finally{loading.value=false}}
async function remove(p:Project){try{await ElMessageBox.confirm('确定删除“'+p.title+'”？','删除项目',{confirmButtonText:'删除',cancelButtonText:'取消',type:'warning'})}catch{return}try{await deleteProject(p);await load()}catch(e){error.value=errorText(e)}}
onMounted(load);watch(()=>route.name,()=>{page.value=1;load()})
</script>
<template><div class="work-kind" role="group" aria-label="作品类型"><el-button :type="route.query.kind!=='ppt'?'primary':'default'" @click="router.replace({query:{...route.query,kind:'video'}})">视频</el-button><el-button :type="route.query.kind==='ppt'?'primary':'default'" @click="router.replace({query:{...route.query,kind:'ppt'}})">PPT</el-button></div><PptList v-if="route.query.kind==='ppt'" :drafts="isDrafts()"/><section v-else v-loading="loading" class="project-list-page"><div class="heading"><div><h1>{{isDrafts()?'草稿箱':'我的视频'}}</h1><p class="ev-muted">{{isDrafts()?'未完成的视频会保存在这里，之后可以继续编辑。':'已完成的视频会显示在这里。'}}</p></div></div><el-alert v-if="error" :title="error" type="error" :closable="false"/><el-empty v-if="!loading&&!items.length" :description="isDrafts()?'还没有未完成的视频草稿':'还没有已完成的视频'"/><div class="projects"><article v-for="p in items" :key="p.id"><div class="project-cover" aria-hidden="true"><ProjectCover v-if="['preview_ready','video_exporting','completed'].includes(p.status)" :key="p.id+String(p.updated_at)" :project-id="p.id" :title="p.title"/><AppIcon v-else :name="isDrafts()?'drafts':'videos'"/></div><div class="project-info"><span class="status">{{labels[p.status]??p.status}}</span><h2>{{p.title}}</h2><p class="summary">{{p.prompt}}</p><small class="ev-muted">更新于 {{new Date(p.updated_at).toLocaleString('zh-CN')}}</small><div class="actions"><div class="project-open-actions"><el-button @click="router.push({name:!isDrafts()||['outline_confirmed','video_generating','video_failed','preview_ready','video_exporting','completed'].includes(p.status)?'project-video':p.status==='draft'?'project-edit':'project-outline',params:{id:p.id}})">{{isDrafts()?'继续编辑':'查看视频'}}</el-button><a v-if="!isDrafts()&&p.download_url" class="project-download" :href="p.download_url" download>下载 MP4</a></div><el-button text type="danger" @click="remove(p)">删除</el-button></div></div></article></div><el-pagination v-if="total>20" v-model:current-page="page" :total="total" :page-size="20" layout="prev,pager,next" @current-change="load"/></section></template>
<style scoped src="../../styles/project-list.css"></style>
<style scoped>.work-kind{display:flex;gap:8px;margin-bottom:20px}.work-kind .el-button{margin:0}</style>
