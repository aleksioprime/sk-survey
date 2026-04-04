<script setup>
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <main class="flex-1">
      <router-view />
    </main>
    <footer class="py-4 text-center text-xs text-muted">
      Сервисы автоматизации Гимназии Сколково · © {{ new Date().getFullYear() }}  Алексей Семочкин
    </footer>
  </div>
</template>
