import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { RouterView, createMemoryHistory, createRouter, onBeforeRouteLeave } from 'vue-router'
import * as api from '@/api/auth'
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/auth', () => ({ logout: vi.fn() }))

async function openCabinet() {
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.setUser({ email: 'editor@example.org' })
  auth.canCreateSurveys = true
  auth.hasPassword = true
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        name: 'home',
        component: AppLayout,
        children: [{
          path: 'surveys',
          name: 'surveys',
          component: {
            setup() {
              onBeforeRouteLeave(() => false)
            },
            template: '<p>Список опросов</p>',
          },
        }],
      },
      { path: '/login', name: 'login', component: { template: '<h1>Вход</h1>' } },
    ],
  })
  await router.push('/surveys')
  const wrapper = mount(RouterView, {
    global: { plugins: [pinia, router], stubs: { RouterLink: true, SchoolFooter: true, OverflowNav: true } },
  })
  return { wrapper, router, auth }
}

describe('выход из кабинета', () => {
  it.each([undefined, 401])('закрывает кабинет и показывает вход (ошибка API: %s)', async (status) => {
    if (status) vi.mocked(api.logout).mockRejectedValueOnce({ response: { status } })
    else vi.mocked(api.logout).mockResolvedValueOnce(undefined)
    const { wrapper, router, auth } = await openCabinet()
    try {
      expect(wrapper.text()).toContain('Список опросов')
      await wrapper.get('button').trigger('click')
      await flushPromises()
      expect(router.currentRoute.value.name).toBe('login')
      expect(wrapper.text()).toBe('Вход')
      expect(auth.isAuthenticated).toBe(false)
      expect(auth.canCreateSurveys).toBe(false)
      expect(auth.hasPassword).toBe(false)
    } finally {
      wrapper.unmount()
    }
  })

  it('показывает ошибку и позволяет повторить выход при недоступности сервера', async () => {
    vi.mocked(api.logout).mockRejectedValueOnce(new Error('Network error'))
    const { wrapper, router, auth } = await openCabinet()
    try {
      await wrapper.get('button').trigger('click')
      await flushPromises()
      expect(wrapper.get('[role="alert"]').text()).toContain('Сервер недоступен')
      expect(router.currentRoute.value.name).toBe('surveys')
      expect(auth.isAuthenticated).toBe(true)
      expect(wrapper.get('button').attributes('disabled')).toBeUndefined()
    } finally {
      wrapper.unmount()
    }
  })
})
