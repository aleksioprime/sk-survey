<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { errorMessage, SkeletonPage, UiBadge, UiBreadcrumbs, UiButton, UiCard, UiSwitch, useUrlQuery } from 'sk-ui'
import { exportUrl, getIndividualResponses, getPublishing, getResults } from '@/api/surveys'
import SurveyArchiveBadge from '@/components/SurveyArchiveBadge.vue'
import QuestionTypeIcon from '@/components/questions/QuestionTypeIcon.vue'
import ChoiceBreakdown from '@/components/questions/ChoiceBreakdown.vue'
import { QUESTION_TYPES } from '@/utils/questionTypes'
import PublishingResponseList from './PublishingResponseList.vue'

const props = defineProps({ id: { type: String, required: true } })

const publishing = ref(null)
const results = ref(null)
const { route, setQuery } = useUrlQuery()
const includeInProgress = computed({
  get: () => route.query.drafts === '1',
  set: (value) => setQuery({ drafts: value ? '1' : undefined, page: undefined }),
})
const showResponses = computed(() => route.query.view === 'responses')
const responsePage = computed(() => {
  const page = Number(route.query.page)
  return showResponses.value && Number.isSafeInteger(page) && page > 0 ? page : 1
})
const breadcrumbs = computed(() => [
  { label: 'Опросы', to: { name: 'surveys' } },
  ...(publishing.value ? [{
    label: 'Публикации',
    to: { name: publishing.value.can_edit ? 'survey-publishings' : 'survey-results', params: { id: publishing.value.survey_id } },
  }] : []),
  { label: 'Результаты' },
])
const error = ref('')
const textLimit = ref({})

let lastLoad = 0
async function load() {
  const request = ++lastLoad
  error.value = ''
  results.value = null
  try {
    const result = showResponses.value
      ? await getIndividualResponses(props.id, includeInProgress.value, responsePage.value)
      : await getResults(props.id, includeInProgress.value)
    if (request === lastLoad) results.value = result
  } catch (e) {
    if (request === lastLoad) error.value = errorMessage(e)
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
watch([includeInProgress, showResponses, responsePage], () => { if (publishing.value) load() })

const total = computed(() => (results.value ? results.value.responses + (includeInProgress.value ? results.value.in_progress : 0) : 0))
const maxCount = (items) => Math.max(1, ...items.map((i) => i.count))
const shownTexts = (q) => q.texts.slice(0, textLimit.value[q.question_id] || 10)
const format = (value) => (value == null ? '-' : Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 2 }))
</script>

<template>
  <div>
    <UiBreadcrumbs :items="breadcrumbs" />
    <p v-if="error" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>

    <template v-if="publishing">
      <div class="mt-2 flex flex-wrap items-start gap-4">
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
            {{ publishing.survey_title }}
            <SurveyArchiveBadge :active="publishing.survey_is_active" />
          </div>
          <h1 class="text-2xl font-bold wrap-anywhere">{{ publishing.title }}</h1>
          <p class="mt-2 flex flex-wrap gap-2">
            <UiBadge tone="brand">Ответов: {{ results?.responses ?? publishing.submitted_count }}</UiBadge>
            <UiBadge v-if="results?.in_progress">Не отправлено: {{ results.in_progress }}</UiBadge>
            <UiBadge>{{ publishing.is_anonymous ? 'Анонимно' : 'С именами' }}</UiBadge>
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <UiSwitch v-model="includeInProgress" label="Учитывать неотправленные" />
          <a
            :href="exportUrl(props.id, includeInProgress)"
            class="inline-flex h-10 items-center rounded-control bg-brand-600 px-4 font-medium text-white hover:bg-brand-700"
          >
            Скачать Excel
          </a>
        </div>
      </div>

      <div role="group" aria-label="Вид отчёта" class="mt-5 flex flex-wrap gap-2">
        <UiButton :variant="showResponses ? 'secondary' : 'primary'" :aria-pressed="!showResponses" @click="setQuery({ view: undefined, page: undefined })">
          Сводка
        </UiButton>
        <UiButton :variant="showResponses ? 'primary' : 'secondary'" :aria-pressed="showResponses" @click="!showResponses && setQuery({ view: 'responses' })">
          Отдельные ответы
        </UiButton>
      </div>

      <SkeletonPage v-if="!results && !error" class="mt-6" />
      <PublishingResponseList
        v-else-if="results && showResponses"
        :key="results.page"
        :responses="results"
        @page="setQuery({ page: $event === 1 ? undefined : $event })"
      />
      <p v-else-if="results && !total" class="mt-10 text-center text-ink-muted">Ответов пока нет.</p>

      <div v-else-if="results" class="mt-6 grid gap-4">
        <UiCard v-for="(q, index) in results.questions" :key="q.question_id">
          <p class="flex items-center gap-2 text-xs text-ink-muted">
            <QuestionTypeIcon :type="q.question_type" class="size-4 text-brand-700" />
            <span>
              {{ index + 1 }} · {{ QUESTION_TYPES[q.question_type] }} · {{ q.is_required ? 'обязательный' : 'необязательный' }} · ответили {{ q.answered }}<template v-if="q.skipped">, пропустили {{ q.skipped }}</template>
              <template v-if="!q.is_active"> · вопрос скрыт</template>
            </span>
          </p>
          <h2 class="mt-1 font-semibold">{{ q.text }}</h2>

          <ChoiceBreakdown v-if="q.comparison" :breakdown="q.comparison" :answered="q.answered" />
          <p v-if="q.question_type === 'matrix_multiple'" class="mt-2 text-sm text-ink-muted">
            В каждой строке можно было выбрать несколько вариантов.
          </p>
          <div v-if="q.matrix_rows.length" class="mt-4 grid gap-3">
            <section v-for="row in q.matrix_rows" :key="row.row_id" class="rounded-control border border-line p-3 sm:p-4">
              <h3 class="font-medium">{{ row.title }}</h3>
              <p class="mt-1 text-xs text-ink-muted">Ответили на строку: {{ row.answered }}</p>
              <ChoiceBreakdown :breakdown="row" :answered="row.answered" />
            </section>
          </div>
          <ul v-if="q.options.length && !q.comparison" class="mt-4 grid gap-2">
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
            <div v-if="q.distribution.length" class="mt-4 flex h-32 items-end gap-1" role="img" :aria-label="`Распределение ответов: ${q.distribution.map((d) => `${d.value} - ${d.count}`).join(', ')}`">
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
        </UiCard>
      </div>
    </template>
    <SkeletonPage v-else-if="!error" class="mt-4" />
  </div>
</template>
