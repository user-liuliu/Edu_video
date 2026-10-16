<!-- 编辑一个可选值：值、显示名称；教材版本另有"适用科目"。新增和修改共用 -->
<script setup lang="ts">
import type { FormInstance, FormItemRule } from 'element-plus'
import { reactive, ref, watch } from 'vue'
import type { FieldOption } from '../../api/admin'

const props = defineProps<{
  /** 弹窗标题，例如"添加可选值：科目" */
  title: string
  /** 要修改的可选值；新增时为 null */
  option: FieldOption | null
  /** 同一项里其他可选值的 value，用来检查重复 */
  otherValues: string[]
  /** 教材版本才传：科目的可选值，用于"适用科目"多选 */
  subjectOptions?: FieldOption[]
}>()

const visible = defineModel<boolean>({ required: true })

const emit = defineEmits<{
  save: [opt: FieldOption]
  remove: []
}>()

const formRef = ref<FormInstance>()
const form = reactive({ value: '', label: '', subjects: [] as string[] })

// 每次打开都从传入的可选值重新填写
watch(visible, (open) => {
  if (!open) return
  form.value = props.option?.value ?? ''
  form.label = props.option?.label ?? ''
  form.subjects = [...(props.option?.subjects ?? [])]
  formRef.value?.clearValidate()
})

const rules: Record<string, FormItemRule[]> = {
  value: [
    {
      trigger: 'blur',
      validator: (_rule, v: string, cb) => {
        const value = (v ?? '').trim()
        if (!value) return cb(new Error('请输入值'))
        if (props.otherValues.includes(value)) return cb(new Error('这个值已经存在'))
        cb()
      },
    },
  ],
  label: [{ trigger: 'blur', validator: (_r, v: string, cb) => (v?.trim() ? cb() : cb(new Error('请输入显示名称'))) }],
}

async function onSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  emit('save', {
    value: form.value.trim(),
    label: form.label.trim(),
    subjects: props.subjectOptions && form.subjects.length > 0 ? [...form.subjects] : null,
  })
  visible.value = false
}

function onRemove() {
  emit('remove')
  visible.value = false
}
</script>

<template>
  <el-dialog v-model="visible" :title="title" width="440px">
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="onSave">
      <el-form-item label="值" prop="value">
        <el-input v-model="form.value" aria-describedby="option-value-hint" />
        <p id="option-value-hint" class="ev-muted hint">保存到配置里的值，例如"数学""5"</p>
      </el-form-item>
      <el-form-item label="显示名称" prop="label">
        <el-input v-model="form.label" />
      </el-form-item>
      <el-form-item v-if="subjectOptions" label="适用科目">
        <el-select v-model="form.subjects" multiple clearable placeholder="所有科目" aria-describedby="option-subjects-hint">
          <el-option v-for="s in subjectOptions" :key="s.value" :value="s.value" :label="s.label" />
        </el-select>
        <p id="option-subjects-hint" class="ev-muted hint">留空表示适用于所有科目</p>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button v-if="option" type="danger" plain class="remove" @click="onRemove">删除</el-button>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="onSave">确定</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint {
  margin: 4px 0 0;
  line-height: 1.5;
}

.el-form-item.is-error .hint {
  display: none;
}

.remove {
  float: left;
}
</style>
