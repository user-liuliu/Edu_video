<script setup lang="ts">
defineProps<{ name: string }>()
const paths: Record<string, string> = {
  'chevrons-left': 'm13 7-5 5 5 5m6-10-5 5 5 5',
  'chevrons-right': 'm5 7 5 5-5 5m6-10 5 5-5 5',
  'panel-close': 'M3 4h18v16H3ZM9 4v16m7-12-4 4 4 4',
  'panel-open': 'M3 4h18v16H3ZM9 4v16m4-12 4 4-4 4',
  info: 'M3 12a9 9 0 1 0 18 0 9 9 0 1 0-18 0M12 11v6m0-10v.01',
  make: 'M3 4h18v16H3ZM10 9l5 3-5 3Z',
  videos: 'M5 5h16v16H5ZM16 2H5a3 3 0 0 0-3 3v11m9-6 5 3-5 3Z',
  drafts: 'M4 7h6l2-3h6a2 2 0 0 1 2 2v13H4ZM4 10h16m-11 5h6',
  memory: 'M4 7h16M4 17h16M5 7a3 3 0 1 0 6 0 3 3 0 1 0-6 0m8 10a3 3 0 1 0 6 0 3 3 0 1 0-6 0',
  account: 'M8.5 8a3.5 3.5 0 1 0 7 0 3.5 3.5 0 1 0-7 0M5 21v-2a7 7 0 0 1 14 0v2',
  subject: 'M12 5C9 3 6 3 2 4v15c4-1 7-1 10 1 3-2 6-2 10-1V4c-4-1-7-1-10 1Zm0 0v15',
  textbook_edition: 'M4 3h14a2 2 0 0 1 2 2v16H6a2 2 0 0 1-2-2Zm0 13h16M8 7h8M8 11h6',
  grade: 'm2 9 10-5 10 5-10 5Zm4 2v6q6 5 12 0v-6m4-2v8',
  duration: 'M3 12a9 9 0 1 0 18 0 9 9 0 1 0-18 0M12 7v5l3 2',
  aspect_ratio: 'M3 5h18v14H3ZM7 9h3m-3 0v3m10 3h-3m3 0v-3',
  voice: 'm11 5-5 4H3v6h3l5 4Zm4 3a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14',
  attach: 'm8 12 6-6a3 3 0 0 1 4 4l-8 8a5 5 0 0 1-7-7l8-8m-3 9 4-4',
  globe: 'M3 12a9 9 0 1 0 18 0 9 9 0 1 0-18 0M12 3c-5 5-5 13 0 18 5-5 5-13 0-18ZM3 12h18',
  save: 'M4 3h13l4 4v14H3V3Zm3 0v6h10V3M7 21v-8h10v8',
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  'admin-page-config': 'M3 3h18v18H3ZM3 9h18M9 9v12',
  'admin-model-config': 'm12 2 9 5v10l-9 5-9-5V7Zm0 10L3 7m9 5 9-5m-9 5v10',
  'admin-users': 'M6 8a3 3 0 1 0 6 0 3 3 0 1 0-6 0M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5',
}
</script>
<template>
  <svg class="app-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path :d="paths[name] ?? paths.make"/></svg>
</template>
<style scoped>.app-icon{display:inline-block;width:20px;height:20px;flex:none;vertical-align:middle}</style>
