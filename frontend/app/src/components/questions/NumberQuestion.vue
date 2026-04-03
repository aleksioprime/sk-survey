<!--
  NumberQuestion — поле ввода числа с ограничениями min/max.
  Сохраняется автоматически при изменении.
-->
<script setup>
const props = defineProps({
  question: { type: Object, required: true },
  modelValue: { default: null },
})

const emit = defineEmits(['update:modelValue'])

function onInput(e) {
  const val = e.target.value
  emit('update:modelValue', val === '' ? null : Number(val))
}
</script>

<template>
  <div>
    <p v-if="question.min_number != null || question.max_number != null" class="mb-2 text-xs text-muted">
      <span v-if="question.min_number != null">От {{ question.min_number }}</span>
      <span v-if="question.min_number != null && question.max_number != null"> до </span>
      <span v-if="question.max_number != null">{{ question.max_number }}</span>
    </p>
    <input
      type="number"
      class="field-input"
      :value="modelValue"
      :min="question.min_number"
      :max="question.max_number"
      placeholder="Введите число..."
      @input="onInput"
    />
  </div>
</template>
