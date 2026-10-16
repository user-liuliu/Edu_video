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
    throw toApiError(res.status, data as ErrorBody | null)
  }
  return data as T
}
