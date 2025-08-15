import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import Login from '@/views/Login.vue'
import Translation from '@/views/Translation.vue'
import LogManagement from '@/components/LogManagement.vue'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/translation',
    name: 'Translation',
    component: Translation,
    meta: { requiresAuth: true }
  },
  {
    path: '/logs',
    name: 'LogManagement',
    component: LogManagement,
    meta: { requiresAuth: true, requiresAdmin: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 导航守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  // 检查是否需要认证
  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!authStore.isAuthenticated) {
      next({
        path: '/login',
        query: { redirect: to.fullPath }
      })
      return
    }
    
    // 检查是否需要管理员权限
    if (to.matched.some(record => record.meta.requiresAdmin)) {
      if (!authStore.isAdmin) {
        next({ path: '/' })
        return
      }
    }
  }
  
  next()
})

export default router 