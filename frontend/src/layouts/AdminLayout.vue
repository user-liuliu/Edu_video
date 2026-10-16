<!-- 占位布局，Task 13 会替换成三个选项卡 -->
<template>
  <section aria-label="管理后台">
    <nav aria-label="管理后台">
      <RouterLink :to="{ name: 'admin-page-config' }">页面配置</RouterLink>
      <RouterLink :to="{ name: 'admin-model-config' }">模型配置</RouterLink>
      <RouterLink :to="{ name: 'admin-users' }">用户管理</RouterLink>
    </nav>
    <RouterView />
  </section>
</template>

<style scoped>
nav {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}
</style>
