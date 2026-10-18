<!--
  编辑一项模型配置。API key 输入框永远从空开始，不回填任何已保存的内容；
  留空表示不修改，提交时不带 api_key 字段。tts 一项多一个音色列表。
-->
<script setup lang="ts">
import { ElMessage, type FormInstance, type FormItemRule } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'
import { putModelConfig, type ModelConfigUpdate, type ModelConfigView, type Voice } from '../../api/admin'
import { errorText } from '../../api/http'

const props = defineProps<{ config: ModelConfigView | null }>()
const visible = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [cfg: ModelConfigView] }>()

const formRef = ref<FormInstance>()
const form = reactive({
  base_url: '',
  model: '',
  enabled: false,
  api_key: '',
  clear_api_key: false,
  voices: [] as Voice[],
})
const saving = ref(false)
const voiceError = ref('')

const isTts = computed(() => props.config?.purpose === 'tts')
// 走 OpenAI 兼容接口的用途：地址通常要带 /v1
const OPENAI_PURPOSES = new Set(['outline_llm', 'review_llm', 'vision_llm', 'embedding', 'image_gen'])
const baseUrlPlaceholder = computed(() => {
  const purpose = props.config?.purpose ?? ''
  if (purpose === 'tts') return 'https://openspeech.bytedance.com'
  if (purpose === 'web_search') return 'https://api.tavily.com'
  return OPENAI_PURPOSES.has(purpose) ? '例如 https://example.com/v1' : 'https://'
})
const hasSavedKey = computed(() => props.config?.api_key_status !== 'missing')

// 每次打开都按当前配置重新填写；key 一律清空
watch(visible, (open) => {
  const c = props.config
  if (!open || !c) {
    form.api_key = ''
    return
  }
  form.base_url = c.base_url
  form.model = c.model
  form.enabled = c.enabled
  form.api_key = ''
  form.clear_api_key = false
  form.voices = c.voices.map((v) => ({ ...v }))
  voiceError.value = ''
  formRef.value?.clearValidate()
})

const rules: Record<string, FormItemRule[]> = {
  base_url: [
    {
      trigger: 'blur',
      validator: (_r, v: string, cb) => {
        const url = (v ?? '').trim()
        if (url && !/^https?:\/\/.+/i.test(url)) return cb(new Error('接口地址必须以 http:// 或 https:// 开头'))
        cb()
      },
    },
  ],
}

function addVoice() {
  form.voices.push({ speaker_id: '', label: '' })
}

function removeVoice(i: number) {
  form.voices.splice(i, 1)
}

/** 去掉整行空白的音色；有一半没填或 ID 重复时返回错误提示 */
function checkVoices(): { voices: Voice[]; error: string } {
  const voices = form.voices
    .map((v) => ({ speaker_id: v.speaker_id.trim(), label: v.label.trim() }))
    .filter((v) => v.speaker_id || v.label)
  if (voices.some((v) => !v.speaker_id || !v.label)) return { voices, error: '每个音色都要填写音色 ID 和显示名称' }
  const ids = voices.map((v) => v.speaker_id)
  if (new Set(ids).size !== ids.length) return { voices, error: '音色 ID 不能重复' }
  return { voices, error: '' }
}

function buildUpdate(voices: Voice[]): ModelConfigUpdate {
  const upd: ModelConfigUpdate = { base_url: form.base_url.trim(), model: form.model.trim(), enabled: form.enabled }
  // 只有真的填了新 key 才带上 api_key；空白等于没填
  const key = form.api_key.trim()
  if (key) upd.api_key = key
  else if (form.clear_api_key) upd.clear_api_key = true
  if (isTts.value) upd.voices = voices
  return upd
}

async function onSave() {
  const c = props.config
  if (!c || saving.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const { voices, error } = checkVoices()
  voiceError.value = isTts.value ? error : ''
  if (voiceError.value) return

  saving.value = true
  try {
    const saved = await putModelConfig(c.purpose, buildUpdate(voices))
    ElMessage.success('已保存')
    emit('saved', saved)
    visible.value = false
  } catch (e) {
    ElMessage.error(errorText(e))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" :title="`编辑模型配置：${config?.label ?? ''}`" width="560px" @closed="form.api_key = ''">
    <el-form v-if="config" ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="onSave">
      <el-form-item label="接口地址" prop="base_url">
        <el-input v-model="form.base_url" :placeholder="baseUrlPlaceholder" autocomplete="off" :aria-describedby="isTts ? 'tts-url-hint' : undefined" />
        <p v-if="isTts" id="tts-url-hint" class="ev-muted key-status">支持填写 https://openspeech.bytedance.com 或完整接口地址 https://openspeech.bytedance.com/api/v3/tts/create。</p>
        <p v-if="config.purpose === 'web_search'" class="ev-muted key-status">使用 Tavily Search，支持服务根地址或完整 /search 地址。填写 API Key 即可，模型名称留空；测试连接会执行一次最小搜索。</p>
      </el-form-item>
      <el-form-item :label="config.purpose === 'web_search' ? '模型名称（搜索不需要）' : '模型名称'" prop="model">
        <el-input v-model="form.model" autocomplete="off" />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input
          v-model="form.api_key"
          type="password"
          placeholder="留空表示不修改"
          autocomplete="new-password"
          :disabled="form.clear_api_key"
          aria-describedby="api-key-status"
        />
        <div class="key-row">
          <p id="api-key-status" class="ev-muted key-status">
            <template v-if="config?.api_key_status === 'set'">已保存：{{ config.api_key_masked }}</template>
            <span v-else-if="config?.api_key_status === 'undecryptable'" class="key-undecryptable">无法解密，请重新填写</span>
            <template v-else>未设置</template>
          </p>
          <el-checkbox v-model="form.clear_api_key" :disabled="!hasSavedKey || form.api_key.trim() !== ''">
            清除已保存的 Key
          </el-checkbox>
        </div>
        <p v-if="isTts" class="ev-muted key-status">
          使用火山引擎新版语音控制台「API Key 管理」中的 Key（X-Api-Key），不能直接填写旧版 Access Token。
          请确认当前项目已开通所填模型对应的音频生成服务；403 / 45000030 且提示 requested resource not granted 表示资源未授权。
          <a href="https://console.volcengine.com/speech/new/setting/apikeys?projectName=default." target="_blank" rel="noopener noreferrer">打开 API Key 管理</a>
        </p>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" aria-label="启用" />
      </el-form-item>

      <fieldset v-if="isTts" class="voices">
        <legend>音色列表</legend>
        <p class="ev-muted voices-desc">老师在"新建视频"页面的"配音声音"从这里选择。</p>
        <table v-if="form.voices.length" class="voice-table">
          <thead>
            <tr>
              <th scope="col">音色 ID</th>
              <th scope="col">显示名称</th>
              <th scope="col"><span class="sr-only">操作</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(v, i) in form.voices" :key="i">
              <td><el-input v-model="v.speaker_id" :aria-label="`音色 ID ${i + 1}`" autocomplete="off" /></td>
              <td><el-input v-model="v.label" :aria-label="`显示名称 ${i + 1}`" autocomplete="off" /></td>
              <td>
                <el-button link type="danger" :aria-label="`删除第 ${i + 1} 个音色`" @click="removeVoice(i)">删除</el-button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="voiceError" class="voice-error" role="alert">{{ voiceError }}</p>
        <el-button size="small" @click="addVoice">添加音色</el-button>
      </fieldset>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="saving" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.key-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  margin-top: 4px;
}

.key-status {
  margin: 0;
}

.key-undecryptable {
  color: var(--ev-color-danger);
}

.voices {
  margin: 0;
  padding: 12px 16px 16px;
  border: 1px solid var(--ev-color-border);
  border-radius: var(--ev-radius);
}

.voices legend {
  padding: 0 4px;
  font-weight: 600;
}

.voices-desc {
  margin: 0 0 8px;
}

.voice-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 8px;
}

.voice-table th {
  padding: 4px 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ev-color-muted);
  text-align: left;
}

.voice-table td {
  padding: 4px 6px;
}

.voice-error {
  margin: 0 0 8px;
  color: var(--ev-color-danger);
}
</style>
