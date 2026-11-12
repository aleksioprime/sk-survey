import { createRouter, createWebHistory } from 'vue-router'
import { setUnauthorizedHandler } from 'sk-ui'
import { pageTitle } from '@/brand'
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

export const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/auth/LoginView.vue'), meta: { public: true } },
  {
    path: '/auth/magic',
    name: 'magic-link',
    component: () => import('@/views/auth/MagicLinkView.vue'),
    meta: { public: true },
  },
  {
    path: '/s/:token',
    name: 'survey-pass',
    component: () => import('@/views/public/SurveyPassView.vue'),
    props: true,
    meta: { public: true },
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', name: 'home', component: { render: () => null } },
      {
        path: 'surveys',
        name: 'surveys',
        component: () => import('@/views/surveys/SurveyListView.vue'),
      },
      {
        path: 'surveys/:id',
        name: 'survey',
        component: () => import('@/views/surveys/SurveyEditorView.vue'),
        props: true,
      },
      {
        path: 'surveys/:id/publishings',
        name: 'survey-publishings',
        component: () => import('@/views/publishings/SurveyPublishingsView.vue'),
        props: true,
      },
      {
        path: 'surveys/:id/results',
        name: 'survey-results',
        component: () => import('@/views/publishings/PublishingListView.vue'),
        props: true,
      },
      {
        path: 'surveys/:id/preview',
        name: 'survey-preview',
        component: () => import('@/views/public/SurveyPassView.vue'),
        props: (route) => ({ token: route.params.id, preview: true }),
      },
      { path: 'publishings', redirect: { name: 'surveys' } },
      {
        path: 'publishings/:id',
        name: 'publishing',
        component: () => import('@/views/publishings/PublishingResultsView.vue'),
        props: true,
      },
      { path: 'profile', name: 'profile', component: () => import('@/views/profile/ProfileView.vue') },
      {
        path: 'directories',
        component: () => import('@/layouts/DirectoriesLayout.vue'),
        children: [
          {
            path: '',
            alias: 'scales',
            name: 'scales',
            component: () => import('@/views/scales/ScaleListView.vue'),
            meta: { creator: true },
          },
          {
            path: 'people',
            name: 'admin-people',
            component: () => import('@/views/admin/PeopleView.vue'),
            meta: { admin: true },
          },
        ],
      },
      { path: 'admin/people', redirect: { name: 'admin-people' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: { name: 'home' } },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

/** Проверка доступа к маршруту. Вынесена отдельно, чтобы её можно было протестировать. */
export function resolveAccess(to, auth) {
  if (to.meta.public) return true
  if (!auth.isAuthenticated) return { name: 'login', query: { next: to.fullPath } }
  if (to.name === 'home' || (to.meta.creator && !auth.canCreateSurveys) || (to.meta.admin && !auth.isAdmin)) {
    return { name: 'surveys' }
  }
  if (to.name === 'survey' && to.query?.tab === 'publishings') {
    const query = { ...to.query }
    delete query.tab
    delete query.question
    delete query.section
    return { name: 'survey-publishings', params: to.params, query, hash: to.hash, replace: true }
  }
  return true
}

router.afterEach((to) => {
  // Страницы со своим заголовком (прохождение опроса) ставят его сами
  if (to.name !== 'survey-pass') document.title = pageTitle(to.meta.title)
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.load()
  return resolveAccess(to, auth)
})

setUnauthorizedHandler(() => {
  const auth = useAuthStore()
  auth.setUser(null)
  const current = router.currentRoute.value
  // До завершения первой навигации маршрута ещё нет: доступ решит beforeEach
  if (!current.matched.length || current.meta.public) return
  router.push({ name: 'login', query: { next: current.fullPath } })
})
