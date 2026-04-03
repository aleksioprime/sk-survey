<!--
  TextQuestion — поле ввода текстового ответа (textarea).
  Сохраняется по явной кнопке в QuestionCard.
-->
<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'

const props = defineProps({
  question: { type: Object, required: true },
  modelValue: { default: null },
})

const emit = defineEmits(['update:modelValue', 'blur'])
const textareaRef = ref(null)

function resize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

// Авторазмер при монтировании (e.g. восстановленный текст)
onMounted(() => {
  nextTick(resize)
})

// Авторазмер при внешнем изменении modelValue (e.g. сброс стора)
watch(() => props.modelValue, () => { nextTick(resize) })

function onInput(e) {
  resize()
  emit('update:modelValue', e.target.value)
}

// При paste браузер обновляет DOM асинхронно,
// поэтому читаем значение через nextTick, чтобы получить уже вставленный текст
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
    :placeholder="question.description || 'Введите ответ...'"
    rows="4"
    @input="onInput"
    @paste="onPaste"
    @blur="emit('blur')"
  />
</template>
