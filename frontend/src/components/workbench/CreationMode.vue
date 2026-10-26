<script setup lang="ts">
import {useRouter} from 'vue-router'
import AppIcon from '../AppIcon.vue'
import {creationPath} from '../../utils/creation-memory'
const props=defineProps<{mode:'video'|'ppt';disabled?:boolean}>()
const emit=defineEmits<{switch:[]}>();const router=useRouter()
function change(mode:'video'|'ppt'){if(mode===props.mode||props.disabled)return;emit('switch');void router.push(creationPath(mode))}
</script>
<template><div class="creation-mode" role="group" aria-label="制作类型"><button v-for="item in [{id:'video',label:'生成视频',icon:'make'},{id:'ppt',label:'生成 PPT',icon:'textbook_edition'}] as const" :key="item.id" type="button" :data-mode="item.id" :aria-pressed="mode===item.id" :class="{active:mode===item.id}" :disabled="disabled" @click="change(item.id)"><AppIcon :name="item.icon"/>{{item.label}}</button></div></template>
<style scoped>
.creation-mode{display:flex;width:max-content;margin:0 auto 16px;padding:4px;border:1px solid var(--ev-color-border);border-radius:11px;background:var(--ev-color-surface-muted);gap:4px}.creation-mode button{display:flex;align-items:center;justify-content:center;gap:8px;min-height:42px;min-width:124px;padding:8px 18px;border:0;border-radius:7px;background:transparent;color:var(--ev-color-muted);font:inherit;cursor:pointer}.creation-mode button.active{background:var(--ev-color-primary);color:white;box-shadow:var(--ev-shadow-sm)}.creation-mode button:focus-visible{outline:2px solid var(--ev-color-primary);outline-offset:3px}.creation-mode .app-icon{width:18px;height:18px}.creation-mode button:disabled{opacity:.6;cursor:wait}
</style>
