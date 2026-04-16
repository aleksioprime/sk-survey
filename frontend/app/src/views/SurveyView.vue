<!--
  SurveyView — основная страница прохождения опроса.

  Поток: экран приветствия → вопросы (по разделам) → отправка.
  Текстовые вопросы сохраняются по кнопке, остальные — автоматически (debounce 500ms).
  Поддерживает возобновление сессии через localStorage.
-->
<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSurveyStore } from '@/stores/survey'
import ProgressBar from '@/components/ProgressBar.vue'
import QuestionCard from '@/components/QuestionCard.vue'

const props = defineProps({
  token: { type: String, required: true },
})

const router = useRouter()
const store = useSurveyStore()

const started = ref(false)
const saveTimeouts = ref({})

onMounted(async () => {
  store.$reset()
  try {
    await store.loadBundle(props.token)
    // Если восстановлена существующая сессия — сразу показать вопросы
    if (store.responseData) {
      started.value = true
    }
  } catch {
    // error is in store.error
  }
})

async function handleStart() {
  // Если сессия не восстановлена — создаём новую
  if (!store.responseData) {
    await store.startResponse(props.token)
  }
  started.value = true
}

function onAnswer(questionId, value) {
  store.setAnswer(questionId, value)
  const question = store.questions.find((q) => q.id === questionId)
  if (!question) return
  // Вопросы с кнопкой (text/rich_text/ranking) сохраняются вручную.
  if (!['text', 'rich_text', 'ranking'].includes(question.question_type)) {
    debounceSave(questionId, value)
  }
}

function onSaveAnswer(questionId) {
  const value = store.answers[questionId]
  const question = store.questions.find((q) => q.id === questionId)
  if (!question) return

  if (question.question_type === 'ranking') {
    const totalOptions = store.getOptionsForQuestion(question).length
    if (!Array.isArray(value) || totalOptions === 0 || value.length !== totalOptions) return
  } else if (value == null || value === '') {
    return
  }

  const payload = buildPayload(question, value)
  store.saveAnswer(props.token, questionId, payload)
}

function onCancelChanges(questionId) {
  const question = store.questions.find((q) => q.id === questionId)
  if (!question) return

  const hasSaved = store.isAnswerSaved(questionId)
  if (hasSaved) {
    const savedValue = store.getSavedValue(questionId)
    if (Array.isArray(savedValue)) {
      store.setAnswer(questionId, [...savedValue])
    } else {
      store.setAnswer(questionId, savedValue)
    }
    return
  }

  if (question.question_type === 'ranking') {
    store.setAnswer(questionId, [])
  } else {
    store.setAnswer(questionId, '')
  }
}

// Сохранение при потере фокуса для числовых полей
function onBlurSave(questionId) {
  const question = store.questions.find((q) => q.id === questionId)
  if (!question) return
  if (!['number'].includes(question.question_type)) return
  const value = store.answers[questionId]
  if (value == null || value === '') return
  // Отменяем ожидающий debounce и сохраняем немедленно
  clearTimeout(saveTimeouts.value[questionId])
  const payload = buildPayload(question, value)
  store.saveAnswer(props.token, questionId, payload)
}

function debounceSave(questionId, value) {
  clearTimeout(saveTimeouts.value[questionId])
  saveTimeouts.value[questionId] = setTimeout(() => {
    const question = store.questions.find((q) => q.id === questionId)
    if (!question) return

    const payload = buildPayload(question, value)
    store.saveAnswer(props.token, questionId, payload)
  }, 500)
}

function buildPayload(question, value) {
  const payload = {}

  switch (question.question_type) {
    case 'text':
      payload.text_value = value
      break
    case 'rich_text':
      payload.rich_text_value = value
      break
    case 'number':
      payload.number_value = value
      break
    case 'yes_no':
      payload.boolean_value = value
      break
    case 'single_choice':
      payload.option_id = value
      break
    case 'multiple_choice':
      payload.option_ids = value
      break
    case 'scale':
      if (question.scale?.scale_type === 'generated') {
        payload.number_value = value
      } else {
        payload.scale_item_id = value
      }
      break
    case 'ranking':
      payload.ranking_option_ids = value
      break
  }

  return payload
}

function handleNext() {
  store.nextSection(props.token)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function handlePrev() {
  store.prevSection(props.token)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function handleSubmit() {
  try {
    await store.submitResponse(props.token)
    router.push({ name: 'survey-complete', params: { token: props.token } })
  } catch {
    // error is in store
  }
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 to-teal-50/30">
    <!-- Loading -->
    <div v-if="store.loading" class="flex min-h-screen items-center justify-center">
      <div class="text-center">
        <div class="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p class="mt-3 text-sm text-muted">Загрузка опроса...</p>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="store.error" class="flex min-h-screen items-center justify-center px-4">
      <div class="glass-panel max-w-md p-8 text-center">
        <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-red-100">
          <svg class="h-7 w-7 text-danger" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/>
          </svg>
        </div>
        <h2 class="text-lg font-semibold text-slate-800">Ошибка</h2>
        <p class="mt-2 text-sm text-muted">{{ store.error }}</p>
      </div>
    </div>

    <!-- Intro screen (before start) -->
    <div
      v-else-if="store.survey && !started"
      class="flex min-h-screen items-center justify-center px-4"
    >
      <div class="glass-panel max-w-lg w-full p-8 text-center">
        <div class="mx-auto mb-4 text-5xl">📋</div>
        <h1 class="text-2xl font-bold text-slate-800">{{ store.survey.title }}</h1>
        <p
          v-if="store.survey.description"
          class="mt-2 text-sm text-muted"
        >
          {{ store.survey.description }}
        </p>
        <p
          v-if="store.survey.intro_text"
          class="mt-4 text-sm text-slate-600 leading-relaxed"
        >
          {{ store.survey.intro_text }}
        </p>
        <div class="mt-4 text-xs text-muted">
          <span v-if="store.questions.length">{{ store.questions.length }} вопросов</span>
          <span v-if="store.hasSections"> · {{ store.totalSections }} разделов</span>
        </div>
        <button class="btn-primary mt-6" @click="handleStart">
          Начать опрос
        </button>
      </div>
    </div>

    <!-- Survey questions (section per page) -->
    <div v-else-if="store.survey && started" class="mx-auto max-w-2xl px-4 py-6">
      <!-- Header -->
      <div class="mb-4">
        <h1 class="text-xl font-bold text-slate-800">{{ store.survey.title }}</h1>
      </div>

      <!-- Progress -->
      <div class="mb-6 sticky top-0 z-10 bg-white/80 backdrop-blur-xl rounded-2xl p-3 border border-white/40 shadow-sm">
        <ProgressBar :value="store.progress" />
        <div v-if="store.hasSections" class="mt-2 flex items-center justify-between text-xs text-muted">
          <span>Раздел {{ store.currentSectionIndex + 1 }} из {{ store.totalSections }}</span>
          <span v-if="store.currentSection">{{ store.currentSection.title }}</span>
        </div>
      </div>

      <!-- Section title & description -->
      <div v-if="store.currentSection" class="mb-5">
        <h2 class="text-lg font-semibold text-slate-800">
          {{ store.currentSection.title }}
        </h2>
        <p
          v-if="store.currentSection.description"
          class="mt-1 text-sm text-muted leading-relaxed"
        >
          {{ store.currentSection.description }}
        </p>
      </div>

      <!-- Questions -->
      <div class="space-y-4">
        <QuestionCard
          v-for="(question, idx) in store.currentQuestions"
          :key="question.id"
          :question="question"
          :question-index="idx"
          :options="store.getOptionsForQuestion(question)"
          :scale-items="store.getScaleItemsForQuestion(question)"
          :scale-ranges="store.getScaleRangesForQuestion(question.id)"
          :model-value="store.answers[question.id]"
          :saved-value="store.getSavedValue(question.id)"
          :is-saving="store.isAnswerSaving(question.id)"
          @update:model-value="onAnswer(question.id, $event)"
          @save-answer="onSaveAnswer(question.id)"
          @cancel-changes="onCancelChanges(question.id)"
          @blur="onBlurSave(question.id)"
        />
      </div>

      <!-- Navigation -->
      <div class="mt-8 flex items-center justify-between gap-4 pb-8">
        <button
          v-if="!store.isFirstSection"
          class="btn-outline"
          @click="handlePrev"
        >
          ← Назад
        </button>
        <div v-else />

        <button
          v-if="!store.isLastSection"
          class="btn-primary"
          :disabled="!store.currentSectionValid"
          @click="handleNext"
        >
          Далее →
        </button>
        <button
          v-else
          class="btn-primary"
          :disabled="!store.allRequiredAnswered || store.submitting"
          @click="handleSubmit"
        >
          {{ store.submitting ? 'Отправка...' : 'Отправить ответы' }}
        </button>
      </div>
    </div>
  </div>
</template>
