<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { errorMessage, SkeletonPage, UiBadge, UiButton, UiCard, UiConfirm, UiCopyField, UiInput } from 'sk-ui'
import * as api from '@/api/surveys'
import PersonPicker from '@/components/editor/PersonPicker.vue'
import QuestionEditor from '@/components/editor/QuestionEditor.vue'
import ScaleEditor from '@/components/editor/ScaleEditor.vue'
import QuestionTypeIcon from '@/components/questions/QuestionTypeIcon.vue'
import { QUESTION_TYPES } from '@/utils/questionTypes'

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()

const survey = ref(null)
const scales = ref([])
const publishings = ref([])
const tab = ref('questions')
const error = ref('')
const notice = ref('')

// Конструктор
const selected = ref(null) // id вопроса, 'new', 'section'
const sectionId = ref(null)
const outlineOpen = ref(false)
const editorHeading = ref(null)
const editorVersion = ref(0)
const questionDirty = ref(false)
const discardAction = ref(null)
const questionError = ref('')
const saving = ref(false)
const scaleForm = ref(false)
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
const editors = ref([])

// Публикации
const publishingDraft = ref(null)

const isOwner = computed(() => ['owner', 'admin'].includes(survey.value?.role))
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
const questionIndex = computed(() => currentGroup.value?.questions.indexOf(currentQuestion.value) ?? -1)
const position = computed(() => orderedQuestions.value.indexOf(currentQuestion.value) + 1)
const sectionDirty = computed(() => sectionDraft.value && (
  sectionDraft.value.title !== (currentSection.value?.title || '')
  || sectionDraft.value.description !== (currentSection.value?.description || '')
))

async function focusEditor() {
  outlineOpen.value = false
  await nextTick()
  editorHeading.value?.focus()
}

function resetDraft() {
  questionDirty.value = false
  questionError.value = ''
  scaleForm.value = false
  sectionDraft.value = null
  editorVersion.value += 1
}

function openQuestion(id, focus = true) {
  resetDraft()
  selected.value = id
  if (focus) focusEditor()
}

function openSection(section, focus = true) {
  resetDraft()
  selected.value = 'section'
  sectionId.value = section?.id ?? null
  sectionDraft.value = { title: section?.title || '', description: section?.description || '' }
  if (focus) focusEditor()
}

function changePanel(action) {
  if (saving.value) return
  if (questionDirty.value || sectionDirty.value) discardAction.value = action
  else action()
}

function discardAndContinue() {
  const action = discardAction.value
  discardAction.value = null
  action?.()
}

function chooseQuestion(id) {
  if (selected.value === id) focusEditor()
  else changePanel(() => openQuestion(id))
}

function changeTab(key) {
  if (tab.value === key) return
  changePanel(() => {
    if (selected.value === 'section') openSection(currentSection.value, false)
    else if (selected.value === 'new') openQuestion(orderedQuestions.value[0]?.id ?? null, false)
    else resetDraft()
    tab.value = key
  })
}

function setSurvey(data) {
  survey.value = data
  settings.value = {
    title: data.title,
    code: data.code || '',
    description: data.description,
    intro_text: data.intro_text,
    thank_you_text: data.thank_you_text,
    is_active: data.is_active,
    is_anonymous: data.is_anonymous,
  }
  editors.value = data.members.filter((m) => m.role === 'editor').map((m) => ({ ...m }))
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
    const [data, scaleList, publishingList] = await Promise.all([
      api.getSurvey(props.id),
      api.listScales(),
      api.surveyPublishings(props.id),
    ])
    setSurvey(data)
    selected.value = orderedQuestions.value[0]?.id ?? null
    scales.value = scaleList
    publishings.value = publishingList
  })
})

const reload = async () => setSurvey(await api.getSurvey(props.id))

// --- Вопросы и разделы ---

async function saveQuestion(payload, question) {
  saving.value = true
  questionError.value = ''
  notice.value = ''
  try {
    const saved = question ? await api.updateQuestion(question.id, payload) : await api.addQuestion(props.id, payload)
    survey.value.questions = question
      ? survey.value.questions.map((item) => item.id === saved.id ? saved : item)
      : [...survey.value.questions, saved]
    openQuestion(saved.id, false)
    notice.value = 'Вопрос сохранён'
  } catch (e) {
    questionError.value = errorMessage(e)
  } finally {
    saving.value = false
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
      openQuestion(copied.id)
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
        openQuestion(orderedQuestions.value[index]?.id ?? orderedQuestions.value.at(-1)?.id ?? null)
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
  else if (currentSection.value) openSection(currentSection.value)
  else openQuestion(orderedQuestions.value[0]?.id ?? null)
}

async function moveQuestion(question, delta) {
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
      const body = { title: draft.title.trim(), description: draft.description.trim(), is_active: currentSection.value?.is_active ?? true }
      const section = currentSection.value
        ? await api.updateSection(currentSection.value.id, body)
        : await api.addSection(props.id, body)
      await reload()
      openSection(section, false)
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
        openQuestion(orderedQuestions.value[0]?.id ?? null)
      }),
  }
}

function onScaleCreated(scale) {
  scales.value = [...scales.value, scale].sort((a, b) => a.title.localeCompare(b.title))
  scaleForm.value = false
}

// --- Настройки ---

async function saveSettings() {
  await run(async () => {
    setSurvey(await api.updateSurvey(props.id, { ...settings.value, code: settings.value.code.trim() || null }))
  }, 'Настройки сохранены')
}

async function saveEditors() {
  await run(async () => setSurvey(await api.setEditors(props.id, editors.value.map((e) => e.person_id))), 'Редакторы сохранены')
}

async function copy() {
  const copied = await run(() => api.copySurvey(props.id))
  if (copied) await router.push({ name: 'survey', params: { id: copied.id } })
}

function remove() {
  removal.value = {
    title: 'Удалить опрос?',
    text: 'Это возможно, только пока по нему нет отправленных ответов.',
    action: async () => {
      const done = await run(() => api.deleteSurvey(props.id))
      if (done !== undefined) await router.push({ name: 'surveys' })
    },
  }
}

// --- Публикации ---

const publicUrl = (p) => `${window.location.origin}/s/${p.public_token}`

function newPublishing() {
  publishingDraft.value = { title: '', is_anonymous: survey.value.is_anonymous, opens_at: '', closes_at: '', observers: [] }
}

function editPublishing(p) {
  publishingDraft.value = {
    id: p.id,
    title: p.title,
    is_anonymous: p.is_anonymous,
    is_active: p.is_active,
    opens_at: toLocalInput(p.opens_at),
    closes_at: toLocalInput(p.closes_at),
    observers: p.observers.map((o) => ({ ...o })),
    has_responses: p.submitted_count + p.in_progress_count > 0,
  }
}

function toLocalInput(value) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

async function savePublishing() {
  const d = publishingDraft.value
  const body = {
    title: d.title.trim(),
    is_anonymous: d.is_anonymous,
    opens_at: d.opens_at ? new Date(d.opens_at).toISOString() : null,
    closes_at: d.closes_at ? new Date(d.closes_at).toISOString() : null,
    observer_person_ids: d.observers.map((o) => o.person_id),
  }
  if (body.opens_at && body.closes_at && body.closes_at <= body.opens_at) {
    error.value = 'Закрытие должно быть позже открытия'
    return
  }
  await run(async () => {
    if (d.id) await api.updatePublishing(d.id, { ...body, is_active: d.is_active })
    else await api.createPublishing(props.id, body)
    publishingDraft.value = null
    publishings.value = await api.surveyPublishings(props.id)
  })
}

async function togglePublishing(p) {
  await run(async () => {
    await api.updatePublishing(p.id, { is_active: !p.is_active })
    publishings.value = await api.surveyPublishings(props.id)
  })
}

const publishingStatus = { open: 'Принимает ответы', scheduled: 'Запланирована', closed: 'Закрыта' }
const canPublish = computed(() => survey.value.questions.some(
  (q) => q.is_active && (!q.section_id || survey.value.sections.some((s) => s.id === q.section_id && s.is_active)),
))
const tabs = { questions: 'Вопросы', publishings: 'Публикации', settings: 'Настройки' }
const textarea = 'rounded-control border border-line bg-surface p-3 outline-none focus:border-brand-500'
</script>

<template>
  <div v-if="survey">
    <RouterLink :to="{ name: 'surveys' }" class="text-sm text-ink-muted hover:text-ink">← Опросы</RouterLink>
    <div class="mt-2 flex flex-wrap items-center gap-3">
      <h1 class="text-2xl font-bold">{{ survey.title }}</h1>
      <UiBadge v-if="!survey.is_active" tone="warning">Выключен</UiBadge>
    </div>

    <RouterLink
      :to="{ name: 'survey-preview', params: { id: props.id } }"
      target="_blank"
      rel="noopener"
      class="mt-3 inline-block text-sm font-medium text-brand-700 hover:underline"
    >Предпросмотр ↗</RouterLink>

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
                @click="changePanel(() => openSection(group.section))"
              >
                <span class="min-w-0 break-words">{{ group.section.title || 'Раздел без названия' }}</span>
                <span v-if="!group.section.is_active" class="shrink-0 text-xs font-normal text-ink-muted">Скрыт</span>
              </button>
              <p v-else-if="group.questions.length && survey.sections.length" class="px-2 pt-2 pb-1 text-xs font-semibold text-ink-muted">Без раздела</p>

              <button
                v-for="question in group.questions"
                :key="question.id"
                type="button"
                class="mt-1 flex w-full items-start gap-2.5 rounded-control px-2.5 py-2 text-left hover:bg-canvas"
                :class="selected === question.id ? 'bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200 hover:bg-brand-50' : ''"
                :aria-current="selected === question.id ? 'true' : undefined"
                :title="question.text"
                :disabled="saving"
                @click="chooseQuestion(question.id)"
              >
                <QuestionTypeIcon :type="question.question_type" class="mt-0.5 text-brand-700" />
                <span class="min-w-0">
                  <span class="line-clamp-2 break-words text-sm font-medium">{{ question.text }}<span v-if="question.is_required" class="text-red-600" aria-label="Обязательный"> *</span></span>
                  <span class="mt-0.5 block text-xs text-ink-muted">
                    {{ QUESTION_TYPES[question.question_type] }}<template v-if="!question.is_active"> · Скрыт</template>
                  </span>
                </span>
              </button>
            </div>
            <p v-if="!orderedQuestions.length && !survey.sections.length" class="px-2 py-3 text-sm text-ink-muted">Вопросов пока нет.</p>
          </nav>
        </div>
      </aside>

      <div class="grid min-w-0 gap-3">
        <template v-if="currentQuestion || selected === 'new'">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="min-w-0">
              <p v-if="currentSection" class="break-words text-xs text-ink-muted">{{ currentSection.title || 'Раздел без названия' }}</p>
              <h2 ref="editorHeading" tabindex="-1" class="scroll-mt-20 text-lg font-semibold outline-none">
                {{ currentQuestion ? `Вопрос ${position} из ${orderedQuestions.length}` : 'Новый вопрос' }}
              </h2>
              <p v-if="questionDirty" class="text-xs text-ink-muted">Есть несохранённые изменения</p>
            </div>
            <div v-if="currentQuestion" class="flex flex-wrap gap-1">
              <UiButton size="sm" variant="ghost" :disabled="saving || questionIndex <= 0" aria-label="Вопрос выше" title="Вопрос выше" @click="moveQuestion(currentQuestion, -1)">↑</UiButton>
              <UiButton size="sm" variant="ghost" :disabled="saving || questionIndex >= currentGroup.questions.length - 1" aria-label="Вопрос ниже" title="Вопрос ниже" @click="moveQuestion(currentQuestion, 1)">↓</UiButton>
              <UiButton size="sm" :disabled="saving" @click="changePanel(() => duplicateQuestion(currentQuestion))">Скопировать вопрос</UiButton>
            </div>
          </div>
          <QuestionEditor
            :key="editorVersion"
            :question="currentQuestion || null"
            :sections="survey.sections"
            :scales="scales"
            :section-id="currentSection?.id ?? null"
            :saving="saving"
            :error="questionError"
            @dirty="questionDirty = $event"
            @save="saveQuestion($event, currentQuestion)"
            @cancel="cancelQuestion"
            @delete="removeQuestion(currentQuestion)"
            @new-scale="scaleForm = true"
          />
          <ScaleEditor v-if="scaleForm" @created="onScaleCreated" @cancel="scaleForm = false" />
        </template>

        <template v-else-if="selected === 'section'">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 ref="editorHeading" tabindex="-1" class="scroll-mt-20 text-lg font-semibold outline-none">{{ currentSection ? 'Настройки раздела' : 'Новый раздел' }}</h2>
            <div v-if="currentSection" class="flex flex-wrap gap-1">
              <UiButton size="sm" variant="ghost" :disabled="saving || survey.sections[0]?.id === currentSection.id" aria-label="Раздел выше" @click="moveSection(currentSection, -1)">↑</UiButton>
              <UiButton size="sm" variant="ghost" :disabled="saving || survey.sections.at(-1)?.id === currentSection.id" aria-label="Раздел ниже" @click="moveSection(currentSection, 1)">↓</UiButton>
              <UiButton size="sm" variant="ghost" class="text-red-600" :disabled="saving" @click="removeSection(currentSection)">Удалить раздел</UiButton>
            </div>
          </div>
          <form class="grid gap-3 rounded-card border border-line bg-surface p-4 sm:p-5" @submit.prevent="saveSection">
            <UiInput v-model="sectionDraft.title" label="Название раздела" />
            <label class="grid gap-1.5 text-sm font-medium">
              Пояснение
              <textarea v-model="sectionDraft.description" rows="3" :class="textarea" />
            </label>
            <div class="flex gap-2">
              <UiButton type="submit" variant="primary" size="sm" :loading="saving">Сохранить раздел</UiButton>
              <UiButton size="sm" variant="ghost" :disabled="saving" @click="currentSection ? openSection(currentSection) : cancelQuestion()">Отмена</UiButton>
            </div>
          </form>
        </template>

        <UiCard v-else>
          <h2 ref="editorHeading" tabindex="-1" class="scroll-mt-20 font-semibold outline-none">Добавьте первый вопрос</h2>
          <p class="mt-1 text-sm text-ink-muted">Используйте кнопку «+ Вопрос». Чтобы разбить опрос на части, добавьте разделы.</p>
        </UiCard>
      </div>
    </section>

    <!-- Публикации -->
    <section v-else-if="tab === 'publishings'" class="mt-6 grid gap-4">
      <p class="text-sm text-ink-muted">
        Публикация — это ссылка на опрос для конкретной группы и периода. Ответы и результаты собираются по публикации.
      </p>
      <UiCard v-for="p in publishings" :key="p.id" class="grid gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <h2 class="font-semibold">{{ p.title }}</h2>
          <UiBadge :tone="p.status === 'open' ? 'success' : 'warning'">{{ publishingStatus[p.status] }}</UiBadge>
          <UiBadge>{{ p.is_anonymous ? 'Анонимная' : 'С входом через SkolStream' }}</UiBadge>
        </div>
        <UiCopyField :value="publicUrl(p)" label="Ссылка на опрос" />
        <p class="text-sm text-ink-muted">
          Отправлено: {{ p.submitted_count }} · Начато, не отправлено: {{ p.in_progress_count }}
          <template v-if="p.observers.length"> · Наблюдатели: {{ p.observers.map((o) => o.full_name).join(', ') }}</template>
        </p>
        <div class="flex flex-wrap gap-2">
          <RouterLink :to="{ name: 'publishing', params: { id: p.id } }" class="inline-flex h-8 items-center rounded-control bg-brand-600 px-3 text-sm font-medium text-white hover:bg-brand-700">Результаты</RouterLink>
          <UiButton size="sm" @click="editPublishing(p)">Изменить</UiButton>
          <UiButton size="sm" variant="ghost" @click="togglePublishing(p)">{{ p.is_active ? 'Закрыть приём ответов' : 'Открыть снова' }}</UiButton>
        </div>
      </UiCard>

      <form v-if="publishingDraft" class="grid gap-4 rounded-card border border-brand-200 bg-surface p-4" @submit.prevent="savePublishing">
        <UiInput v-model="publishingDraft.title" label="Название публикации" placeholder="Например, «Опрос в конце года, 2026»" required />
        <label class="flex items-center gap-2 text-sm">
          <input v-model="publishingDraft.is_anonymous" type="checkbox" class="accent-brand-600" :disabled="publishingDraft.has_responses" />
          Анонимная — без входа, ответы не связаны с человеком
        </label>
        <p v-if="!publishingDraft.is_anonymous" class="-mt-2 text-xs text-ink-muted">Отвечающие входят через SkolStream; у каждого одно прохождение, в выгрузке — ФИО и класс.</p>
        <div class="flex flex-wrap gap-4">
          <UiInput v-model="publishingDraft.opens_at" label="Открыть с" type="datetime-local" />
          <UiInput v-model="publishingDraft.closes_at" label="Закрыть после" type="datetime-local" />
        </div>
        <PersonPicker v-model="publishingDraft.observers" label="Наблюдатели" hint="Видят результаты этой публикации, но не могут менять опрос." />
        <div class="flex gap-2">
          <UiButton type="submit" variant="primary">{{ publishingDraft.id ? 'Сохранить' : 'Опубликовать' }}</UiButton>
          <UiButton variant="ghost" @click="publishingDraft = null">Отмена</UiButton>
        </div>
      </form>
      <UiButton v-else variant="primary" class="justify-self-start" :disabled="!canPublish" @click="newPublishing">Новая публикация</UiButton>
    </section>

    <!-- Настройки -->
    <section v-else class="mt-6 grid max-w-3xl gap-6">
      <form class="grid gap-4 rounded-card border border-line bg-surface p-5" @submit.prevent="saveSettings">
        <UiInput v-model="settings.title" label="Название" required />
        <UiInput v-model="settings.code" label="Код" hint="Латиница, цифры, «_» и «-». Для выгрузок и поиска, необязательно." />
        <label class="grid gap-1.5 text-sm font-medium">Описание <textarea v-model="settings.description" rows="2" :class="textarea" /></label>
        <label class="grid gap-1.5 text-sm font-medium">
          Вступительный текст <span class="font-normal text-ink-muted">— на первом экране опроса</span>
          <textarea v-model="settings.intro_text" rows="5" :class="textarea" />
        </label>
        <label class="grid gap-1.5 text-sm font-medium">
          Текст после отправки
          <textarea v-model="settings.thank_you_text" rows="3" :class="textarea" />
        </label>
        <label class="flex items-center gap-2 text-sm"><input v-model="settings.is_active" type="checkbox" class="accent-brand-600" /> Опрос включён (выключенный не открывается по ссылкам)</label>
        <label class="flex items-center gap-2 text-sm"><input v-model="settings.is_anonymous" type="checkbox" class="accent-brand-600" /> Новые публикации — анонимные</label>
        <UiButton type="submit" variant="primary" class="justify-self-start">Сохранить</UiButton>
      </form>

      <UiCard v-if="isOwner" class="grid gap-4">
        <PersonPicker v-model="editors" label="Редакторы" hint="Могут менять вопросы и публикации, видят результаты." />
        <UiButton class="justify-self-start" @click="saveEditors">Сохранить редакторов</UiButton>
      </UiCard>

      <div class="flex flex-wrap gap-2">
        <UiButton @click="copy">Сделать копию опроса</UiButton>
        <UiButton v-if="isOwner" variant="ghost" class="text-red-600" @click="remove">Удалить опрос</UiButton>
      </div>
    </section>

    <UiConfirm
      :open="!!discardAction"
      title="Перейти без сохранения?"
      confirm-label="Перейти"
      @update:open="discardAction = null"
      @confirm="discardAndContinue"
    >
      Изменения в текущем редакторе будут потеряны.
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
