<script setup>
import { computed, ref, watch } from 'vue'
import { UiButton, UiSelect } from 'sk-ui'

const props = defineProps({
  publishingId: { type: String, required: true },
  catalog: { type: Object, required: true },
  selection: { type: Object, required: true },
})
const emit = defineEmits(['apply'])
const publications = ref([])
const filters = ref({})
const adding = ref(false)
const panel = ref(null)
const selectedQuestions = computed(() => props.catalog.questions.filter((q) => q.id in filters.value))
const availableQuestions = computed(() => props.catalog.questions.filter((q) => !(q.id in filters.value)))
const applied = computed(() => props.catalog.questions.flatMap((q) => {
  const titles = q.options.filter((o) => props.selection.options.includes(o.id)).map((o) => o.title)
  return titles.length ? [{ id: q.id, label: `${q.text}: ${titles.join(', ')}` }] : []
}))
watch(() => [props.selection, props.catalog], () => {
  publications.value = [props.publishingId, ...props.selection.publications]
  filters.value = {}
  for (const q of props.catalog.questions) {
    const ids = q.options.map((o) => o.id).filter((id) => props.selection.options.includes(id))
    if (ids.length) filters.value[q.id] = ids
  }
  adding.value = false
}, { immediate: true })

function add(id) {
  if (!id) return
  filters.value[id] = []
  adding.value = false
}
function apply() {
  emit('apply', {
    publications: [...publications.value],
    options: Object.values(filters.value).flat(),
  })
  panel.value.open = false
}
function reset() {
  publications.value = [props.publishingId]
  filters.value = {}
  adding.value = false
  apply()
}
</script>

<template>
  <details ref="panel" class="mt-5 rounded-card border border-line bg-surface">
    <summary class="cursor-pointer px-4 py-3 text-sm font-semibold">Публикации и фильтры</summary>
    <form class="grid gap-4 border-t border-line p-4" @submit.prevent="apply">
      <fieldset class="min-w-0">
        <legend class="mb-2 font-semibold">Публикации в отчёте</legend>
        <div class="flex flex-wrap gap-x-5 gap-y-2">
          <label v-for="p in catalog.publications" :key="p.id" class="flex min-w-0 max-w-full items-start gap-2 text-sm">
            <input v-model="publications" type="checkbox" :value="p.id" class="mt-0.5 shrink-0 accent-brand-600">
            <span class="wrap-anywhere">{{ p.title }}</span>
          </label>
        </div>
      </fieldset>
      <div v-if="catalog.questions.length" class="grid gap-3">
        <h2 class="font-semibold">Фильтры по ответам</h2>
        <p v-if="selectedQuestions.length" class="text-sm text-ink-muted">В каждом вопросе достаточно одного из отмеченных вариантов. Если вопросов несколько, ответ должен подходить под каждый фильтр.</p>
        <div class="grid grid-cols-[repeat(auto-fill,minmax(min(100%,18rem),1fr))] items-end gap-3">
          <div v-for="q in selectedQuestions" :key="q.id" class="grid min-w-0 gap-1">
            <div class="flex items-center justify-between gap-2">
              <label :for="`report-options-${q.id}`" class="text-sm font-semibold wrap-anywhere">{{ q.text }}</label>
              <UiButton size="sm" variant="ghost" :aria-label="`Убрать фильтр: ${q.text}`" @click="delete filters[q.id]">Убрать</UiButton>
            </div>
            <UiSelect :id="`report-options-${q.id}`" v-model="filters[q.id]" multiple class="w-full" placeholder="Выберите варианты ответа">
              <option v-for="o in q.options" :key="o.id" :value="o.id">{{ o.title }}</option>
            </UiSelect>
          </div>
          <div v-if="adding" class="grid min-w-0 gap-1 text-sm">
            <label for="report-filter-question">Вопрос для фильтра</label>
            <UiSelect id="report-filter-question" class="w-full" :model-value="null" @update:model-value="add">
              <option :value="null" disabled>Выберите вопрос</option>
              <option v-for="q in availableQuestions" :key="q.id" :value="q.id">{{ q.text }}</option>
            </UiSelect>
          </div>
          <div v-else-if="availableQuestions.length">
            <UiButton size="sm" @click="adding = true">Добавить фильтр</UiButton>
          </div>
        </div>
      </div>
      <div class="flex flex-wrap gap-2">
        <UiButton type="submit" size="sm" variant="primary" :disabled="!publications.length || Object.values(filters).some((ids) => !ids.length)">Применить</UiButton>
        <UiButton size="sm" variant="ghost" @click="reset">Сбросить</UiButton>
      </div>
    </form>
  </details>
  <ul v-if="applied.length" aria-label="Применённые фильтры" class="mt-2 flex flex-wrap gap-2 text-sm">
    <li v-for="filter in applied" :key="filter.id" class="rounded-control bg-brand-50 px-2 py-1 wrap-anywhere">{{ filter.label }}</li>
  </ul>
</template>
