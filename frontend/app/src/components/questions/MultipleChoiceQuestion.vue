<!--
  MultipleChoiceQuestion — множественный выбор из вариантов (чекбоксы).
  Поддерживает ограничения min_selections / max_selections.
  Сохраняется автоматически при выборе.
-->
<script setup>
import { computed } from 'vue'

const props = defineProps({
  question: { type: Object, required: true },
  options: { type: Array, default: () => [] },
  modelValue: { default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

const selected = computed(() => Array.isArray(props.modelValue) ? props.modelValue : [])

function toggle(optionId) {
  const current = [...selected.value]
  const idx = current.indexOf(optionId)

  if (idx >= 0) {
    current.splice(idx, 1)
  } else {
    const max = props.question.max_selections
    if (max && current.length >= max) return
    current.push(optionId)
  }

  emit('update:modelValue', current)
}

function isSelected(optionId) {
  return selected.value.includes(optionId)
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
      <button
        v-for="option in options"
        :key="option.id"
        class="flex w-full cursor-pointer items-center gap-3 rounded-2xl border px-4 py-3 text-left text-sm transition"
        :class="
          isSelected(option.id)
            ? 'border-primary bg-primary/5 text-primary font-medium'
            : 'border-slate-200 hover:border-primary/30 hover:bg-primary/[0.02]'
        "
        @click="toggle(option.id)"
      >
        <span
          class="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition"
          :class="
            isSelected(option.id)
              ? 'border-primary bg-primary'
              : 'border-slate-300'
          "
        >
          <svg
            v-if="isSelected(option.id)"
            class="h-3 w-3 text-white"
            viewBox="0 0 12 12"
            fill="none"
          >
            <path d="M2 6l3 3 5-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
        <span>{{ option.title }}</span>
      </button>
    </div>
  </div>
</template>
