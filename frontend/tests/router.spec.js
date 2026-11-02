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

  it('главная ведёт авторов к опросам, остальных к результатам', () => {
    expect(resolveAccess(route('home'), { isAuthenticated: true, canCreateSurveys: true })).toEqual({ name: 'surveys' })
    expect(resolveAccess(route('home'), { isAuthenticated: true, canCreateSurveys: false })).toEqual({ name: 'publishings' })
  })

  it('конструктор только для авторов', () => {
    const auth = { isAuthenticated: true, canCreateSurveys: false }
    expect(resolveAccess(route('surveys', { creator: true }), auth)).toEqual({ name: 'publishings' })
  })
})
