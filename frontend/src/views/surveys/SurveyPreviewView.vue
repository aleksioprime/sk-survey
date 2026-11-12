<script setup>
import { RouterLink, useRoute } from 'vue-router'
import SurveyPassView from '@/views/public/SurveyPassView.vue'

defineProps({ id: { type: String, required: true } })
const route = useRoute()
</script>

<template>
  <div class="grid gap-4">
    <div class="flex items-center justify-between gap-3 rounded-card border border-brand-200 bg-brand-50 px-3 py-2.5 sm:px-4">
      <p class="min-w-0 text-sm font-medium text-brand-800">Предпросмотр. Ответы не сохраняются.</p>
      <RouterLink
        :to="{ name: 'survey', params: { id }, query: route.query }"
        class="inline-flex min-h-10 shrink-0 items-center rounded-control border border-line bg-surface px-3 text-sm font-medium text-ink hover:bg-brand-100"
      >
        Вернуться
      </RouterLink>
    </div>
    <section aria-label="Страница участника" class="-mx-2 min-w-0 overflow-hidden rounded-card border border-line bg-canvas shadow-sm sm:mx-0">
      <SurveyPassView :token="id" preview />
    </section>
  </div>
</template>
