/**
 * Маршрутизация приложения.
 *
 * Публичные маршруты:
 * /s/:token                    — прохождение опроса по публичному токену
 * /s/:token/complete           — страница благодарности
 * /                             — главная
 * /login                       — вход в личный кабинет
 *
 * Защищенные маршруты (роль Survey):
 * /cabinet                     — список публикаций опросов
 * /cabinet/publishings/:id     — просмотр результатов конкретной публикации
 */

import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

import HomeView from '@/views/HomeView.vue'
import LoginView from '@/views/LoginView.vue'
import NoAccessView from '@/views/NoAccessView.vue'
import CabinetView from '@/views/CabinetView.vue'
import PublishingResultsView from '@/views/PublishingResultsView.vue'
import SurveyView from '@/views/SurveyView.vue'
import SurveyCompleteView from '@/views/SurveyCompleteView.vue'
import NotFoundView from '@/views/NotFoundView.vue'

const routes = [
  {
    path: '/s/:token',
    name: 'survey',
    component: SurveyView,
    props: true,
    meta: { hideHeader: true },
  },
  {
    path: '/s/:token/complete',
    name: 'survey-complete',
    component: SurveyCompleteView,
    props: true,
    meta: { hideHeader: true },
  },
  {
    path: '/',
    name: 'home',
    component: HomeView,
    meta: { hideHeader: true },
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { hideHeader: true },
  },
  {
    path: '/no-access',
    name: 'no-access',
    component: NoAccessView,
  },
  {
    path: '/cabinet',
    name: 'cabinet',
    component: CabinetView,
    meta: { requiresAuth: true, requiresSurveyAccess: true },
  },
  {
    path: '/cabinet/publishings/:publishingId',
    name: 'publishing-results',
    component: PublishingResultsView,
    props: true,
    meta: { requiresAuth: true, requiresSurveyAccess: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundView,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.name === 'login' && auth.isAuthenticated) {
    if (!auth.user) {
      try {
        await auth.fetchUser()
      } catch {
        await auth.logout()
        return true
      }
    }

    if (auth.hasAccess) {
      const redirect = typeof to.query.redirect === 'string' ? to.query.redirect : '/cabinet'
      if (redirect.startsWith('/')) return redirect
      return '/cabinet'
    }

    return { name: 'no-access' }
  }

  if (!to.meta.requiresAuth) return true

  if (!auth.isAuthenticated) {
    return {
      name: 'login',
      query: { redirect: to.fullPath },
    }
  }

  if (!auth.user) {
    try {
      await auth.fetchUser()
    } catch {
      await auth.logout()
      return {
        name: 'login',
        query: { redirect: to.fullPath },
      }
    }
  }

  if (to.meta.requiresSurveyAccess && !auth.hasAccess) {
    return { name: 'no-access' }
  }

  return true
})

export default router
