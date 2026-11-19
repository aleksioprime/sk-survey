<script setup>
import { computed } from 'vue'

const props = defineProps({ publishings: { type: Array, required: true } })
const target = computed(() => ({
  name: 'publishing',
  params: { id: props.publishings[0].id },
  query: { publication: props.publishings.slice(1).map((p) => String(p.id)) },
}))
</script>

<template>
  <RouterLink
    v-if="publishings.length > 1" :to="target"
    class="inline-flex min-h-9 items-center rounded-control border border-line bg-surface px-3 text-sm font-medium text-brand-700 hover:bg-brand-50"
  >Общая статистика</RouterLink>
</template>
