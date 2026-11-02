<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { errorMessage } from '@/api/http'
import { cabinetPublishings } from '@/api/surveys'
import SkeletonTable from '@/components/skeleton/SkeletonTable.vue'
import UiBadge from '@/components/ui/UiBadge.vue'

const publishings = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    publishings.value = await cabinetPublishings()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})

const date = (value) => new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold">Результаты опросов</h1>
    <p class="mt-1 text-ink-muted">Публикации опросов, которые вы ведёте или результаты которых вам открыли.</p>
    <p v-if="error" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <SkeletonTable v-if="loading" class="mt-6" :rows="4" />
    <p v-else-if="!publishings.length" class="mt-10 text-center text-ink-muted">Пока нет публикаций, результаты которых вам доступны.</p>
    <ul v-else class="mt-6 grid gap-3">
      <li v-for="p in publishings" :key="p.id">
        <RouterLink
          :to="{ name: 'publishing', params: { id: p.id } }"
          class="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-card border border-line bg-surface p-4 hover:border-brand-200"
        >
          <div class="min-w-0 flex-1">
            <p class="text-sm text-ink-muted">{{ p.survey_title }}</p>
            <p class="font-semibold">{{ p.title }}</p>
            <p class="mt-1 text-sm text-ink-muted">с {{ date(p.created_at) }} · ответов: {{ p.submitted_count }}</p>
          </div>
          <UiBadge :tone="p.is_active ? 'success' : 'neutral'">{{ p.is_active ? 'Идёт' : 'Закрыта' }}</UiBadge>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
