<template>
  <div class="mx-auto max-w-2xl px-4 py-12 text-center">
    <div class="glass-panel p-8">
      <h1 class="text-2xl font-bold text-slate-800">Доступ закрыт</h1>
      <p class="mt-3 text-muted">
        У вашей учетной записи нет роли для просмотра результатов опросов.
      </p>
      <p class="mt-1 text-sm text-muted">
        Обратитесь к администратору, чтобы выдать доступ к результатам.
      </p>
      <router-link to="/login" class="btn-outline mt-6 inline-flex">Вернуться ко входу</router-link>
    </div>
  </div>
</template>
