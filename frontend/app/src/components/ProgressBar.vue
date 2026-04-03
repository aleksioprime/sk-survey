<!--
  ProgressBar — полоса прогресса прохождения опроса.
  Принимает value (0–100), отображает анимированную полоску с процентами.
-->
<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },
})

const widthStyle = computed(() => `${Math.min(100, Math.max(0, props.value))}%`)
</script>

<template>
  <div class="w-full">
    <div class="flex items-center justify-between mb-1">
      <span class="text-xs text-muted">Прогресс</span>
      <span class="text-xs font-semibold text-primary">{{ value }}%</span>
    </div>
    <div class="h-2 w-full rounded-full bg-slate-200 overflow-hidden">
      <div
        class="h-full rounded-full bg-primary transition-all duration-500 ease-out"
        :style="{ width: widthStyle }"
      />
    </div>
  </div>
</template>
