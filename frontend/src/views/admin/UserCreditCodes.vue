<script setup lang="ts">
import {onBeforeUnmount,ref,watch} from 'vue'
import {listCreditCodes,issueCreditCode,revokeCreditCode,formatPoints,formatCreditTime,type CreditCode,type IssuedCode} from '../../api/credits'
import {errorText} from '../../api/http'
import AppIcon from '../../components/AppIcon.vue'
const props=defineProps<{user:{id:string;username:string}}>()
const amount=ref(100),days=ref(30),page=ref(1),items=ref<CreditCode[]>([]),total=ref(0),issued=ref<IssuedCode>(),saving=ref(false),loading=ref(false),error=ref(''),listError=ref(''),copyMessage=ref(''),busy=ref('')
const statusText:Record<CreditCode['status'],string>={available:'待兑换',redeemed:'已兑换',expired:'已过期',revoked:'已停用'}
let sequence=0,disposed=false
async function load(){const seq=++sequence;loading.value=true;listError.value='';const uid=props.user.id;try{const value=await listCreditCodes(uid,page.value);if(!disposed&&seq===sequence&&uid===props.user.id){items.value=value.items;total.value=value.total}}catch(e){if(!disposed&&seq===sequence)listError.value=errorText(e)}finally{if(!disposed&&seq===sequence)loading.value=false}}
watch(()=>props.user.id,()=>{page.value=1;issued.value=undefined;error.value='';copyMessage.value='';void load()},{immediate:true})
async function generate(){
 if(saving.value)return;error.value='';copyMessage.value=''
 if(!Number.isInteger(Number(amount.value))||amount.value<1||amount.value>1000000){error.value='请输入 1 至 1,000,000 之间的整数积分';return}
 if(!Number.isInteger(Number(days.value))||days.value<1||days.value>365){error.value='有效期须为 1 至 365 天';return}
 const uid=props.user.id;saving.value=true
 try{const value=await issueCreditCode(uid,Number(amount.value),Number(days.value));if(disposed||uid!==props.user.id)return;issued.value=value;page.value=1;await load()}catch(e){if(!disposed)error.value=errorText(e)}finally{if(!disposed)saving.value=false}
}
async function copy(){if(!issued.value)return;try{await navigator.clipboard.writeText(issued.value.code);copyMessage.value='兑换码已复制'}catch{copyMessage.value='自动复制不可用，请选中上方兑换码复制'}}
async function revoke(item:CreditCode){if(busy.value)return;busy.value=item.id;error.value='';try{await revokeCreditCode(item.id);if(!disposed)await load()}catch(e){if(!disposed)error.value=errorText(e)}finally{if(!disposed)busy.value=''}}
onBeforeUnmount(()=>{disposed=true})
</script>
<template>
 <section class="user-credit-codes" aria-label="用户积分兑换码">
  <div class="target-user"><span class="target-icon"><AppIcon name="ticket"/></span><div><strong>{{user.username}}</strong><p>兑换码仅限此账户使用，兑换后即时到账。</p></div></div>
  <form class="issue-form" @submit.prevent="generate"><div><label for="code-amount">兑换额度（积分）</label><el-input id="code-amount" v-model.number="amount" type="number" :min="1" :max="1000000" :step="1" :disabled="saving"/></div><div><label for="code-days">有效期（天）</label><el-input id="code-days" v-model.number="days" type="number" :min="1" :max="365" :step="1" :disabled="saving"/></div><el-button type="primary" native-type="submit" :loading="saving" :disabled="saving">生成兑换码</el-button></form>
  <p v-if="error" class="inline-error" role="alert">{{error}}</p>
  <div v-if="issued" class="issued-code" role="status"><strong>已生成 {{formatPoints(issued.amount)}} 积分兑换码</strong><p>完整兑换码仅在本次显示，请复制后交给 {{user.username}}。</p><code tabindex="0" aria-label="新生成的兑换码">{{issued.code}}</code><div><span>{{formatCreditTime(issued.expires_at)}} 到期</span><el-button size="small" @click="copy">复制兑换码</el-button></div><p v-if="copyMessage">{{copyMessage}}</p></div>
  <header class="codes-heading"><h3>兑换码记录</h3><span>共 {{total}} 条</span></header>
  <div v-if="listError" class="inline-error" role="alert"><p>{{listError}}</p><el-button @click="load">重试加载</el-button></div>
  <p v-else-if="loading" class="list-empty" role="status">正在加载…</p>
  <p v-else-if="!items.length" class="list-empty">尚未为此用户生成兑换码</p>
  <div v-else class="code-list"><article v-for="item in items" :key="item.id" class="code-row"><div><strong>{{formatPoints(item.amount)}} 积分</strong><span>尾号 {{item.suffix}} · {{formatCreditTime(item.expires_at)}} 到期</span></div><span class="code-state" :class="item.status">{{statusText[item.status]}}</span><el-button v-if="item.status==='available'" size="small" :loading="busy===item.id" :disabled="!!busy" @click="revoke(item)">停用</el-button></article></div>
  <el-pagination v-if="total>20" v-model:current-page="page" :total="total" :page-size="20" layout="prev, pager, next" @current-change="load"/>
 </section>
</template>
<style scoped>
.target-user{display:flex;align-items:center;gap:12px;padding:16px;background:#f4f7fc;border-radius:10px;margin-bottom:22px}.target-icon{display:grid;place-items:center;width:38px;height:38px;border-radius:10px;background:#e8f0ff;color:var(--ev-color-primary);flex:none}.target-user strong{font-size:14px;font-weight:600}.target-user p{font-size:12px;color:var(--ev-color-muted);margin:5px 0 0;line-height:1.7}.issue-form{display:grid;grid-template-columns:1fr 1fr auto;gap:12px;align-items:end}.issue-form label{display:block;font-size:12px;color:var(--ev-color-muted);margin-bottom:8px}.issue-form :deep(.el-input__wrapper){min-height:42px}.issue-form>.el-button{min-height:44px}.inline-error{color:var(--ev-color-danger);font-size:12px;line-height:1.7}.issued-code{padding:20px;margin:22px 0;background:#f1f6ff;border:1px solid #d8e5fb;border-radius:10px}.issued-code>strong{color:#294e88;font-size:14px}.issued-code p{color:#536c8e;font-size:12px;line-height:1.7}.issued-code code{display:block;padding:13px;background:white;border:1px dashed #b7cbee;border-radius:6px;font-size:13px;font-weight:600;letter-spacing:.02em;color:#24569a;overflow-wrap:anywhere;user-select:all}.issued-code>div{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:13px;font-size:11px;color:#536c8e}.codes-heading{display:flex;justify-content:space-between;align-items:center;margin:25px 0 10px}.codes-heading h3{font-size:14px;font-weight:600;margin:0}.codes-heading>span{font-size:11px;color:var(--ev-color-muted)}.code-list{border-top:1px solid var(--ev-color-border)}.code-row{display:flex;align-items:center;gap:15px;border-bottom:1px solid var(--ev-color-border);padding:16px 0}.code-row>div{flex:1;min-width:0}.code-row strong{display:block;font-size:13px;font-weight:550}.code-row>div>span{display:block;font-size:11px;line-height:1.7;color:var(--ev-color-muted);margin-top:5px}.code-state{white-space:nowrap;color:var(--ev-color-muted);font-size:11px}.code-state.available{color:var(--ev-color-primary)}.code-state.redeemed{color:var(--ev-color-success)}.list-empty{text-align:center;padding:28px 10px;color:var(--ev-color-muted);font-size:12px}.el-pagination{justify-content:flex-end;margin-top:16px}@media(max-width:600px){.issue-form{grid-template-columns:1fr 1fr}.issue-form>.el-button{grid-column:1/-1}.code-row{gap:10px}.issued-code{padding:16px}.issued-code code{font-size:12px}.issued-code>div{flex-wrap:wrap}}
</style>
