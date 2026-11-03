<script setup>
/**
 * Прохождение опроса по ссылке /s/<токен>. Ответы сохраняются сразу (через полсекунды после изменения),
 * ключ прохождения хранится в браузере: можно закрыть вкладку и вернуться.
 */
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { skolstreamLoginUrl } from '@/api/auth'
import { errorMessage } from '@/api/http'
import {
  fetchPublicSurvey,
  fetchResponse,
  forgetResponseToken,
  rememberResponseToken,
  saveAnswer,
  savedResponseToken,
  startResponse,
  submitResponse,
} from '@/api/public'
import QuestionField from '@/components/questions/QuestionField.vue'
import UiButton from '@/components/ui/UiButton.vue'
import { paragraphs } from '@/utils/richText'
import { seededShuffle } from '@/utils/shuffle'

const props = defineProps({ token: { type: String, required: true } })
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

const emptyAnswer = () => ({
  text_value: null,
  rich_text_value: null,
  number_value: null,
  boolean_value: null,
  scale_item_id: null,
  option_id: null,
  option_ids: [],
  ranking: [],
  is_skipped: false,
})

const scales = computed(() => Object.fromEntries((survey.value?.scales || []).map((s) => [s.id, s])))

/** Страницы: вопросы без раздела — первой страницей, дальше разделы по порядку. */
const pages = computed(() => {
  if (!survey.value) return []
  const questions = survey.value.questions
  const result = []
  const loose = questions.filter((q) => !q.section_id || !survey.value.sections.some((s) => s.id === q.section_id))
  if (loose.length) result.push({ id: 'loose', title: '', description: '', questions: loose })
  for (const section of survey.value.sections) {
    const items = questions.filter((q) => q.section_id === section.id)
    if (items.length) result.push({ ...section, questions: items })
  }
  return result
})
const current = computed(() => pages.value[page.value])
const isLast = computed(() => page.value === pages.value.length - 1)
const progress = computed(() => {
  const total = survey.value?.questions.length || 0
  const done = survey.value?.questions.filter((q) => isAnswered(answers[q.id])).length || 0
  return total ? Math.round((done * 100) / total) : 0
})

function optionsFor(question) {
  return question.is_options_shuffled ? seededShuffle(question.options, `${responseId.value}${question.id}`) : question.options
}

function isAnswered(answer) {
  if (!answer) return false
  return Boolean(
    answer.is_skipped ||
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
    survey.value = await fetchPublicSurvey(props.token)
  } catch (e) {
    loadError.value = errorMessage(e, 'Опрос не найден')
    stage.value = 'error'
    return
  }
  document.title = survey.value.title
  if (survey.value.requires_login) {
    stage.value = 'login'
    return
  }
  const saved = savedResponseToken(props.token)
  if (saved) {
    try {
      const state = await fetchResponse(saved)
      responseToken.value = saved
      applyState(state)
      if (state.status === 'submitted') {
        thankYou.value = survey.value.thank_you_text
        stage.value = 'done'
        return
      }
    } catch {
      forgetResponseToken(props.token)
    }
  }
  stage.value = 'intro'
})

onBeforeUnmount(() => timers.forEach((timer) => clearTimeout(timer)))

async function begin() {
  busy.value = true
  try {
    if (!responseToken.value) {
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
  clearTimeout(timers.get(question.id))
  timers.set(question.id, setTimeout(() => persist(question.id), 500))
}

async function persist(questionId) {
  timers.delete(questionId)
  saveState[questionId] = 'saving'
  try {
    await saveAnswer(responseToken.value, questionId, answers[questionId])
    saveState[questionId] = 'saved'
  } catch (e) {
    saveState[questionId] = 'error'
    errors[questionId] = errorMessage(e, 'Ответ не сохранился. Попробуйте ещё раз.')
  }
}

async function flush() {
  const pending = [...timers.keys()]
  pending.forEach((id) => clearTimeout(timers.get(id)))
  await Promise.all(pending.map(persist))
  return pending.every((id) => saveState[id] !== 'error')
}

function skip(question) {
  onChange(question, { ...emptyAnswer(), is_skipped: true })
}

function checkPage() {
  let ok = true
  for (const question of current.value.questions) {
    const answer = answers[question.id]
    const count = (answer?.option_ids?.length || 0) + (answer?.ranking?.length || 0)
    if (question.is_required && !isAnswered(answer)) {
      errors[question.id] = 'Это обязательный вопрос'
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
  if (!checkPage() || !(await flush())) return
  page.value += 1
  window.scrollTo({ top: 0 })
}

function goBack() {
  page.value -= 1
  window.scrollTo({ top: 0 })
}

async function submit() {
  submitError.value = ''
  if (!checkPage() || !(await flush())) return
  busy.value = true
  try {
    const result = await submitResponse(responseToken.value)
    thankYou.value = result.thank_you_text
    stage.value = 'done'
    forgetResponseToken(props.token)
    window.scrollTo({ top: 0 })
  } catch (e) {
    const missing = e?.response?.data?.detail?.question_ids
    if (missing?.length) {
      missing.forEach((id) => (errors[id] = 'Это обязательный вопрос'))
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
  <div class="min-h-dvh">
    <div class="mx-auto max-w-2xl px-4 py-8 sm:py-12">
      <p v-if="stage === 'loading'" class="text-ink-muted" role="status">Загружаем опрос…</p>

      <div v-else-if="stage === 'error'" class="rounded-card border border-line bg-surface p-6">
        <h1 class="text-xl font-bold">Опрос недоступен</h1>
        <p class="mt-2 text-ink-muted">{{ loadError }}</p>
      </div>

      <template v-else>
        <header class="mb-6">
          <p v-if="survey.publishing_title" class="text-sm font-medium text-brand-700">{{ survey.publishing_title }}</p>
          <h1 class="mt-1 text-2xl font-bold sm:text-3xl">{{ survey.title }}</h1>
        </header>

        <section v-if="stage === 'login'" class="rounded-card border border-line bg-surface p-6">
          <p>Этот опрос не анонимный: войдите, чтобы ответить. Ответы будут связаны с вашей учётной записью.</p>
          <a
            :href="skolstreamLoginUrl(route.fullPath)"
            class="mt-5 flex h-11 items-center justify-center rounded-control bg-brand-600 font-medium text-white hover:bg-brand-700"
          >
            Войти через SkolStream
          </a>
        </section>

        <section v-else-if="stage === 'intro'" class="rounded-card border border-line bg-surface p-6">
          <div v-if="survey.description || survey.intro_text" class="prose-text text-ink">
            <p v-for="(paragraph, index) in paragraphs(survey.intro_text || survey.description)" :key="index" class="whitespace-pre-line">
              {{ paragraph }}
            </p>
          </div>
          <p class="mt-4 text-sm text-ink-muted">
            Вопросов: {{ survey.questions.length }}.
            <template v-if="survey.is_anonymous">Опрос анонимный: ответы не связаны с вашим именем.</template>
            Ответы сохраняются сразу — можно прерваться и продолжить позже на этом устройстве.
          </p>
          <p v-if="loadError" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ loadError }}</p>
          <UiButton class="mt-6 w-full sm:w-auto" variant="primary" :loading="busy" @click="begin">
            {{ responseToken ? 'Продолжить' : 'Начать' }}
          </UiButton>
        </section>

        <section v-else-if="stage === 'questions'">
          <div class="mb-6">
            <div class="flex justify-between text-sm text-ink-muted">
              <span v-if="pages.length > 1">Часть {{ page + 1 }} из {{ pages.length }}</span>
              <span>Отвечено {{ progress }}%</span>
            </div>
            <div class="mt-2 h-2 overflow-hidden rounded-full bg-line" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
              <div class="h-full rounded-full bg-brand-500 transition-all" :style="{ width: `${progress}%` }" />
            </div>
          </div>

          <div v-if="current.title || current.description" class="mb-4">
            <h2 class="text-xl font-semibold">{{ current.title }}</h2>
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
            <UiButton v-if="page > 0" @click="goBack">Назад</UiButton>
            <span v-else />
            <UiButton v-if="!isLast" variant="primary" @click="goNext">Далее</UiButton>
            <UiButton v-else variant="primary" :loading="busy" @click="submit">Отправить ответы</UiButton>
          </div>
        </section>

        <section v-else-if="stage === 'done'" class="rounded-card border border-line bg-surface p-6 text-center">
          <div class="mx-auto grid size-12 place-items-center rounded-full bg-brand-100 text-2xl text-brand-700" aria-hidden="true">✓</div>
          <h2 class="mt-4 text-xl font-bold">Ответы отправлены</h2>
          <div class="prose-text mt-3 text-ink-muted">
            <p v-for="(paragraph, index) in paragraphs(thankYou || 'Спасибо за участие!')" :key="index" class="whitespace-pre-line">
              {{ paragraph }}
            </p>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>
