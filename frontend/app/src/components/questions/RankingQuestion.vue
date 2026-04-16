<!--
  RankingQuestion — ранжирование вариантов ответа.
  Пользователь формирует упорядоченный список выбранных опций.
  Сохраняется автоматически при изменениях.
-->
<script setup>
import { computed } from 'vue'

const props = defineProps({
  question: { type: Object, required: true },
  options: { type: Array, default: () => [] },
  modelValue: { default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

const selectedIds = computed(() => {
  if (!Array.isArray(props.modelValue)) return []
  return props.modelValue.filter((id, index, arr) => id != null && arr.indexOf(id) === index)
})

const optionMap = computed(() => {
  const map = new Map()
  for (const option of props.options) {
    if (option?.id != null) map.set(option.id, option)
  }
  return map
})

const selectedOptions = computed(() =>
  selectedIds.value
    .map((id) => optionMap.value.get(id))
    .filter(Boolean),
)

const availableOptions = computed(() =>
  props.options.filter((option) => !selectedIds.value.includes(option.id)),
)

const maxSelections = computed(() => props.question.max_selections || null)
const canAddMore = computed(() => !maxSelections.value || selectedIds.value.length < maxSelections.value)

function update(ids) {
  emit('update:modelValue', ids)
}

function addOption(optionId) {
  if (selectedIds.value.includes(optionId)) return
  if (!canAddMore.value) return
  update([...selectedIds.value, optionId])
}

function removeOption(optionId) {
  update(selectedIds.value.filter((id) => id !== optionId))
}

function moveUp(index) {
  if (index <= 0) return
  const next = [...selectedIds.value]
  ;[next[index - 1], next[index]] = [next[index], next[index - 1]]
  update(next)
}

function moveDown(index) {
  if (index >= selectedIds.value.length - 1) return
  const next = [...selectedIds.value]
  ;[next[index], next[index + 1]] = [next[index + 1], next[index]]
  update(next)
}
</script>

<template>
  <div>
    <p v-if="question.min_selections || question.max_selections" class="mb-2 text-xs text-muted">
      <span v-if="question.min_selections">Минимум: {{ question.min_selections }}</span>
      <span v-if="question.min_selections && question.max_selections"> · </span>
      <span v-if="question.max_selections">Максимум: {{ question.max_selections }}</span>
    </p>

    <div class="space-y-2">
      <div
        v-for="(option, index) in selectedOptions"
        :key="option.id"
        class="flex items-center gap-2 rounded-2xl border border-primary/30 bg-primary/[0.03] px-3 py-2"
      >
        <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
          {{ index + 1 }}
        </span>
        <span class="flex-1 text-sm font-medium text-slate-800">{{ option.title }}</span>

        <button
          class="inline-flex h-8 w-8 items-center justify-center rounded-xl border border-slate-200 text-slate-600 transition hover:border-primary/40 hover:text-primary disabled:opacity-40"
          :disabled="index === 0"
          title="Выше"
          @click="moveUp(index)"
        >
          ↑
        </button>
        <button
          class="inline-flex h-8 w-8 items-center justify-center rounded-xl border border-slate-200 text-slate-600 transition hover:border-primary/40 hover:text-primary disabled:opacity-40"
          :disabled="index === selectedOptions.length - 1"
          title="Ниже"
          @click="moveDown(index)"
        >
          ↓
        </button>
        <button
          class="inline-flex h-8 items-center justify-center rounded-xl border border-slate-200 px-2 text-xs text-slate-600 transition hover:border-danger/40 hover:text-danger"
          title="Убрать"
          @click="removeOption(option.id)"
        >
          Убрать
        </button>
      </div>

      <div v-if="!selectedOptions.length" class="rounded-2xl border border-dashed border-slate-300 px-4 py-3 text-sm text-muted">
        Добавьте варианты и расставьте их по порядку.
      </div>
    </div>

    <div v-if="availableOptions.length" class="mt-3">
      <p class="mb-2 text-xs text-muted">Добавить вариант:</p>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="option in availableOptions"
          :key="option.id"
          class="rounded-xl border border-slate-200 px-3 py-1.5 text-sm transition hover:border-primary/40 hover:bg-primary/[0.02] disabled:opacity-40"
          :disabled="!canAddMore"
          @click="addOption(option.id)"
        >
          + {{ option.title }}
        </button>
      </div>
    </div>
  </div>
</template>
