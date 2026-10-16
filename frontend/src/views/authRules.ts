/** 注册、登录表单的前端校验规则，和后端 app/auth/schemas.py 的规则保持一致。 */
import type { FormItemRule } from 'element-plus'

const USERNAME_PATTERN = /^[A-Za-z0-9_\u4e00-\u9fff]+$/
const USERNAME_MIN = 3
const USERNAME_MAX = 32
const PASSWORD_MIN = 8
const PASSWORD_MAX = 128

export const USERNAME_HINT = `用户名为 ${USERNAME_MIN}–${USERNAME_MAX} 位，只能包含字母、数字、下划线和汉字`
export const PASSWORD_HINT = `密码长度为 ${PASSWORD_MIN}–${PASSWORD_MAX} 位`

/** 按 Unicode 码点计数，和后端 Python 的 len() 一致 */
const charCount = (s: string) => Array.from(s).length

type Validator = NonNullable<FormItemRule['validator']>

function rule(validator: Validator): FormItemRule[] {
  // 有 validator 时 async-validator 只运行它；required 只用来告诉 Element Plus 这是必填项
  return [{ required: true, trigger: 'blur', validator }]
}

/** 用户名：去掉首尾空格后校验长度和字符 */
export const usernameRules = rule((_rule, value: string, callback) => {
  const v = (value ?? '').trim()
  if (!v) return callback(new Error('请输入用户名'))
  const n = charCount(v)
  if (n < USERNAME_MIN || n > USERNAME_MAX || !USERNAME_PATTERN.test(v)) return callback(new Error(USERNAME_HINT))
  callback()
})

/** 注册时的密码：8–128 位，不去空格（后端也不去） */
export const passwordRules = rule((_rule, value: string, callback) => {
  if (!value) return callback(new Error('请输入密码'))
  const n = charCount(value)
  if (n < PASSWORD_MIN || n > PASSWORD_MAX) return callback(new Error(PASSWORD_HINT))
  callback()
})

/**
 * 登录时的密码：只拦下明显不可能正确的短密码。
 * 不限制上限，因为命令行创建的初始管理员密码只要求至少 8 位。
 */
export const loginPasswordRules = rule((_rule, value: string, callback) => {
  if (!value) return callback(new Error('请输入密码'))
  if (charCount(value) < PASSWORD_MIN) return callback(new Error(PASSWORD_HINT))
  callback()
})

/** 确认密码：必须和 getPassword() 返回的密码一致 */
export function confirmRules(getPassword: () => string): FormItemRule[] {
  return rule((_rule, value: string, callback) => {
    if (!value) return callback(new Error('请再次输入密码'))
    if (value !== getPassword()) return callback(new Error('两次输入的密码不一致'))
    callback()
  })
}
