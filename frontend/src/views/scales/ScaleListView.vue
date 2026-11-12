<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { errorMessage, SkeletonTable, UiBadge, UiButton, UiDialog } from 'sk-ui'
import { listScales } from '@/api/surveys'
import ScaleEditor from '@/components/editor/ScaleEditor.vue'

const scales = ref([])
const loading = ref(true)
const error = ref('')
const editor = ref(null)
const saving = ref(false)

onMounted(async () => {
  try {
    scales.value = await listScales({ include_usage: true })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})

function openEditor(source = null) {
  editor.value = { source }
}

function closeEditor() {
  if (!saving.value) editor.value = null
}

function addScale(scale) {
  scales.value = [...scales.value, scale].sort((a, b) => a.title.localeCompare(b.title, 'ru'))
  editor.value = null
}

function numericPreview(scale) {
  const count = Math.floor((scale.max_value - scale.min_value) / scale.step) + 1
  const values = Array.from({ length: Math.min(12, count) }, (_, i) => scale.min_value + i * scale.step)
  return values.join(' · ') + (count > values.length ? ' · …' : '')
}
</script>

<template>
  <section class="min-w-0">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-lg font-semibold">Шкалы</h2>
      <UiButton variant="primary" @click="openEditor()">Новая шкала</UiButton>
    </div>
    <p v-if="error" role="alert" class="mt-4 rounded-control bg-red-100 px-4 py-3 text-sm text-red-800">{{ error }}</p>
    <SkeletonTable v-if="loading" class="mt-4" :rows="4" />
    <p v-else-if="!error && !scales.length" class="mt-6 text-sm text-ink-muted">Шкал пока нет.</p>
    <ul v-else-if="scales.length" class="mt-4 grid gap-3">
      <li v-for="scale in scales" :key="scale.id" class="min-w-0 rounded-card border border-line bg-surface p-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0 flex-1 basis-40">
            <h3 class="font-semibold wrap-anywhere">{{ scale.title }}</h3>
            <p class="mt-1 text-sm text-ink-muted">
              {{ scale.scale_type === 'items' ? `Подписей: ${scale.items.length}` : `${scale.min_value}–${scale.max_value}, шаг ${scale.step}` }}
            </p>
          </div>
          <UiButton size="sm" @click="openEditor(scale)">Копировать</UiButton>
        </div>
        <details class="mt-3 text-sm">
          <summary class="w-fit cursor-pointer font-medium text-brand-700">Предпросмотр</summary>
          <p v-if="scale.description" class="mt-2 wrap-anywhere text-ink-muted">{{ scale.description }}</p>
          <ol v-if="scale.scale_type === 'items'" class="mt-2 grid gap-2">
            <li v-for="item in scale.items" :key="item.id" class="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-control bg-canvas px-3 py-2">
              <span class="min-w-0 font-medium wrap-anywhere">{{ item.title }}</span>
              <span v-if="item.score != null" class="text-ink-muted">Баллы: {{ item.score }}</span>
              <p v-if="item.description" class="w-full wrap-anywhere text-ink-muted">{{ item.description }}</p>
            </li>
          </ol>
          <p v-else class="mt-2 font-medium wrap-anywhere">{{ numericPreview(scale) }}</p>
        </details>
        <div v-if="scale.used_in?.length" class="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span class="text-ink-muted">В ваших опросах:</span>
          <RouterLink v-for="survey in scale.used_in" :key="survey.id" :to="{ name: 'survey', params: { id: survey.id } }" class="max-w-full wrap-anywhere hover:underline">
            <UiBadge tone="brand" class="max-w-full">{{ survey.title }}</UiBadge>
          </RouterLink>
        </div>
      </li>
    </ul>

    <UiDialog :open="!!editor" :title="editor?.source ? 'Копия шкалы' : 'Новая шкала'" :busy="saving" @update:open="closeEditor">
      <ScaleEditor v-if="editor" v-model:saving="saving" :source="editor.source" embedded @created="addScale" @cancel="closeEditor" />
    </UiDialog>
  </section>
</template>
