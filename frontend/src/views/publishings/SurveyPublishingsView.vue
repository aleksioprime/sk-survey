<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { errorMessage, SkeletonPage, UiBadge, UiButton, UiCard, UiCopyField, UiDialog, UiInput } from 'sk-ui'
import * as api from '@/api/surveys'
import PersonPicker from '@/components/editor/PersonPicker.vue'

const props = defineProps({ id: { type: String, required: true } })
const survey = ref(null)
const publishings = ref([])
const publishingDraft = ref(null)
const publishingSaving = ref(false)
const publishingError = ref('')
const error = ref('')
const loading = ref(true)

onMounted(async () => {
  try {
    const [data, list] = await Promise.all([api.getSurvey(props.id), api.surveyPublishings(props.id)])
    survey.value = data
    publishings.value = list
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})

const publicUrl = (p) => `${window.location.origin}/s/${p.public_token}`

function newPublishing() {
  publishingError.value = ''
  publishingDraft.value = { title: '', is_anonymous: survey.value.is_anonymous, opens_at: '', closes_at: '', observers: [] }
}

function editPublishing(p) {
  publishingError.value = ''
  publishingDraft.value = {
    id: p.id,
    title: p.title,
    is_anonymous: p.is_anonymous,
    opens_at: toLocalInput(p.opens_at),
    closes_at: toLocalInput(p.closes_at),
    observers: p.observers.map((o) => ({ ...o })),
    has_responses: p.submitted_count + p.in_progress_count > 0,
  }
}

function closePublishing() {
  if (!publishingSaving.value) publishingDraft.value = null
}

function toLocalInput(value) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

async function savePublishing() {
  if (publishingSaving.value || !publishingDraft.value) return
  const d = publishingDraft.value
  publishingError.value = ''
  if (!d.title.trim()) {
    publishingError.value = 'Введите название публикации'
    return
  }
  const body = {
    title: d.title.trim(),
    is_anonymous: d.is_anonymous,
    opens_at: d.opens_at ? new Date(d.opens_at).toISOString() : null,
    closes_at: d.closes_at ? new Date(d.closes_at).toISOString() : null,
  }
  if (body.opens_at && body.closes_at && body.closes_at <= body.opens_at) {
    publishingError.value = 'Закрытие должно быть позже открытия'
    return
  }
  const original = publishings.value.find((p) => p.id === d.id)?.observers
  const observersChanged = !original || original.length !== d.observers.length
    || original.some((observer, index) => observer.person_id !== d.observers[index].person_id
      || observer.user_id !== d.observers[index].user_id)
  if (observersChanged) {
    if (d.observers.some((observer) => observer.person_id == null)) {
      publishingError.value = 'Чтобы изменить список наблюдателей, уберите из него пользователей без записи в справочнике.'
      return
    }
    body.observer_person_ids = d.observers.map((observer) => observer.person_id)
  }

  publishingSaving.value = true
  try {
    const saved = d.id ? await api.updatePublishing(d.id, body) : await api.createPublishing(props.id, body)
    publishings.value = d.id
      ? publishings.value.map((p) => p.id === saved.id ? saved : p)
      : [saved, ...publishings.value]
    publishingDraft.value = null
  } catch (e) {
    publishingError.value = errorMessage(e)
  } finally {
    publishingSaving.value = false
  }
}

async function togglePublishing(p) {
  error.value = ''
  try {
    const saved = await api.updatePublishing(p.id, { is_active: !p.is_active })
    publishings.value = publishings.value.map((item) => item.id === saved.id ? saved : item)
  } catch (e) {
    error.value = errorMessage(e)
  }
}

const publishingStatus = { open: 'Принимает ответы', scheduled: 'Запланирована', closed: 'Закрыта' }
const canPublish = computed(() => survey.value.questions.some(
  (q) => q.is_active && (!q.section_id || survey.value.sections.some((s) => s.id === q.section_id && s.is_active)),
))
</script>

<template>
  <div>
    <RouterLink :to="{ name: 'surveys' }" class="text-sm text-ink-muted hover:text-ink">← Опросы</RouterLink>
    <p v-if="survey" class="mt-2 text-sm text-ink-muted">{{ survey.title }}</p>
    <h1 class="mt-2 text-2xl font-bold">Публикации</h1>
    <p v-if="error" role="alert" class="mt-4 rounded-control bg-red-100 px-4 py-3 text-sm text-red-800">{{ error }}</p>
    <SkeletonPage v-if="loading" class="mt-6" />
    <section v-if="survey" class="mt-6 grid grid-cols-[minmax(0,1fr)] gap-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <p class="max-w-xl text-sm text-ink-muted">
          Публикация - это ссылка на опрос для конкретной группы и периода. Ответы и результаты собираются по публикации.
        </p>
        <UiButton variant="primary" :disabled="!canPublish || publishingSaving" @click="newPublishing">Новая публикация</UiButton>
      </div>
      <UiCard v-for="p in publishings" :key="p.id" class="grid grid-cols-[minmax(0,1fr)] gap-3 p-4 sm:p-5">
        <div class="flex flex-col items-start gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          <h2 class="min-w-0 font-semibold wrap-anywhere">{{ p.title }}</h2>
          <div class="flex max-w-full flex-wrap gap-1.5">
            <UiBadge :tone="p.status === 'open' ? 'success' : 'warning'">{{ publishingStatus[p.status] }}</UiBadge>
            <UiBadge>{{ p.is_anonymous ? 'Анонимная' : 'С входом через SkolStream' }}</UiBadge>
          </div>
        </div>
        <UiCopyField :value="publicUrl(p)" label="Ссылка на опрос" />
        <p class="text-sm text-ink-muted">
          Отправлено: {{ p.submitted_count }} · Начато, не отправлено: {{ p.in_progress_count }}
          <template v-if="p.observers.length"> · Наблюдатели: {{ p.observers.map((o) => o.full_name).join(', ') }}</template>
        </p>
        <div class="flex flex-wrap gap-2">
          <RouterLink :to="{ name: 'publishing', params: { id: p.id } }" class="inline-flex h-8 items-center rounded-control bg-brand-600 px-3 text-sm font-medium text-white hover:bg-brand-700">Результаты</RouterLink>
          <UiButton size="sm" :disabled="publishingSaving" @click="editPublishing(p)">Изменить</UiButton>
          <UiButton size="sm" variant="ghost" @click="togglePublishing(p)">{{ p.is_active ? 'Закрыть приём ответов' : 'Открыть снова' }}</UiButton>
        </div>
      </UiCard>

      <UiDialog
        :open="!!publishingDraft"
        :title="publishingDraft?.id ? 'Редактирование публикации' : 'Новая публикация'"
        :busy="publishingSaving"
        @update:open="closePublishing"
      >
        <form v-if="publishingDraft" class="grid gap-4" @submit.prevent="savePublishing">
          <fieldset class="grid min-w-0 gap-4" :disabled="publishingSaving">
            <UiInput v-model="publishingDraft.title" label="Название публикации" placeholder="Например, «Пульс-опрос, ноябрь 2026»" maxlength="500" required autofocus />
            <label class="flex items-start gap-2 text-sm">
              <input v-model="publishingDraft.is_anonymous" type="checkbox" class="mt-0.5 size-4 shrink-0 accent-brand-600" :disabled="publishingDraft.has_responses" />
              Анонимная - без входа, ответы не связаны с человеком
            </label>
            <p v-if="publishingDraft.has_responses" class="-mt-2 text-xs text-ink-muted">Режим анонимности зафиксирован: по публикации уже есть ответы.</p>
            <p v-else-if="!publishingDraft.is_anonymous" class="-mt-2 text-xs text-ink-muted">Участники войдут через SkolStream. В выгрузке будут ФИО и класс.</p>
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <UiInput v-model="publishingDraft.opens_at" class="min-w-0" label="Открыть с" type="datetime-local" />
              <UiInput v-model="publishingDraft.closes_at" class="min-w-0" label="Закрыть после" type="datetime-local" />
            </div>
            <PersonPicker
              v-model="publishingDraft.observers"
              label="Наблюдатели"
              hint="Видят результаты этой публикации, но не могут менять опрос."
              :disabled="publishingSaving"
              inline-results
            />
          </fieldset>
          <p v-if="publishingError" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ publishingError }}</p>
          <div class="flex flex-wrap justify-end gap-2">
            <UiButton variant="secondary" :disabled="publishingSaving" @click="closePublishing">Отмена</UiButton>
            <UiButton type="submit" variant="primary" :loading="publishingSaving">{{ publishingDraft.id ? 'Сохранить' : 'Опубликовать' }}</UiButton>
          </div>
        </form>
      </UiDialog>
    </section>
  </div>
</template>
