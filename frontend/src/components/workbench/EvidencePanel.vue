<script setup lang="ts">
import {ref,watch} from 'vue'
import {getEvidence,type Evidence} from '../../api/outline'
import {errorText} from '../../api/http'
const props=defineProps<{projectId:string;evidenceId:string|null}>()
const emit=defineEmits<{close:[]}>()
const data=ref<Evidence>(),error=ref(''),loading=ref(false)
watch(()=>props.evidenceId,async id=>{data.value=undefined;error.value='';if(!id)return;loading.value=true;try{data.value=await getEvidence(props.projectId,id)}catch(e){error.value=errorText(e)}finally{loading.value=false}},{immediate:true})
function safeUrl(url:string){try{const parsed=new URL(url);return ['https:','http:'].includes(parsed.protocol)&&!parsed.username?url:undefined}catch{return undefined}}
const grades:Record<string,string>={uploaded:'上传材料',institution:'机构来源',secondary:'百科等次级来源',discussion:'论坛讨论',general:'一般网页'}
</script>
<template><el-drawer :model-value="Boolean(evidenceId)" title="查看内容依据" size="min(480px, 100vw)" @close="emit('close')"><div v-loading="loading"><el-alert v-if="error" :title="error" type="error" :closable="false"/><template v-if="data"><h2>{{data.claim}}</h2><p>{{grades[data.source_grade]??data.source_grade}} · {{data.location}}</p><el-alert title="本资料为参考依据，尚不等于事实已核实，请对照原文检查。" type="warning" :closable="false"/><p class="excerpt">{{data.excerpt}}</p><a v-if="data.source_type==='web'&&safeUrl(data.source_ref)" :href="safeUrl(data.source_ref)" target="_blank" rel="noopener noreferrer">打开来源原文</a><a v-else-if="data.source_type==='material'" :href="'/api/projects/'+projectId+'/materials/'+data.source_ref+'/download'">下载原始素材，查看{{data.location}}</a></template></div></el-drawer></template>
<style scoped>h2{font-size:20px;overflow-wrap:anywhere}p{color:var(--ev-color-muted);line-height:1.8}.excerpt{white-space:pre-wrap;color:var(--ev-color-text);overflow-wrap:anywhere;padding:16px 0}a{color:var(--ev-color-primary-dark)}</style>
