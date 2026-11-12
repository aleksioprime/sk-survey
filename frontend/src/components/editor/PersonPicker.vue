<script setup>
/** Выбор сотрудников из справочника SkolStream для опроса или публикации. */
import { UiInput } from 'sk-ui'
import { computed, ref, watch } from 'vue'
import { searchEmployees } from '@/api/surveys'

const props = defineProps({
  label: { type: String, required: true },
  hint: { type: String, default: '' },
  excluded: { type: Array, default: () => [] },
  showSelection: { type: Boolean, default: true },
  inlineResults: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})
// [{ person_id, full_name, email }]
const model = defineModel({ type: Array, default: () => [] })

const query = ref('')
const found = ref([])
const normalize = (value) => value?.trim().toLowerCase()
const available = computed(() => {
  const excluded = [...model.value, ...props.excluded]
  const ids = new Set(excluded.map((person) => person.person_id))
  const emails = new Set(excluded.map((person) => normalize(person.email)).filter(Boolean))
  return found.value.filter((person) => !ids.has(person.id) && !emails.has(normalize(person.email)))
})

watch(query, (value, _, onCleanup) => {
  found.value = []
  if (value.trim().length < 2) return
  let current = true
  const timer = setTimeout(async () => {
    try {
      const people = await searchEmployees(value.trim())
      if (current) found.value = people
    } catch {
      if (current) found.value = []
    }
  }, 300)
  onCleanup(() => {
    current = false
    clearTimeout(timer)
  })
})

function add(person) {
  model.value = [...model.value, { person_id: person.id, full_name: person.full_name, email: person.email }]
  query.value = ''
  found.value = []
}

function remove(index) {
  model.value = model.value.filter((_, i) => i !== index)
}
</script>

<template>
  <div class="grid gap-2">
    <p class="text-sm font-medium">{{ props.label }}</p>
    <p v-if="props.hint" class="-mt-1 text-xs text-ink-muted">{{ props.hint }}</p>
    <ul v-if="props.showSelection && model.length" class="flex flex-wrap gap-2">
      <li v-for="(person, index) in model" :key="person.person_id ?? person.email" class="flex max-w-full items-center gap-2 rounded-full bg-brand-50 py-1 pl-3 pr-1 text-sm">
        <span :title="person.email" class="min-w-0 wrap-anywhere">{{ person.full_name }}</span>
        <button type="button" class="grid size-6 shrink-0 place-items-center rounded-full hover:bg-brand-100" :aria-label="`Убрать ${person.full_name}`" @click="remove(index)">✕</button>
      </li>
    </ul>
    <div class="relative">
      <UiInput v-model="query" type="search" placeholder="Фамилия или email сотрудника" :disabled="props.disabled" :aria-label="props.showSelection ? `Добавить: ${props.label}` : props.label" />
      <p v-if="!props.showSelection && found.length && !available.length" class="mt-1 text-xs text-ink-muted">
        Найденные сотрудники уже в списке или имеют доступ.
      </p>
      <ul
        v-if="!props.disabled && available.length"
        class="max-h-56 overflow-auto rounded-control border border-line bg-surface"
        :class="props.inlineResults ? 'mt-2' : 'absolute inset-x-0 top-11 z-10 shadow-lg'"
      >
        <li v-for="person in available" :key="person.id">
          <button type="button" class="w-full px-3 py-2 text-left hover:bg-brand-50" @click="add(person)">
            {{ person.full_name }}
            <span class="block text-xs wrap-anywhere text-ink-muted">{{ [person.email, ...person.departments].filter(Boolean).join(' · ') }}</span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>
