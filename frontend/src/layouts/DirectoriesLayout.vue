<script setup>
import { RouterLink, RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const linkClass = 'border-b-2 border-transparent px-3 py-2 text-sm font-medium text-ink-muted hover:text-ink'
const activeClass = 'border-brand-600! text-brand-700!'
</script>

<template>
  <div class="min-w-0">
    <h1 class="text-2xl font-bold">Справочники</h1>
    <nav aria-label="Справочники" class="mt-5 flex flex-wrap gap-1 border-b border-line">
      <RouterLink v-if="auth.canCreateSurveys" :to="{ name: 'scales' }" :class="linkClass" :exact-active-class="activeClass">Шкалы</RouterLink>
      <RouterLink v-if="auth.isAdmin" :to="{ name: 'admin-people' }" :class="linkClass" :exact-active-class="activeClass">Люди</RouterLink>
    </nav>
    <div class="mt-6 min-w-0"><RouterView /></div>
  </div>
</template>
