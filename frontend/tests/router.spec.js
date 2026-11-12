import { describe, expect, it } from 'vitest'
import { resolveAccess } from '@/router'

const route = (name, meta = {}) => ({ name, meta, fullPath: `/${name}` })

describe('resolveAccess', () => {
  it('пускает на прохождение опроса без входа', () => {
    expect(resolveAccess(route('survey-pass', { public: true }), { isAuthenticated: false })).toBe(true)
  })

  it('отправляет на вход с возвратом', () => {
    expect(resolveAccess(route('publishings'), { isAuthenticated: false })).toEqual({ name: 'login', query: { next: '/publishings' } })
  })

  it('главная ведёт авторов и наблюдателей в общий список опросов', () => {
    expect(resolveAccess(route('home'), { isAuthenticated: true, canCreateSurveys: true })).toEqual({ name: 'surveys' })
    expect(resolveAccess(route('home'), { isAuthenticated: true, canCreateSurveys: false })).toEqual({ name: 'surveys' })
  })

  it('справочник шкал доступен сотрудникам, а люди только администраторам', () => {
    const auth = { isAuthenticated: true, canCreateSurveys: false }
    expect(resolveAccess(route('scales', { creator: true }), auth)).toEqual({ name: 'surveys' })
    expect(resolveAccess(route('admin-people', { admin: true }), { ...auth, canCreateSurveys: true })).toEqual({ name: 'surveys' })
    expect(resolveAccess(route('admin-people', { admin: true }), { ...auth, isAdmin: true })).toBe(true)
  })

  it('перенаправляет старую ссылку на вкладку публикаций', () => {
    const params = { id: '5' }
    const target = { ...route('survey'), params, query: { tab: 'publishings', question: '2', source: 'link' }, hash: '#list' }
    expect(resolveAccess(target, { isAuthenticated: true })).toEqual({
      name: 'survey-publishings', params, query: { source: 'link' }, hash: '#list', replace: true,
    })
  })
})
