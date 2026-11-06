<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { errorMessage, UiBadge } from 'sk-ui'
import { exportUrl, getPublishing, getResults } from '@/api/surveys'
import { QUESTION_TYPES } from '@/utils/questionTypes'

const props = defineProps({ id: { type: String, required: true } })

const publishing = ref(null)
const results = ref(null)
const includeInProgress = ref(false)
const error = ref('')
const textLimit = ref({})

async function load() {
  try {
    results.value = await getResults(props.id, includeInProgress.value)
  } catch (e) {
    error.value = errorMessage(e)
  }
}

onMounted(async () => {
  try {
    publishing.value = await getPublishing(props.id)
  } catch (e) {
    error.value = errorMessage(e)
    return
  }
  await load()
})
watch(includeInProgress, load)

const total = computed(() => (results.value ? results.value.responses + (includeInProgress.value ? results.value.in_progress : 0) : 0))
const maxCount = (items) => Math.max(1, ...items.map((i) => i.count))
const shownTexts = (q) => q.texts.slice(0, textLimit.value[q.question_id] || 10)
const format = (value) => (value == null ? '—' : Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 2 }))
</script>

<template>
  <div>
    <RouterLink :to="{ name: 'publishings' }" class="text-sm text-ink-muted hover:text-ink">← Результаты</RouterLink>
    <p v-if="error" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>

    <template v-if="publishing && results">
      <div class="mt-2 flex flex-wrap items-start gap-4">
        <div class="min-w-0 flex-1">
          <p class="text-sm text-ink-muted">{{ results.survey_title }}</p>
          <h1 class="text-2xl font-bold">{{ results.title }}</h1>
          <p class="mt-2 flex flex-wrap gap-2">
            <UiBadge tone="brand">Ответов: {{ results.responses }}</UiBadge>
            <UiBadge v-if="results.in_progress">Не отправлено: {{ results.in_progress }}</UiBadge>
            <UiBadge>{{ results.is_anonymous ? 'Анонимно' : 'С именами' }}</UiBadge>
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <label class="flex items-center gap-2 text-sm">
            <input v-model="includeInProgress" type="checkbox" class="accent-brand-600" /> Учитывать неотправленные
          </label>
          <a
            :href="exportUrl(props.id, includeInProgress)"
            class="inline-flex h-10 items-center rounded-control bg-brand-600 px-4 font-medium text-white hover:bg-brand-700"
          >
            Скачать Excel
          </a>
          <RouterLink
            v-if="publishing.can_edit"
            :to="{ name: 'survey', params: { id: publishing.survey_id } }"
            class="inline-flex h-10 items-center rounded-control border border-line bg-surface px-4 hover:bg-brand-50"
          >
            Опрос
          </RouterLink>
        </div>
      </div>

      <p v-if="!total" class="mt-10 text-center text-ink-muted">Ответов пока нет.</p>

      <div v-else class="mt-6 grid gap-4">
        <article v-for="(q, index) in results.questions" :key="q.question_id" class="rounded-card border border-line bg-surface p-5">
          <p class="text-xs text-ink-muted">
            {{ index + 1 }} · {{ QUESTION_TYPES[q.question_type] }} · ответили {{ q.answered }}<template v-if="q.skipped">, пропустили {{ q.skipped }}</template>
            <template v-if="!q.is_active"> · вопрос скрыт</template>
          </p>
          <h2 class="mt-1 font-semibold">{{ q.text }}</h2>

          <ul v-if="q.options.length" class="mt-4 grid gap-2">
            <li v-for="option in q.options" :key="option.title" class="grid gap-1">
              <div class="flex justify-between gap-3 text-sm">
                <span>{{ option.title }}</span>
                <span class="shrink-0 tabular-nums text-ink-muted">{{ option.count }} · {{ format(option.percent) }}%</span>
              </div>
              <div class="h-2.5 overflow-hidden rounded-full bg-canvas">
                <div class="h-full rounded-full bg-brand-500" :style="{ width: `${option.percent}%` }" />
              </div>
            </li>
          </ul>

          <template v-if="q.mean != null">
            <dl class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div v-for="(value, label) in { Среднее: q.mean, Медиана: q.median, Минимум: q.min, Максимум: q.max }" :key="label" class="rounded-control bg-canvas p-3">
                <dt class="text-xs text-ink-muted">{{ label }}</dt>
                <dd class="text-lg font-semibold tabular-nums">{{ format(value) }}</dd>
              </div>
            </dl>
            <div v-if="q.distribution.length" class="mt-4 flex h-32 items-end gap-1" role="img" :aria-label="`Распределение ответов: ${q.distribution.map((d) => `${d.value} — ${d.count}`).join(', ')}`">
              <div v-for="item in q.distribution" :key="item.value" class="flex min-w-0 flex-1 flex-col items-center gap-1">
                <span class="text-xs tabular-nums text-ink-muted">{{ item.count || '' }}</span>
                <div class="w-full rounded-t bg-brand-500" :style="{ height: `${(item.count / maxCount(q.distribution)) * 88}px`, minHeight: item.count ? '3px' : '0' }" />
                <span class="text-xs tabular-nums">{{ format(item.value) }}</span>
              </div>
            </div>
            <ul v-if="q.ranges.length" class="mt-4 flex flex-wrap gap-2 text-sm">
              <li v-for="range in q.ranges" :key="range.title" class="rounded-control bg-canvas px-3 py-2">
                {{ range.title }} ({{ range.from_value }}–{{ range.to_value }}): <span class="font-semibold">{{ range.count }}</span> · {{ format(range.percent) }}%
              </li>
            </ul>
          </template>

          <ol v-if="q.ranking.length" class="mt-4 grid gap-2">
            <li v-for="(item, place) in q.ranking" :key="item.id" class="flex items-center gap-3 rounded-control bg-canvas px-3 py-2 text-sm">
              <span class="grid size-7 shrink-0 place-items-center rounded-full bg-brand-600 font-semibold text-white">{{ place + 1 }}</span>
              <span class="flex-1">{{ item.title }}</span>
              <span class="text-ink-muted">средняя позиция {{ format(item.average_rank) }} · первое место {{ item.first_places }}</span>
            </li>
          </ol>

          <template v-if="q.texts.length">
            <ul class="mt-4 grid gap-2">
              <li v-for="text in shownTexts(q)" :key="text.response_id" class="whitespace-pre-line rounded-control bg-canvas px-3 py-2 text-sm">
                <span v-if="q.question_type === 'rich_text'" class="prose-text" v-html="text.text" />
                <template v-else>{{ text.text }}</template>
              </li>
            </ul>
            <button
              v-if="q.texts.length > shownTexts(q).length"
              type="button"
              class="mt-2 text-sm font-medium text-brand-700"
              @click="textLimit = { ...textLimit, [q.question_id]: shownTexts(q).length + 30 }"
            >
              Показать ещё ({{ q.texts.length - shownTexts(q).length }})
            </button>
          </template>
        </article>
      </div>
    </template>
    <p v-else-if="!error" class="mt-4 text-ink-muted" role="status">Загружаем результаты…</p>
  </div>
</template>
