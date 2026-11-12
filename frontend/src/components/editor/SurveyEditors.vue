<script setup>
import { computed } from 'vue'
import { UiBadge, UiButton, UiCard } from 'sk-ui'
import PersonPicker from './PersonPicker.vue'

const props = defineProps({
  members: { type: Array, required: true },
  saving: { type: Boolean, default: false },
  error: { type: String, default: '' },
  notice: { type: String, default: '' },
})
const model = defineModel({ type: Array, required: true })
const emit = defineEmits(['save'])

const keyFor = (person) => person.person_id ?? `user:${person.user_id}`
const owners = computed(() => props.members.filter((member) => member.role === 'owner'))
const saved = computed(() => props.members.filter((member) => member.role === 'editor'))
const savedKeys = computed(() => new Set(saved.value.map(keyFor)))
const selectedKeys = computed(() => new Set(model.value.map(keyFor)))
const additions = computed(() => model.value.filter((person) => !savedKeys.value.has(keyFor(person))))
const rows = computed(() => [
  ...saved.value.map((person) => ({
    person,
    state: selectedKeys.value.has(keyFor(person)) ? 'saved' : 'removed',
  })),
  ...additions.value.map((person) => ({ person, state: 'added' })),
])
const changed = computed(() => rows.value.some((row) => row.state !== 'saved'))
const excluded = computed(() => [...owners.value, ...saved.value])
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
      <p class="mt-1 text-sm text-ink-muted">Могут менять вопросы и публикации, видят результаты.</p>
    </div>

    <div class="grid gap-2">
      <h3 class="text-sm font-medium">Назначенные редакторы · {{ saved.length }}</h3>
      <p v-if="!saved.length" class="text-sm text-ink-muted">Редакторы пока не назначены.</p>
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
      <p v-if="owners.length" class="break-words text-xs text-ink-muted">
        {{ owners.length === 1 ? 'Владелец' : 'Владельцы' }} уже {{ owners.length === 1 ? 'имеет' : 'имеют' }} доступ:
        {{ owners.map((owner) => owner.full_name).join(', ') }}.
      </p>
    </div>

    <PersonPicker v-model="model" label="Добавить редакторов" :excluded="excluded" :show-selection="false" :disabled="saving" />

    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <p v-if="notice && !changed" role="status" class="text-sm text-brand-700">{{ notice }}</p>
    <UiButton class="justify-self-start" :loading="saving" :disabled="!changed" @click="emit('save')">Сохранить редакторов</UiButton>
  </UiCard>
</template>
