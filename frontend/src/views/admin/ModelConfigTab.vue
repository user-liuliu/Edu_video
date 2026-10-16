<!-- 模型配置：每种用途一行，显示接口地址、key 掩码、模型和测试状态；可以编辑和测试连接 -->
<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { listModelConfigs, testModelConfig, type ModelConfigView, type Purpose } from '../../api/admin'
import { errorText } from '../../api/http'
import ModelConfigDialog from './ModelConfigDialog.vue'

const loading = ref(true)
const loadError = ref('')
const configs = ref<ModelConfigView[]>([])

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    configs.value = await listModelConfigs()
  } catch (e) {
    loadError.value = errorText(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

/** 必需项可用：启用、key 正常、地址和模型都填了，且最近一次测试没有失败 */
function usable(c: ModelConfigView) {
  return c.enabled && c.api_key_status === 'set' && !!c.base_url && !!c.model && c.last_test_ok !== false
}

const unavailable = computed(() => configs.value.filter((c) => c.required && !usable(c)))

type Status = { text: string; tone: 'ok' | 'bad' | 'muted' }

function status(c: ModelConfigView): Status {
  if (!c.enabled) return { text: '未启用', tone: 'muted' }
  if (c.last_test_ok === false) return { text: '失败', tone: 'bad' }
  if (c.last_test_ok === true) return { text: '正常', tone: 'ok' }
  return { text: '未测试', tone: 'muted' }
}

function formatTime(iso: string | null) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

// ---------- 测试连接 ----------

/** 联网搜索第 1 部分还没有接入，不能测试 */
const UNTESTABLE: readonly Purpose[] = ['web_search']
const testing = reactive<Partial<Record<Purpose, boolean>>>({})

async function onTest(c: ModelConfigView) {
  if (testing[c.purpose]) return
  testing[c.purpose] = true
  try {
    const result = await testModelConfig(c.purpose)
    if (result.ok) ElMessage.success(result.message)
    else ElMessage.error(result.message)
  } catch (e) {
    ElMessage.error(errorText(e))
  } finally {
    testing[c.purpose] = false
  }
  // 测试结果已记录在服务端，重新读取状态列
  await load()
}

// ---------- 编辑 ----------

const editing = ref<ModelConfigView | null>(null)
const dialogOpen = ref(false)

function onEdit(c: ModelConfigView) {
  editing.value = c
  dialogOpen.value = true
}

function onSaved(saved: ModelConfigView) {
  configs.value = configs.value.map((c) => (c.purpose === saved.purpose ? saved : c))
}
</script>

<template>
  <div v-loading="loading" class="model-config">
    <h2 class="sr-only">模型配置</h2>
    <el-alert v-if="loadError" type="error" :title="loadError" :closable="false" show-icon />

    <template v-if="configs.length">
      <el-alert
        v-if="unavailable.length"
        type="warning"
        title="老师暂时无法新建视频"
        :description="`以下必需的配置还不能用：${unavailable.map((c) => c.label).join('、')}。请填写完整、启用并测试通过。`"
        :closable="false"
        show-icon
        class="availability"
      />
      <el-alert
        v-else
        type="success"
        title="必需的配置都已就绪，老师可以新建视频"
        :closable="false"
        show-icon
        class="availability"
      />

      <div class="ev-table-wrap">
        <table class="ev-table">
          <caption class="sr-only">各用途的模型配置</caption>
          <thead>
            <tr>
              <th scope="col">用途</th>
              <th scope="col">接口地址</th>
              <th scope="col">Key</th>
              <th scope="col">模型</th>
              <th scope="col">状态</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in configs" :key="c.purpose">
              <th scope="row">
                {{ c.label }}
                <span v-if="c.required" class="required">必需</span>
              </th>
              <td class="url">{{ c.base_url || '—' }}</td>
              <td class="key">
                <code v-if="c.api_key_status === 'set'">{{ c.api_key_masked }}</code>
                <span v-else-if="c.api_key_status === 'undecryptable'" class="key-undecryptable">无法解密，请重新填写</span>
                <span v-else class="ev-muted">未设置</span>
              </td>
              <td>{{ c.model || '—' }}</td>
              <td>
                <span :class="['status', `status-${status(c).tone}`]">{{ status(c).text }}</span>
                <p v-if="c.enabled && c.last_test_ok === false && c.last_test_message" class="ev-muted status-detail">
                  {{ c.last_test_message }}
                </p>
                <p v-if="c.enabled && c.last_tested_at" class="ev-muted status-detail">{{ formatTime(c.last_tested_at) }}</p>
              </td>
              <td class="actions">
                <el-button size="small" @click="onEdit(c)">编辑</el-button>
                <el-button
                  size="small"
                  :loading="testing[c.purpose]"
                  :disabled="UNTESTABLE.includes(c.purpose) || testing[c.purpose]"
                  :aria-describedby="UNTESTABLE.includes(c.purpose) ? `untestable-${c.purpose}` : undefined"
                  @click="onTest(c)"
                >
                  测试
                </el-button>
                <p v-if="UNTESTABLE.includes(c.purpose)" :id="`untestable-${c.purpose}`" class="ev-muted status-detail">
                  第 2 部分接入搜索服务后可测试
                </p>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <ModelConfigDialog v-model="dialogOpen" :config="editing" @saved="onSaved" />
  </div>
</template>

<style scoped>
.model-config {
  min-height: 200px;
}

.availability {
  margin-bottom: 16px;
}

.required {
  display: inline-block;
  margin-left: 4px;
  padding: 0 6px;
  font-size: 12px;
  font-weight: 400;
  line-height: 18px;
  color: var(--ev-color-primary);
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 9px;
}

.url {
  max-width: 260px;
  word-break: break-all;
}

.key code {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 13px;
}

.key-undecryptable {
  color: var(--ev-color-danger);
  font-weight: 600;
}

.status {
  white-space: nowrap;
}

.status::before {
  content: '●';
  margin-right: 4px;
}

.status-ok {
  color: var(--ev-color-success);
}

.status-bad {
  color: var(--ev-color-danger);
}

.status-muted {
  color: var(--ev-color-muted);
}

.status-detail {
  margin: 2px 0 0;
  font-size: 12px;
  line-height: 1.5;
}

.actions {
  white-space: nowrap;
}

.actions .status-detail {
  white-space: normal;
  max-width: 160px;
}
</style>
