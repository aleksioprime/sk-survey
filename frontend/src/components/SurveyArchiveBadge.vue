<script setup>
import { UiBadge } from 'sk-ui'

defineProps({ active: { type: Boolean, default: true } })
</script>

<template>
  <UiBadge v-if="active === false" tone="warning" class="shrink-0">В архиве</UiBadge>
</template>
