import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const canCreateSurveys = ref(false)
  const hasPassword = ref(false)
  const loaded = ref(false)

  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => !!user.value?.is_superuser)
  const displayName = computed(() => user.value?.person?.short_name || user.value?.email || '')

  async function load(force = false) {
    if (loaded.value && !force) return user.value
    try {
      const me = await api.fetchMe()
      user.value = me.user
      canCreateSurveys.value = me.can_create_surveys
      hasPassword.value = me.has_password
    } catch {
      user.value = null
      canCreateSurveys.value = false
    }
    loaded.value = true
    return user.value
  }

  function setUser(value) {
    user.value = value
    loaded.value = true
  }

  async function logout() {
    try {
      await api.logout()
    } finally {
      user.value = null
      canCreateSurveys.value = false
    }
  }

  return { user, canCreateSurveys, hasPassword, loaded, isAuthenticated, isAdmin, displayName, load, setUser, logout }
})
