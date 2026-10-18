<!-- 页面配置：老师"新建视频"页面上每个选项的可见性、默认值和可选值；下方是生成参数 -->
<script setup lang="ts">
import { ElMessage, type FormInstance } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  getFormFields,
  getGenerationParams,
  putFormFields,
  putGenerationParams,
  type FieldConfig,
  type FieldKey,
  type FieldOption,
  type FormFieldsConfig,
  type GenerationParams,
} from '../../api/admin'
import { errorText } from '../../api/http'
import OptionDialog from './OptionDialog.vue'
import {
  OPTION_FIELDS,
  addOption,
  cloneConfig,
  fieldOf,
  removeOption,
  setDefaultsBySubject,
  updateOption,
} from './formFieldsEdit'

// ---------- 加载 ----------

const loading = ref(true)
const loadError = ref('')
/** 正在编辑的配置（加载结果的深拷贝），保存时整份提交 */
const cfg = ref<FormFieldsConfig | null>(null)
const params = ref<GenerationParams | null>(null)

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [fields, p] = await Promise.all([getFormFields(), getGenerationParams()])
    cfg.value = cloneConfig(fields)
    params.value = { ...p }
  } catch (e) {
    loadError.value = errorText(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const isOptionField = (key: FieldKey) => OPTION_FIELDS.includes(key)
const subjectOptions = computed(() => (cfg.value ? (fieldOf(cfg.value, 'subject')?.options ?? []) : []))

function subjectLabel(value: string) {
  return subjectOptions.value.find((o) => o.value === value)?.label ?? value
}

// ---------- 保存 ----------

const savingFields = ref(false)
const savingParams = ref(false)

async function saveFields() {
  if (!cfg.value || savingFields.value) return
  savingFields.value = true
  try {
    cfg.value = cloneConfig(await putFormFields(cloneConfig(cfg.value)))
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(errorText(e))
  } finally {
    savingFields.value = false
  }
}

const paramsForm = ref<FormInstance>()

async function saveParams() {
  if (!params.value || savingParams.value) return
  const valid = await paramsForm.value?.validate().catch(() => false)
  if (!valid) return
  savingParams.value = true
  try {
    params.value = { ...(await putGenerationParams({ ...params.value })) }
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(errorText(e))
  } finally {
    savingParams.value = false
  }
}

// ---------- 可选值编辑弹窗 ----------

const optionDialog = reactive({
  open: false,
  key: 'subject' as FieldKey,
  /** 正在修改的可选值下标；新增时为 -1 */
  index: -1,
})

const dialogField = computed(() => (cfg.value ? fieldOf(cfg.value, optionDialog.key) : undefined))
const dialogOption = computed(() => dialogField.value?.options[optionDialog.index] ?? null)
const dialogOtherValues = computed(() =>
  (dialogField.value?.options ?? []).filter((_, i) => i !== optionDialog.index).map((o) => o.value),
)
const dialogTitle = computed(
  () => `${optionDialog.index < 0 ? '添加可选值' : '编辑可选值'}：${dialogField.value?.label ?? ''}`,
)

function openOption(f: FieldConfig, index: number) {
  optionDialog.key = f.key
  optionDialog.index = index
  optionDialog.open = true
}

function onOptionSave(opt: FieldOption) {
  if (!cfg.value) return
  if (optionDialog.index < 0) addOption(cfg.value, optionDialog.key, opt)
  else updateOption(cfg.value, optionDialog.key, optionDialog.index, opt)
}

function onOptionRemove() {
  if (cfg.value && optionDialog.index >= 0) removeOption(cfg.value, optionDialog.key, optionDialog.index)
}

// ---------- 各科目默认版本弹窗 ----------

const bySubject = reactive({ open: false, draft: {} as Record<string, string | undefined> })

const editionField = computed(() => (cfg.value ? fieldOf(cfg.value, 'textbook_edition') : undefined))

/** 某个科目能选的教材版本：适用科目为空（所有科目）或包含这个科目的 */
function editionsFor(subject: string) {
  return (editionField.value?.options ?? []).filter((o) => !o.subjects || o.subjects.includes(subject))
}

function openBySubject() {
  bySubject.draft = { ...(editionField.value?.default_by_subject ?? {}) }
  bySubject.open = true
}

function saveBySubject() {
  if (cfg.value) setDefaultsBySubject(cfg.value, 'textbook_edition', bySubject.draft)
  bySubject.open = false
}

// ---------- 生成参数 ----------

type NumberParam = Exclude<keyof GenerationParams, 'long_term_memory_enabled'>

/** 上下限和后端 GenerationParams 一致 */
const NUMBER_PARAMS: { key: NumberParam; label: string; min: number; max: number; unit?: string }[] = [
  { key: 'max_concurrent_jobs', label: '同时生成的任务数', min: 1, max: 20 },
  { key: 'max_retries', label: '失败重试次数', min: 0, max: 5 },
  { key: 'duration_tolerance_pct', label: '时长允许偏差', min: 5, max: 50, unit: '%' },
]

</script>

<template>
  <div v-loading="loading" class="page-config">
    <h2 class="sr-only">页面配置</h2>
    <el-alert v-if="loadError" type="error" :title="loadError" :closable="false" show-icon />

    <section v-if="cfg" class="block" aria-labelledby="fields-title">
      <div class="block-head">
        <div>
          <h3 id="fields-title">新建视频页面选项</h3>
          <p class="ev-muted desc">控制老师在"新建视频"页面能看到哪些选项。隐藏的选项老师看不到，系统直接用默认值。</p>
        </div>
        <el-button type="primary" :loading="savingFields" :disabled="savingFields" @click="saveFields">保存</el-button>
      </div>

      <div class="ev-table-wrap">
        <table class="ev-table">
          <thead>
            <tr>
              <th scope="col">选项</th>
              <th scope="col">老师可见</th>
              <th scope="col">默认值</th>
              <th scope="col">可选值</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in cfg.fields" :key="f.key">
              <th scope="row">{{ f.label }}</th>
              <td class="visible-cell">
                <template v-if="f.key === 'prompt'">
                  <el-switch :model-value="true" disabled :aria-label="`${f.label}：老师可见`" />
                  <span class="ev-muted">必填，不能隐藏</span>
                </template>
                <el-switch v-else v-model="f.visible" :aria-label="`${f.label}：老师可见`" />
              </td>

              <!-- 配音声音：音色来自模型配置里的 tts 一项 -->
              <td v-if="f.key === 'voice'" colspan="2" class="ev-muted">音色在模型配置中维护</td>
              <template v-else>
                <td class="default-cell">
                  <el-switch
                    v-if="f.key === 'web_search'"
                    :model-value="f.default === true"
                    :aria-label="`${f.label}：默认开启`"
                    active-text="默认开启"
                    @update:model-value="(v: string | number | boolean) => (f.default = Boolean(v))"
                  />
                  <el-select
                    v-else-if="isOptionField(f.key)"
                    v-model="f.default"
                    :aria-label="`${f.label}：默认值`"
                    class="default-select"
                  >
                    <el-option v-for="o in f.options" :key="o.value" :value="o.value" :label="o.label" />
                  </el-select>
                  <span v-else class="ev-muted">—</span>
                </td>
                <td>
                  <div v-if="isOptionField(f.key)" class="chips">
                    <span v-for="(o, i) in f.options" :key="o.value" class="chip-wrap">
                      <el-button size="small" round :aria-label="`${o.label}（编辑可选值）`" @click="openOption(f, i)">
                        {{ o.label }}
                      </el-button>
                      <span v-if="f.key === 'textbook_edition' && o.subjects" class="ev-muted chip-note">
                        {{ o.subjects.map(subjectLabel).join('、') }}
                      </span>
                    </span>
                    <el-button size="small" round type="primary" plain :aria-label="`+ 添加${f.label}的可选值`" @click="openOption(f, -1)">
                      + 添加
                    </el-button>
                    <el-button v-if="f.key === 'textbook_edition'" size="small" link type="primary" @click="openBySubject">
                      各科目默认版本
                    </el-button>
                  </div>
                  <span v-else class="ev-muted">—</span>
                </td>
              </template>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="params" class="block" aria-labelledby="params-title">
      <div class="block-head">
        <div>
          <h3 id="params-title">生成参数</h3>
          <p class="ev-muted desc">只有管理员能看到和修改，老师的页面上不显示。</p>
        </div>
        <el-button type="primary" :loading="savingParams" :disabled="savingParams" @click="saveParams">保存</el-button>
      </div>

      <el-form ref="paramsForm" :model="params" label-position="top" class="params" @submit.prevent="saveParams">
        <el-form-item v-for="p in NUMBER_PARAMS" :key="p.key" :label="p.label" :prop="p.key">
          <el-input-number v-model="params[p.key]" :min="p.min" :max="p.max" :step="1" step-strictly value-on-clear="min" />
          <span class="ev-muted range">{{ p.min }}–{{ p.max }}{{ p.unit ?? '' }}</span>
        </el-form-item>
        <el-form-item label="长期记忆" class="memory">
          <el-switch v-model="params.long_term_memory_enabled" aria-label="长期记忆" />
          <span class="ev-muted range">关闭后不再读取和记录老师的偏好</span>
        </el-form-item>
      </el-form>
    </section>

    <OptionDialog
      v-model="optionDialog.open"
      :title="dialogTitle"
      :option="dialogOption"
      :other-values="dialogOtherValues"
      :subject-options="optionDialog.key === 'textbook_edition' ? subjectOptions : undefined"
      @save="onOptionSave"
      @remove="onOptionRemove"
    />

    <el-dialog v-model="bySubject.open" title="各科目默认版本" width="480px">
      <p class="ev-muted by-subject-desc">没有单独设置的科目使用教材版本的默认值。</p>
      <el-form label-position="left" label-width="96px" @submit.prevent="saveBySubject">
        <el-form-item v-for="s in subjectOptions" :key="s.value" :label="s.label">
          <el-select v-model="bySubject.draft[s.value]" clearable placeholder="使用默认值" :aria-label="`${s.label}：默认教材版本`">
            <el-option v-for="o in editionsFor(s.value)" :key="o.value" :value="o.value" :label="o.label" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bySubject.open = false">取消</el-button>
        <el-button type="primary" @click="saveBySubject">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-config {
  min-height: 200px;
}

.block + .block {
  margin-top: 36px;
}

.block-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.block-head h3 {
  font-size: 17px;
}

.desc {
  margin: 4px 0 0;
}

.visible-cell {
  white-space: nowrap;
}

.visible-cell .ev-muted {
  margin-left: 8px;
}

.default-select {
  width: 160px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.chips .el-button + .el-button {
  margin-left: 0;
}

.chip-wrap {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.chip-note {
  font-size: 12px;
}

.params {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0 24px;
  padding: 20px 20px 4px;
  border: 1px solid var(--ev-color-border);
  border-radius: var(--ev-radius);
  background: var(--ev-color-surface);
}

.range {
  margin-left: 8px;
}

.by-subject-desc {
  margin: 0 0 16px;
}
</style>
