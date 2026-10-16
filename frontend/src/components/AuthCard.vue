<!-- 登录、注册、账号状态页共用的外框：页面中间一张作业本式的卡片，上方是楷体品牌名 -->
<script setup lang="ts">
defineProps<{ title: string }>()
</script>

<template>
  <main class="auth-page">
    <p class="brand">教学视频助手</p>
    <section class="card" aria-labelledby="auth-title">
      <h1 id="auth-title" class="title">{{ title }}</h1>
      <slot />
    </section>
    <footer v-if="$slots.footer" class="footer">
      <slot name="footer" />
    </footer>
  </main>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 48px 16px;
}

.brand {
  margin: 0;
  font-family: var(--ev-font-display);
  font-size: 26px;
  letter-spacing: 0.08em;
  color: var(--ev-color-primary);
}

/* 卡片顶边一道黑板绿，和登录后顶栏底边的绿线呼应 */
.card {
  width: 100%;
  max-width: 400px;
  padding: 32px 32px 28px;
  background: var(--ev-color-surface);
  border: 1px solid var(--ev-color-border);
  border-top: 3px solid var(--ev-color-primary);
  border-radius: var(--ev-radius);
}

.title {
  margin-bottom: 24px;
  font-family: var(--ev-font-display);
  font-size: 24px;
  font-weight: 400;
  letter-spacing: 0.04em;
}

.footer {
  color: var(--ev-color-muted);
}

@media (max-width: 480px) {
  .auth-page {
    justify-content: flex-start;
    padding-top: 32px;
  }

  .card {
    padding: 24px 20px 20px;
  }
}
</style>
