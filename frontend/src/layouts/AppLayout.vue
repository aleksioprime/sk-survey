<script setup>
import { computed, nextTick, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { BrandMark, errorMessage, OverflowNav, SchoolFooter, UiButton } from 'sk-ui'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const loggingOut = ref(false)
const logoutError = ref('')

const links = computed(() => [
  { to: { name: 'surveys' }, label: 'Опросы' },
  ...(auth.canCreateSurveys || auth.isAdmin
    ? [{ to: { name: route.name === 'admin-people' || !auth.canCreateSurveys ? 'admin-people' : 'scales' }, label: 'Справочники' }]
    : []),
])

async function logout() {
  if (loggingOut.value) return
  loggingOut.value = true
  logoutError.value = ''
  try {
    await auth.logout()
    // Закрываем кабинет до перехода, чтобы его страницы больше не управляли навигацией.
    await nextTick()
    await router.replace({ name: 'login' })
  } catch (error) {
    logoutError.value = errorMessage(error, 'Не удалось выйти. Попробуйте ещё раз.')
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <div v-if="auth.isAuthenticated" class="flex min-h-dvh flex-col">
    <header class="sticky top-0 z-10 border-b border-line bg-surface/90 backdrop-blur print:hidden">
      <div class="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
        <RouterLink :to="{ name: 'home' }" class="shrink-0">
          <BrandMark />
        </RouterLink>
        <OverflowNav :links="links">
          <template #burger-footer>
            <RouterLink :to="{ name: 'profile' }" class="grid rounded-control px-3 py-2.5 hover:bg-brand-50" active-class="bg-brand-100!" title="Профиль и пароль">
              <span class="truncate font-medium text-ink">{{ auth.displayName }}</span>
              <span class="text-xs text-ink-muted">Профиль и пароль</span>
            </RouterLink>
            <UiButton variant="ghost" class="w-full justify-start! px-3!" :loading="loggingOut" @click="logout">Выйти</UiButton>
          </template>
        </OverflowNav>
        <div class="hidden shrink-0 items-center gap-3 text-sm sm:flex">
          <RouterLink
            :to="{ name: 'profile' }"
            class="max-w-32 truncate text-ink-muted hover:text-ink lg:max-w-48"
            title="Профиль и пароль"
          >
            {{ auth.displayName }}
          </RouterLink>
          <UiButton size="sm" variant="ghost" :loading="loggingOut" @click="logout">Выйти</UiButton>
        </div>
      </div>
    </header>
    <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
      <p v-if="logoutError" role="alert" class="mb-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ logoutError }}</p>
      <RouterView :key="$route.path" />
    </main>
    <SchoolFooter />
  </div>
</template>
