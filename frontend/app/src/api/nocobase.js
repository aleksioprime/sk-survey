/**
 * HTTP-клиент для прямой работы с NocoBase REST API.
 *
 * Базовый URL: /api (проксируется через Vite/nginx).
 * В каждый запрос добавляет Bearer-токен из localStorage.
 */
import axios from 'axios'
import router from '@/router'
import { AUTH_TOKEN_STORAGE_KEY } from '@/constants/auth'

const nocobaseApi = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

nocobaseApi.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

nocobaseApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
      if (router.currentRoute.value.name !== 'login') {
        router.push({ name: 'login' })
      }
    }
    return Promise.reject(error)
  },
)

export default nocobaseApi
