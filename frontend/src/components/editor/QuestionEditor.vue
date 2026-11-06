<script setup>
import { computed, ref } from 'vue'
import { UiButton } from 'sk-ui'
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

const field = 'h-10 rounded-control border border-line bg-surface px-3 outline-none focus:border-brand-500'
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
        <select id="q-type" v-model="form.question_type" :class="field" :disabled="answered">
          <option v-for="(label, key) in QUESTION_TYPES" :key="key" :value="key">{{ label }}</option>
        </select>
        <p v-if="answered" class="text-xs text-ink-muted">На вопрос уже отвечали — тип менять нельзя.</p>
      </div>
      <div class="grid gap-1.5">
        <label class="text-sm font-medium" for="q-section">Раздел</label>
        <select id="q-section" v-model="form.section_id" :class="field">
          <option :value="null">Без раздела</option>
          <option v-for="section in sections" :key="section.id" :value="section.id">{{ section.title || 'Без названия' }}</option>
        </select>
      </div>
    </div>

    <div v-if="isScale" class="grid gap-3">
      <div class="flex flex-wrap items-end gap-3">
        <div class="grid min-w-56 flex-1 gap-1.5">
          <label class="text-sm font-medium" for="q-scale">Шкала</label>
          <select id="q-scale" v-model="form.scale_id" :class="field" required>
            <option v-for="scale in scales" :key="scale.id" :value="scale.id">{{ scale.title }}</option>
          </select>
        </div>
        <UiButton size="sm" @click="emit('new-scale')">Новая шкала</UiButton>
      </div>
      <div class="grid gap-2">
        <p class="text-sm font-medium">Диапазоны для отчёта <span class="font-normal text-ink-muted">— например, «1–3: низкая»</span></p>
        <div v-for="(range, index) in form.ranges" :key="index" class="flex flex-wrap items-center gap-2">
          <input v-model.number="range.from_value" type="number" :class="[field, 'w-20']" aria-label="От" placeholder="от" />
          <span>–</span>
          <input v-model.number="range.to_value" type="number" :class="[field, 'w-20']" aria-label="До" placeholder="до" />
          <input v-model="range.title" :class="[field, 'min-w-40 flex-1']" aria-label="Название диапазона" placeholder="Название" />
          <button type="button" class="px-2 text-ink-muted hover:text-red-600" :aria-label="`Удалить диапазон ${range.title}`" @click="form.ranges.splice(index, 1)">✕</button>
        </div>
        <UiButton size="sm" variant="ghost" class="justify-self-start" @click="addRange">+ Диапазон</UiButton>
      </div>
    </div>

    <div v-if="hasOptions" class="grid gap-2">
      <p class="text-sm font-medium">Варианты ответа</p>
      <div v-for="(option, index) in form.options" :key="option.id || `new-${index}`" class="flex items-center gap-2">
        <input
          v-model="option.title"
          :class="[field, 'flex-1', option.is_active === false ? 'text-ink-muted line-through' : '']"
          :aria-label="`Вариант ${index + 1}`"
          :placeholder="`Вариант ${index + 1}`"
        />
        <label v-if="option.is_active === false" class="flex items-center gap-1 text-xs text-ink-muted">
          <input v-model="option.is_active" type="checkbox" class="accent-brand-600" /> вернуть
        </label>
        <button type="button" class="px-1.5 disabled:opacity-30" :disabled="index === 0" aria-label="Выше" @click="moveOption(index, -1)">↑</button>
        <button type="button" class="px-1.5 disabled:opacity-30" :disabled="index === form.options.length - 1" aria-label="Ниже" @click="moveOption(index, 1)">↓</button>
        <button type="button" class="px-1.5 text-ink-muted hover:text-red-600" :aria-label="`Удалить вариант ${index + 1}`" @click="removeOption(index)">✕</button>
      </div>
      <UiButton size="sm" variant="ghost" class="justify-self-start" @click="addOption">+ Вариант</UiButton>
      <p v-if="answered" class="text-xs text-ink-muted">Варианты, которые уже выбирали, при удалении выключаются и остаются в результатах.</p>
      <label class="flex items-center gap-2 text-sm">
        <input v-model="form.is_options_shuffled" type="checkbox" class="accent-brand-600" /> Показывать варианты в случайном порядке
      </label>
    </div>

    <div v-if="hasSelections" class="flex flex-wrap gap-4">
      <label class="grid gap-1.5 text-sm font-medium">
        Минимум выборов
        <input v-model="form.min_selections" type="number" min="0" :class="[field, 'w-28']" />
      </label>
      <label class="grid gap-1.5 text-sm font-medium">
        Максимум выборов
        <input v-model="form.max_selections" type="number" min="1" :class="[field, 'w-28']" />
      </label>
    </div>

    <div v-if="form.question_type === 'number'" class="flex flex-wrap gap-4">
      <label class="grid gap-1.5 text-sm font-medium">
        Минимальное число
        <input v-model="form.min_number" type="number" :class="[field, 'w-32']" />
      </label>
      <label class="grid gap-1.5 text-sm font-medium">
        Максимальное число
        <input v-model="form.max_number" type="number" :class="[field, 'w-32']" />
      </label>
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
