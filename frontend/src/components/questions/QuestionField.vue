<script setup>
/**
 * Поле ответа на вопрос любого типа. v-model — ответ в форме API:
 * { text_value, rich_text_value, number_value, boolean_value, scale_item_id, option_id, option_ids, ranking, is_skipped }.
 */
import { computed, useId } from 'vue'
import { htmlToText, textToHtml } from '@/utils/richText'

const props = defineProps({
  question: { type: Object, required: true },
  scale: { type: Object, default: null },
  // Порядок вариантов для этого прохождения (при is_options_shuffled — перемешанный)
  options: { type: Array, default: () => [] },
  error: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const model = defineModel({ type: Object, required: true })
const id = useId()

function update(changes) {
  model.value = { ...model.value, ...changes, is_skipped: false }
}

const scaleSteps = computed(() => {
  const scale = props.scale
  if (!scale) return []
  if (scale.scale_type === 'items') return scale.items.map((item) => ({ key: item.id, label: item.title, item }))
  const steps = []
  for (let v = scale.min_value; v <= scale.max_value; v += scale.step || 1) steps.push({ key: v, label: String(v), value: v })
  return steps
})

function scaleSelected(step) {
  return step.item ? model.value.scale_item_id === step.item.id : model.value.number_value === step.value
}

function selectScale(step) {
  update(step.item ? { scale_item_id: step.item.id } : { number_value: step.value })
}

const activeRange = computed(() => {
  const value = model.value.number_value
  if (value == null) return null
  return props.question.ranges?.find((r) => value >= r.from_value && value <= r.to_value) ?? null
})

function toggleOption(optionId) {
  const ids = model.value.option_ids || []
  const next = ids.includes(optionId) ? ids.filter((i) => i !== optionId) : [...ids, optionId]
  if (props.question.max_selections && next.length > props.question.max_selections) return
  update({ option_ids: next })
}

const ranked = computed(() => (model.value.ranking || []).map((oid) => props.options.find((o) => o.id === oid)).filter(Boolean))
const unranked = computed(() => props.options.filter((o) => !(model.value.ranking || []).includes(o.id)))
const canRankMore = computed(() => !props.question.max_selections || ranked.value.length < props.question.max_selections)

function rankAdd(optionId) {
  if (canRankMore.value) update({ ranking: [...(model.value.ranking || []), optionId] })
}
function rankRemove(optionId) {
  update({ ranking: (model.value.ranking || []).filter((i) => i !== optionId) })
}
function rankMove(index, delta) {
  const next = [...(model.value.ranking || [])]
  const target = index + delta
  if (target < 0 || target >= next.length) return
  ;[next[index], next[target]] = [next[target], next[index]]
  update({ ranking: next })
}

const limits = computed(() => {
  const { min_selections: min, max_selections: max } = props.question
  if (min && max) return min === max ? `Выберите ${max}` : `Выберите от ${min} до ${max}`
  if (max) return `Не больше ${max}`
  if (min) return `Не меньше ${min}`
  return ''
})

const numberHint = computed(() => {
  const { min_number: min, max_number: max } = props.question
  if (min != null && max != null) return `От ${min} до ${max}`
  if (min != null) return `Не меньше ${min}`
  if (max != null) return `Не больше ${max}`
  return ''
})

const choiceClass = (active) =>
  active
    ? 'border-brand-500 bg-brand-50 ring-1 ring-brand-500'
    : 'border-line bg-surface hover:border-brand-200 hover:bg-brand-50/50'
</script>

<template>
  <fieldset :aria-describedby="error ? `${id}-error` : undefined" :disabled="disabled" class="grid gap-3">
    <legend class="sr-only">{{ question.text }}</legend>

    <textarea
      v-if="question.question_type === 'text'"
      :value="model.text_value || ''"
      rows="4"
      class="w-full rounded-control border border-line bg-surface p-3 outline-none focus:border-brand-500"
      placeholder="Ваш ответ"
      :aria-label="question.text"
      @input="update({ text_value: $event.target.value })"
    />

    <textarea
      v-else-if="question.question_type === 'rich_text'"
      :value="htmlToText(model.rich_text_value)"
      rows="6"
      class="w-full rounded-control border border-line bg-surface p-3 outline-none focus:border-brand-500"
      placeholder="Ваш ответ. Пустая строка — новый абзац."
      :aria-label="question.text"
      @input="update({ rich_text_value: textToHtml($event.target.value) })"
    />

    <div v-else-if="question.question_type === 'number'" class="grid max-w-xs gap-1.5">
      <input
        type="number"
        inputmode="decimal"
        :value="model.number_value ?? ''"
        :min="question.min_number ?? undefined"
        :max="question.max_number ?? undefined"
        class="h-10 rounded-control border border-line bg-surface px-3 outline-none focus:border-brand-500"
        :aria-label="question.text"
        @input="update({ number_value: $event.target.value === '' ? null : Number($event.target.value) })"
      />
      <p v-if="numberHint" class="text-sm text-ink-muted">{{ numberHint }}</p>
    </div>

    <div v-else-if="question.question_type === 'yes_no'" class="flex gap-2" role="radiogroup" :aria-label="question.text">
      <button
        v-for="choice in [{ value: true, label: 'Да' }, { value: false, label: 'Нет' }]"
        :key="choice.label"
        type="button"
        role="radio"
        :aria-checked="model.boolean_value === choice.value"
        class="min-w-24 rounded-control border px-5 py-2.5 font-medium transition"
        :class="choiceClass(model.boolean_value === choice.value)"
        @click="update({ boolean_value: choice.value })"
      >
        {{ choice.label }}
      </button>
    </div>

    <div v-else-if="question.question_type === 'single_choice'" class="grid gap-2" role="radiogroup" :aria-label="question.text">
      <button
        v-for="option in options"
        :key="option.id"
        type="button"
        role="radio"
        :aria-checked="model.option_id === option.id"
        class="flex items-start gap-3 rounded-control border px-4 py-3 text-left transition"
        :class="choiceClass(model.option_id === option.id)"
        @click="update({ option_id: option.id })"
      >
        <span
          class="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border-2"
          :class="model.option_id === option.id ? 'border-brand-600' : 'border-line'"
          aria-hidden="true"
        >
          <span v-if="model.option_id === option.id" class="size-2.5 rounded-full bg-brand-600" />
        </span>
        <span>
          {{ option.title }}
          <span v-if="option.description" class="block text-sm text-ink-muted">{{ option.description }}</span>
        </span>
      </button>
    </div>

    <div v-else-if="question.question_type === 'multiple_choice'" class="grid gap-2">
      <p v-if="limits" class="text-sm text-ink-muted">{{ limits }}</p>
      <label
        v-for="option in options"
        :key="option.id"
        class="flex items-start gap-3 rounded-control border px-4 py-3 transition"
        :class="choiceClass((model.option_ids || []).includes(option.id))"
      >
        <input
          type="checkbox"
          class="mt-1 size-4 accent-brand-600"
          :checked="(model.option_ids || []).includes(option.id)"
          @change="toggleOption(option.id)"
        />
        <span>
          {{ option.title }}
          <span v-if="option.description" class="block text-sm text-ink-muted">{{ option.description }}</span>
        </span>
      </label>
    </div>

    <div v-else-if="question.question_type === 'scale'" class="grid gap-3">
      <div class="flex flex-wrap gap-2" role="radiogroup" :aria-label="question.text">
        <button
          v-for="step in scaleSteps"
          :key="step.key"
          type="button"
          role="radio"
          :aria-checked="scaleSelected(step)"
          :title="step.item?.description || undefined"
          class="min-w-11 rounded-control border px-3 py-2 font-medium tabular-nums transition"
          :class="scaleSelected(step) ? 'border-brand-600 bg-brand-600 text-white' : 'border-line bg-surface hover:border-brand-200'"
          @click="selectScale(step)"
        >
          {{ step.label }}
        </button>
      </div>
      <div v-if="question.ranges?.length" class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <span
          v-for="range in question.ranges"
          :key="range.id"
          :class="activeRange?.id === range.id ? 'font-semibold text-brand-700' : 'text-ink-muted'"
        >
          {{ range.from_value }}–{{ range.to_value }}: {{ range.title }}
        </span>
      </div>
    </div>

    <div v-else-if="question.question_type === 'ranking'" class="grid gap-3">
      <p class="text-sm text-ink-muted">
        Нажимайте на варианты в порядке важности: первый — самый важный.<template v-if="limits"> {{ limits }}.</template>
      </p>
      <ol v-if="ranked.length" class="grid gap-2">
        <li
          v-for="(option, index) in ranked"
          :key="option.id"
          class="flex items-center gap-3 rounded-control border border-brand-200 bg-brand-50 px-3 py-2"
        >
          <span class="grid size-7 shrink-0 place-items-center rounded-full bg-brand-600 text-sm font-semibold text-white">
            {{ index + 1 }}
          </span>
          <span class="flex-1">{{ option.title }}</span>
          <button type="button" class="rounded-control px-2 py-1 hover:bg-surface disabled:opacity-40" :disabled="index === 0" :aria-label="`Выше: ${option.title}`" @click="rankMove(index, -1)">↑</button>
          <button
            type="button"
            class="rounded-control px-2 py-1 hover:bg-surface disabled:opacity-40"
            :disabled="index === ranked.length - 1"
            :aria-label="`Ниже: ${option.title}`"
            @click="rankMove(index, 1)"
          >
            ↓
          </button>
          <button type="button" class="rounded-control px-2 py-1 text-sm text-ink-muted hover:bg-surface" @click="rankRemove(option.id)">
            Убрать
          </button>
        </li>
      </ol>
      <div v-if="unranked.length" class="flex flex-wrap gap-2">
        <button
          v-for="option in unranked"
          :key="option.id"
          type="button"
          class="rounded-control border border-line bg-surface px-3 py-2 text-left hover:border-brand-200 disabled:opacity-50"
          :disabled="!canRankMore"
          @click="rankAdd(option.id)"
        >
          + {{ option.title }}
        </button>
      </div>
    </div>

    <p v-if="error" :id="`${id}-error`" role="alert" class="text-sm text-red-600">{{ error }}</p>
  </fieldset>
</template>
