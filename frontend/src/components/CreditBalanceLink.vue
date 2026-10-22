<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {useRoute} from 'vue-router'
import {useAuthStore} from '../stores/auth'
import {getCreditBalance,formatPoints,type CreditBalance} from '../api/credits'
import AppIcon from './AppIcon.vue'
const auth=useAuthStore(),route=useRoute(),balance=ref<CreditBalance>(),failed=ref(false)
let disposed=false,sequence=0,timer:ReturnType<typeof setInterval>|undefined
const label=computed(()=>balance.value?`账户余额，可用 ${formatPoints(balance.value.available)} 积分`:'账户余额')
async function refresh(){
 if(document.hidden)return
 const seq=++sequence,owner=auth.user?.id
 if(!owner)return
 try{const value=await getCreditBalance();if(!disposed&&seq===sequence&&owner===auth.user?.id){balance.value=value;failed.value=false}}
 catch{if(!disposed&&seq===sequence){balance.value=undefined;failed.value=true}}
}
watch(()=>auth.user?.id,()=>{balance.value=undefined;void refresh()})
watch(()=>route.path,()=>{void refresh()})
onMounted(()=>{void refresh();window.addEventListener('edu-video:credits-changed',refresh);window.addEventListener('focus',refresh);timer=setInterval(()=>void refresh(),15000)})
onBeforeUnmount(()=>{disposed=true;clearInterval(timer);window.removeEventListener('edu-video:credits-changed',refresh);window.removeEventListener('focus',refresh)})
</script>
<template>
 <RouterLink to="/account/balance" class="balance-link" :class="{active:route.path==='/account/balance'}" :aria-label="label" :title="label" :aria-current="route.path==='/account/balance'?'page':undefined">
  <span class="wallet-icon"><AppIcon name="wallet"/></span>
  <span class="wallet-content"><span class="wallet-label">账户余额<AppIcon name="arrow"/></span><span v-if="balance" class="wallet-points">{{formatPoints(balance.available)}}<small>积分</small></span><span v-else class="wallet-loading">{{failed?'点击查看余额':'正在读取…'}}</span></span>
 </RouterLink>
</template>
<style scoped>
.balance-link{display:flex;align-items:center;gap:12px;flex:none;margin-top:auto;padding:17px 14px;border:1px solid #dce7fa;border-radius:12px;background:linear-gradient(125deg,#f0f5ff,#fbfdff);color:var(--ev-color-primary-dark);text-decoration:none;transition:border-color .18s,box-shadow .18s;min-height:82px}.balance-link:hover,.balance-link.active{border-color:var(--ev-color-primary);box-shadow:0 3px 12px #2563eb0a}.balance-link:focus-visible{outline:2px solid var(--ev-color-primary);outline-offset:3px}.wallet-icon{display:grid;place-items:center;width:32px;height:36px}.wallet-icon .app-icon{width:24px;height:24px}.wallet-content{flex:1;min-width:0}.wallet-label{display:flex;align-items:center;justify-content:space-between;font-size:12px;gap:10px}.wallet-label .app-icon{width:14px;height:14px}.wallet-points{display:flex;align-items:baseline;gap:6px;margin-top:6px;font-size:23px;font-weight:650;line-height:1.1;font-variant-numeric:tabular-nums}.wallet-points small{font-size:11px;font-weight:400;color:var(--ev-color-muted)}.wallet-loading{display:block;margin-top:6px;font-size:11px;color:var(--ev-color-muted)}
@media(min-width:901px){:global(.rail-collapsed) .balance-link{padding:10px;justify-content:center;min-height:48px}:global(.rail-collapsed) .wallet-content{display:none}}
@media(max-width:900px){.balance-link{margin:0 0 0 5px;min-height:44px;padding:7px 11px;border-radius:8px;gap:7px}.wallet-icon{width:20px;height:24px}.wallet-icon .app-icon{width:19px;height:19px}.wallet-label{font-size:11px}.wallet-label .app-icon{display:none}.wallet-points{margin:3px 0 0;font-size:14px}.wallet-points small{font-size:10px}.wallet-loading{font-size:10px}}
@media(max-width:650px){.balance-link{min-height:55px;flex:1;flex-direction:column;gap:3px;margin:0;padding:6px 5px;background:transparent;border-color:transparent}.wallet-icon{display:none}.wallet-label{white-space:nowrap;font-size:11px}.wallet-points{justify-content:center;font-size:13px}.wallet-points small{display:none}}
@media(prefers-reduced-motion:reduce){.balance-link{transition:none}}
</style>
