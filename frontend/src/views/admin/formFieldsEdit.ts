/**
 * 页面配置的编辑操作：增删改可选值时，把引用这个值的地方（默认值、各科目默认版本、
 * 教材版本的适用科目）一起改掉，免得保存时才被后端以"默认值必须在可选值中"拒绝。
 * 这些函数直接修改传入的配置（页面上编辑的是一份深拷贝）。
 */
import type { FieldConfig, FieldKey, FieldOption, FormFieldsConfig } from '../../api/admin'

/** 有可选值列表、需要在后台编辑的表单项（和后端 OPTION_FIELDS 一致） */
export const OPTION_FIELDS: readonly FieldKey[] = [
  'subject',
  'grade',
  'textbook_edition',
  'duration',
  'aspect_ratio',
  'style',
]

export function cloneConfig<T>(v: T): T {
  // 页面上的数据是 reactive 代理，structuredClone 不能处理；配置本身就是 JSON
  return JSON.parse(JSON.stringify(v)) as T
}

export function fieldOf(cfg: FormFieldsConfig, key: FieldKey): FieldConfig | undefined {
  return cfg.fields.find((f) => f.key === key)
}

/** 空数组表示"适用于所有科目"，按后端约定发 null */
export function normalizeSubjects(subjects: string[] | null | undefined): string[] | null {
  return subjects && subjects.length > 0 ? [...subjects] : null
}

export function addOption(cfg: FormFieldsConfig, key: FieldKey, opt: FieldOption): void {
  const f = fieldOf(cfg, key)
  if (!f) return
  f.options.push({ value: opt.value, label: opt.label, subjects: normalizeSubjects(opt.subjects) })
  // 列表原来是空的：新加的值直接作为默认值
  if (typeof f.default !== 'string' || f.default === '') f.default = opt.value
}

/** 修改第 index 个可选值；value 改了的话，同步改掉所有引用旧值的地方 */
export function updateOption(cfg: FormFieldsConfig, key: FieldKey, index: number, opt: FieldOption): void {
  const f = fieldOf(cfg, key)
  const old = f?.options[index]
  if (!f || !old) return
  f.options[index] = { value: opt.value, label: opt.label, subjects: normalizeSubjects(opt.subjects) }
  if (old.value === opt.value) return

  if (f.default === old.value) f.default = opt.value
  for (const [subject, v] of Object.entries(f.default_by_subject)) {
    if (v === old.value) f.default_by_subject[subject] = opt.value
  }
  if (key === 'subject') renameSubject(cfg, old.value, opt.value)
}

/** 删除第 index 个可选值；默认值指向它时改成剩下的第一个，其他引用一起删掉 */
export function removeOption(cfg: FormFieldsConfig, key: FieldKey, index: number): void {
  const f = fieldOf(cfg, key)
  const old = f?.options[index]
  if (!f || !old) return
  f.options.splice(index, 1)

  if (f.default === old.value) f.default = f.options[0]?.value ?? null
  for (const [subject, v] of Object.entries(f.default_by_subject)) {
    if (v === old.value) delete f.default_by_subject[subject]
  }
  if (key === 'subject') removeSubject(cfg, old.value)
}

function renameSubject(cfg: FormFieldsConfig, from: string, to: string): void {
  for (const f of cfg.fields) {
    for (const o of f.options) {
      if (o.subjects) o.subjects = o.subjects.map((s) => (s === from ? to : s))
    }
    if (from in f.default_by_subject) {
      f.default_by_subject[to] = f.default_by_subject[from]
      delete f.default_by_subject[from]
    }
  }
}

function removeSubject(cfg: FormFieldsConfig, subject: string): void {
  for (const f of cfg.fields) {
    for (const o of f.options) {
      // 删到一个不剩就变成"适用于所有科目"，和多选框留空的含义一致
      if (o.subjects) o.subjects = normalizeSubjects(o.subjects.filter((s) => s !== subject))
    }
    delete f.default_by_subject[subject]
  }
}

/** 设置各科目默认版本；没选的科目不写进去 */
export function setDefaultsBySubject(cfg: FormFieldsConfig, key: FieldKey, map: Record<string, string | undefined>): void {
  const f = fieldOf(cfg, key)
  if (!f) return
  const next: Record<string, string> = {}
  for (const [subject, v] of Object.entries(map)) {
    if (v) next[subject] = v
  }
  f.default_by_subject = next
}
