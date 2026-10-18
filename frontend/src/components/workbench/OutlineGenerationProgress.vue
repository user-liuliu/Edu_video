<script setup lang="ts">
import {computed,onMounted,onBeforeUnmount,ref} from 'vue'

const props=defineProps<{stage:string;createdAt?:string;connectionError?:boolean}>()
const mountedAt=Date.now()
const now=ref(mountedAt)
let timer:ReturnType<typeof setInterval>|undefined
const elapsed=computed(()=>{
  const parsed=props.createdAt?Date.parse(props.createdAt):NaN
  const seconds=Math.max(0,Math.floor((now.value-(Number.isFinite(parsed)?parsed:mountedAt))/1000))
  return `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`
})
const statusText=computed(()=>props.connectionError?'正在重新连接':props.stage||'任务处理中')
onMounted(()=>{timer=setInterval(()=>{now.value=Date.now()},1000)})
onBeforeUnmount(()=>clearInterval(timer))
</script>

<template>
  <section class="generation-progress" :class="{'connection-lost':connectionError}" data-testid="live-outline-progress" aria-label="大纲生成进度">
    <div class="progress-heading">
      <div class="progress-stage" role="status" aria-live="polite">
        <span class="status-dot" aria-hidden="true"></span>
        <strong>{{statusText}}…</strong>
      </div>
      <span class="elapsed-time" data-testid="outline-elapsed-time">已等待 {{elapsed}}</span>
    </div>
    <div class="progress-track" role="progressbar" aria-label="大纲任务处理中" :aria-valuetext="statusText">
      <div class="loading-band" data-testid="outline-loading-band" aria-hidden="true"></div>
    </div>
    <p v-if="connectionError">暂时无法获取任务状态，正在自动重连；后台任务可能仍在继续，请勿重复提交。</p>
    <p v-else>后台持续处理，切换页面不会中断任务。</p>
  </section>
</template>

<style scoped>
.generation-progress{margin:20px 0;padding:22px;border:1px solid var(--ev-color-border);border-radius:var(--ev-radius);background:var(--ev-color-surface)}
.progress-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px}
.progress-stage{display:flex;align-items:center;gap:10px;min-width:0;color:var(--ev-color-text)}
.progress-stage strong{font-size:15px;line-height:1.5;overflow-wrap:anywhere}
.status-dot{flex:none;width:8px;height:8px;border-radius:50%;background:var(--ev-color-primary);box-shadow:0 0 0 4px var(--ev-color-surface-muted)}
.elapsed-time{flex:none;color:var(--ev-color-muted);font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap}
.progress-track{position:relative;height:8px;overflow:hidden;border-radius:999px;background:var(--ev-color-border)}
.loading-band{position:absolute;inset:0 -48px;background:repeating-linear-gradient(115deg,var(--el-color-primary-light-5) 0px,var(--el-color-primary-light-5) 12px,var(--ev-color-primary) 12px,var(--ev-color-primary) 24px);opacity:.86;animation:outline-stripe-flow 1.2s linear infinite}
.generation-progress p{margin:12px 0 0;font-size:13px;line-height:1.7;color:var(--ev-color-muted)}
.connection-lost .loading-band{animation-play-state:paused;opacity:.45}
.connection-lost .status-dot{background:var(--ev-color-muted)}
/* One horizontal stripe period (24px / sin(115deg)) keeps the loop seamless. */
@keyframes outline-stripe-flow{from{transform:translateX(-26.48px)}to{transform:translateX(0)}}
@media(max-width:480px){.generation-progress{padding:16px}.progress-heading{gap:12px;align-items:flex-start}.progress-stage{align-items:flex-start}.status-dot{margin-top:7px}.elapsed-time{font-size:12px;padding-top:2px}}
@media(prefers-reduced-motion:reduce){.loading-band{animation:none;transform:none;opacity:.65}}
</style>
