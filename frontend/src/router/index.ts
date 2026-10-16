import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../layouts/AppLayout.vue'
import { useAuthStore } from '../stores/auth'
import { decideRoute } from './guards'

declare module 'vue-router' {
  interface RouteMeta {
    /** 未登录也能访问 */
    public?: boolean
    /** 只有管理员能访问 */
    admin?: boolean
  }
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
    { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue'), meta: { public: true } },
    { path: '/account-status', name: 'account-status', component: () => import('../views/AccountStatusView.vue') },
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', name: 'home', component: () => import('../views/HomeView.vue') },
        {
          path: 'admin',
          name: 'admin',
          component: () => import('../layouts/AdminLayout.vue'),
          meta: { admin: true },
          redirect: { name: 'admin-page-config' },
          children: [
            { path: 'page-config', name: 'admin-page-config', component: () => import('../views/admin/PageConfigTab.vue'), meta: { admin: true } },
            { path: 'model-config', name: 'admin-model-config', component: () => import('../views/admin/ModelConfigTab.vue'), meta: { admin: true } },
            { path: 'users', name: 'admin-users', component: () => import('../views/admin/UsersTab.vue'), meta: { admin: true } },
          ],
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.loaded) {
    try {
      await auth.fetchMe()
    } catch {
      // 后端暂时不可用：按未登录处理，下次导航会再查一次
    }
  }
  return decideRoute({ name: String(to.name ?? ''), meta: to.meta }, auth.user)
})
