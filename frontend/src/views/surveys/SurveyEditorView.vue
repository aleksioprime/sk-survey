<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { errorMessage, SkeletonPage, UiBadge, UiButton, UiCard, UiConfirm, UiCopyField, UiInput } from 'sk-ui'
import * as api from '@/api/surveys'
import PersonPicker from '@/components/editor/PersonPicker.vue'
import QuestionEditor from '@/components/editor/QuestionEditor.vue'
import ScaleEditor from '@/components/editor/ScaleEditor.vue'
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
const editing = ref(null) // id вопроса | 'new:<sectionId|none>'
const questionError = ref('')
const saving = ref(false)
const scaleForm = ref(false)
const sectionDraft = ref(null) // { id?, title, description }

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
    scales.value = scaleList
    publishings.value = publishingList
  })
})

const reload = async () => setSurvey(await api.getSurvey(props.id))

// --- Вопросы и разделы ---

async function saveQuestion(payload, question) {
  saving.value = true
  questionError.value = ''
  try {
    if (question) await api.updateQuestion(question.id, payload)
    else await api.addQuestion(props.id, payload)
    editing.value = null
    await reload()
  } catch (e) {
    questionError.value = errorMessage(e)
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
        editing.value = null
        await reload()
      }),
  }
}

function startNew(section) {
  questionError.value = ''
  editing.value = `new:${section?.id ?? 'none'}`
}

function newSectionId(key) {
  const raw = key.split(':')[1]
  return raw === 'none' ? null : Number(raw)
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
  await run(async () => {
    setSurvey(
      await api.reorder(props.id, {
        sections: sectionIds,
        questions: questions.map((q) => ({ id: q.id, section_id: q.section_id })),
      }),
    )
  })
}

async function saveSection() {
  const draft = sectionDraft.value
  await run(async () => {
    const body = { title: draft.title.trim(), description: draft.description.trim() }
    if (draft.id) await api.updateSection(draft.id, body)
    else await api.addSection(props.id, body)
    sectionDraft.value = null
    await reload()
  })
}

function removeSection(section) {
  removal.value = {
    title: 'Удалить раздел?',
    text: `«${section.title}». Вопросы останутся без раздела.`,
    action: () =>
      run(async () => {
        await api.deleteSection(section.id)
        await reload()
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

    <div class="mt-5 flex gap-1 border-b border-line" role="tablist">
      <button
        v-for="(label, key) in tabs"
        :key="key"
        type="button"
        role="tab"
        :aria-selected="tab === key"
        class="-mb-px border-b-2 px-4 py-2 text-sm font-medium"
        :class="tab === key ? 'border-brand-600 text-brand-700' : 'border-transparent text-ink-muted hover:text-ink'"
        @click="tab = key"
      >
        {{ label }}
      </button>
    </div>

    <p v-if="error" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <p v-if="notice" role="status" class="mt-4 rounded-control bg-brand-50 px-3 py-2 text-sm text-brand-700">{{ notice }}</p>

    <!-- Вопросы -->
    <section v-if="tab === 'questions'" class="mt-6 grid gap-6">
      <div v-for="group in groups" :key="group.section?.id ?? 'none'" class="grid gap-3">
        <div v-if="group.section" class="flex flex-wrap items-center gap-2">
          <h2 class="text-lg font-semibold">{{ group.section.title || 'Раздел без названия' }}</h2>
          <UiBadge v-if="!group.section.is_active" tone="warning">Скрыт</UiBadge>
          <div class="ml-auto flex gap-1 text-sm">
            <UiButton size="sm" variant="ghost" aria-label="Раздел выше" @click="moveSection(group.section, -1)">↑</UiButton>
            <UiButton size="sm" variant="ghost" aria-label="Раздел ниже" @click="moveSection(group.section, 1)">↓</UiButton>
            <UiButton size="sm" variant="ghost" @click="sectionDraft = { id: group.section.id, title: group.section.title, description: group.section.description }">Изменить</UiButton>
            <UiButton size="sm" variant="ghost" class="text-red-600" @click="removeSection(group.section)">Удалить</UiButton>
          </div>
        </div>
        <p v-if="group.section?.description" class="-mt-2 text-sm text-ink-muted">{{ group.section.description }}</p>
        <p v-else-if="!group.section && group.questions.length && survey.sections.length" class="text-sm font-medium text-ink-muted">Без раздела</p>

        <template v-for="(question, index) in group.questions" :key="question.id">
          <QuestionEditor
            v-if="editing === question.id"
            :question="question"
            :sections="survey.sections"
            :scales="scales"
            :saving="saving"
            :error="questionError"
            @save="saveQuestion($event, question)"
            @cancel="editing = null"
            @delete="removeQuestion(question)"
            @new-scale="scaleForm = true"
          />
          <UiCard v-else class="flex items-start gap-3" :class="!question.is_active ? 'opacity-60' : ''">
            <div class="min-w-0 flex-1">
              <p class="font-medium">{{ question.text }}<span v-if="question.is_required" class="text-red-600"> *</span></p>
              <p class="mt-1 flex flex-wrap gap-2 text-xs text-ink-muted">
                <span>{{ QUESTION_TYPES[question.question_type] }}</span>
                <span v-if="question.options.length">· вариантов: {{ question.options.filter((o) => o.is_active).length }}</span>
                <span v-if="question.answers_count">· ответов: {{ question.answers_count }}</span>
                <span v-if="!question.is_active">· скрыт</span>
              </p>
            </div>
            <div class="flex shrink-0 gap-1 text-sm">
              <UiButton size="sm" variant="ghost" :disabled="index === 0" aria-label="Выше" @click="moveQuestion(question, -1)">↑</UiButton>
              <UiButton size="sm" variant="ghost" :disabled="index === group.questions.length - 1" aria-label="Ниже" @click="moveQuestion(question, 1)">↓</UiButton>
              <UiButton size="sm" variant="ghost" class="text-brand-700!" @click="(editing = question.id), (questionError = '')">Изменить</UiButton>
            </div>
          </UiCard>
        </template>

        <QuestionEditor
          v-if="editing === `new:${group.section?.id ?? 'none'}`"
          :sections="survey.sections"
          :scales="scales"
          :section-id="newSectionId(editing)"
          :saving="saving"
          :error="questionError"
          @save="saveQuestion($event, null)"
          @cancel="editing = null"
          @new-scale="scaleForm = true"
        />
        <UiButton v-else-if="group.section || !survey.sections.length" size="sm" class="justify-self-start" @click="startNew(group.section)">
          + Вопрос{{ group.section ? ' в раздел' : '' }}
        </UiButton>
      </div>

      <ScaleEditor v-if="scaleForm" @created="onScaleCreated" @cancel="scaleForm = false" />

      <form v-if="sectionDraft" class="grid gap-3 rounded-card border border-brand-200 bg-surface p-4" @submit.prevent="saveSection">
        <UiInput v-model="sectionDraft.title" label="Название раздела" autofocus />
        <label class="grid gap-1.5 text-sm font-medium">
          Пояснение
          <textarea v-model="sectionDraft.description" rows="2" :class="textarea" />
        </label>
        <div class="flex gap-2">
          <UiButton type="submit" variant="primary" size="sm">Сохранить раздел</UiButton>
          <UiButton size="sm" variant="ghost" @click="sectionDraft = null">Отмена</UiButton>
        </div>
      </form>
      <UiButton v-else class="justify-self-start" @click="sectionDraft = { title: '', description: '' }">+ Раздел</UiButton>
    </section>

    <!-- Публикации -->
    <section v-else-if="tab === 'publishings'" class="mt-6 grid gap-4">
      <p class="text-sm text-ink-muted">
        Публикация — это ссылка на опрос для конкретной группы и периода. Ответы и результаты собираются по публикации.
      </p>
      <UiCard v-for="p in publishings" :key="p.id" class="grid gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <h2 class="font-semibold">{{ p.title }}</h2>
          <UiBadge :tone="p.is_active ? 'success' : 'warning'">{{ p.is_active ? 'Принимает ответы' : 'Закрыта' }}</UiBadge>
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
      <UiButton v-else variant="primary" class="justify-self-start" :disabled="!survey.questions.length" @click="newPublishing">Новая публикация</UiButton>
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
