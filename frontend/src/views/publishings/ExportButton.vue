<script setup>
import { ref } from 'vue'
import { errorMessage, UiButton } from 'sk-ui'

const props = defineProps({
  download: { type: Function, required: true },
  variant: { type: String, default: 'primary' },
  size: { type: String, default: 'md' },
})
const loading = ref(false)
const error = ref('')

async function downloadFile() {
  loading.value = true
  error.value = ''
  try {
    await props.download()
  } catch (e) {
    error.value = errorMessage(e, 'Не удалось скачать файл. Попробуйте ещё раз.')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <UiButton :variant="variant" :size="size" :loading="loading" @click="downloadFile">
      <slot />
    </UiButton>
    <p v-if="error" role="alert" class="mt-1 text-sm text-red-700">{{ error }}</p>
  </div>
</template>
