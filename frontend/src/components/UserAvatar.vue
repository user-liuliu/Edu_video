<script setup lang="ts">
import { ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
const props = defineProps<{ src?: string | null; name?: string }>()
const failed = ref(false)
watch(() => props.src, () => { failed.value = false })
</script>
<template>
  <span class="user-avatar" aria-hidden="true">
    <img v-if="src && !failed" :src="src" alt="" @error="failed = true" />
    <span v-else-if="name" class="initial">{{ Array.from(name)[0] }}</span>
    <AppIcon v-else name="account" />
  </span>
</template>
<style scoped>
.user-avatar{display:inline-flex;align-items:center;justify-content:center;flex:none;width:var(--avatar-size,76px);height:var(--avatar-size,76px);overflow:hidden;border-radius:50%;background:#edf3ff;color:var(--ev-color-primary);vertical-align:middle}.user-avatar img{width:100%;height:100%;object-fit:cover}.app-icon{width:52%;height:52%}.initial{font-size:calc(var(--avatar-size,76px) * .38);font-weight:500;line-height:1}
</style>
