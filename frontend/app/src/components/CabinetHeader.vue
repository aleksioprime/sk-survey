<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const isCabinetRoute = computed(() => route.path.startsWith('/cabinet'))
const userLabel = computed(() => auth.user?.nickname || auth.user?.email || 'Пользователь')

async function logout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <header class="sticky top-0 z-20 border-b border-slate-200/80 bg-white/85 backdrop-blur">
    <div class="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-4">
      <router-link to="/" class="font-semibold text-slate-800 no-underline">SK Опросы</router-link>

      <div class="flex items-center gap-2">
        <router-link
          v-if="auth.isAuthenticated && !isCabinetRoute"
          to="/cabinet"
          class="btn-outline !px-4 !py-2"
        >
          Кабинет
        </router-link>

        <template v-if="auth.isAuthenticated">
          <div class="hidden text-right sm:block">
            <p class="text-sm font-medium text-slate-800">{{ userLabel }}</p>
            <p v-if="auth.roleName" class="text-xs text-muted">{{ auth.roleName }}</p>
          </div>
          <button class="btn-outline !px-4 !py-2" @click="logout">Выйти</button>
        </template>
      </div>
    </div>
  </header>
</template>
