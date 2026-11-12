<script setup>
defineProps({
  breakdown: { type: Object, required: true },
  answered: { type: Number, required: true },
})

const format = (value) => Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 1 })
</script>

<template>
  <div class="mt-3 grid gap-3 text-sm">
    <p v-if="breakdown.excluded.length" class="text-ink-muted">
      База сравнения: {{ breakdown.base }} из {{ answered }} ответивших.
    </p>
    <p v-if="!breakdown.base" class="text-ink-muted">{{ breakdown.excluded.length ? 'Нет данных для сравнения.' : 'Нет ответов.' }}</p>
    <ul v-else class="grid gap-2">
      <li v-for="option in breakdown.options" :key="option.id">
        <div class="mb-1 flex justify-between gap-3">
          <span>{{ option.title }}</span>
          <span class="shrink-0 tabular-nums text-ink-muted">{{ option.count }} · {{ format(option.percent) }}%</span>
        </div>
        <div class="h-2 overflow-hidden rounded-full bg-canvas">
          <div class="h-full rounded-full bg-brand-500" :style="{ width: `${option.percent}%` }" />
        </div>
      </li>
    </ul>
    <div v-if="breakdown.excluded.length" class="rounded-control bg-canvas p-3">
      <p class="mb-2 text-xs font-medium text-ink-muted">Вне базы сравнения · доля от всех ответивших</p>
      <ul class="grid gap-1">
        <li v-for="option in breakdown.excluded" :key="option.id" class="flex justify-between gap-3">
          <span>{{ option.title }}</span>
          <span class="shrink-0 tabular-nums text-ink-muted">
            {{ option.count }}<template v-if="answered"> · {{ format(option.percent) }}%</template>
          </span>
        </li>
      </ul>
    </div>
  </div>
</template>
