/**
 * Хранилище состояния опроса (Pinia).
 *
 * Управляет полным жизненным циклом прохождения:
 * - Загрузка бандла (метаданные + вопросы + варианты + шкалы)
 * - Создание анонимного ответа и навигация по разделам
 * - Автосохранение ответов на сервере (debounce) и их восстановление
 * - Персистентность сессии через localStorage (возобновление при перезагрузке)
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import publicApi from '@/api/public'

const STORAGE_KEY_PREFIX = 'sk_survey_'
const SHUFFLE_QUESTION_TYPES = new Set(['single_choice', 'multiple_choice', 'scale', 'ranking'])
const MANUAL_SAVE_QUESTION_TYPES = new Set(['text', 'rich_text', 'ranking'])

function hashString(str) {
  let h1 = 0xdeadbeef ^ str.length
  let h2 = 0x41c6ce57 ^ str.length

  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i)
    h1 = Math.imul(h1 ^ ch, 2654435761)
    h2 = Math.imul(h2 ^ ch, 1597334677)
  }

  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909)
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909)

  return 4294967296 * (2097151 & h2) + (h1 >>> 0)
}

function mulberry32(seed) {
  let t = seed >>> 0
  return () => {
    t += 0x6d2b79f5
    let x = Math.imul(t ^ (t >>> 15), 1 | t)
    x ^= x + Math.imul(x ^ (x >>> 7), 61 | x)
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296
  }
}

function seededShuffle(items, seedString) {
  const arr = [...items]
  const random = mulberry32(hashString(seedString))

  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1))
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
  }

  return arr
}

export const useSurveyStore = defineStore('survey', () => {
  const bundle = ref(null)
  const responseData = ref(null)
  const answers = ref({})
  const savedAnswers = ref(new Set())
  const loading = ref(false)
  const error = ref(null)
  const currentSectionIndex = ref(0)
  const submitting = ref(false)
  const pendingSaves = ref({})

  const survey = computed(() => bundle.value?.survey || null)
  const publishing = computed(() => bundle.value?.publishing || null)
  const sections = computed(() => bundle.value?.sections || [])
  const questions = computed(() => bundle.value?.questions || [])
  const options = computed(() => bundle.value?.options || [])
  const scaleItems = computed(() => bundle.value?.scale_items || [])
  const scaleRanges = computed(() => bundle.value?.scale_ranges || [])

  const hasSections = computed(() => sections.value.length > 0)

  const currentSection = computed(() =>
    hasSections.value ? sections.value[currentSectionIndex.value] : null,
  )

  const currentQuestions = computed(() => {
    if (!hasSections.value) return questions.value
    const sectionId = currentSection.value?.id
    return questions.value.filter((q) => q.section_id === sectionId)
  })

  const totalSections = computed(() =>
    hasSections.value ? sections.value.length : 1,
  )

  const isLastSection = computed(() =>
    currentSectionIndex.value >= totalSections.value - 1,
  )

  const isFirstSection = computed(() =>
    currentSectionIndex.value === 0,
  )

  // Прогресс определяется по ответам, успешно сохранённым на сервере (savedAnswers),
  // а не по локальному состоянию. Полоса растёт только после PATCH 200.
  const progress = computed(() => {
    const required = questions.value.filter((q) => q.is_required)
    if (required.length === 0) return 100
    const answered = required.filter((q) => savedAnswers.value[q.id] !== undefined).length
    return Math.round((answered / required.length) * 100)
  })

  const currentSectionValid = computed(() => {
    return currentQuestions.value
      .filter((q) => q.is_required)
      .every((q) => isQuestionAnswered(q, answers.value[q.id]))
  })

  const allRequiredAnswered = computed(() => {
    return questions.value
      .filter((q) => q.is_required)
      .every((q) => isQuestionAnswered(q, answers.value[q.id]))
  })

  function _resolveQuestion(questionOrId) {
    if (!questionOrId) return null
    if (typeof questionOrId === 'object') return questionOrId
    return questions.value.find((q) => q.id === questionOrId) || null
  }

  function _isShuffleEnabled(question) {
    return Boolean(
      question?.is_options_shuffled && SHUFFLE_QUESTION_TYPES.has(question.question_type),
    )
  }

  function _shuffleSeed(questionId, suffix) {
    const responseToken = responseData.value?.token || 'no-response'
    return `${responseToken}:${questionId}:${suffix}`
  }

  function getOptionsForQuestion(questionOrId) {
    const question = _resolveQuestion(questionOrId)
    if (!question) return []

    const questionOptions = options.value.filter((o) => o.question_id === question.id)
    if (!_isShuffleEnabled(question) || question.question_type === 'scale') {
      return questionOptions
    }

    return seededShuffle(questionOptions, _shuffleSeed(question.id, 'options'))
  }

  function getScaleItemsForQuestion(questionOrId) {
    const question = _resolveQuestion(questionOrId)
    if (!question?.scale_id) return []

    const items = scaleItems.value.filter((s) => s.scale_id === question.scale_id)
    const isGeneratedScale = question.scale?.scale_type === 'generated'

    if (!_isShuffleEnabled(question) || question.question_type !== 'scale' || isGeneratedScale) {
      return items
    }

    return seededShuffle(items, _shuffleSeed(question.id, 'scale_items'))
  }

  function getScaleRangesForQuestion(questionId) {
    return scaleRanges.value.filter((r) => r.question_id === questionId)
  }

  function isQuestionAnswered(question, value) {
    if (!hasAnswerValue(question, value)) return false

    if (isManualSaveQuestion(question)) {
      if (!(question.id in savedAnswers.value)) return false
      return !isQuestionDirty(question)
    }

    return true
  }

  function isManualSaveQuestion(question) {
    return MANUAL_SAVE_QUESTION_TYPES.has(question.question_type)
  }

  function hasAnswerValue(question, value) {
    if (value == null || value === '') return false

    if (question.question_type === 'ranking') {
      if (!Array.isArray(value) || value.length === 0) return false
      const totalOptions = options.value.filter((o) => o.question_id === question.id).length
      return totalOptions > 0 && value.length === totalOptions
    }

    return !(Array.isArray(value) && value.length === 0)
  }

  function areAnswerValuesEqual(a, b) {
    if (Array.isArray(a) && Array.isArray(b)) {
      if (a.length !== b.length) return false
      return a.every((item, idx) => item === b[idx])
    }
    return a === b
  }

  function isQuestionDirty(questionOrId) {
    const question = _resolveQuestion(questionOrId)
    if (!question || !isManualSaveQuestion(question)) return false

    const current = answers.value[question.id]
    const hasSavedValue = question.id in savedAnswers.value

    if (!hasSavedValue) {
      return hasAnswerValue(question, current)
    }

    return !areAnswerValuesEqual(current, savedAnswers.value[question.id])
  }

  function isAnswerSaving(questionId) {
    return pendingSaves.value[questionId] === true
  }

  function setAnswerSaving(questionId, isSaving) {
    if (isSaving) {
      pendingSaves.value = { ...pendingSaves.value, [questionId]: true }
      return
    }
    const { [questionId]: _removed, ...rest } = pendingSaves.value
    pendingSaves.value = rest
  }

  // --- Persistence (localStorage) ---

  function _storageKey(token) {
    return `${STORAGE_KEY_PREFIX}${token}`
  }

  function saveSession(token) {
    if (!responseData.value) return
    const session = {
      responseId: responseData.value.id,
      responseToken: responseData.value.token,
      sectionIndex: currentSectionIndex.value,
    }
    try {
      localStorage.setItem(_storageKey(token), JSON.stringify(session))
    } catch { /* quota exceeded — ignore */ }
  }

  function loadSession(token) {
    try {
      const raw = localStorage.getItem(_storageKey(token))
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  }

  function clearSession(token) {
    localStorage.removeItem(_storageKey(token))
  }

  // --- API ---

  async function loadBundle(token) {
    loading.value = true
    error.value = null
    try {
      const session = loadSession(token)
      const params = session?.responseToken
        ? { response_token: session.responseToken }
        : {}

      const { data } = await publicApi.get(`/public/surveys/${token}`, { params })
      bundle.value = data

      // Восстановить сессию если есть
      if (data.existing_response) {
        responseData.value = data.existing_response
        currentSectionIndex.value = session?.sectionIndex || 0
        // Восстановить ответы из existing_answers
        if (data.existing_answers?.length) {
          _restoreAnswers(data.existing_answers)
        }
      }
    } catch (e) {
      error.value = e.response?.data?.detail || 'Не удалось загрузить опрос'
      throw e
    } finally {
      loading.value = false
    }
  }

  function _restoreAnswers(existingAnswers) {
    for (const ans of existingAnswers) {
      const qId = ans.question_id
      const question = questions.value.find((q) => q.id === qId)
      if (!question) continue

      let restored = false
      switch (question.question_type) {
        case 'text':
          if (ans.text_value) { answers.value[qId] = ans.text_value; restored = true }
          break
        case 'rich_text':
          if (ans.rich_text_value) { answers.value[qId] = ans.rich_text_value; restored = true }
          break
        case 'number':
          if (ans.number_value != null) { answers.value[qId] = ans.number_value; restored = true }
          break
        case 'yes_no':
          if (ans.boolean_value != null) { answers.value[qId] = ans.boolean_value; restored = true }
          break
        case 'single_choice':
          if (ans.option_id) { answers.value[qId] = ans.option_id; restored = true }
          break
        case 'multiple_choice': {
          const opts = ans.options || []
          if (opts.length) { answers.value[qId] = opts.map((o) => o.id); restored = true }
          break
        }
        case 'scale':
          if (question.scale?.scale_type === 'generated' && ans.number_value != null) {
            answers.value[qId] = ans.number_value; restored = true
          } else if (ans.scale_item_id) {
            answers.value[qId] = ans.scale_item_id; restored = true
          }
          break
        case 'ranking': {
          const rankingItems = (ans.ranking_items || [])
            .slice()
            .sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0))

          const rankingIds = rankingItems
            .map((item) => item.option_id || item.option?.id)
            .filter(Boolean)

          if (rankingIds.length) {
            answers.value[qId] = rankingIds
            restored = true
          }
          break
        }
      }
      if (restored) {
        if (hasAnswerValue(question, answers.value[qId])) {
          savedAnswers.value = { ...savedAnswers.value, [qId]: answers.value[qId] }
        }
      }
    }
  }

  async function startResponse(token) {
    try {
      const { data } = await publicApi.post(`/public/surveys/${token}/start`)
      responseData.value = data
      saveSession(token)
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || 'Не удалось начать опрос'
      throw e
    }
  }

  async function saveAnswer(token, questionId, payload) {
    if (!responseData.value) return
    // Защита от дублей: если запрос для этого вопроса уже в полёте — пропускаем
    if (isAnswerSaving(questionId)) return
    setAnswerSaving(questionId, true)
    const responseId = responseData.value.id
    try {
      await publicApi.patch(
        `/public/surveys/${token}/responses/${responseId}/answers/${questionId}`,
        payload,
      )
      const question = questions.value.find((q) => q.id === questionId)
      const answerValue = answers.value[questionId]

      if (question && hasAnswerValue(question, answerValue)) {
        savedAnswers.value = { ...savedAnswers.value, [questionId]: answerValue }
      } else {
        const { [questionId]: _removed, ...rest } = savedAnswers.value
        savedAnswers.value = rest
      }
    } catch (e) {
      console.error('[saveAnswer] error:', e)
    } finally {
      setAnswerSaving(questionId, false)
    }
  }

  function isAnswerSaved(questionId) {
    return savedAnswers.value[questionId] !== undefined
  }

  function getSavedValue(questionId) {
    return questionId in savedAnswers.value ? savedAnswers.value[questionId] : null
  }

  function setAnswer(questionId, value) {
    answers.value[questionId] = value
  }

  async function submitResponse(token) {
    if (!responseData.value) return
    submitting.value = true
    try {
      await publicApi.post(
        `/public/surveys/${token}/responses/${responseData.value.id}/submit`,
      )
      clearSession(token)
    } catch (e) {
      error.value = e.response?.data?.detail || 'Не удалось отправить ответы'
      throw e
    } finally {
      submitting.value = false
    }
  }

  function nextSection(token) {
    if (currentSectionIndex.value < totalSections.value - 1) {
      currentSectionIndex.value++
      saveSession(token)
    }
  }

  function prevSection(token) {
    if (currentSectionIndex.value > 0) {
      currentSectionIndex.value--
      saveSession(token)
    }
  }

  function $reset() {
    bundle.value = null
    responseData.value = null
    answers.value = {}
    savedAnswers.value = {}
    loading.value = false
    error.value = null
    currentSectionIndex.value = 0
    submitting.value = false
    pendingSaves.value = {}
  }

  return {
    bundle,
    responseData,
    answers,
    loading,
    error,
    currentSectionIndex,
    submitting,
    survey,
    publishing,
    sections,
    questions,
    options,
    scaleItems,
    scaleRanges,
    hasSections,
    currentSection,
    currentQuestions,
    totalSections,
    isLastSection,
    isFirstSection,
    progress,
    currentSectionValid,
    allRequiredAnswered,
    getOptionsForQuestion,
    getScaleItemsForQuestion,
    getScaleRangesForQuestion,
    loadBundle,
    startResponse,
    saveAnswer,
    isAnswerSaving,
    isQuestionDirty,
    isAnswerSaved,
    getSavedValue,
    setAnswer,
    submitResponse,
    nextSection,
    prevSection,
    saveSession,
    loadSession,
    clearSession,
    $reset,
  }
})
