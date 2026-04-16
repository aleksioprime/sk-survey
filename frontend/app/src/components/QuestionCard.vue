<!--
  QuestionCard — карточка вопроса.

  Диспетчеризирует отображение нужного компонента по question_type.
  Показывает номер вопроса, индикатор «Сохранено» и кнопку «Сохранить»
  для текстовых вопросов (text / rich_text).
-->
<script setup>
import { computed } from 'vue'
import TextQuestion from '@/components/questions/TextQuestion.vue'
import RichTextQuestion from '@/components/questions/RichTextQuestion.vue'
import SingleChoiceQuestion from '@/components/questions/SingleChoiceQuestion.vue'
import MultipleChoiceQuestion from '@/components/questions/MultipleChoiceQuestion.vue'
import NumberQuestion from '@/components/questions/NumberQuestion.vue'
import YesNoQuestion from '@/components/questions/YesNoQuestion.vue'
import ScaleQuestion from '@/components/questions/ScaleQuestion.vue'
import RankingQuestion from '@/components/questions/RankingQuestion.vue'

const props = defineProps({
  question: { type: Object, required: true },
  questionIndex: { type: Number, required: true },
  options: { type: Array, default: () => [] },
  scaleItems: { type: Array, default: () => [] },
  scaleRanges: { type: Array, default: () => [] },
  modelValue: { default: null },
  savedValue: { default: null },
  isSaving: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'save-answer', 'cancel-changes', 'blur'])

const componentMap = {
  text: TextQuestion,
  rich_text: RichTextQuestion,
  single_choice: SingleChoiceQuestion,
  multiple_choice: MultipleChoiceQuestion,
  number: NumberQuestion,
  yes_no: YesNoQuestion,
  scale: ScaleQuestion,
  ranking: RankingQuestion,
}

const questionComponent = computed(() => componentMap[props.question.question_type] || TextQuestion)

const isManualSaveType = computed(() =>
  ['text', 'rich_text', 'ranking'].includes(props.question.question_type),
)

function areValuesEqual(a, b) {
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false
    return a.every((item, idx) => item === b[idx])
  }
  return a === b
}

const hasAnyInput = computed(() => {
  if (props.question.question_type === 'ranking') {
    return Array.isArray(props.modelValue) && props.modelValue.length > 0
  }
  return props.modelValue != null && props.modelValue !== ''
})

const hasValue = computed(() => {
  if (props.question.question_type === 'ranking') {
    return Array.isArray(props.modelValue) &&
      props.options.length > 0 &&
      props.modelValue.length === props.options.length
  }
  return props.modelValue != null && props.modelValue !== ''
})

const isDirty = computed(() => {
  if (!isManualSaveType.value) return false
  const hasSaved = props.savedValue !== null && props.savedValue !== undefined
  if (!hasSaved) return hasAnyInput.value
  return !areValuesEqual(props.modelValue, props.savedValue)
})

const isSaved = computed(() => {
  const hasSaved = props.savedValue !== null && props.savedValue !== undefined
  return hasSaved && !isDirty.value
})

const canSave = computed(() =>
  isManualSaveType.value &&
  hasValue.value &&
  isDirty.value,
)
</script>

<template>
  <div
    class="glass-panel p-6 transition-all duration-300"
    :class="isSaved ? 'border-primary/40 bg-primary/[0.03]' : ''"
  >
    <div class="mb-4">
      <div class="flex items-start gap-3">
        <span
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-colors duration-300"
          :class="isSaved ? 'bg-primary text-white' : 'bg-primary/10 text-primary'"
        >
          {{ questionIndex + 1 }}
        </span>
        <div class="flex-1">
          <p class="text-sm font-semibold text-slate-800 leading-snug">
            {{ question.text }}
            <span v-if="question.is_required" class="text-danger ml-1">*</span>
          </p>
          <p v-if="question.description" class="mt-1 text-xs text-muted">
            {{ question.description }}
          </p>
        </div>
        <span
          v-if="isSaving"
          class="shrink-0 flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 animate-pulse"
        >
          <svg class="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" class="opacity-30" />
            <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
          Сохраняется...
        </span>
        <span
          v-else-if="isDirty"
          class="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"
        >
          Изменено
        </span>
        <span
          v-else-if="isSaved"
          class="shrink-0 flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary"
        >
          <svg class="h-3 w-3" viewBox="0 0 12 12" fill="none">
            <path d="M2 6l3 3 5-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          Сохранено
        </span>
      </div>
    </div>

    <component
      :is="questionComponent"
      :question="question"
      :options="options"
      :scale-items="scaleItems"
      :scale-ranges="scaleRanges"
      :model-value="modelValue"
      @update:model-value="emit('update:modelValue', $event)"
      @blur="emit('blur')"
    />

    <div v-if="isManualSaveType" class="mt-3 flex justify-end gap-2">
      <button
        v-if="isDirty"
        class="btn-outline text-xs px-4 py-2"
        :disabled="isSaving"
        @click="emit('cancel-changes')"
      >
        Отменить изменения
      </button>
      <button
        class="btn-primary text-xs px-4 py-2"
        :disabled="!canSave || isSaving"
        @click="emit('save-answer')"
      >
        {{ isSaving ? 'Сохранение...' : 'Сохранить ответ' }}
      </button>
    </div>
  </div>
</template>
