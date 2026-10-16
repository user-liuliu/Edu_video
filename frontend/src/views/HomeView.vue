<template>
  <section class="home" aria-labelledby="home-title">
    <h1 id="home-title" class="page-title">我的视频</h1>
    <div class="empty">
      <p>新建视频功能即将上线</p>
    </div>
  </section>
</template>

<style scoped>
.page-title {
  font-family: var(--ev-font-display);
  font-size: 28px;
  font-weight: 400;
  letter-spacing: 0.04em;
  margin-bottom: 24px;
}

/* 空状态：作业本的田字格底纹 */
.empty {
  display: grid;
  place-items: center;
  min-height: 260px;
  padding: 32px;
  border: 1px solid var(--ev-color-border);
  border-radius: var(--ev-radius);
  background-color: var(--ev-color-surface);
  background-image:
    linear-gradient(to right, rgba(34, 97, 79, 0.07) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(34, 97, 79, 0.07) 1px, transparent 1px);
  background-size: 32px 32px;
  background-position: center;
}

.empty p {
  margin: 0;
  padding: 4px 12px;
  background: var(--ev-color-surface);
  color: var(--ev-color-muted);
}
</style>
