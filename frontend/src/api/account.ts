import { request } from './http'
import type { CurrentUser, UserGender } from './auth'

export type ProfileUpdate = { display_name: string | null; gender: UserGender; school: string | null }
export const getProfile = () => request<CurrentUser>('GET', '/api/account/profile')
export const updateProfile = (profile: ProfileUpdate) => request<CurrentUser>('PATCH', '/api/account/profile', profile)
export function uploadAvatar(file: File) {
  const body = new FormData()
  body.append('file', file)
  return request<CurrentUser>('POST', '/api/account/avatar', body)
}
export const removeAvatar = () => request<void>('DELETE', '/api/account/avatar')
export const changePassword = (current_password: string, new_password: string) =>
  request<void>('POST', '/api/account/password', { current_password, new_password })
