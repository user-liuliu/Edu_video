<!-- 管理后台子页面由 AppLayout 的侧边栏切换。 -->

<template>
  <section class="admin" aria-label="管理后台">
    <div class="admin-heading">
      <p class="eyebrow">管理员后台</p>
      <h1>系统配置</h1>
      <p class="ev-muted">页面配置默认展示，模型和用户管理从左侧切换。</p>
    </div>
    <RouterView />
  </section>
</template>

<style scoped>
.admin { min-width: 0; }
.admin-heading { margin-bottom: 24px; }
.admin-heading h1 { margin-top: 4px; font-size: 28px; letter-spacing: -.03em; }
.admin-heading .ev-muted { margin-top: 7px; }
.eyebrow { margin: 0; color: var(--ev-color-primary-dark); font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }

@media (max-width: 720px) {
  .admin-heading h1 { font-size: 24px; }
}
</style>
