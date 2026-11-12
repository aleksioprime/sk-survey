<script setup>
import { ref } from 'vue'
import { errorMessage, UiButton, UiInput } from 'sk-ui'
import { createScale, updateScale } from '@/api/surveys'

const emit = defineEmits(['saved', 'cancel', 'unavailable'])
const props = defineProps({
  source: { type: Object, default: null },
  editing: { type: Boolean, default: false },
  embedded: { type: Boolean, default: false },
})

const source = props.source
const form = ref({
  title: props.editing ? source.title : source ? `${source.title.slice(0, 247)} (копия)` : '',
  description: source?.description ?? '',
  scale_type: source?.scale_type ?? 'generated',
  min_value: source?.min_value ?? 1,
  max_value: source?.max_value ?? 5,
  step: source?.step ?? 1,
  items: source?.items.length
    ? source.items.map(({ id, title, description, value, score }) => ({
      id: props.editing ? id : undefined, title, description, value, score,
    }))
    : [{ title: '' }, { title: '' }],
})
const saving = defineModel('saving', { type: Boolean, default: false })
const error = ref('')
const unavailable = ref(false)

async function save() {
  if (saving.value || unavailable.value) return
  error.value = ''
  saving.value = true
  try {
    const f = form.value
    const payload = {
      title: f.title.trim() || `Шкала ${f.min_value}–${f.max_value}`,
      description: f.description,
      scale_type: f.scale_type,
      min_value: Number(f.min_value),
      max_value: Number(f.max_value),
      step: Number(f.step) || 1,
      items: f.scale_type === 'items' ? f.items.filter((i) => i.title.trim()).map((item, index) => ({
        id: item.id,
        title: item.title.trim(),
        description: item.description ?? '',
        value: item.value ?? String(index + 1),
        score: Object.hasOwn(item, 'score') ? item.score : index + 1,
      })) : [],
    }
    const scale = props.editing ? await updateScale(source.id, payload) : await createScale(payload)
    emit('saved', scale)
  } catch (e) {
    error.value = errorMessage(e)
    const status = e.response?.status
    if (props.editing && (status === 404 || status === 409)) {
      unavailable.value = true
      emit('unavailable', source.id, status)
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <form class="grid gap-4" :class="embedded ? '' : 'rounded-card border border-line bg-canvas p-4'" @submit.prevent="save">
    <p v-if="!embedded" class="font-semibold">Новая шкала</p>
    <UiInput v-model="form.title" label="Название" placeholder="Например, «Согласие 1–5»" maxlength="255" :autofocus="embedded" />
    <label v-if="editing" class="grid gap-1.5 text-sm font-medium">
      Описание
      <textarea v-model="form.description" rows="2" class="rounded-control border border-line bg-surface p-2 font-normal focus:border-brand-500" />
    </label>
    <div class="flex gap-4 text-sm">
      <label class="flex items-center gap-2"><input v-model="form.scale_type" type="radio" value="generated" class="accent-brand-600" /> Числа</label>
      <label class="flex items-center gap-2"><input v-model="form.scale_type" type="radio" value="items" class="accent-brand-600" /> Подписи</label>
    </div>
    <div v-if="form.scale_type === 'generated'" class="grid grid-cols-3 gap-3">
      <UiInput v-model="form.min_value" label="От" type="number" class="min-w-0" required />
      <UiInput v-model="form.max_value" label="До" type="number" class="min-w-0" required />
      <UiInput v-model="form.step" label="Шаг" type="number" min="1" class="min-w-0" required />
    </div>
    <div v-else class="grid gap-2">
      <p class="text-xs text-ink-muted">{{ source ? 'Баллы существующих подписей сохраняются.' : 'По порядку от меньшего к большему, баллы - номер подписи.' }}</p>
      <div v-for="(item, index) in form.items" :key="index" class="flex gap-2">
        <UiInput v-model="item.title" class="min-w-0 flex-1" :placeholder="`Подпись ${index + 1}`" :aria-label="`Подпись ${index + 1}`" />
        <UiButton size="sm" variant="ghost" class="text-ink-muted hover:text-red-600" aria-label="Удалить" @click="form.items.splice(index, 1)">✕</UiButton>
      </div>
      <UiButton size="sm" variant="ghost" class="justify-self-start" @click="form.items.push({ title: '' })">+ Подпись</UiButton>
    </div>
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <div class="flex flex-wrap gap-2" :class="{ 'justify-end': embedded }">
      <UiButton size="sm" variant="secondary" :disabled="saving" @click="emit('cancel')">Отмена</UiButton>
      <UiButton type="submit" variant="primary" size="sm" :loading="saving" :disabled="unavailable">
        {{ editing ? 'Сохранить' : source ? 'Создать копию' : 'Создать шкалу' }}
      </UiButton>
    </div>
  </form>
</template>
