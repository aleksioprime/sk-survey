<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { errorMessage, SkeletonTable, UiBadge } from 'sk-ui'
import SurveyArchiveBadge from '@/components/SurveyArchiveBadge.vue'
import { cabinetPublishings } from '@/api/surveys'

const props = defineProps({ id: { type: String, required: true } })
const publishings = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    publishings.value = await cabinetPublishings(props.id)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})

const status = { open: 'Идёт', scheduled: 'Запланирована', closed: 'Закрыта' }
const date = (value) => new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
</script>

<template>
  <div>
    <RouterLink :to="{ name: 'surveys' }" class="text-sm text-ink-muted hover:text-ink">← Опросы</RouterLink>
    <div v-if="publishings.length" class="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink-muted">
      {{ publishings[0].survey_title }}
      <SurveyArchiveBadge :active="publishings[0].survey_is_active" />
    </div>
    <h1 class="mt-2 text-2xl font-bold">Публикации</h1>
    <p v-if="error" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <SkeletonTable v-if="loading" class="mt-6" :rows="4" />
    <p v-else-if="!error && !publishings.length" class="mt-10 text-center text-ink-muted">Доступных публикаций пока нет.</p>
    <ul v-else-if="publishings.length" class="mt-6 grid gap-3">
      <li v-for="p in publishings" :key="p.id">
        <RouterLink
          :to="{ name: 'publishing', params: { id: p.id } }"
          class="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-card border border-line bg-surface p-4 hover:border-brand-200"
        >
          <div class="min-w-0 flex-1">
            <p class="font-semibold wrap-anywhere">{{ p.title }}</p>
            <p class="mt-1 text-sm text-ink-muted">с {{ date(p.created_at) }} · ответов: {{ p.submitted_count }}</p>
          </div>
          <UiBadge :tone="p.status === 'open' ? 'success' : 'neutral'">{{ status[p.status] }}</UiBadge>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
