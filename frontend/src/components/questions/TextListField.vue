<script setup>
import { computed, nextTick, ref } from 'vue'
import { UiButton } from 'sk-ui'
import { TEXT_LIST_MAX_ROWS, TEXT_LIST_ROW_LENGTH, countTextRows } from '@/utils/questionTypes'

const props = defineProps({ question: { type: Object, required: true } })
const model = defineModel({ type: Array, required: true })
const list = ref(null)
const rows = computed(() => model.value.length ? model.value : [''])
const max = computed(() => props.question.max_rows ?? TEXT_LIST_MAX_ROWS)
const min = computed(() => props.question.min_rows ?? (props.question.is_required ? 1 : null))

function update(index, value) {
  model.value = rows.value.map((row, i) => i === index ? value : row)
}

async function focusRow(index) {
  await nextTick()
  list.value?.querySelectorAll('input')[index]?.focus()
}

function addRow() {
  if (rows.value.length >= max.value) return
  const index = rows.value.length
  model.value = [...rows.value, '']
  focusRow(index)
}

function removeRow(index) {
  const remaining = rows.value.filter((_, i) => i !== index)
  model.value = remaining
  focusRow(Math.max(0, Math.min(index, remaining.length - 1)))
}
</script>

<template>
  <div class="grid gap-3">
    <p class="text-sm text-ink-muted">
      <template v-if="min">
        {{ question.is_required ? 'Минимум заполненных строк' : 'Если отвечаете, минимум заполненных строк' }}: {{ min }}.
      </template>
      Максимум: {{ max }}.
    </p>
    <div ref="list" class="grid gap-2">
      <div v-for="(row, index) in rows" :key="index" class="flex min-w-0 items-center gap-2">
        <input
          type="text"
          :aria-label="`Строка ${index + 1}`"
          :placeholder="`Строка ${index + 1}`"
          :value="row"
          :maxlength="TEXT_LIST_ROW_LENGTH"
          class="h-10 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 outline-none focus:border-brand-500"
          @input="update(index, $event.target.value)"
        />
        <UiButton
          v-if="rows.length > 1"
          variant="ghost"
          :aria-label="`Удалить строку ${index + 1}`"
          @click="removeRow(index)"
        >
          ✕
        </UiButton>
      </div>
    </div>
    <div class="flex flex-wrap items-center gap-3">
      <UiButton size="sm" :disabled="rows.length >= max" @click="addRow">+ Добавить строку</UiButton>
      <span class="text-xs text-ink-muted">Заполнено: {{ countTextRows(rows) }}</span>
    </div>
  </div>
</template>
