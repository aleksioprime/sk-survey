<script setup>
import { computed } from 'vue'
import { UiBadge, UiButton } from 'sk-ui'

const props = defineProps({ responses: { type: Object, required: true } })
const emit = defineEmits(['page'])
const pageCount = computed(() => Math.ceil((props.responses.responses + props.responses.in_progress) / props.responses.page_size))
const attemptTime = new Intl.DateTimeFormat('ru-RU', {
  dateStyle: 'short',
  timeStyle: 'medium',
  timeZone: 'Europe/Moscow',
})
</script>

<template>
  <p v-if="!responses.items.length" class="mt-10 text-center text-ink-muted">Ответов пока нет.</p>
  <div v-else class="mt-6 grid gap-3">
    <details v-for="item in responses.items" :key="item.number" class="group min-w-0 rounded-card border border-line bg-surface">
      <summary class="flex min-h-12 cursor-pointer list-none flex-wrap items-center justify-between gap-2 rounded-card px-4 py-3 hover:bg-brand-50">
        <span class="grid min-w-0 gap-1">
          <span class="flex flex-wrap items-center gap-2">
            <span class="font-semibold wrap-anywhere">{{ item.respondent || `Ответ ${item.number}` }}</span>
            <span v-if="item.study_class" class="text-sm text-ink-muted">{{ item.study_class }}</span>
            <UiBadge v-if="!item.submitted" tone="warning">Не отправлен</UiBadge>
          </span>
          <span class="flex flex-wrap gap-x-3 text-xs text-ink-muted">
            <span v-if="item.started_at">Начат <time :datetime="item.started_at">{{ attemptTime.format(new Date(item.started_at)) }}</time> МСК</span>
            <span v-if="item.submitted_at">Отправлен <time :datetime="item.submitted_at">{{ attemptTime.format(new Date(item.submitted_at)) }}</time> МСК</span>
          </span>
        </span>
        <span class="text-sm font-medium text-brand-700">
          <span class="group-open:hidden">Показать ответы</span>
          <span class="hidden group-open:inline">Скрыть ответы</span>
        </span>
      </summary>
      <dl v-if="item.answers.length" class="grid gap-4 border-t border-line px-4 py-4">
        <div v-for="answer in item.answers" :key="answer.question_id" class="grid min-w-0 gap-1">
          <dt class="text-sm font-medium wrap-anywhere">{{ answer.question }}</dt>
          <dd v-if="answer.is_rich_text" class="prose-text rounded-control bg-canvas px-3 py-2 text-sm wrap-anywhere" v-html="answer.text" />
          <dd v-else class="rounded-control bg-canvas px-3 py-2 text-sm wrap-anywhere whitespace-pre-wrap">{{ answer.text }}</dd>
        </div>
      </dl>
      <p v-else class="border-t border-line px-4 py-4 text-sm text-ink-muted">В этом прохождении пока нет ответов.</p>
    </details>
    <nav v-if="pageCount > 1" aria-label="Страницы ответов" class="flex flex-wrap items-center gap-3 text-sm">
      <UiButton size="sm" :disabled="responses.page === 1" @click="emit('page', responses.page - 1)">Назад</UiButton>
      <span class="text-ink-muted">Страница {{ responses.page }} из {{ pageCount }}</span>
      <UiButton size="sm" :disabled="responses.page === pageCount" @click="emit('page', responses.page + 1)">Дальше</UiButton>
    </nav>
  </div>
</template>
