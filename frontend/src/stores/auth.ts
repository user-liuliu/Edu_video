import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as authApi from '../api/auth'
import type { CurrentUser } from '../api/auth'
import { ApiError } from '../api/http'
import { clearAllVideoDraftCache } from '../utils/video-draft-cache'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  // 是否已经向后端确认过登录状态
  const loaded = ref(false)
  const avatarRevision = ref(0)
  const avatarUrl = computed(() => {
    const url = user.value?.avatar_url
    return url ? `${url}${url.includes('?') ? '&' : '?'}v=${avatarRevision.value}` : null
  })
  function refreshAvatar() { avatarRevision.value += 1 }

  /** 查询当前登录用户；401 表示未登录，user 置为 null。其他错误继续抛出。 */
  async function fetchMe(): Promise<void> {
    try {
      user.value = await authApi.getMe()
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) throw e
      user.value = null
    }
    loaded.value = true
  }

  async function login(username: string, password: string): Promise<CurrentUser> {
    const me = await authApi.login(username, password)
    user.value = me
    loaded.value = true
    return me
  }

  async function logout(): Promise<void> {
    await authApi.logout()
    await clearAllVideoDraftCache()
    user.value = null
    loaded.value = true
  }

  /** 注册不会登录（账号待审核），所以不改动 user。 */
  function register(username: string, password: string): Promise<CurrentUser> {
    return authApi.register(username, password)
  }

  return { user, loaded, avatarUrl, refreshAvatar, fetchMe, login, logout, register }
})
