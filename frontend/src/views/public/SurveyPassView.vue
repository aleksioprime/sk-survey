<script setup>
/**
 * Прохождение опроса по ссылке /s/<токен>. Ответы сохраняются сразу (через полсекунды после изменения),
 * ключ прохождения хранится в браузере: можно закрыть вкладку и вернуться.
 */
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { skolstreamLoginUrl } from '@/api/auth'
import { BrandMark, errorMessage, SchoolFooter, SkeletonPage, UiButton, UiCard } from 'sk-ui'
import {
  fetchPreview,
  fetchPublicSurvey,
  fetchResponse,
  forgetResponseToken,
  hasCompleted,
  markCompleted,
  rememberResponseToken,
  saveAnswer,
  savedResponseToken,
  startResponse,
  submitResponse,
} from '@/api/public'
import QuestionField from '@/components/questions/QuestionField.vue'
import { pageTitle } from '@/brand'
import { paragraphs } from '@/utils/richText'
import { MATRIX_TYPES, TEXT_LIST, countTextRows, textListError } from '@/utils/questionTypes'
import { seededShuffle } from '@/utils/shuffle'

const props = defineProps({
  token: { type: String, required: true },
  preview: { type: Boolean, default: false },
})
const route = useRoute()

const survey = ref(null)
const loadError = ref('')
const stage = ref('loading') // loading | intro | login | questions | done | error
const responseToken = ref(null)
const responseId = ref(null)
const answers = reactive({})
const errors = reactive({})
const saveState = reactive({}) // question_id → saving | saved | error
const page = ref(0)
const busy = ref(false)
const submitError = ref('')
const thankYou = ref('')
const timers = new Map()
const pending = new Map()
const inFlight = new Map()

const emptyAnswer = () => ({
  text_value: null,
  rich_text_value: null,
  number_value: null,
  boolean_value: null,
  scale_item_id: null,
  option_id: null,
  option_ids: [],
  ranking: [],
  matrix_choices: {},
  text_rows: [],
  is_skipped: false,
})

const scales = computed(() => Object.fromEntries((survey.value?.scales || []).map((s) => [s.id, s])))

/** Сначала вопросы без раздела, затем вопросы разделов в заданном порядке. */
const pages = computed(() => {
  if (!survey.value) return []
  const { questions, sections, one_question_per_page: oneQuestionPerPage } = survey.value
  const known = new Set(sections.map((section) => section.id))
  const groups = [
    { title: '', description: '', questions: questions.filter((q) => !known.has(q.section_id)) },
    ...sections.map((section) => ({
      title: section.title,
      description: section.description,
      questions: questions.filter((q) => q.section_id === section.id),
    })),
  ].filter((group) => group.questions.length)
  if (!oneQuestionPerPage) return groups
  return groups.flatMap(({ title, description, questions: items }) => items.map((question, index) => ({
    title: index === 0 ? title : '',
    description: index === 0 ? description : '',
    questions: [question],
  })))
})
const current = computed(() => pages.value[page.value])
const isLast = computed(() => page.value === pages.value.length - 1)
const progress = computed(() => {
  const total = survey.value?.questions.length || 0
  const done = survey.value?.questions.filter((q) => isAnswered(q, answers[q.id])).length || 0
  return total ? Math.round((done * 100) / total) : 0
})

function optionsFor(question) {
  return question.is_options_shuffled ? seededShuffle(question.options, `${responseId.value}${question.id}`) : question.options
}

const hasMatrix = computed(() => current.value?.questions.some((q) => MATRIX_TYPES.includes(q.question_type)))

function isAnswered(question, answer) {
  if (!answer) return false
  if (answer.is_skipped) return !question.is_required
  if (question.question_type === TEXT_LIST) return countTextRows(answer.text_rows) > 0 && !textListError(question, answer)
  if (MATRIX_TYPES.includes(question.question_type)) {
    const choices = answer.matrix_choices || {}
    const selected = (row) => Object.hasOwn(choices, row.id) && choices[row.id].length > 0
    return question.is_required ? question.matrix_rows.every(selected) : question.matrix_rows.some(selected)
  }
  return Boolean(
    answer.text_value?.trim() ||
      answer.rich_text_value ||
      answer.number_value != null ||
      answer.boolean_value != null ||
      answer.scale_item_id ||
      answer.option_id ||
      answer.option_ids?.length ||
      answer.ranking?.length,
  )
}

function applyState(state) {
  responseId.value = state.response_id
  for (const question of survey.value.questions) answers[question.id] = emptyAnswer()
  for (const saved of state.answers) {
    answers[saved.question_id] = {
      ...emptyAnswer(),
      ...saved,
      option_ids: saved.option_ids,
      ranking: saved.ranking_ids,
    }
  }
}

onMounted(async () => {
  try {
    survey.value = await (props.preview ? fetchPreview(props.token) : fetchPublicSurvey(props.token))
  } catch (e) {
    loadError.value = errorMessage(e, 'Опрос не найден')
    stage.value = 'error'
    return
  }
  document.title = pageTitle(survey.value.title)
  if (survey.value.requires_login) {
    stage.value = 'login'
    return
  }
  if (!survey.value.questions.length) {
    loadError.value = 'В опросе пока нет доступных вопросов.'
    stage.value = 'error'
    return
  }
  if (!props.preview && survey.value.is_anonymous && hasCompleted(props.token)) {
    thankYou.value = survey.value.thank_you_text
    stage.value = 'done'
    return
  }
  const saved = props.preview ? null : savedResponseToken(props.token)
  if (saved) {
    try {
      const state = await fetchResponse(saved)
      responseToken.value = saved
      applyState(state)
      if (state.status === 'submitted') {
        thankYou.value = survey.value.thank_you_text
        if (survey.value.is_anonymous) markCompleted(props.token)
        stage.value = 'done'
        return
      }
    } catch (e) {
      if (e?.response?.status !== 401) {
        loadError.value = errorMessage(e)
        stage.value = 'error'
        return
      }
      forgetResponseToken(props.token)
    }
  }
  stage.value = 'intro'
})

onBeforeUnmount(() => timers.forEach((timer) => clearTimeout(timer)))

async function begin() {
  busy.value = true
  try {
    if (props.preview) {
      applyState({ response_id: 'preview', answers: [] })
    } else if (!responseToken.value) {
      const started = await startResponse(props.token)
      responseToken.value = started.response_token
      rememberResponseToken(props.token, started.response_token)
      applyState(started)
      if (started.status === 'submitted') {
        thankYou.value = survey.value.thank_you_text
        stage.value = 'done'
        return
      }
    }
    stage.value = 'questions'
    window.scrollTo({ top: 0 })
  } catch (e) {
    loadError.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

function onChange(question, value) {
  answers[question.id] = value
  errors[question.id] = ''
  if (props.preview) return
  pending.set(question.id, value)
  clearTimeout(timers.get(question.id))
  timers.set(question.id, setTimeout(() => persist(question.id), 500))
}

function persist(questionId) {
  clearTimeout(timers.get(questionId))
  timers.delete(questionId)
  if (inFlight.has(questionId)) return inFlight.get(questionId)

  const request = savePending(questionId).finally(() => inFlight.delete(questionId))
  inFlight.set(questionId, request)
  return request
}

async function savePending(questionId) {
  while (pending.has(questionId)) {
    const value = pending.get(questionId)
    saveState[questionId] = 'saving'
    try {
      await saveAnswer(responseToken.value, questionId, value)
    } catch (e) {
      saveState[questionId] = 'error'
      errors[questionId] = errorMessage(e, 'Ответ не сохранился. Попробуйте ещё раз.')
      return false
    }
    if (pending.get(questionId) === value) pending.delete(questionId)
  }
  errors[questionId] = ''
  saveState[questionId] = 'saved'
  return true
}

async function flush() {
  const ids = new Set([...pending.keys(), ...inFlight.keys()])
  const saved = await Promise.all([...ids].map(persist))
  if (saved.every(Boolean) && !pending.size) return true
  const first = pending.keys().next().value
  const target = pages.value.findIndex((part) => part.questions.some((q) => q.id === first))
  if (target >= 0) page.value = target
  submitError.value = 'Некоторые ответы не сохранились. Повторите действие, чтобы сохранить их снова.'
  return false
}

function skip(question) {
  onChange(question, { ...emptyAnswer(), is_skipped: true })
}

function checkPage() {
  let ok = true
  for (const question of current.value.questions) {
    const answer = answers[question.id]
    if (question.question_type === TEXT_LIST) {
      const error = textListError(question, answer)
      if (error) {
        errors[question.id] = error
        ok = false
      }
      continue
    }
    const count = (answer?.option_ids?.length || 0) + (answer?.ranking?.length || 0)
    if (question.is_required && !isAnswered(question, answer)) {
      errors[question.id] = MATRIX_TYPES.includes(question.question_type)
        ? 'Выберите ответ в каждой строке'
        : 'Это обязательный вопрос'
      ok = false
    } else if (question.min_selections && count && count < question.min_selections) {
      errors[question.id] = `Выберите не меньше ${question.min_selections}`
      ok = false
    }
  }
  if (!ok) document.querySelector('[data-has-error="true"]')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  return ok
}

async function goNext() {
  if (busy.value || !checkPage()) return
  busy.value = true
  submitError.value = ''
  try {
    if (!(await flush())) return
    page.value += 1
    window.scrollTo({ top: 0 })
  } finally {
    busy.value = false
  }
}

function goBack() {
  page.value -= 1
  window.scrollTo({ top: 0 })
}

async function submit() {
  submitError.value = ''
  if (busy.value || !checkPage()) return
  busy.value = true
  try {
    if (!(await flush())) return
    if (props.preview) {
      thankYou.value = survey.value.thank_you_text
      stage.value = 'done'
      window.scrollTo({ top: 0 })
      return
    }
    const result = await submitResponse(responseToken.value)
    thankYou.value = result.thank_you_text
    stage.value = 'done'
    if (survey.value.is_anonymous) markCompleted(props.token)
    else forgetResponseToken(props.token)
    window.scrollTo({ top: 0 })
  } catch (e) {
    const detail = e?.response?.data?.detail
    const missing = detail?.question_ids
    if (missing?.length) {
      missing.forEach((id) => (errors[id] = detail.question_errors?.[id] || 'Это обязательный вопрос'))
      const target = pages.value.findIndex((p) => p.questions.some((q) => missing.includes(q.id)))
      if (target >= 0) page.value = target
    }
    submitError.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="flex flex-col" :class="{ 'min-h-dvh': !preview }">
    <div class="mx-auto w-full flex-1 px-4 py-8 sm:py-12" :class="hasMatrix && stage === 'questions' ? 'max-w-5xl' : 'max-w-2xl'">
      <BrandMark class="mb-8" />
      <SkeletonPage v-if="stage === 'loading'" />

      <UiCard v-else-if="stage === 'error'" class="p-6">
        <h1 class="text-xl font-bold">Опрос недоступен</h1>
        <p class="mt-2 text-ink-muted">{{ loadError }}</p>
      </UiCard>

      <template v-else>
        <header class="mb-6">
          <p v-if="survey.publishing_title" class="text-sm font-medium text-brand-700">{{ survey.publishing_title }}</p>
          <h1 class="mt-1 text-2xl font-bold sm:text-3xl">{{ survey.title }}</h1>
        </header>

        <UiCard v-if="stage === 'login'" class="p-6">
          <p>Этот опрос не анонимный: войдите, чтобы ответить. Ответы будут связаны с вашей учётной записью.</p>
          <a
            :href="skolstreamLoginUrl(route.fullPath)"
            class="mt-5 flex h-11 items-center justify-center rounded-control bg-brand-600 font-medium text-white hover:bg-brand-700"
          >
            Войти через SkolStream
          </a>
        </UiCard>

        <UiCard v-else-if="stage === 'intro'" class="p-6">
          <div v-if="survey.description || survey.intro_text" class="prose-text text-ink">
            <p v-for="(paragraph, index) in paragraphs(survey.intro_text || survey.description)" :key="index" class="whitespace-pre-line">
              {{ paragraph }}
            </p>
          </div>
          <div class="mt-4 space-y-1 text-sm text-ink-muted">
            <p>Вопросов: {{ survey.questions.length }}.</p>
            <p v-if="survey.is_anonymous">Опрос анонимный: ответы не связаны с вашим именем.</p>
            <p v-if="!preview">Ответы сохраняются автоматически. Можно продолжить позже на этом устройстве.</p>
          </div>
          <p v-if="loadError" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ loadError }}</p>
          <UiButton class="mt-6 w-full sm:w-auto" variant="primary" :loading="busy" @click="begin">
            {{ responseToken ? 'Продолжить' : 'Начать' }}
          </UiButton>
        </UiCard>

        <section v-else-if="stage === 'questions'">
          <div class="mb-6">
            <div class="flex justify-between text-sm text-ink-muted">
              <span v-if="pages.length > 1">{{ survey.one_question_per_page ? 'Вопрос' : 'Часть' }} {{ page + 1 }} из {{ pages.length }}</span>
              <span>Отвечено {{ progress }}%</span>
            </div>
            <div class="mt-2 h-2 overflow-hidden rounded-full bg-line" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
              <div class="h-full rounded-full bg-brand-500 transition-all" :style="{ width: `${progress}%` }" />
            </div>
          </div>

          <div v-if="current.title || current.description" class="mb-4">
            <h2 v-if="current.title" class="text-xl font-semibold">{{ current.title }}</h2>
            <p v-if="current.description" class="mt-1 whitespace-pre-line text-ink-muted">{{ current.description }}</p>
          </div>

          <div class="grid gap-4">
            <article
              v-for="question in current.questions"
              :key="question.id"
              :data-has-error="!!errors[question.id]"
              class="rounded-card border bg-surface p-5"
              :class="errors[question.id] ? 'border-red-400' : 'border-line'"
            >
              <h3 class="font-semibold">
                {{ question.text }}<span v-if="question.is_required" class="text-red-600" aria-label="обязательный"> *</span>
              </h3>
              <p v-if="question.description" class="mt-1 whitespace-pre-line text-sm text-ink-muted">{{ question.description }}</p>
              <QuestionField
                :disabled="busy"
                class="mt-4"
                :model-value="answers[question.id]"
                :question="question"
                :scale="scales[question.scale_id]"
                :options="optionsFor(question)"
                :error="errors[question.id]"
                @update:model-value="onChange(question, $event)"
              />
              <div class="mt-3 flex items-center justify-between text-xs text-ink-muted">
                <button
                  v-if="!question.is_required"
                  type="button"
                  :disabled="busy"
                  class="hover:text-ink"
                  :class="answers[question.id]?.is_skipped ? 'font-medium text-brand-700' : ''"
                  @click="skip(question)"
                >
                  {{ answers[question.id]?.is_skipped ? 'Вопрос пропущен' : 'Пропустить вопрос' }}
                </button>
                <span v-else />
                <span aria-live="polite">
                  {{ { saving: 'Сохраняем…', saved: 'Сохранено', error: '' }[saveState[question.id]] || '' }}
                </span>
              </div>
            </article>
          </div>

          <p v-if="submitError" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ submitError }}</p>
          <div class="mt-6 flex justify-between gap-3">
            <UiButton v-if="page > 0" :disabled="busy" @click="goBack">Назад</UiButton>
            <span v-else />
            <UiButton v-if="!isLast" variant="primary" :loading="busy" @click="goNext">Далее</UiButton>
            <UiButton v-else variant="primary" :loading="busy" @click="submit">{{ preview ? 'Завершить предпросмотр' : 'Отправить ответы' }}</UiButton>
          </div>
        </section>

        <UiCard v-else-if="stage === 'done'" class="p-6 text-center">
          <div class="mx-auto grid size-12 place-items-center rounded-full bg-brand-100 text-2xl text-brand-700" aria-hidden="true">✓</div>
          <h2 class="mt-4 text-xl font-bold">{{ preview ? 'Предпросмотр завершён' : 'Ответы отправлены' }}</h2>
          <div class="prose-text mt-3 text-ink-muted">
            <p v-for="(paragraph, index) in paragraphs(thankYou || 'Спасибо за участие!')" :key="index" class="whitespace-pre-line">
              {{ paragraph }}
            </p>
          </div>
        </UiCard>
      </template>
    </div>
    <SchoolFooter v-if="!preview" />
  </div>
</template>
