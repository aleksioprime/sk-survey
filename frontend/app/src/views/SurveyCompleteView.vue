<!--
  SurveyCompleteView — страница благодарности после отправки опроса.
  Использует данные из Pinia-стора (уже загружены в ходе опроса) — без повторных API-запросов.
-->
<script setup>
import { computed } from 'vue'
import { useSurveyStore } from '@/stores/survey'

defineProps({
  token: { type: String, required: true },
})

const store = useSurveyStore()

const thankYouText = computed(() =>
  store.survey?.thank_you_text || 'Ваши ответы успешно отправлены. Благодарим за участие в опросе!',
)
</script>

<template>
  <div class="flex min-h-screen items-center justify-center px-4">
    <div class="glass-panel w-full max-w-lg p-8 text-center">
      <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
        <svg class="h-8 w-8 text-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>

      <h1 class="text-xl font-bold text-slate-800">Спасибо!</h1>

      <p class="mt-3 text-sm text-muted leading-relaxed break-words">
        {{ thankYouText }}
      </p>
    </div>
  </div>
</template>
