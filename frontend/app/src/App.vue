<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import CabinetHeader from '@/components/CabinetHeader.vue'

const route = useRoute()
const hideHeader = computed(() => route.meta.hideHeader === true)
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <CabinetHeader v-if="!hideHeader" />
    <main class="flex-1">
      <router-view />
    </main>
    <footer class="py-4 text-center text-xs text-muted">
      Сервисы автоматизации Гимназии Сколково · © {{ new Date().getFullYear() }} Алексей Семочкин
    </footer>
  </div>
</template>
