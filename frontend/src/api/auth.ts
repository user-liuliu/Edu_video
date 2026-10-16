/** 后端 /api/auth/* 接口。 */
import { request } from './http'

export type CurrentUser = {
  id: string
  username: string
  role: 'teacher' | 'admin'
  status: 'pending' | 'active' | 'rejected' | 'disabled'
}

export function getMe(): Promise<CurrentUser> {
  return request<CurrentUser>('GET', '/api/auth/me')
}

export function login(username: string, password: string): Promise<CurrentUser> {
  return request<CurrentUser>('POST', '/api/auth/login', { username, password })
}

/** 注册后账号处于待审核状态，后端不会建立会话。 */
export function register(username: string, password: string): Promise<CurrentUser> {
  return request<CurrentUser>('POST', '/api/auth/register', { username, password })
}

export function logout(): Promise<void> {
  return request<void>('POST', '/api/auth/logout')
}
