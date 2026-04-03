/**
 * HTTP-клиент для публичного API.
 *
 * Все запросы к BFF-бэкенду проходят через этот экземпляр Axios.
 * В dev-режиме запросы проксируются через Vite (/backend → backend:8000).
 * В production nginx выполняет аналогичный проксинг.
 */

import axios from 'axios'

const publicApi = axios.create({
  baseURL: import.meta.env.VITE_BACKEND_API_URL || '/backend',
  headers: { 'Content-Type': 'application/json' },
})

export default publicApi
