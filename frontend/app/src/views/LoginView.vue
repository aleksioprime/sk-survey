<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const account = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

function getRedirectTarget() {
  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/')) {
    return redirect
  }
  return '/cabinet'
}

async function handleLogin() {
  loading.value = true
  error.value = ''

  try {
    await auth.login(account.value, password.value)
    await router.push(getRedirectTarget())
  } catch (e) {
    error.value = e?.response?.data?.errors?.[0]?.message || 'Неверный логин или пароль'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-[80vh] items-center justify-center px-4 py-10">
    <form class="glass-panel w-full max-w-md p-8" @submit.prevent="handleLogin">
      <h1 class="text-center text-2xl font-bold text-slate-800">Личный кабинет опросов</h1>
      <p class="mt-2 text-center text-sm text-muted">Вход для сотрудников с доступом к результатам</p>

      <label class="mt-6 block text-sm font-medium text-slate-700" for="account">Логин или email</label>
      <input
        id="account"
        v-model="account"
        type="text"
        required
        autofocus
        class="field-input mt-2"
        placeholder="Введите логин"
      />

      <label class="mt-4 block text-sm font-medium text-slate-700" for="password">Пароль</label>
      <input
        id="password"
        v-model="password"
        type="password"
        required
        class="field-input mt-2"
        placeholder="Введите пароль"
      />

      <p v-if="error" class="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-danger">
        {{ error }}
      </p>

      <button type="submit" :disabled="loading" class="btn-primary mt-6 w-full">
        {{ loading ? 'Вход...' : 'Войти' }}
      </button>
    </form>
  </div>
</template>
