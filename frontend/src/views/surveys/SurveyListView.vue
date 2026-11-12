<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { errorMessage, SkeletonTable, UiBadge, UiButton, UiDialog, UiInput, UiSelect } from 'sk-ui'
import { createSurvey, listSurveys } from '@/api/surveys'
import SurveyArchiveBadge from '@/components/SurveyArchiveBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { useUrlQuery } from '@/utils/useUrlQuery'

const router = useRouter()
const auth = useAuthStore()
const surveys = ref([])
const loading = ref(true)
const error = ref('')
const creating = ref(false)
const title = ref('')
const saving = ref(false)
const createError = ref('')
const search = ref('')

const roles = { editor: 'Редактор', observer: 'Наблюдатель' }
const canEdit = (survey) => survey.role === 'editor'
const actionClass = 'inline-flex min-h-9 items-center rounded-control border border-line px-3 text-sm font-medium hover:border-brand-200 hover:bg-brand-50'
const statuses = { active: 'Активные', archived: 'В архиве', all: 'Все статусы' }
const { route, setQuery } = useUrlQuery()
const status = computed({
  get: () => {
    const value = route.query.status
    if (value === 'inactive') return 'archived'
    return typeof value === 'string' && Object.hasOwn(statuses, value) ? value : 'active'
  },
  set: (value) => setQuery({ status: value === 'active' ? undefined : value }),
})
const role = computed({
  get: () => {
    const value = route.query.role
    if (value === 'owner' || value === 'admin') return 'editor'
    return typeof value === 'string' && Object.hasOwn(roles, value) ? value : ''
  },
  set: (value) => setQuery({ role: value || undefined }),
})
const searchTerm = computed(() => search.value.trim().toLocaleLowerCase('ru'))
const filtering = computed(() => !!(searchTerm.value || status.value !== 'active' || role.value))
const shown = computed(() => surveys.value.filter((survey) => {
  if (status.value !== 'all' && (status.value === 'active') !== survey.is_active) return false
  if (role.value && survey.role !== role.value) return false
  return [survey.title, survey.code].some((value) => value?.toLocaleLowerCase('ru').includes(searchTerm.value))
}))

function resetFilters() {
  search.value = ''
  if (status.value !== 'active' || role.value) setQuery({ status: undefined, role: undefined })
}

onMounted(async () => {
  try {
    surveys.value = await listSurveys()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})

function openCreate() {
  title.value = ''
  createError.value = ''
  creating.value = true
}

async function create() {
  if (saving.value) return
  const name = title.value.trim()
  if (!name) {
    createError.value = 'Введите название опроса'
    return
  }
  createError.value = ''
  saving.value = true
  try {
    const survey = await createSurvey({ title: name })
    creating.value = false
    await router.push({ name: 'survey', params: { id: survey.id } })
  } catch (e) {
    if (creating.value) createError.value = errorMessage(e)
    else error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-2xl font-bold">Опросы</h1>
      <UiButton v-if="auth.canCreateSurveys" variant="primary" @click="openCreate">Новый опрос</UiButton>
    </div>

    <UiDialog v-model:open="creating" title="Новый опрос" :busy="saving">
      <form class="grid gap-4" @submit.prevent="create">
        <UiInput
          v-model="title"
          label="Название опроса"
          placeholder="Например, «Пульс-опрос сотрудников»"
          maxlength="500"
          :disabled="saving"
          required
          autofocus
        />
        <p v-if="createError" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ createError }}</p>
        <div class="flex flex-wrap justify-end gap-2">
          <UiButton variant="secondary" :disabled="saving" @click="creating = false">Отмена</UiButton>
          <UiButton type="submit" variant="primary" :loading="saving">Создать</UiButton>
        </div>
      </form>
    </UiDialog>

    <p v-if="error" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>

    <div v-if="surveys.length" class="mt-6 grid grid-cols-1 items-center gap-3 min-[360px]:grid-cols-2 sm:flex sm:flex-wrap">
      <UiInput v-model="search" type="search" aria-label="Поиск опросов" placeholder="Название или код опроса" class="col-span-full min-w-0 sm:min-w-56 sm:flex-1" />
      <UiSelect v-model="status" aria-label="Статус опроса">
        <option v-for="(label, key) in statuses" :key="key" :value="key">{{ label }}</option>
      </UiSelect>
      <UiSelect v-model="role" aria-label="Роль в опросе">
        <option value="">Все роли</option>
        <option v-for="(label, key) in roles" :key="key" :value="key">{{ label }}</option>
      </UiSelect>
      <UiButton v-if="filtering" variant="ghost" class="col-span-full justify-self-start" @click="resetFilters">Сбросить</UiButton>
    </div>

    <SkeletonTable v-if="loading" class="mt-6" :rows="4" />
    <p v-else-if="!error && !surveys.length" class="mt-10 text-center text-ink-muted">
      {{ auth.canCreateSurveys ? 'Опросов пока нет. Создайте первый - добавьте вопросы и опубликуйте ссылку.' : 'Здесь появятся опросы, к которым вам откроют доступ.' }}
    </p>
    <p v-else-if="surveys.length && !shown.length" class="mt-10 text-center text-ink-muted">
      {{ filtering ? 'По этим условиям опросов нет.' : 'Активных опросов нет.' }}
    </p>
    <ul v-else-if="shown.length" class="mt-4 grid gap-3">
      <li
        v-for="survey in shown"
        :key="survey.id"
        class="flex min-w-0 flex-col gap-3 rounded-card border border-line bg-surface p-4 lg:flex-row lg:items-center lg:justify-between"
      >
        <div class="min-w-0">
          <div class="flex flex-col items-start gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <h2 class="min-w-0 font-semibold wrap-anywhere">{{ survey.title }}</h2>
            <div class="flex max-w-full flex-wrap gap-1.5">
              <SurveyArchiveBadge :active="survey.is_active" />
              <UiBadge>{{ roles[survey.role] || survey.role }}</UiBadge>
            </div>
          </div>
          <p class="mt-1 text-sm text-ink-muted">
            <template v-if="canEdit(survey)">Вопросов: {{ survey.questions_count }} · </template>
            Публикаций: {{ survey.publishings_count }} · Ответов: {{ survey.responses_count }}
          </p>
        </div>
        <div class="flex shrink-0 flex-wrap gap-2">
          <template v-if="canEdit(survey)">
            <RouterLink :to="{ name: 'survey', params: { id: survey.id } }" :class="actionClass">Редактировать</RouterLink>
          </template>
          <RouterLink
            v-if="canEdit(survey) || survey.publishings_count"
            :to="{ name: canEdit(survey) ? 'survey-publishings' : 'survey-results', params: { id: survey.id } }"
            :class="actionClass"
          >
            Публикации
          </RouterLink>
        </div>
      </li>
    </ul>
  </div>
</template>
