<!--
  RichTextQuestion — поле ввода развёрнутого текстового ответа.
  Сохраняется по явной кнопке в QuestionCard.
-->
<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'

const props = defineProps({
  question: { type: Object, required: true },
  modelValue: { default: null },
})

const emit = defineEmits(['update:modelValue'])
const textareaRef = ref(null)

function resize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

onMounted(() => {
  nextTick(resize)
})

watch(() => props.modelValue, () => { nextTick(resize) })

function onInput(e) {
  resize()
  emit('update:modelValue', e.target.value)
}

function onPaste(e) {
  nextTick(() => {
    emit('update:modelValue', e.target.value)
    resize()
  })
}
</script>

<template>
  <textarea
    ref="textareaRef"
    class="field-input w-full resize-none overflow-hidden"
    :value="modelValue || ''"
    placeholder="Введите развёрнутый ответ..."
    rows="6"
    @input="onInput"
    @paste="onPaste"
  />
</template>
