<!--
  ScaleQuestion — выбор значения по шкале.

  Поддерживает два типа шкал:
  - generated — числовой диапазон (min..max с шагом)
  - items — предопределённые элементы шкалы
  Показывает название активного диапазона (scale_ranges).
  Сохраняется автоматически при выборе.
-->
<script setup>
import { computed } from 'vue'

const props = defineProps({
  question: { type: Object, required: true },
  scaleItems: { type: Array, default: () => [] },
  scaleRanges: { type: Array, default: () => [] },
  modelValue: { default: null },
})

const emit = defineEmits(['update:modelValue'])

const scale = computed(() => props.question.scale || {})

const isGenerated = computed(() => scale.value.scale_type === 'generated')

const generatedItems = computed(() => {
  if (!isGenerated.value) return []
  const min = scale.value.min_value ?? 1
  const max = scale.value.max_value ?? 5
  const step = scale.value.step ?? 1
  const items = []
  for (let v = min; v <= max; v += step) {
    items.push({ id: v, title: String(v), value: v })
  }
  return items
})

const items = computed(() =>
  isGenerated.value ? generatedItems.value : props.scaleItems,
)

const activeRange = computed(() => {
  if (!props.scaleRanges.length || props.modelValue == null) return null
  const val = typeof props.modelValue === 'object' ? props.modelValue.value : props.modelValue
  return props.scaleRanges.find(
    (r) => val >= r.from_value && val <= r.to_value,
  )
})

function select(item) {
  if (isGenerated.value) {
    emit('update:modelValue', item.value)
  } else {
    emit('update:modelValue', item.id)
  }
}

function isSelected(item) {
  if (isGenerated.value) {
    return props.modelValue === item.value
  }
  return props.modelValue === item.id
}
</script>

<template>
  <div>
    <div class="flex flex-wrap gap-2">
      <button
        v-for="item in items"
        :key="item.id"
        class="min-w-[48px] cursor-pointer rounded-2xl border px-4 py-2 text-sm font-medium transition"
        :class="
          isSelected(item)
            ? 'border-primary bg-primary text-white shadow-md'
            : 'border-slate-200 hover:border-primary/30 hover:bg-primary/[0.02]'
        "
        :title="item.description || item.title"
        @click="select(item)"
      >
        {{ item.title }}
      </button>
    </div>

    <!-- Легенда диапазонов шкалы -->
    <div v-if="scaleRanges.length" class="mt-3 flex flex-wrap gap-x-4 gap-y-1">
      <span
        v-for="range in scaleRanges"
        :key="range.id"
        class="text-xs transition-colors duration-200"
        :class="activeRange?.id === range.id ? 'text-primary font-semibold' : 'text-muted'"
      >
        {{ range.from_value }}–{{ range.to_value }}: {{ range.title }}
      </span>
    </div>
  </div>
</template>
