<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { errorMessage, SkeletonTable, UiButton, UiConfirm, UiDialog, UiTable } from 'sk-ui'
import { deleteScale, listScales } from '@/api/surveys'
import SurveyArchiveBadge from '@/components/SurveyArchiveBadge.vue'
import ScaleEditor from '@/components/editor/ScaleEditor.vue'

const scales = ref([])
const loading = ref(true)
const error = ref('')
const editor = ref(null)
const saving = ref(false)
const removal = ref(null)
const removing = ref(false)
const editorTitles = { new: 'Новая шкала', copy: 'Копия шкалы', edit: 'Редактирование шкалы' }
const usageHint = 'Шкала используется в вопросах'
const blockedHint = ref(null)
const columns = [
  { key: 'title', label: 'Название', primary: true, sortable: true },
  { key: 'type', label: 'Тип', sortable: true },
  { key: 'parameters', label: 'Параметры' },
  { key: 'usage', label: 'Где используется', desktopOnly: true },
  { key: 'actions', label: 'Действия', fullWidth: true, mobileLabel: false },
]
const sort = ref({ key: 'title', direction: 'ascending' })
const typeLabel = (scale) => scale.scale_type === 'items' ? 'С подписями' : 'Числовая'
const orderedScales = computed(() => [...scales.value].sort((a, b) => {
  const compareTitle = a.title.localeCompare(b.title, 'ru')
  const order = sort.value.key === 'type' ? typeLabel(a).localeCompare(typeLabel(b), 'ru') || compareTitle : compareTitle
  return sort.value.direction === 'descending' ? -order : order
}))

onMounted(async () => {
  try {
    scales.value = await listScales({ include_usage: true })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})

function openEditor(mode = 'new', source = null) {
  editor.value = { mode, source }
}

function closeEditor() {
  if (!saving.value) editor.value = null
}

function applyScale(scale) {
  scales.value = editor.value.mode === 'edit'
    ? scales.value.map((item) => item.id === scale.id ? scale : item)
    : [...scales.value, scale]
  editor.value = null
}

function markUnavailable(id, status) {
  if (status === 409) {
    scales.value = scales.value.map((scale) => scale.id === id ? { ...scale, can_delete: false } : scale)
  } else if (status === 404) {
    scales.value = scales.value.filter((scale) => scale.id !== id)
  }
}

function scaleAction(row, action) {
  if (!row.can_delete) {
    blockedHint.value = blockedHint.value === row.id ? null : row.id
  } else if (action === 'edit') {
    openEditor('edit', row)
  } else {
    removal.value = row
  }
}

async function confirmRemoval() {
  if (!removal.value || removing.value) return
  const id = removal.value.id
  removing.value = true
  error.value = ''
  try {
    await deleteScale(id)
    scales.value = scales.value.filter((scale) => scale.id !== id)
  } catch (e) {
    error.value = errorMessage(e)
    markUnavailable(id, e.response?.status)
  } finally {
    removing.value = false
    removal.value = null
  }
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
    <UiTable
      v-else-if="scales.length"
      v-model:sort="sort"
      label="Шкалы"
      :columns="columns"
      :rows="orderedScales"
      class="mt-4 md:[&_th:last-child]:w-px md:[&_th:last-child]:text-end"
    >
      <template #cell-title="{ row }">
        <p class="font-semibold">{{ row.title }}</p>
      </template>
      <template #cell-type="{ row }">{{ typeLabel(row) }}</template>
      <template #cell-parameters="{ row }">
        {{ row.scale_type === 'items' ? `Подписей: ${row.items.length}` : `${row.min_value}–${row.max_value}, шаг ${row.step}` }}
      </template>
      <template #cell-usage="{ row }">
        <span v-if="row.used_in?.length">{{ row.used_in.length }}</span>
        <span v-else-if="row.can_delete === false" class="text-ink-muted">Используется</span>
        <span v-else class="text-ink-muted">-</span>
      </template>
      <template #cell-actions="{ row }">
        <div class="flex flex-wrap items-center justify-end gap-2 md:flex-nowrap">
          <UiButton
            class="size-10 p-0!"
            :aria-label="`Копировать шкалу ${row.title}`"
            title="Копировать шкалу"
            @click="openEditor('copy', row)"
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" class="size-5">
              <rect x="8" y="8" width="12" height="12" rx="2" />
              <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
            </svg>
          </UiButton>
          <div class="relative flex flex-wrap gap-2 md:flex-nowrap">
            <UiButton
              class="size-10 p-0! aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
              :aria-label="`Редактировать шкалу ${row.title}`"
              :aria-describedby="blockedHint === row.id ? `scale-usage-${row.id}` : undefined"
              :title="row.can_delete ? 'Редактировать шкалу' : undefined"
              :aria-disabled="!row.can_delete || undefined"
              @click="scaleAction(row, 'edit')"
              @blur="blockedHint = null"
              @keydown.esc.stop="blockedHint = null"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" class="size-5">
                <path d="m14.5 5.5 4 4M4 20l1-4.5L16.5 4a2.8 2.8 0 0 1 4 4L9 19z" />
              </svg>
            </UiButton>
            <UiButton
              variant="danger-outline"
              class="size-10 p-0! aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
              :aria-label="`Удалить шкалу ${row.title}`"
              :aria-describedby="blockedHint === row.id ? `scale-usage-${row.id}` : undefined"
              :title="row.can_delete ? 'Удалить шкалу' : undefined"
              :aria-disabled="!row.can_delete || undefined"
              @click="scaleAction(row, 'delete')"
              @blur="blockedHint = null"
              @keydown.esc.stop="blockedHint = null"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" class="size-5">
                <path d="M4 6h16M9 6V4h6v2m3 0-1 14H7L6 6m4 4v6m4-6v6" />
              </svg>
            </UiButton>
            <span
              v-if="blockedHint === row.id"
              :id="`scale-usage-${row.id}`"
              role="status"
              class="absolute end-0 bottom-full z-10 mb-2 w-max max-w-56 rounded-control border border-line bg-surface px-2.5 py-1.5 text-xs text-ink shadow-sm"
            >{{ usageHint }}</span>
          </div>
        </div>
      </template>
      <template #details="{ row }">
        <div class="grid gap-3">
          <p v-if="row.description" class="wrap-anywhere text-ink-muted">{{ row.description }}</p>
          <ol v-if="row.scale_type === 'items'" class="grid gap-2">
            <li v-for="item in row.items" :key="item.id" class="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-control bg-surface px-3 py-2">
              <span class="min-w-0 font-medium wrap-anywhere">{{ item.title }}</span>
              <span v-if="item.score != null" class="text-ink-muted">Баллы: {{ item.score }}</span>
              <p v-if="item.description" class="w-full wrap-anywhere text-ink-muted">{{ item.description }}</p>
            </li>
          </ol>
          <p v-else class="font-medium wrap-anywhere">{{ numericPreview(row) }}</p>
          <div v-if="row.used_in?.length" class="grid gap-1">
            <span class="font-medium">В ваших опросах</span>
            <ul class="grid gap-1">
              <li v-for="survey in row.used_in" :key="survey.id" class="flex flex-wrap items-center gap-2">
                <RouterLink :to="{ name: 'survey', params: { id: survey.id } }" class="min-w-0 wrap-anywhere text-brand-700 hover:underline">{{ survey.title }}</RouterLink>
                <SurveyArchiveBadge :active="survey.is_active" />
              </li>
            </ul>
          </div>
        </div>
      </template>
    </UiTable>

    <UiDialog :open="!!editor" :title="editorTitles[editor?.mode || 'new']" :busy="saving" @update:open="closeEditor">
      <ScaleEditor
        v-if="editor"
        v-model:saving="saving"
        :source="editor.source"
        :editing="editor.mode === 'edit'"
        embedded
        @saved="applyScale"
        @cancel="closeEditor"
        @unavailable="markUnavailable"
      />
    </UiDialog>
    <UiConfirm
      :open="!!removal"
      title="Удалить шкалу?"
      confirm-label="Удалить"
      variant="danger"
      :loading="removing"
      @update:open="removal = null"
      @confirm="confirmRemoval"
    >
      <span class="wrap-anywhere">Шкала «{{ removal?.title }}» будет удалена из справочника.</span>
    </UiConfirm>
  </section>
</template>
