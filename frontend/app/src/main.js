/**
 * Точка входа приложения SK Survey.
 *
 * Инициализирует Vue 3, подключает Pinia (стейт-менеджер)
 * и Vue Router, монтирует корневой компонент.
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
