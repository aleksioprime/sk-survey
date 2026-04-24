/**
 * Хранилище авторизации для личного кабинета результатов.
 *
 * Роль доступа:
 * - Survey (по умолчанию, маркер задаётся через VITE_SURVEY_ROLE)
 * - admin (служебный доступ)
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import nocobaseApi from '@/api/nocobase'
import { AUTH_TOKEN_STORAGE_KEY } from '@/constants/auth'

const SURVEY_ROLE_MARKER = String(import.meta.env.VITE_SURVEY_ROLE || 'Survey').trim()

function normalize(value) {
  return String(value || '').trim().toLowerCase()
}

function roleMatchesMarker(role, marker) {
  const normalizedMarker = normalize(marker)
  if (!normalizedMarker) return false

  const roleValues = [role?.name, role?.title, role?.slug, role?.key]
    .map(normalize)
    .filter(Boolean)

  return roleValues.includes(normalizedMarker)
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || '')
  const user = ref(null)
  const person = ref(null)

  const isAuthenticated = computed(() => token.value !== '')

  const roles = computed(() => {
    const rawRoles = user.value?.roles
    if (!Array.isArray(rawRoles)) return []
    return rawRoles
  })

  const isAdmin = computed(() => {
    return roles.value.some((role) => roleMatchesMarker(role, 'admin'))
  })

  const isSurvey = computed(() => {
    return roles.value.some((role) => roleMatchesMarker(role, SURVEY_ROLE_MARKER))
  })

  const hasAccess = computed(() => isSurvey.value || isAdmin.value)

  const roleName = computed(() => {
    const result = []
    if (isSurvey.value) result.push('Доступ к результатам')
    if (isAdmin.value) result.push('Admin')
    return result.join(' / ') || null
  })

  const currentPerson = computed(() => {
    if (person.value) return person.value

    const userPerson = user.value?.person
    if (Array.isArray(userPerson)) {
      return userPerson[0] || null
    }
    return userPerson || (user.value?.person_id ? { id: user.value.person_id } : null)
  })

  async function login(account, password) {
    const { data } = await nocobaseApi.post('/auth:signIn', { account, password }, {
      headers: { 'X-Authenticator': 'basic' },
    })

    const receivedToken = data?.data?.token
    if (!receivedToken) {
      throw new Error('Token missing in auth response')
    }

    token.value = receivedToken
    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, receivedToken)
    await fetchUser()
  }

  async function fetchUser() {
    const { data } = await nocobaseApi.get('/auth:check')
    user.value = data?.data || null

    if (!currentPerson.value && user.value?.id) {
      try {
        const personRes = await nocobaseApi.get('/persons:list', {
          params: {
            filter: JSON.stringify({ user_id: Number(user.value.id) }),
            pageSize: 1,
          },
        })

        person.value = personRes?.data?.data?.[0] || null
      } catch {
        // person relation is optional, ignore if collection is unavailable or forbidden
      }
    } else {
      person.value = currentPerson.value
    }

    return user.value
  }

  async function logout() {
    try {
      await nocobaseApi.post('/auth:signOut')
    } catch {
      // ignore network/logout errors
    }

    token.value = ''
    user.value = null
    person.value = null
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
  }

  return {
    token,
    user,
    person,
    currentPerson,
    roles,
    isAuthenticated,
    isAdmin,
    isSurvey,
    hasAccess,
    roleName,
    login,
    fetchUser,
    logout,
  }
})
