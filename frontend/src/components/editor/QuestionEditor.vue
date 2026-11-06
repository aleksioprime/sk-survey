<script setup>
import { computed, ref } from 'vue'
import { UiButton, UiInput, UiSelect } from 'sk-ui'
import { QUESTION_TYPES } from '@/utils/questionTypes'

const props = defineProps({
  question: { type: Object, default: null }, // null — новый вопрос
  sections: { type: Array, default: () => [] },
  scales: { type: Array, default: () => [] },
  sectionId: { type: [Number, String], default: null },
  saving: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['save', 'cancel', 'delete', 'new-scale'])

const source = props.question
const form = ref({
  text: source?.text ?? '',
  description: source?.description ?? '',
  question_type: source?.question_type ?? 'single_choice',
  section_id: source ? source.section_id : props.sectionId,
  is_required: source?.is_required ?? false,
  is_active: source?.is_active ?? true,
  scale_id: source?.scale_id ?? props.scales[0]?.id ?? null,
  min_selections: source?.min_selections ?? null,
  max_selections: source?.max_selections ?? null,
  min_number: source?.min_number ?? null,
  max_number: source?.max_number ?? null,
  is_options_shuffled: source?.is_options_shuffled ?? false,
  options: (source?.options ?? [{ title: '' }, { title: '' }]).map((o) => ({ ...o })),
  ranges: (source?.ranges ?? []).map((r) => ({ ...r })),
})

const answered = computed(() => (source?.answers_count || 0) > 0)
const hasOptions = computed(() => ['single_choice', 'multiple_choice', 'ranking'].includes(form.value.question_type))
const hasSelections = computed(() => ['multiple_choice', 'ranking'].includes(form.value.question_type))
const isScale = computed(() => form.value.question_type === 'scale')
const scaleMissing = ref(false)

function addOption() {
  form.value.options.push({ title: '' })
}
function removeOption(index) {
  form.value.options.splice(index, 1)
}
function moveOption(index, delta) {
  const list = form.value.options
  const target = index + delta
  if (target < 0 || target >= list.length) return
  ;[list[index], list[target]] = [list[target], list[index]]
}
function addRange() {
  form.value.ranges.push({ title: '', from_value: null, to_value: null })
}

const numberOrNull = (value) => (value === '' || value == null ? null : Number(value))

function save() {
  const f = form.value
  // UiSelect - кнопка, браузер не проверяет её как обязательное поле
  scaleMissing.value = isScale.value && !f.scale_id
  if (scaleMissing.value) return
  const payload = {
    text: f.text.trim(),
    description: f.description.trim(),
    question_type: f.question_type,
    section_id: f.section_id || null,
    is_required: f.is_required,
    is_active: f.is_active,
    scale_id: isScale.value ? f.scale_id : null,
    min_selections: hasSelections.value ? numberOrNull(f.min_selections) : null,
    max_selections: hasSelections.value ? numberOrNull(f.max_selections) : null,
    min_number: f.question_type === 'number' ? numberOrNull(f.min_number) : null,
    max_number: f.question_type === 'number' ? numberOrNull(f.max_number) : null,
    is_options_shuffled: hasOptions.value && f.is_options_shuffled,
    options: hasOptions.value
      ? f.options.filter((o) => o.title.trim()).map((o) => ({ id: o.id, title: o.title.trim(), description: o.description || '', value: o.value || '', score: o.score ?? null, is_active: o.is_active ?? true }))
      : [],
    ranges: isScale.value
      ? f.ranges.filter((r) => r.title.trim()).map((r) => ({ title: r.title.trim(), from_value: Number(r.from_value), to_value: Number(r.to_value) }))
      : [],
  }
  emit('save', payload)
}
</script>

<template>
  <form class="grid gap-4 rounded-card border border-brand-200 bg-surface p-5" @submit.prevent="save">
    <div class="grid gap-1.5">
      <label class="text-sm font-medium" for="q-text">Текст вопроса</label>
      <textarea id="q-text" v-model="form.text" rows="2" required class="rounded-control border border-line bg-surface p-3 outline-none focus:border-brand-500" />
    </div>
    <div class="grid gap-1.5">
      <label class="text-sm font-medium" for="q-description">Пояснение <span class="font-normal text-ink-muted">— необязательно</span></label>
      <textarea id="q-description" v-model="form.description" rows="2" class="rounded-control border border-line bg-surface p-3 outline-none focus:border-brand-500" />
    </div>

    <div class="grid gap-4 sm:grid-cols-2">
      <div class="grid gap-1.5">
        <label class="text-sm font-medium" for="q-type">Тип ответа</label>
        <UiSelect id="q-type" v-model="form.question_type" :disabled="answered">
          <option v-for="(label, key) in QUESTION_TYPES" :key="key" :value="key">{{ label }}</option>
        </UiSelect>
        <p v-if="answered" class="text-xs text-ink-muted">На вопрос уже отвечали — тип менять нельзя.</p>
      </div>
      <div class="grid gap-1.5">
        <label class="text-sm font-medium" for="q-section">Раздел</label>
        <UiSelect id="q-section" v-model="form.section_id">
          <option :value="null">Без раздела</option>
          <option v-for="section in sections" :key="section.id" :value="section.id">{{ section.title || 'Без названия' }}</option>
        </UiSelect>
      </div>
    </div>

    <div v-if="isScale" class="grid gap-3">
      <div class="flex flex-wrap items-end gap-3">
        <div class="grid min-w-56 flex-1 gap-1.5">
          <label class="text-sm font-medium" for="q-scale">Шкала</label>
          <UiSelect id="q-scale" v-model="form.scale_id" :invalid="scaleMissing" @update:model-value="scaleMissing = false">
            <option v-for="scale in scales" :key="scale.id" :value="scale.id">{{ scale.title }}</option>
          </UiSelect>
          <p v-if="scaleMissing" role="alert" class="text-sm text-red-600">Выберите шкалу</p>
        </div>
        <UiButton size="sm" @click="emit('new-scale')">Новая шкала</UiButton>
      </div>
      <div class="grid gap-2">
        <p class="text-sm font-medium">Диапазоны для отчёта <span class="font-normal text-ink-muted">— например, «1–3: низкая»</span></p>
        <div v-for="(range, index) in form.ranges" :key="index" class="flex flex-wrap items-center gap-2">
          <UiInput v-model.number="range.from_value" type="number" class="w-20" aria-label="От" placeholder="от" />
          <span>–</span>
          <UiInput v-model.number="range.to_value" type="number" class="w-20" aria-label="До" placeholder="до" />
          <UiInput v-model="range.title" class="min-w-40 flex-1" aria-label="Название диапазона" placeholder="Название" />
          <UiButton size="sm" variant="ghost" class="text-ink-muted hover:text-red-600" :aria-label="`Удалить диапазон ${range.title}`" @click="form.ranges.splice(index, 1)">✕</UiButton>
        </div>
        <UiButton size="sm" variant="ghost" class="justify-self-start" @click="addRange">+ Диапазон</UiButton>
      </div>
    </div>

    <div v-if="hasOptions" class="grid gap-2">
      <p class="text-sm font-medium">Варианты ответа</p>
      <div v-for="(option, index) in form.options" :key="option.id || `new-${index}`" class="flex items-center gap-2">
        <UiInput
          v-model="option.title"
          class="flex-1"
          :class="option.is_active === false ? '[&_input]:text-ink-muted [&_input]:line-through' : ''"
          :aria-label="`Вариант ${index + 1}`"
          :placeholder="`Вариант ${index + 1}`"
        />
        <label v-if="option.is_active === false" class="flex items-center gap-1 text-xs text-ink-muted">
          <input v-model="option.is_active" type="checkbox" class="accent-brand-600" /> вернуть
        </label>
        <UiButton size="sm" variant="ghost" :disabled="index === 0" aria-label="Выше" @click="moveOption(index, -1)">↑</UiButton>
        <UiButton size="sm" variant="ghost" :disabled="index === form.options.length - 1" aria-label="Ниже" @click="moveOption(index, 1)">↓</UiButton>
        <UiButton size="sm" variant="ghost" class="text-ink-muted hover:text-red-600" :aria-label="`Удалить вариант ${index + 1}`" @click="removeOption(index)">✕</UiButton>
      </div>
      <UiButton size="sm" variant="ghost" class="justify-self-start" @click="addOption">+ Вариант</UiButton>
      <p v-if="answered" class="text-xs text-ink-muted">Варианты, которые уже выбирали, при удалении выключаются и остаются в результатах.</p>
      <label class="flex items-center gap-2 text-sm">
        <input v-model="form.is_options_shuffled" type="checkbox" class="accent-brand-600" /> Показывать варианты в случайном порядке
      </label>
    </div>

    <div v-if="hasSelections" class="flex flex-wrap gap-4">
      <UiInput v-model="form.min_selections" label="Минимум выборов" type="number" min="0" class="w-40" />
      <UiInput v-model="form.max_selections" label="Максимум выборов" type="number" min="1" class="w-40" />
    </div>

    <div v-if="form.question_type === 'number'" class="flex flex-wrap gap-4">
      <UiInput v-model="form.min_number" label="Минимальное число" type="number" class="w-40" />
      <UiInput v-model="form.max_number" label="Максимальное число" type="number" class="w-40" />
    </div>

    <div class="flex flex-wrap gap-5 text-sm">
      <label class="flex items-center gap-2"><input v-model="form.is_required" type="checkbox" class="accent-brand-600" /> Обязательный</label>
      <label class="flex items-center gap-2"><input v-model="form.is_active" type="checkbox" class="accent-brand-600" /> Показывать в опросе</label>
    </div>

    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <div class="flex flex-wrap gap-2">
      <UiButton type="submit" variant="primary" :loading="saving">{{ question ? 'Сохранить' : 'Добавить вопрос' }}</UiButton>
      <UiButton variant="ghost" @click="emit('cancel')">Отмена</UiButton>
      <UiButton v-if="question && !answered" variant="ghost" class="ml-auto text-red-600" @click="emit('delete')">Удалить вопрос</UiButton>
    </div>
  </form>
</template>
