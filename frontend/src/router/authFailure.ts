import type { Router } from 'vue-router'
import type { ApiError } from '../api/http'
import { useAuthStore } from '../stores/auth'
import { decideRoute } from './guards'

/**
 * 使用中登录状态失效（见 setAuthFailureHandler）时怎么处理：
 * - 401：会话已失效，按未登录处理，回到登录页（已在公开页面就不动）
 * - 403：账号状态或角色变了，重新查询当前用户，再按路由守卫的规则决定去哪
 * 同一时间只处理一次：页面上几个请求同时失败时不会重复查询和跳转。
 */
export function createAuthFailureHandler(router: Router) {
  let handling: Promise<void> | null = null

  async function handle(e: ApiError): Promise<void> {
    const auth = useAuthStore()
    const current = router.currentRoute.value
    if (e.status === 401) {
      auth.user = null
      auth.loaded = true
      if (!current.meta.public) await router.replace({ name: 'login' })
      return
    }
    try {
      await auth.fetchMe()
    } catch {
      return // 查询失败（例如网络问题）：留在原页面，下次导航时守卫会再查
    }
    const target = decideRoute({ name: String(current.name ?? ''), meta: current.meta }, auth.user)
    if (target !== true) await router.replace(target)
  }

  return (e: ApiError): Promise<void> => {
    if (!handling) {
      handling = handle(e).finally(() => {
        handling = null
      })
    }
    return handling
  }
}
