<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import AppIcon from '../AppIcon.vue'
import {pptPageApproved,pptPageDelivered,pptPreviewUrl,type PptProject} from '../../api/presentations'

const props=defineProps<{project:PptProject}>()
const ready=ref(false),failed=ref(false)
const source=computed(()=>{
 const p=props.project,first=p.pages[0],slides=p.outline?.slides
 if(!first||p.rendered_revision!==p.revision||!slides||slides.length!==p.pages.length||slides.some((s,i)=>s.id!==p.pages[i]?.id))return ''
 // Keep the real first page as the cover, including partial deliveries.
 if(p.pages.some(s=>s.review||s.delivery)&&!pptPageDelivered(first)&&!pptPageApproved(first))return ''
 return pptPreviewUrl(p,first.id)
})
watch(source,()=>{ready.value=false;failed.value=false})
</script>
<template>
 <div class="ppt-cover" :aria-busy="Boolean(source)&&!ready&&!failed" aria-hidden="true">
  <img v-if="source&&!failed" :key="source" :src="source" alt="" loading="lazy" decoding="async" :class="{ready}" @load="ready=true" @error="failed=true;ready=false"/>
  <div v-if="!source||!ready||failed" class="cover-placeholder"><AppIcon name="ppt"/></div>
 </div>
</template>
<style scoped>
.ppt-cover{position:relative;width:100%;height:100%;overflow:hidden;background:#f0f5fc}.ppt-cover img{display:block;width:100%;height:100%;object-fit:contain;opacity:0;transition:opacity .2s ease;pointer-events:none}.ppt-cover img.ready{opacity:1}.cover-placeholder{position:absolute;inset:0;display:grid;place-items:center;color:#7297bf}.cover-placeholder .app-icon{width:44px;height:44px;stroke-width:1}@media(prefers-reduced-motion:reduce){.ppt-cover img{transition:none}}
</style>
