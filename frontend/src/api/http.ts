/** 调用后端 /api 的统一入口：带上会话 cookie，把错误响应转成 ApiError。 */

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

const CJK = /[\u4e00-\u9fff]/

/**
 * 把任意错误转成给老师看的中文提示。界面上显示服务端错误一律经过这里。
 * - 422 validation_error：自定义校验器给的中文消息原样显示（去掉 pydantic 加的 "Value error, " 前缀）；
 *   pydantic 自带的英文消息换成通用中文提示
 * - 其他 ApiError：显示后端给的 message
 * - 其他异常：通用提示
 */
export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === 'validation_error') {
      return CJK.test(e.message) ? e.message.replace(/^Value error, /, '') : '提交的内容不符合要求，请检查后重试'
    }
    return e.message
  }
  return '操作失败，请稍后重试'
}

type ValidationItem = { type?: string; loc?: unknown[]; msg?: string }
type ErrorBody = { detail?: { code?: string; message?: string } | ValidationItem[] | string }

function toApiError(status: number, body: ErrorBody | null): ApiError {
  const detail = body?.detail
  // FastAPI 请求校验失败：422 + detail 为错误列表
  if (Array.isArray(detail)) {
    return new ApiError(status, 'validation_error', detail[0]?.msg ?? '提交的内容不符合要求')
  }
  // 业务错误：detail 为 {code, message}
  if (detail && typeof detail === 'object' && detail.code) {
    return new ApiError(status, detail.code, detail.message ?? detail.code)
  }
  return new ApiError(status, 'http_error', `请求失败（${status}）`)
}

type AuthFailureHandler = (e: ApiError, path: string) => void

let authFailureHandler: AuthFailureHandler | null = null

/**
 * 登录状态在使用中失效时的回调（例如会话过期、账号被停用、被取消管理员）。
 * 由 main.ts 注册，负责更新登录状态并跳到合适的页面；传 null 取消。
 */
export function setAuthFailureHandler(fn: AuthFailureHandler | null): void {
  authFailureHandler = fn
}

// 这几个接口自己处理 401/403（登录失败、注册关闭、查询登录状态），不触发回调
const AUTH_FLOW_PATHS = new Set(['/api/auth/login', '/api/auth/register', '/api/auth/me'])
const ACCOUNT_403_CODES = new Set(['account_pending', 'account_rejected', 'account_disabled', 'forbidden'])

function isAuthFailure(e: ApiError): boolean {
  return (e.status === 401 && e.code === 'not_authenticated') || (e.status === 403 && ACCOUNT_403_CODES.has(e.code))
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, credentials: 'same-origin' }
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }

  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    throw new ApiError(0, 'network_error', '无法连接服务器，请检查网络后重试')
  }

  if (res.status === 204) {
    return undefined as T
  }

  const text = await res.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }

  if (!res.ok) {
    const err = toApiError(res.status, data as ErrorBody | null)
    if (authFailureHandler && isAuthFailure(err) && !AUTH_FLOW_PATHS.has(path)) {
      authFailureHandler(err, path)
    }
    // 回调只负责跳转；调用方照常拿到错误
    throw err
  }
  return data as T
}
