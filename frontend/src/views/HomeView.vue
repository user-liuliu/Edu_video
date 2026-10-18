<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const sectionMeta: Record<string, { eyebrow: string; title: string; description: string; message: string }> = {
  make: {
    eyebrow: '视频制作',
    title: '视频制作',
    description: '新建视频流程将在后续版本接入，当前先保留入口和工作区结构。',
    message: '视频制作功能即将上线',
  },
  videos: {
    eyebrow: '我的视频',
    title: '我的视频',
    description: '集中查看和管理你创建的视频项目。',
    message: '新建视频功能即将上线',
  },
  drafts: {
    eyebrow: '草稿箱',
    title: '草稿箱',
    description: '未完成的视频项目会在这里继续编辑。',
    message: '草稿箱功能即将上线',
  },
  memory: {
    eyebrow: '我的偏好',
    title: '我的偏好',
    description: '管理系统为你记录的长期创作偏好。',
    message: '偏好设置功能即将上线',
  },
  account: {
    eyebrow: '账户设置',
    title: '账户设置',
    description: '管理账号信息和登录安全设置。',
    message: '账户设置功能即将上线',
  },
}

const current = computed(() => sectionMeta[String(route.query.section ?? 'videos')] ?? sectionMeta.videos)
</script>

<template>
  <section class="home" :aria-labelledby="`home-title-${String(route.query.section ?? 'videos')}`">
    <div class="page-heading">
      <div>
        <p class="eyebrow">{{ current.eyebrow }}</p>
        <h1 :id="`home-title-${String(route.query.section ?? 'videos')}`">{{ current.title }}</h1>
        <p class="intro">{{ current.description }}</p>
      </div>
    </div>

    <div class="workspace-grid">
      <section class="empty-state" aria-label="当前页面状态">
        <div class="empty-icon" aria-hidden="true">＋</div>
        <div>
          <h2>{{ current.message }}</h2>
          <p>功能接入后，你可以在这里继续完成教学视频项目。</p>
        </div>
      </section>

      <aside class="next-card" aria-label="工作区提示">
        <span class="next-label">工作区提示</span>
        <strong>先配置好模型与页面选项</strong>
        <p>管理员可以从左侧管理后台维护生成所需的配置。</p>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.home { min-width: 0; }
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 28px; }
.eyebrow { margin: 0 0 5px; color: var(--ev-color-primary-dark); font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
h1 { font-family: var(--ev-font-display); font-size: 32px; font-weight: 400; letter-spacing: .02em; }
.intro { max-width: 560px; margin: 9px 0 0; color: var(--ev-color-muted); }
.workspace-grid { display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 18px; align-items: stretch; }
.empty-state, .next-card { border: 1px solid var(--ev-color-border); border-radius: var(--ev-radius); background: var(--ev-color-surface); box-shadow: var(--ev-shadow-sm); }
.empty-state { display: flex; align-items: center; gap: 20px; min-height: 290px; padding: 34px; background-image: linear-gradient(135deg, rgba(184, 107, 61, .05), transparent 55%); }
.empty-icon { display: grid; flex: 0 0 54px; place-items: center; width: 54px; height: 54px; border: 1px solid var(--el-color-primary-light-5); border-radius: 50%; color: var(--ev-color-primary); font-size: 30px; font-weight: 300; }
.empty-state h2 { margin: 0; font-size: 20px; }
.empty-state p { margin: 8px 0 0; color: var(--ev-color-muted); }
.next-card { align-self: stretch; padding: 22px; }
.next-label { display: block; margin-bottom: 16px; color: var(--ev-color-primary-dark); font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
.next-card strong { display: block; font-size: 16px; line-height: 1.45; }
.next-card p { margin: 10px 0 0; color: var(--ev-color-muted); font-size: 13px; line-height: 1.65; }

@media (max-width: 860px) {
  .workspace-grid { grid-template-columns: 1fr; }
  .next-card { min-height: 0; }
}

@media (max-width: 520px) {
  .page-heading { display: block; }
  h1 { font-size: 28px; }
  .empty-state { min-height: 230px; padding: 24px; }
}
</style>
