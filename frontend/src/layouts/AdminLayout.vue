<!-- 管理后台：三个选项卡分别对应三个子路由，当前选项卡跟着路由走 -->
<script setup lang="ts">
import type { TabPaneName } from 'element-plus'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const TABS = [
  { name: 'admin-page-config', label: '页面配置' },
  { name: 'admin-model-config', label: '模型配置' },
  { name: 'admin-users', label: '用户管理' },
] as const

const route = useRoute()
const router = useRouter()
const active = computed(() => String(route.name ?? ''))

function onChange(name: TabPaneName) {
  if (name !== route.name) void router.push({ name: String(name) })
}
</script>

<template>
  <!-- AppLayout 已经提供 main；这里不再加 main / h1，各选项卡用 h2 / h3 作为分节标题 -->
  <section class="admin" aria-label="管理后台">
    <el-tabs :model-value="active" @tab-change="onChange">
      <el-tab-pane v-for="tab in TABS" :key="tab.name" :name="tab.name" :label="tab.label">
        <!-- 只渲染当前路由对应的选项卡，切换时重新加载数据 -->
        <RouterView v-if="active === tab.name" />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.admin :deep(.el-tabs__item) {
  font-size: 15px;
}
</style>
