<script setup>
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <main class="flex-1">
      <router-view />
    </main>
    <footer class="py-4 text-center text-xs text-muted">
      © {{ new Date().getFullYear() }} Гимназия Сколково
    </footer>
  </div>
</template>
