<script setup>
defineProps({ type: { type: String, required: true } })

const shapes = {
  single_choice: 'M8 8a3 3 0 1 0-6 0 3 3 0 0 0 6 0ZM8 16a3 3 0 1 0-6 0 3 3 0 0 0 6 0ZM12 8h9m-9 8h9M5 8h.01',
  multiple_choice: 'M2 5h6v6H2zm0 8h6v6H2zm10-5h9m-9 8h9M3.5 8l1 1L7 6.5',
  matrix_single: 'M3 4h18v16H3zM3 9h18m-18 5h18M10 4v16m5-16v16M12.5 11.5h.01m5.5 5h.01',
  matrix_multiple: 'M3 4h18v16H3zM3 9h18m-18 5h18M10 4v16m5-16v16m-4-8 1 1 2-2m2 1 1 1 2-2m-8 6 1 1 2-2',
  scale: 'M3 8h18v8H3zM7 8v3m5-3v5m5-5v3',
  text: 'M4 6h16M4 11h16M4 16h10',
  rich_text: 'M5 3h11l3 3v15H5zm10 0v5h4M8 11h8m-8 3h8m-8 3h5',
  number: 'M10 4 6 20M18 4l-4 16M4 9h17M3 15h17',
  yes_no: 'm2 12 3 3 5-6m5 0 6 6m0-6-6 6',
  ranking: 'M10 5h11M10 12h8m-8 7h5M5 4v16m-3-3 3 3 3-3',
}
</script>

<template>
  <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" class="size-5 shrink-0">
    <path :d="shapes[type] || shapes.text" />
  </svg>
</template>
