<!--
  YesNoQuestion — кнопки «Да» / «Нет».
  Сохраняется автоматически при выборе.
-->
<script setup>
defineProps({
  question: { type: Object, required: true },
  modelValue: { default: null },
})

const emit = defineEmits(['update:modelValue'])

function select(val) {
  emit('update:modelValue', val)
}
</script>

<template>
  <div class="flex gap-3">
    <button
      class="flex-1 cursor-pointer rounded-2xl border px-4 py-3 text-sm font-medium transition"
      :class="
        modelValue === true
          ? 'border-success bg-green-50 text-success'
          : 'border-slate-200 hover:border-success/30'
      "
      @click="select(true)"
    >
      Да
    </button>
    <button
      class="flex-1 cursor-pointer rounded-2xl border px-4 py-3 text-sm font-medium transition"
      :class="
        modelValue === false
          ? 'border-danger bg-red-50 text-danger'
          : 'border-slate-200 hover:border-danger/30'
      "
      @click="select(false)"
    >
      Нет
    </button>
  </div>
</template>
