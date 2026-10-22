<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AccountProfile from './AccountProfile.vue'
import AccountSecurity from './AccountSecurity.vue'
import PreferencesView from './PreferencesView.vue'
const route = useRoute(), router = useRouter()
const tabs = [{ key: 'profile', label: '个人资料' }, { key: 'security', label: '账户安全' }, { key: 'preferences', label: '我的偏好' }] as const
type Tab = typeof tabs[number]['key']
const active = computed<Tab>(() => tabs.find(tab => tab.key === route.query.tab)?.key ?? 'profile')
const preferencesVisited = ref(false)
watch(active, tab => { if (tab === 'preferences') preferencesVisited.value = true }, { immediate: true })
async function select(tab: Tab) { await router.replace({ query: { ...route.query, tab } }) }
async function navigate(event: KeyboardEvent, index: number) {
  let target = index
  if (event.key === 'ArrowRight') target = (index + 1) % tabs.length
  else if (event.key === 'ArrowLeft') target = (index + tabs.length - 1) % tabs.length
  else if (event.key === 'Home') target = 0
  else if (event.key === 'End') target = tabs.length - 1
  else return
  event.preventDefault()
  const tab = tabs[target]!
  await select(tab.key)
  await nextTick()
  document.getElementById('tab-' + tab.key)?.focus()
}
</script>
<template>
  <section class="account-settings">
    <h1>账户设置</h1>
    <p class="page-description">管理个人资料、登录密码和创作偏好。</p>
    <div class="account-tabs" role="tablist" aria-label="账户设置">
      <button v-for="(tab, index) in tabs" :id="'tab-' + tab.key" :key="tab.key" type="button" role="tab" :aria-selected="active === tab.key" :aria-controls="'panel-' + tab.key" :tabindex="active === tab.key ? 0 : -1" @click="select(tab.key)" @keydown="navigate($event, index)">{{ tab.label }}</button>
    </div>
    <div id="panel-profile" v-show="active === 'profile'" role="tabpanel" aria-labelledby="tab-profile" tabindex="0" class="account-panel"><AccountProfile /></div>
    <div id="panel-security" v-show="active === 'security'" role="tabpanel" aria-labelledby="tab-security" tabindex="0" class="account-panel"><AccountSecurity /></div>
    <div id="panel-preferences" v-show="active === 'preferences'" role="tabpanel" aria-labelledby="tab-preferences" tabindex="0" class="account-panel"><PreferencesView v-if="preferencesVisited" embedded /></div>
  </section>
</template>
<style scoped>
.account-settings{max-width:1120px!important;margin:0 auto}h1{font:600 28px/1.4 var(--ev-font-display);margin:0}.page-description{color:var(--ev-color-muted);font-size:13px;margin:8px 0 27px}.account-tabs{display:flex;gap:28px;border-bottom:1px solid var(--ev-color-border)}.account-tabs button{position:relative;padding:12px 0 15px;background:transparent;border:0;color:var(--ev-color-muted);font:inherit;font-size:14px;cursor:pointer;white-space:nowrap}.account-tabs button[aria-selected=true]{color:var(--ev-color-primary);font-weight:600}.account-tabs button[aria-selected=true]:after{content:'';position:absolute;left:0;right:0;bottom:-1px;height:2px;background:var(--ev-color-primary)}.account-panel{padding:28px 0 12px}.account-panel:focus-visible{outline-offset:5px}.account-panel :deep(h2){font-size:18px;font-weight:600;margin:0}.account-panel :deep(.section-description){color:var(--ev-color-muted);font-size:13px;margin:8px 0 0}.account-panel :deep(.field-hint){color:var(--ev-color-muted);font-size:12px;line-height:1.7}.account-panel :deep(.el-form-item){margin-bottom:24px}.account-panel :deep(.el-form-item__label){font-size:13px}.account-panel :deep(.el-input__wrapper),.account-panel :deep(.el-select__wrapper){min-height:42px}.account-panel :deep(.form-actions){display:flex;align-items:center;flex-wrap:wrap;gap:16px;margin-top:8px}.account-panel :deep(.form-error){color:var(--ev-color-danger);font-size:13px;margin:10px 0 16px}.account-panel :deep(.form-success){color:var(--ev-color-success);font-size:13px;margin:10px 0 16px}@media(max-width:600px){.account-tabs{gap:24px}.account-panel{padding-top:24px}.page-description{margin-bottom:18px}}
</style>
