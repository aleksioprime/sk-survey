/**
 * Маршрутизация приложения.
 *
 * /s/:token          — страница прохождения опроса по публичному токену
 * /s/:token/complete — страница благодарности после отправки
 * /                  — заглушка (404), т.к. приложение анонимное без главной
 */

import { createRouter, createWebHistory } from 'vue-router'

import SurveyView from '@/views/SurveyView.vue'
import SurveyCompleteView from '@/views/SurveyCompleteView.vue'
import NotFoundView from '@/views/NotFoundView.vue'

const routes = [
  {
    path: '/s/:token',
    name: 'survey',
    component: SurveyView,
    props: true,
  },
  {
    path: '/s/:token/complete',
    name: 'survey-complete',
    component: SurveyCompleteView,
    props: true,
  },
  {
    path: '/',
    name: 'home',
    component: NotFoundView,
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

export default router
