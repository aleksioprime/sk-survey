<script setup>
import { computed, useId } from 'vue'

const props = defineProps({
  question: { type: Object, required: true },
  options: { type: Array, required: true },
})
const choices = defineModel({ type: Object, required: true })
const id = useId()
const multiple = computed(() => props.question.question_type === 'matrix_multiple')
const table = computed(() => props.options.length <= 5)
const columns = computed(() => `minmax(0, 1.5fr) repeat(${props.options.length}, minmax(0, 1fr))`)

function selectedFor(rowId) {
  return Object.hasOwn(choices.value, rowId) ? choices.value[rowId] : []
}

function choose(rowId, optionId, checked) {
  const current = selectedFor(rowId)
  const selected = multiple.value
    ? (checked ? [...current, optionId] : current.filter((id) => id !== optionId))
    : [optionId]
  const next = { ...choices.value, [rowId]: selected }
  if (!selected.length) delete next[rowId]
  choices.value = next
}
</script>

<template>
  <div class="grid gap-3" :style="{ '--matrix-columns': columns }">
    <p class="text-sm text-ink-muted">
      {{ multiple ? 'Можно выбрать несколько вариантов в каждой строке.' : 'Выберите один вариант в каждой строке.' }}
    </p>
    <div
      v-if="table"
      aria-hidden="true"
      class="sticky top-0 z-10 hidden gap-2 bg-surface px-3 py-2 text-center text-xs font-medium text-ink-muted lg:grid lg:grid-cols-(--matrix-columns)"
    >
      <span />
      <span v-for="option in options" :key="option.id" class="break-words">{{ option.title }}</span>
    </div>
    <div
      v-for="(row, index) in question.matrix_rows"
      :key="row.id"
      :role="multiple ? 'group' : 'radiogroup'"
      :aria-labelledby="`${id}-row-${index}`"
      class="grid gap-2 rounded-control border border-line p-3"
      :class="table ? 'lg:grid-cols-(--matrix-columns) lg:items-center' : ''"
    >
      <p :id="`${id}-row-${index}`" class="mb-1 break-words text-sm font-medium">{{ row.title }}</p>
      <label
        v-for="option in options"
        :key="option.id"
        class="flex min-h-10 min-w-0 cursor-pointer items-center gap-2 rounded-control border border-line px-3 py-2 text-sm has-checked:border-brand-500 has-checked:bg-brand-50"
        :class="table ? 'lg:justify-center lg:px-1' : ''"
      >
        <input
          :type="multiple ? 'checkbox' : 'radio'"
          :name="`${id}-${index}`"
          :checked="selectedFor(row.id).includes(option.id)"
          class="size-4 shrink-0 accent-brand-600"
          @change="choose(row.id, option.id, $event.target.checked)"
        />
        <span :class="table ? 'lg:sr-only' : ''">{{ option.title }}</span>
      </label>
    </div>
  </div>
</template>
