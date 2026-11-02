<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { errorMessage } from '@/api/http'
import { createSurvey, listSurveys } from '@/api/surveys'
import SkeletonTable from '@/components/skeleton/SkeletonTable.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiInput from '@/components/ui/UiInput.vue'

const router = useRouter()
const surveys = ref([])
const loading = ref(true)
const error = ref('')
const creating = ref(false)
const title = ref('')
const saving = ref(false)

const roles = { owner: 'Владелец', editor: 'Редактор', admin: 'Администратор' }

onMounted(async () => {
  try {
    surveys.value = await listSurveys()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})

async function create() {
  if (!title.value.trim()) return
  saving.value = true
  try {
    const survey = await createSurvey({ title: title.value.trim() })
    await router.push({ name: 'survey', params: { id: survey.id } })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-2xl font-bold">Опросы</h1>
      <UiButton v-if="!creating" variant="primary" @click="creating = true">Новый опрос</UiButton>
    </div>

    <form v-if="creating" class="mt-6 flex flex-wrap items-end gap-3 rounded-card border border-line bg-surface p-4" @submit.prevent="create">
      <UiInput v-model="title" class="min-w-64 flex-1" label="Название опроса" placeholder="Например, «Пульс-опрос сотрудников»" autofocus />
      <UiButton type="submit" variant="primary" :loading="saving">Создать</UiButton>
      <UiButton variant="ghost" @click="creating = false">Отмена</UiButton>
    </form>

    <p v-if="error" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>

    <SkeletonTable v-if="loading" class="mt-6" :rows="4" />
    <p v-else-if="!surveys.length" class="mt-10 text-center text-ink-muted">
      Опросов пока нет. Создайте первый — добавьте вопросы и опубликуйте ссылку.
    </p>
    <ul v-else class="mt-6 grid gap-3">
      <li v-for="survey in surveys" :key="survey.id">
        <RouterLink
          :to="{ name: 'survey', params: { id: survey.id } }"
          class="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-card border border-line bg-surface p-4 hover:border-brand-200"
        >
          <div class="min-w-0 flex-1">
            <p class="font-semibold">{{ survey.title }}</p>
            <p class="mt-1 text-sm text-ink-muted">
              Вопросов: {{ survey.questions_count }} · Публикаций: {{ survey.publishings_count }} · Ответов:
              {{ survey.responses_count }}
            </p>
          </div>
          <div class="flex gap-2">
            <UiBadge v-if="!survey.is_active" tone="warning">Выключен</UiBadge>
            <UiBadge>{{ roles[survey.role] || survey.role }}</UiBadge>
          </div>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
