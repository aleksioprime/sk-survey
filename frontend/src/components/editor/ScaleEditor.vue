<script setup>
import { ref } from 'vue'
import { errorMessage } from '@/api/http'
import { createScale } from '@/api/surveys'
import UiButton from '@/components/ui/UiButton.vue'
import UiInput from '@/components/ui/UiInput.vue'

const emit = defineEmits(['created', 'cancel'])

const form = ref({ title: '', scale_type: 'generated', min_value: 1, max_value: 5, step: 1, items: [{ title: '' }, { title: '' }] })
const saving = ref(false)
const error = ref('')

async function save() {
  error.value = ''
  saving.value = true
  try {
    const f = form.value
    const scale = await createScale({
      title: f.title.trim() || `Шкала ${f.min_value}–${f.max_value}`,
      scale_type: f.scale_type,
      min_value: Number(f.min_value),
      max_value: Number(f.max_value),
      step: Number(f.step) || 1,
      items: f.scale_type === 'items' ? f.items.filter((i) => i.title.trim()).map((i, n) => ({ title: i.title.trim(), value: String(n + 1), score: n + 1 })) : [],
    })
    emit('created', scale)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

const field = 'h-10 rounded-control border border-line bg-surface px-3 outline-none focus:border-brand-500'
</script>

<template>
  <form class="grid gap-4 rounded-card border border-line bg-canvas p-4" @submit.prevent="save">
    <p class="font-semibold">Новая шкала</p>
    <UiInput v-model="form.title" label="Название" placeholder="Например, «Согласие 1–5»" />
    <div class="flex gap-4 text-sm">
      <label class="flex items-center gap-2"><input v-model="form.scale_type" type="radio" value="generated" class="accent-brand-600" /> Числа</label>
      <label class="flex items-center gap-2"><input v-model="form.scale_type" type="radio" value="items" class="accent-brand-600" /> Подписи</label>
    </div>
    <div v-if="form.scale_type === 'generated'" class="flex flex-wrap gap-4">
      <label class="grid gap-1.5 text-sm font-medium">От <input v-model="form.min_value" type="number" :class="[field, 'w-24']" /></label>
      <label class="grid gap-1.5 text-sm font-medium">До <input v-model="form.max_value" type="number" :class="[field, 'w-24']" /></label>
      <label class="grid gap-1.5 text-sm font-medium">Шаг <input v-model="form.step" type="number" min="1" :class="[field, 'w-24']" /></label>
    </div>
    <div v-else class="grid gap-2">
      <p class="text-xs text-ink-muted">По порядку от меньшего к большему, баллы — номер подписи.</p>
      <div v-for="(item, index) in form.items" :key="index" class="flex gap-2">
        <input v-model="item.title" :class="[field, 'flex-1']" :placeholder="`Подпись ${index + 1}`" :aria-label="`Подпись ${index + 1}`" />
        <button type="button" class="px-2 text-ink-muted hover:text-red-600" aria-label="Удалить" @click="form.items.splice(index, 1)">✕</button>
      </div>
      <UiButton size="sm" variant="ghost" class="justify-self-start" @click="form.items.push({ title: '' })">+ Подпись</UiButton>
    </div>
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <div class="flex gap-2">
      <UiButton type="submit" variant="primary" size="sm" :loading="saving">Создать шкалу</UiButton>
      <UiButton size="sm" variant="ghost" @click="emit('cancel')">Отмена</UiButton>
    </div>
  </form>
</template>
