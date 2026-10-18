import type { CurrentUser } from '../api/auth'

export type GuardTarget = {
  name: string
  meta: { public?: boolean; admin?: boolean }
}

/**
 * 决定一次导航是否放行。纯函数，便于单独测试。
 * - 未登录：只能进 public 页面，其余去登录页
 * - 已登录但账号不是 active：只能停在 account-status
 * - active：管理员仅进入管理页面，其他入口回页面配置；老师默认进入首页，不能进入管理页面
 */
export function decideRoute(to: GuardTarget, user: CurrentUser | null): true | { name: string } {
  if (!user) {
    return to.meta.public ? true : { name: 'login' }
  }
  if (user.status !== 'active') {
    return to.name === 'account-status' ? true : { name: 'account-status' }
  }
  if (user.role === 'admin') {
    return to.meta.admin ? true : { name: 'admin-page-config' }
  }
  if (to.meta.public || to.name === 'account-status') {
    return { name: 'home' }
  }
  if (to.meta.admin) {
    return { name: 'home' }
  }
  return true
}
