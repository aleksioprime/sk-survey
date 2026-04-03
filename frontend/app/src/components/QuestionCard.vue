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

const props = defineProps({
  question: { type: Object, required: true },
  questionIndex: { type: Number, required: true },
  options: { type: Array, default: () => [] },
  scaleItems: { type: Array, default: () => [] },
  scaleRanges: { type: Array, default: () => [] },
  modelValue: { default: null },
  savedValue: { default: null },
})

const emit = defineEmits(['update:modelValue', 'save-text'])

const componentMap = {
  text: TextQuestion,
  rich_text: RichTextQuestion,
  single_choice: SingleChoiceQuestion,
  multiple_choice: MultipleChoiceQuestion,
  number: NumberQuestion,
  yes_no: YesNoQuestion,
  scale: ScaleQuestion,
}

const questionComponent = computed(() => componentMap[props.question.question_type] || TextQuestion)

const isTextType = computed(() =>
  props.question.question_type === 'text' || props.question.question_type === 'rich_text',
)

// Вопрос считается сохранённым, если в store есть подтверждённое значение
const isSaved = computed(() => props.savedValue !== null)

// Кнопка активна, если есть текст И он отличается от последнего сохранённого на сервере
const canSave = computed(() =>
  props.modelValue != null &&
  props.modelValue !== '' &&
  props.modelValue !== props.savedValue,
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
          v-if="isSaved"
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
    />

    <div v-if="isTextType" class="mt-3 flex justify-end">
      <button
        class="btn-primary text-xs px-4 py-2"
        :disabled="!canSave"
        @click="emit('save-text')"
      >
        Сохранить ответ
      </button>
    </div>
  </div>
</template>
