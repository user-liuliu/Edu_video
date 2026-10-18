<script setup lang="ts">
defineProps<{ title: string }>()
</script>

<template>
  <main class="auth-page">
    <section class="auth-story" aria-label="产品简介">
      <p class="story-brand">教学视频助手</p>
      <p class="story-kicker">教师工作台</p>
      <h2>让每一次备课，都更从容。</h2>
      <p class="story-copy">输入教学想法，补充课件素材，确认分段大纲，再预览属于你的讲解视频。</p>
    </section>
    <section class="auth-panel" aria-labelledby="auth-title">
      <p class="panel-kicker">欢迎回来</p>
      <h1 id="auth-title" class="title">{{ title }}</h1>
      <slot />
    </section>
    <footer v-if="$slots.footer" class="footer">
      <slot name="footer" />
    </footer>
  </main>
</template>

<style scoped>
.auth-page { display: grid; grid-template-columns: minmax(0, 1fr) minmax(360px, 470px); align-items: stretch; min-height: 100vh; background: var(--ev-color-bg); }
.auth-story { display: flex; flex-direction: column; justify-content: center; padding: 70px clamp(32px, 8vw, 120px); background: var(--ev-color-rail); color: #fffaf5; }
.story-brand { margin: 0; font-family: var(--ev-font-display); font-size: 24px; font-weight: 700; letter-spacing: .05em; }
.story-kicker, .panel-kicker { margin: 10px 0 0; color: var(--ev-color-primary); font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.story-kicker { color: rgba(255, 255, 255, .56); }
.auth-story h1 { max-width: 430px; margin-top: 62px; font-family: var(--ev-font-display); font-size: clamp(32px, 4vw, 54px); line-height: 1.18; letter-spacing: -.04em; }
.story-copy { max-width: 410px; margin-top: 18px; color: rgba(255, 255, 255, .7); font-size: 15px; line-height: 1.9; }
.auth-panel { align-self: center; width: 100%; padding: 48px clamp(25px, 5vw, 58px); background: var(--ev-color-surface); }
.panel-kicker { margin: 0; }
.title { margin: 6px 0 28px; font-size: 29px; letter-spacing: -.03em; }
.footer { position: absolute; right: clamp(25px, 5vw, 58px); bottom: 24px; color: var(--ev-color-muted); font-size: 13px; }

@media (max-width: 720px) {
  .auth-page { display: flex; flex-direction: column; min-height: 100vh; }
  .auth-story { min-height: 230px; padding: 28px 22px 30px; }
  .auth-story h1 { margin-top: 30px; font-size: 32px; }
  .story-copy { margin-top: 10px; font-size: 13px; line-height: 1.7; }
  .auth-panel { align-self: stretch; padding: 30px 22px 45px; }
  .footer { position: static; padding: 0 22px 26px; text-align: center; background: var(--ev-color-surface); }
}
</style>
