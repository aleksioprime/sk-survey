<script setup>
import { computed } from 'vue'
import { UiBadge, UiButton, UiCard } from 'sk-ui'
import PersonPicker from './PersonPicker.vue'

const props = defineProps({
  surveyId: { type: String, required: true },
  members: { type: Array, required: true },
  saving: { type: Boolean, default: false },
  error: { type: String, default: '' },
  notice: { type: String, default: '' },
})
const model = defineModel({ type: Array, required: true })
const emit = defineEmits(['save'])

const keyFor = (person) => person.user_id == null ? `person:${person.person_id}` : `user:${person.user_id}`
const savedKeys = computed(() => new Set(props.members.map(keyFor)))
const selected = computed(() => new Set(model.value.map(keyFor)))
const additions = computed(() => model.value.filter((person) => !savedKeys.value.has(keyFor(person))))
const rows = computed(() => [
  ...props.members.map((person) => ({ person, state: selected.value.has(keyFor(person)) ? 'saved' : 'removed' })),
  ...additions.value.map((person) => ({ person, state: 'added' })),
])
const changed = computed(() => rows.value.some((row) => row.state !== 'saved'))
const labels = { removed: 'Будет убран', added: 'Будет добавлен' }

function toggle({ person, state }) {
  model.value = state === 'removed'
    ? [...model.value, person]
    : model.value.filter((item) => keyFor(item) !== keyFor(person))
}
</script>

<template>
  <UiCard class="grid gap-4">
    <div>
      <h2 class="font-semibold">Редакторы опроса</h2>
      <p class="mt-1 text-sm text-ink-muted">
        Редакторы меняют опрос и публикации, смотрят результаты и управляют этим списком.
        Наблюдателей добавляют в настройках отдельной публикации.
      </p>
    </div>

    <div class="grid gap-2">
      <ul v-if="rows.length" class="divide-y divide-line rounded-control border border-line">
        <li v-for="row in rows" :key="keyFor(row.person)" class="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
          <div class="min-w-0">
            <p class="break-words text-sm font-medium">{{ row.person.full_name }}</p>
            <p v-if="row.person.email && row.person.email !== row.person.full_name" class="break-all text-xs text-ink-muted">{{ row.person.email }}</p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <UiBadge v-if="labels[row.state]" :tone="row.state === 'removed' ? 'warning' : 'brand'">{{ labels[row.state] }}</UiBadge>
            <UiButton
              size="sm"
              variant="ghost"
              :disabled="saving"
              :aria-label="`${row.state === 'removed' ? 'Вернуть' : 'Убрать'} ${row.person.full_name}`"
              @click="toggle(row)"
            >
              {{ row.state === 'removed' ? 'Вернуть' : 'Убрать' }}
            </UiButton>
          </div>
        </li>
      </ul>
    </div>

    <PersonPicker
      v-model="model"
      :survey-id="surveyId"
      label="Добавить редактора"
      :excluded="members"
      :show-selection="false"
      :disabled="saving"
    />

    <p v-if="!model.length" class="text-sm text-ink-muted">У опроса должен остаться хотя бы один редактор.</p>
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <p v-if="notice && !changed" role="status" class="text-sm text-brand-700">{{ notice }}</p>
    <UiButton class="justify-self-start" :loading="saving" :disabled="!changed || !model.length" @click="emit('save')">
      Сохранить доступ
    </UiButton>
  </UiCard>
</template>
