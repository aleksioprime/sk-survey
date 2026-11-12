<script setup>
import { computed } from 'vue'
import { UiBadge, UiButton, UiCard } from 'sk-ui'
import PersonPicker from './PersonPicker.vue'

const props = defineProps({
  surveyId: { type: String, required: true },
  members: { type: Array, required: true },
  currentUserId: { type: Number, default: null },
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
const isSelf = (person) => person.user_id != null && person.user_id === props.currentUserId

function toggle({ person, state }) {
  if (isSelf(person)) return
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
        <li v-for="row in rows" :key="keyFor(row.person)" class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 px-3 py-2">
          <div class="min-w-0">
            <p class="text-sm font-medium wrap-anywhere">{{ row.person.full_name }}</p>
            <p v-if="row.person.email && row.person.email !== row.person.full_name" class="text-xs text-ink-muted wrap-anywhere">{{ row.person.email }}</p>
            <UiBadge v-if="labels[row.state]" class="mt-1" :tone="row.state === 'removed' ? 'warning' : 'brand'">{{ labels[row.state] }}</UiBadge>
          </div>
          <UiBadge v-if="isSelf(row.person)" tone="brand" title="Себя убрать нельзя">Вы</UiBadge>
          <UiButton
            v-else
            :variant="row.state === 'removed' ? 'secondary' : 'danger-outline'"
            class="size-10 p-0!"
            :disabled="saving"
            :aria-label="`${row.state === 'removed' ? 'Вернуть' : 'Убрать'} ${row.person.full_name}`"
            :title="row.state === 'removed' ? 'Вернуть редактора' : 'Убрать редактора'"
            @click="toggle(row)"
          >
            <svg aria-hidden="true" class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
              <path v-if="row.state === 'removed'" d="M9 14 4 9m0 0 5-5M4 9h10a5 5 0 0 1 0 10h-2" />
              <path v-else d="M4 6h16M9 6V4h6v2m3 0-1 14H7L6 6m4 4v6m4-6v6" />
            </svg>
          </UiButton>
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
