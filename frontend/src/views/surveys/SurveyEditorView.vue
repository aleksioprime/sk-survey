<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, RouterLink, useRoute, useRouter } from 'vue-router'
import { errorMessage, SkeletonPage, UiButton, UiCard, UiConfirm, UiFormActions, UiInput, UiSwitch } from 'sk-ui'
import * as api from '@/api/surveys'
import QuestionEditor from '@/components/editor/QuestionEditor.vue'
import SurveyAccess from '@/components/editor/SurveyAccess.vue'
import SurveyArchiveBadge from '@/components/SurveyArchiveBadge.vue'
import QuestionTypeIcon from '@/components/questions/QuestionTypeIcon.vue'
import { QUESTION_TYPES } from '@/utils/questionTypes'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const survey = ref(null)
const scales = ref([])
const tab = ref('questions')
const error = ref('')
const notice = ref('')
const copying = ref(false)

// Конструктор
const selected = ref(null) // id вопроса, 'new', 'section'
const sectionId = ref(null)
const outlineOpen = ref(false)
const editorHeading = ref(null)
const editorVersion = ref(0)
const questionDirty = ref(false)
const discardAction = ref(null)
const questionError = ref('')
const questionSaved = ref(false)
const saving = ref(false)
const sectionDraft = ref(null)

// Подтверждение удаления
const removal = ref(null) // { title, text, action }
const removing = ref(false)

async function confirmRemoval() {
  removing.value = true
  try {
    await removal.value.action()
  } finally {
    removing.value = false
    removal.value = null
  }
}

// Настройки
const settings = ref(null)
const settingsSaving = ref(false)
const settingsError = ref('')
const activeSaving = ref(false)
const activeError = ref('')
const accessDraft = ref([])
const accessSaving = ref(false)
const accessError = ref('')
const accessNotice = ref('')

const savedSettings = computed(() => survey.value ? settingsFromSurvey(survey.value) : {})
const settingChanged = (key) => settings.value?.[key] !== savedSettings.value[key]
const settingsDirty = computed(() => !!settings.value && Object.keys(savedSettings.value).some(settingChanged))
const groups = computed(() => {
  if (!survey.value) return []
  const known = new Set(survey.value.sections.map((s) => s.id))
  const loose = survey.value.questions.filter((q) => !q.section_id || !known.has(q.section_id))
  return [
    { section: null, questions: loose },
    ...survey.value.sections.map((section) => ({
      section,
      questions: survey.value.questions.filter((q) => q.section_id === section.id),
    })),
  ]
})

const orderedQuestions = computed(() => groups.value.flatMap((group) => group.questions))
const currentQuestion = computed(() => orderedQuestions.value.find((q) => q.id === selected.value))
const currentGroup = computed(() => groups.value.find((group) => (
  currentQuestion.value ? group.questions.includes(currentQuestion.value) : (group.section?.id ?? null) === sectionId.value
)))
const currentSection = computed(() => currentGroup.value?.section)
const position = computed(() => orderedQuestions.value.indexOf(currentQuestion.value) + 1)
const sectionHeadingChanged = computed(() => sectionDraft.value?.show_heading !== (currentSection.value?.show_heading ?? true))
const sectionDirty = computed(() => sectionDraft.value && (
  sectionDraft.value.title !== (currentSection.value?.title || '')
  || sectionDraft.value.description !== (currentSection.value?.description || '')
  || sectionHeadingChanged.value
))

const hasDraft = computed(() => questionDirty.value || sectionDirty.value || settingsDirty.value)

function confirmNavigation() {
  if (saving.value || settingsSaving.value || accessSaving.value) return false
  if (!hasDraft.value) return true
  finishDiscard(false)
  return new Promise((resolve) => {
    discardAction.value = {
      confirm: () => {
        if (settingsDirty.value) cancelSettings()
        resolve(true)
      },
      cancel: () => resolve(false),
    }
  })
}

function protectReload(event) {
  if (!hasDraft.value && !saving.value && !settingsSaving.value) return
  event.preventDefault()
  event.returnValue = true
}

onMounted(() => window.addEventListener('beforeunload', protectReload))
onUnmounted(() => {
  window.removeEventListener('beforeunload', protectReload)
  finishDiscard(false)
})

async function focusEditor() {
  outlineOpen.value = false
  await nextTick()
  editorHeading.value?.focus()
}

function resetDraft() {
  questionDirty.value = false
  questionError.value = ''
  questionSaved.value = false
  sectionDraft.value = null
  editorVersion.value += 1
}

function openQuestion(id, focus = true) {
  resetDraft()
  selected.value = id
  sectionId.value = null
  if (focus) focusEditor()
}

function openSection(section, focus = true) {
  resetDraft()
  selected.value = 'section'
  sectionId.value = section?.id ?? null
  sectionDraft.value = {
    title: section?.title || '',
    description: section?.description || '',
    show_heading: section?.show_heading ?? true,
  }
  if (focus) focusEditor()
}

function changePanel(action) {
  if (saving.value) return
  if (questionDirty.value || sectionDirty.value) discardAction.value = { confirm: action }
  else action()
}

function finishDiscard(confirmed) {
  const action = discardAction.value
  discardAction.value = null
  if (confirmed) action?.confirm()
  else action?.cancel?.()
}

function viewFromQuery(query) {
  const nextTab = typeof query.tab === 'string' && Object.hasOwn(tabs, query.tab) ? query.tab : 'questions'
  const question = orderedQuestions.value.find((item) => String(item.id) === query.question)
  const section = question ? null : survey.value.sections.find((item) => String(item.id) === query.section)
  return {
    tab: nextTab,
    questionId: section ? null : question?.id ?? orderedQuestions.value[0]?.id ?? null,
    sectionId: section?.id ?? null,
  }
}

function matchesView(view) {
  if (tab.value !== view.tab) return false
  if (selected.value === 'section') return view.sectionId != null && sectionId.value === view.sectionId
  return view.sectionId == null && selected.value === view.questionId
}

function goToView(view, replace = false) {
  const query = {
    ...route.query,
    tab: view.tab,
    question: view.questionId == null ? undefined : String(view.questionId),
    section: view.sectionId == null ? undefined : String(view.sectionId),
  }
  if (['tab', 'question', 'section'].every((key) => route.query[key] === query[key])) {
    if (!replace && !matchesView(view)) changePanel(() => restoreView(true))
    return
  }
  return router[replace ? 'replace' : 'push']({ query, hash: route.hash })
}

function restoreView(focus = false) {
  const view = viewFromQuery(route.query)
  if (!matchesView(view)) {
    tab.value = view.tab
    const focusQuestionTab = focus && view.tab === 'questions'
    if (view.sectionId != null) openSection(survey.value.sections.find((section) => section.id === view.sectionId), focusQuestionTab)
    else openQuestion(view.questionId, focusQuestionTab)
  }
  // Запоминаем вопрос по ID, чтобы при перестановке и перезагрузке он оставался выбранным.
  goToView(view, true)
}

watch(() => route.query, () => {
  if (survey.value && route.name === 'survey' && route.params.id === props.id) restoreView(true)
})

onBeforeRouteLeave(confirmNavigation)
onBeforeRouteUpdate((to) => {
  if (!survey.value) return true
  if (to.name === 'survey' && to.params.id === props.id && matchesView(viewFromQuery(to.query))) return true
  return confirmNavigation()
})

function chooseQuestion(id) {
  if (selected.value === id) focusEditor()
  else goToView({ tab: 'questions', questionId: id, sectionId: null })
}

function chooseSection(section) {
  if (selected.value === 'section' && sectionId.value === section.id) focusEditor()
  else goToView({ tab: 'questions', questionId: null, sectionId: section.id })
}

function changeTab(key) {
  if (tab.value !== key) goToView({ ...viewFromQuery(route.query), tab: key })
}

function selectSavedQuestion(id, focus = true) {
  openQuestion(id, focus)
  goToView({ tab: tab.value, questionId: id, sectionId: null }, true)
}

function resetAccessDraft(members) {
  accessDraft.value = members.map((member) => ({ ...member }))
}

function settingsFromSurvey(data) {
  return {
    title: data.title,
    description: data.description,
    intro_text: data.intro_text,
    thank_you_text: data.thank_you_text,
    one_question_per_page: data.one_question_per_page ?? false,
    is_anonymous: data.is_anonymous,
  }
}

function setSurvey(data, { keepAccessDraft = false } = {}) {
  survey.value = data
  settings.value = settingsFromSurvey(data)
  if (!keepAccessDraft) resetAccessDraft(data.members)
}

async function run(action, success = '') {
  error.value = ''
  notice.value = ''
  try {
    const result = await action()
    if (success) notice.value = success
    return result
  } catch (e) {
    error.value = errorMessage(e)
    return undefined
  }
}

onMounted(async () => {
  await run(async () => {
    const [data, scaleList] = await Promise.all([
      api.getSurvey(props.id),
      api.listScales({ survey_id: props.id }),
    ])
    setSurvey(data)
    scales.value = scaleList
    restoreView()
  })
})

const reload = async () => setSurvey(await api.getSurvey(props.id))

// --- Вопросы и разделы ---

async function saveQuestion(payload, question) {
  saving.value = true
  questionError.value = ''
  questionSaved.value = false
  notice.value = ''
  try {
    const saved = question ? await api.updateQuestion(question.id, payload) : await api.addQuestion(props.id, payload)
    survey.value.questions = question
      ? survey.value.questions.map((item) => item.id === saved.id ? saved : item)
      : [...survey.value.questions, saved]
    selectSavedQuestion(saved.id, false)
    questionSaved.value = true
  } catch (e) {
    questionError.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

function requestQuestionCopy(question) {
  if (saving.value) return
  discardAction.value = {
    title: 'Скопировать вопрос?',
    text: questionDirty.value
      ? 'Будет скопирована сохранённая версия вопроса. Несохранённые изменения будут потеряны при переходе к копии.'
      : 'Копия будет добавлена в конец текущего раздела.',
    confirmLabel: 'Скопировать',
    confirm: () => duplicateQuestion(question),
  }
}

async function duplicateQuestion(question) {
  saving.value = true
  try {
    await run(async () => {
      const copied = await api.addQuestion(props.id, {
        ...question,
        text: question.text.length <= 4992 ? `${question.text} (копия)` : question.text,
        options: question.options.filter((o) => o.is_active).map((o) => ({ ...o, id: null })),
      })
      survey.value.questions.push(copied)
      selectSavedQuestion(copied.id)
    }, 'Копия добавлена в конец раздела')
  } finally {
    saving.value = false
  }
}

function removeQuestion(question) {
  removal.value = {
    title: 'Удалить вопрос?',
    text: `«${question.text}»`,
    action: () =>
      run(async () => {
        await api.deleteQuestion(question.id)
        const index = orderedQuestions.value.findIndex((item) => item.id === question.id)
        await reload()
        selectSavedQuestion(orderedQuestions.value[index]?.id ?? orderedQuestions.value.at(-1)?.id ?? null)
      }),
  }
}

function startNew(section) {
  changePanel(() => {
    resetDraft()
    sectionId.value = section?.id ?? null
    selected.value = 'new'
    focusEditor()
  })
}

function cancelQuestion() {
  if (currentQuestion.value) openQuestion(currentQuestion.value.id)
  else restoreView(true)
}

async function moveQuestion(question, delta) {
  if (saving.value) return
  const list = survey.value.questions
  const group = list.filter((q) => (q.section_id ?? null) === (question.section_id ?? null))
  const index = group.indexOf(question)
  const target = group[index + delta]
  if (!target) return
  const order = [...list]
  const a = order.indexOf(question)
  const b = order.indexOf(target)
  ;[order[a], order[b]] = [order[b], order[a]]
  await saveOrder(survey.value.sections.map((s) => s.id), order)
}

async function moveSection(section, delta) {
  const ids = survey.value.sections.map((s) => s.id)
  const index = ids.indexOf(section.id)
  if (index + delta < 0 || index + delta >= ids.length) return
  ;[ids[index], ids[index + delta]] = [ids[index + delta], ids[index]]
  await saveOrder(ids, survey.value.questions)
}

async function saveOrder(sectionIds, questions) {
  saving.value = true
  try {
    await run(async () => {
      setSurvey(
        await api.reorder(props.id, {
          sections: sectionIds,
          questions: questions.map((q) => ({ id: q.id, section_id: q.section_id })),
        }),
      )
    })
  } finally {
    saving.value = false
  }
}

async function saveSection() {
  const draft = sectionDraft.value
  saving.value = true
  try {
    await run(async () => {
      const body = {
        title: draft.title.trim(),
        description: draft.description.trim(),
        show_heading: draft.show_heading,
        is_active: currentSection.value?.is_active ?? true,
      }
      const section = currentSection.value
        ? await api.updateSection(currentSection.value.id, body)
        : await api.addSection(props.id, body)
      await reload()
      openSection(section, false)
      goToView({ tab: tab.value, questionId: null, sectionId: section.id }, true)
    }, 'Раздел сохранён')
  } finally {
    saving.value = false
  }
}

function removeSection(section) {
  removal.value = {
    title: 'Удалить раздел?',
    text: `«${section.title}». Вопросы останутся без раздела.`,
    action: () =>
      run(async () => {
        await api.deleteSection(section.id)
        await reload()
        selectSavedQuestion(orderedQuestions.value[0]?.id ?? null)
      }),
  }
}

function onScaleCreated(scale) {
  scales.value = [...scales.value, scale].sort((a, b) => a.title.localeCompare(b.title))
}

// --- Настройки ---

function cancelSettings() {
  settings.value = settingsFromSurvey(survey.value)
  settingsError.value = ''
}

async function saveSettings() {
  if (!settingsDirty.value || settingsSaving.value || activeSaving.value || copying.value) return
  settingsSaving.value = true
  settingsError.value = ''
  notice.value = ''
  try {
    const data = await api.updateSurvey(props.id, settings.value)
    setSurvey(data, { keepAccessDraft: true })
    notice.value = 'Настройки сохранены'
  } catch (e) {
    settingsError.value = errorMessage(e)
  } finally {
    settingsSaving.value = false
  }
}

async function setArchived(archived) {
  const value = !archived
  if (activeSaving.value || settingsSaving.value || copying.value || value === survey.value.is_active) return
  activeSaving.value = true
  activeError.value = ''
  try {
    const saved = await api.updateSurvey(props.id, { is_active: value })
    survey.value.is_active = saved.is_active
  } catch (e) {
    activeError.value = errorMessage(e)
  } finally {
    activeSaving.value = false
  }
}

async function saveAccess() {
  if (accessSaving.value) return
  accessSaving.value = true
  accessError.value = ''
  accessNotice.value = ''
  try {
    const members = accessDraft.value.map(({ user_id, person_id }) => (
      user_id == null ? { person_id } : { user_id }
    ))
    const expectedUserIds = survey.value.members.map((member) => member.user_id)
    const data = await api.setSurveyAccess(props.id, members, expectedUserIds)
    survey.value.members = data.members
    survey.value.role = data.role
    resetAccessDraft(data.members)
    accessNotice.value = 'Доступ сохранён'
  } catch (e) {
    accessError.value = errorMessage(e)
  } finally {
    accessSaving.value = false
  }
}

function requestCopy() {
  if (copying.value || saving.value || settingsSaving.value || activeSaving.value || accessSaving.value) return
  const discard = hasDraft.value
  discardAction.value = {
    title: 'Сделать копию опроса?',
    text: discard
      ? 'В копию попадёт сохранённая версия опроса. Несохранённые изменения будут потеряны при переходе к копии.'
      : 'Копия будет содержать настройки, разделы и вопросы опроса.',
    confirmLabel: 'Скопировать',
    confirm: () => copy(discard),
  }
}

function discardDrafts() {
  if (settingsDirty.value) cancelSettings()
  if (selected.value === 'section') openSection(currentSection.value, false)
  else openQuestion(selected.value, false)
}

async function copy(discard = false) {
  copying.value = true
  try {
    const copied = await run(() => api.copySurvey(props.id))
    if (!copied || route.name !== 'survey' || route.params.id !== props.id) return
    if (discard) discardDrafts()
    await router.push({ name: 'survey', params: { id: copied.id } })
  } finally {
    copying.value = false
  }
}

function remove() {
  removal.value = {
    title: 'Удалить опрос?',
    text: 'Это возможно, только пока по нему нет отправленных ответов.',
    action: async () => {
      const done = await run(() => api.deleteSurvey(props.id))
      if (done !== undefined) {
        discardDrafts()
        await router.push({ name: 'surveys' })
      }
    },
  }
}

const tabs = { questions: 'Вопросы', settings: 'Настройки' }
const textarea = 'rounded-control border border-line bg-surface p-3 outline-none focus:border-brand-500'
</script>

<template>
  <div v-if="survey">
    <RouterLink :to="{ name: 'surveys' }" class="text-sm text-ink-muted hover:text-ink">← Опросы</RouterLink>
    <div class="mt-2 flex flex-wrap items-start justify-between gap-3 lg:flex-nowrap">
      <div class="flex min-w-0 flex-wrap items-center gap-3">
        <h1 class="min-w-0 text-2xl font-bold wrap-anywhere">{{ survey.title }}</h1>
        <SurveyArchiveBadge :active="survey.is_active" />
      </div>
      <div class="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:shrink-0 lg:justify-end">
        <RouterLink
          :to="{ name: 'survey-preview', params: { id: props.id }, query: route.query }"
          class="inline-flex min-h-10 items-center justify-center rounded-control bg-brand-600 px-3 text-sm font-medium text-white hover:bg-brand-700"
        >
          Предпросмотр
        </RouterLink>
        <RouterLink
          :to="{ name: 'survey-publishings', params: { id: props.id } }"
          class="inline-flex min-h-10 items-center justify-center rounded-control border border-line bg-surface px-3 text-sm font-medium hover:bg-brand-50"
        >
          Публикации
        </RouterLink>
        <UiButton
          class="px-3! text-sm"
          :loading="copying"
          :disabled="saving || settingsSaving || activeSaving || accessSaving"
          @click="requestCopy"
        >
          Сделать копию опроса
        </UiButton>
      </div>
    </div>

    <div class="mt-5 flex flex-wrap gap-1 border-b border-line" role="tablist">
      <button
        v-for="(label, key) in tabs"
        :key="key"
        type="button"
        role="tab"
        :aria-selected="tab === key"
        class="-mb-px border-b-2 px-4 py-2 text-sm font-medium"
        :class="tab === key ? 'border-brand-600 text-brand-700' : 'border-transparent text-ink-muted hover:text-ink'"
        @click="changeTab(key)"
      >
        {{ label }}
      </button>
    </div>

    <p v-if="error" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <p v-if="notice" role="status" class="mt-4 rounded-control bg-brand-50 px-3 py-2 text-sm text-brand-700">{{ notice }}</p>

    <section v-if="tab === 'questions'" class="mt-6 grid items-start gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <aside class="min-w-0 overflow-hidden rounded-card border border-line bg-surface lg:sticky lg:top-20">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-medium lg:hidden"
          :aria-expanded="outlineOpen"
          aria-controls="question-outline"
          @click="outlineOpen = !outlineOpen"
        >
          <span>Список вопросов · {{ orderedQuestions.length }}</span>
          <span aria-hidden="true">{{ outlineOpen ? '▴' : '▾' }}</span>
        </button>
        <p class="hidden px-4 pt-4 pb-2 text-sm font-semibold lg:block">Вопросы · {{ orderedQuestions.length }}</p>
        <div class="flex flex-wrap gap-2 border-b border-line p-3">
          <UiButton size="sm" :disabled="saving" @click="startNew(currentSection)">+ Вопрос</UiButton>
          <UiButton size="sm" variant="ghost" :disabled="saving" @click="changePanel(() => openSection(null))">+ Раздел</UiButton>
        </div>
        <div id="question-outline" :class="outlineOpen ? 'block' : 'hidden'" class="lg:block">
          <nav aria-label="Вопросы опроса" class="max-h-[55dvh] overflow-y-auto px-2 pb-2 lg:max-h-[calc(100dvh-14rem)]">
            <div v-for="group in groups" :key="group.section?.id ?? 'none'">
              <button
                v-if="group.section"
                type="button"
                class="mt-2 flex w-full items-center justify-between gap-2 rounded-control px-2 py-2 text-left text-sm font-semibold hover:bg-canvas"
                :class="selected === 'section' && currentSection?.id === group.section.id ? 'bg-brand-50 text-brand-700' : ''"
                :aria-current="selected === 'section' && currentSection?.id === group.section.id ? 'true' : undefined"
                :disabled="saving"
                @click="chooseSection(group.section)"
              >
                <span class="min-w-0 break-words">{{ group.section.title || 'Раздел без названия' }}</span>
                <span v-if="!group.section.is_active" class="shrink-0 text-xs font-normal text-ink-muted">Скрыт</span>
              </button>
              <p v-else-if="group.questions.length && survey.sections.length" class="px-2 pt-2 pb-1 text-xs font-semibold text-ink-muted">Без раздела</p>

              <div
                v-for="(question, index) in group.questions"
                :key="question.id"
                role="group"
                :aria-label="question.text"
                class="mt-1 flex min-w-0 items-center rounded-control hover:bg-canvas"
                :class="selected === question.id ? 'bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200 hover:bg-brand-50' : ''"
              >
                <button
                  type="button"
                  class="flex min-w-0 flex-1 items-start gap-2 rounded-control py-2 pr-1 pl-2.5 text-left focus-visible:outline-2 focus-visible:outline-brand-600"
                  :aria-current="selected === question.id ? 'true' : undefined"
                  :title="question.text"
                  :disabled="saving"
                  @click="chooseQuestion(question.id)"
                >
                  <span class="mt-0.5 grid w-5 shrink-0 justify-items-center">
                    <QuestionTypeIcon :type="question.question_type" class="text-brand-700" />
                    <span v-if="question.is_required" class="text-sm leading-none font-semibold text-red-600" role="img" aria-label="Обязательный вопрос" title="Обязательный вопрос">*</span>
                  </span>
                  <span v-if="selected === question.id && questionDirty" class="mt-1.5 size-2 shrink-0 rounded-full bg-brand-600" role="img" aria-label="Есть несохранённые изменения" />
                  <span class="min-w-0">
                    <span class="line-clamp-2 break-words text-sm font-medium">{{ question.text }}</span>
                    <span class="mt-0.5 block text-xs text-ink-muted">
                      {{ QUESTION_TYPES[question.question_type] }}<template v-if="!question.is_active"> · Скрыт</template>
                    </span>
                  </span>
                </button>
                <div class="grid shrink-0 pr-1 text-sm text-ink-muted">
                  <button
                    type="button"
                    class="grid size-7 place-items-center rounded-control hover:bg-brand-100 focus-visible:outline-2 focus-visible:outline-brand-600 disabled:opacity-30 disabled:hover:bg-transparent"
                    :disabled="index === 0"
                    :aria-disabled="saving || undefined"
                    aria-label="Вопрос выше"
                    title="Переместить выше"
                    @click="moveQuestion(question, -1)"
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    class="grid size-7 place-items-center rounded-control hover:bg-brand-100 focus-visible:outline-2 focus-visible:outline-brand-600 disabled:opacity-30 disabled:hover:bg-transparent"
                    :disabled="index === group.questions.length - 1"
                    :aria-disabled="saving || undefined"
                    aria-label="Вопрос ниже"
                    title="Переместить ниже"
                    @click="moveQuestion(question, 1)"
                  >
                    ↓
                  </button>
                </div>
              </div>
            </div>
            <p v-if="!orderedQuestions.length && !survey.sections.length" class="px-2 py-3 text-sm text-ink-muted">Вопросов пока нет.</p>
          </nav>
        </div>
      </aside>

      <div class="grid min-w-0 gap-3">
        <template v-if="currentQuestion || selected === 'new'">
          <QuestionEditor
            :key="editorVersion"
            :question="currentQuestion || null"
            :sections="survey.sections"
            :scales="scales"
            :section-id="currentSection?.id ?? null"
            :allow-create-scale="auth.canCreateSurveys"
            :saving="saving"
            :error="questionError"
            @dirty="questionDirty = $event"
            @save="saveQuestion($event, currentQuestion)"
            @cancel="cancelQuestion"
            @delete="removeQuestion(currentQuestion)"
            @scale-created="onScaleCreated"
          >
            <template #heading>
              <div class="min-w-0">
                <p v-if="currentSection" class="break-words text-xs text-ink-muted">{{ currentSection.title || 'Раздел без названия' }}</p>
                <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <h2 ref="editorHeading" tabindex="-1" class="scroll-mt-20 text-lg font-semibold outline-none">
                    {{ currentQuestion ? `Вопрос ${position} из ${orderedQuestions.length}` : 'Новый вопрос' }}
                  </h2>
                  <span v-if="questionSaved" role="status" class="rounded-control bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700">
                    Вопрос сохранён
                  </span>
                </div>
              </div>
            </template>
            <template #actions>
              <UiButton v-if="currentQuestion" size="sm" :disabled="saving" @click="requestQuestionCopy(currentQuestion)">Скопировать вопрос</UiButton>
            </template>
          </QuestionEditor>
        </template>

        <template v-else-if="selected === 'section'">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 ref="editorHeading" tabindex="-1" class="scroll-mt-20 text-lg font-semibold outline-none">{{ currentSection ? 'Настройки раздела' : 'Новый раздел' }}</h2>
            <div v-if="currentSection" class="flex flex-wrap gap-1">
              <UiButton size="sm" variant="ghost" :disabled="saving || survey.sections[0]?.id === currentSection.id" aria-label="Раздел выше" @click="moveSection(currentSection, -1)">↑</UiButton>
              <UiButton size="sm" variant="ghost" :disabled="saving || survey.sections.at(-1)?.id === currentSection.id" aria-label="Раздел ниже" @click="moveSection(currentSection, 1)">↓</UiButton>
              <UiButton size="sm" variant="danger-outline" :disabled="saving" @click="removeSection(currentSection)">Удалить раздел</UiButton>
            </div>
          </div>
          <form class="grid gap-3 rounded-card border border-line bg-surface p-4 sm:p-5" @submit.prevent="saveSection">
            <UiInput v-model="sectionDraft.title" label="Название раздела" :class="{ 'ui-changed': sectionDraft.title !== (currentSection?.title || '') }" :disabled="saving" />
            <label class="grid gap-1.5 text-sm font-medium">
              Пояснение
              <textarea v-model="sectionDraft.description" rows="3" :class="[textarea, { 'ui-changed': sectionDraft.description !== (currentSection?.description || '') }]" :disabled="saving" />
            </label>
            <UiSwitch
              v-model="sectionDraft.show_heading"
              label="Показывать название и пояснение раздела"
              hint="Если выключить, участники увидят только вопросы. Название останется в конструкторе."
              class="px-2"
              :class="{ 'ui-changed': sectionHeadingChanged }"
              :disabled="saving"
            />
            <UiFormActions
              v-if="sectionDirty || !currentSection"
              :message="sectionDirty ? 'Есть несохранённые изменения' : ''"
              :save-label="currentSection ? 'Сохранить' : 'Добавить раздел'"
              :loading="saving"
              @cancel="currentSection ? openSection(currentSection) : cancelQuestion()"
            />
          </form>
        </template>

        <UiCard v-else>
          <h2 ref="editorHeading" tabindex="-1" class="scroll-mt-20 font-semibold outline-none">Добавьте первый вопрос</h2>
          <p class="mt-1 text-sm text-ink-muted">Используйте кнопку «+ Вопрос». Чтобы разбить опрос на части, добавьте разделы.</p>
        </UiCard>
      </div>
    </section>

    <!-- Настройки -->
    <section v-else class="mt-6 grid min-w-0 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,23rem)]">
      <form class="grid min-w-0 gap-4 rounded-card border border-line bg-surface p-4 sm:p-5" @submit.prevent="saveSettings">
        <fieldset class="grid min-w-0 gap-4" :disabled="settingsSaving || copying || accessSaving">
          <UiInput v-model="settings.title" :class="{ 'ui-changed': settingChanged('title') }" label="Название" required />
          <label class="grid gap-1.5 text-sm font-medium">Описание <textarea v-model="settings.description" rows="2" :class="[textarea, { 'ui-changed': settingChanged('description') }]" /></label>
          <label class="grid gap-1.5 text-sm font-medium">
            Вступительный текст
            <textarea v-model="settings.intro_text" rows="5" :class="[textarea, { 'ui-changed': settingChanged('intro_text') }]" />
          </label>
          <label class="grid gap-1.5 text-sm font-medium">
            Текст после отправки
            <textarea v-model="settings.thank_you_text" rows="3" :class="[textarea, { 'ui-changed': settingChanged('thank_you_text') }]" />
          </label>
          <UiSwitch v-model="settings.is_anonymous" label="Новые публикации анонимны" class="justify-self-start px-2" :class="{ 'ui-changed': settingChanged('is_anonymous') }" />
          <UiSwitch
            v-model="settings.one_question_per_page"
            label="Каждый вопрос на отдельной странице"
            hint="Если выключить, вопросы каждого раздела будут показаны на одной странице."
            class="px-2"
            :class="{ 'ui-changed': settingChanged('one_question_per_page') }"
          />
        </fieldset>
        <p v-if="settingsError" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ settingsError }}</p>
        <UiFormActions v-if="settingsDirty" :loading="settingsSaving" :disabled="activeSaving || copying || accessSaving" @cancel="cancelSettings" />
      </form>

      <aside aria-label="Управление опросом" class="grid min-w-0 gap-4">
        <UiCard class="grid gap-2">
          <UiSwitch
            :model-value="!survey.is_active"
            label="В архив"
            hint="Ссылки на публикации закрываются сразу. Собранные ответы доступны."
            class="justify-self-start"
            :loading="activeSaving"
            :disabled="settingsSaving || copying"
            @update:model-value="setArchived"
          />
          <p v-if="activeError" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ activeError }}</p>
        </UiCard>

        <SurveyAccess
          v-model="accessDraft"
          :survey-id="props.id"
          :members="survey.members"
          :current-user-id="auth.user?.id ?? null"
          :saving="accessSaving || settingsSaving"
          :error="accessError"
          :notice="accessNotice"
          @save="saveAccess"
        />

        <UiButton variant="danger-outline" class="justify-self-start" :disabled="accessSaving" @click="remove">Удалить опрос</UiButton>
      </aside>
    </section>

    <UiConfirm
      :open="!!discardAction"
      :title="discardAction?.title ?? 'Перейти без сохранения?'"
      :confirm-label="discardAction?.confirmLabel ?? 'Перейти'"
      @update:open="finishDiscard(false)"
      @confirm="finishDiscard(true)"
    >
      {{ discardAction?.text ?? 'Изменения в текущем редакторе будут потеряны.' }}
    </UiConfirm>

    <UiConfirm
      :open="!!removal"
      :title="removal?.title ?? ''"
      confirm-label="Удалить"
      variant="danger"
      :loading="removing"
      @update:open="removal = null"
      @confirm="confirmRemoval"
    >
      {{ removal?.text }}
    </UiConfirm>
  </div>
  <p v-else-if="error" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>
  <SkeletonPage v-else />
</template>
