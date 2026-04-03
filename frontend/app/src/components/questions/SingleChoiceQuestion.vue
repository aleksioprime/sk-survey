<!--
  SingleChoiceQuestion — одиночный выбор из вариантов (радио-кнопки).
  Сохраняется автоматически при выборе.
-->
<script setup>
defineProps({
  question: { type: Object, required: true },
  options: { type: Array, default: () => [] },
  modelValue: { default: null },
})

const emit = defineEmits(['update:modelValue'])

function select(optionId) {
  emit('update:modelValue', optionId)
}
</script>

<template>
  <div class="space-y-2">
    <button
      v-for="option in options"
      :key="option.id"
      class="flex w-full cursor-pointer items-center gap-3 rounded-2xl border px-4 py-3 text-left text-sm transition"
      :class="
        modelValue === option.id
          ? 'border-primary bg-primary/5 text-primary font-medium'
          : 'border-slate-200 hover:border-primary/30 hover:bg-primary/[0.02]'
      "
      @click="select(option.id)"
    >
      <span
        class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition"
        :class="
          modelValue === option.id
            ? 'border-primary bg-primary'
            : 'border-slate-300'
        "
      >
        <span
          v-if="modelValue === option.id"
          class="h-2 w-2 rounded-full bg-white"
        />
      </span>
      <span>{{ option.title }}</span>
    </button>
  </div>
</template>
