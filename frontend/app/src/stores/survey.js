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

export const useSurveyStore = defineStore('survey', () => {
  const bundle = ref(null)
  const responseData = ref(null)
  const answers = ref({})
  const savedAnswers = ref(new Set())
  const loading = ref(false)
  const error = ref(null)
  const currentSectionIndex = ref(0)
  const submitting = ref(false)

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
      .every((q) => {
        const a = answers.value[q.id]
        return a != null && a !== '' && !(Array.isArray(a) && a.length === 0)
      })
  })

  const allRequiredAnswered = computed(() => {
    return questions.value
      .filter((q) => q.is_required)
      .every((q) => {
        const a = answers.value[q.id]
        return a != null && a !== '' && !(Array.isArray(a) && a.length === 0)
      })
  })

  function getOptionsForQuestion(questionId) {
    return options.value.filter((o) => o.question_id === questionId)
  }

  function getScaleItemsForScale(scaleId) {
    return scaleItems.value.filter((s) => s.scale_id === scaleId)
  }

  function getScaleRangesForQuestion(questionId) {
    return scaleRanges.value.filter((r) => r.question_id === questionId)
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
      }
      if (restored) {
        savedAnswers.value = { ...savedAnswers.value, [qId]: answers.value[qId] }
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
    if (!responseData.value) {
      console.warn('[saveAnswer] no responseData — skip')
      return
    }
    const responseId = responseData.value.id
    console.log('[saveAnswer] PATCH response:', responseId, 'question:', questionId, payload)
    try {
      await publicApi.patch(
        `/public/surveys/${token}/responses/${responseId}/answers/${questionId}`,
        payload,
      )
      savedAnswers.value = { ...savedAnswers.value, [questionId]: answers.value[questionId] }
      console.log('[saveAnswer] saved OK', questionId)
    } catch (e) {
      console.error('[saveAnswer] error:', e)
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
    getScaleItemsForScale,
    getScaleRangesForQuestion,
    loadBundle,
    startResponse,
    saveAnswer,
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
