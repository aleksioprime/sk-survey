<script setup>
import { onMounted, ref } from 'vue'
import nocobaseApi from '@/api/nocobase'
import { useAuthStore } from '@/stores/auth'
import { canUserViewPublishing } from '@/utils/publishingAccess'

const loading = ref(true)
const error = ref('')
const publishings = ref([])
const statsByPublishing = ref({})
const copiedLinks = ref({})
const auth = useAuthStore()

function chunkArray(list, chunkSize) {
  const result = []
  for (let i = 0; i < list.length; i += chunkSize) {
    result.push(list.slice(i, i + chunkSize))
  }
  return result
}

function formatDate(value) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString('ru-RU')
  } catch {
    return '—'
  }
}

function canViewPublishing(publishing) {
  return canUserViewPublishing(publishing, {
    currentUserId: auth.user?.id,
    isAdmin: auth.isAdmin,
  })
}

async function loadStats(publishingIds) {
  if (!publishingIds.length) {
    statsByPublishing.value = {}
    return
  }

  const stats = {}
  for (const publishingId of publishingIds) {
    stats[publishingId] = {
      total: 0,
      submitted: 0,
      inProgress: 0,
      lastSubmittedAt: null,
    }
  }

  const batches = chunkArray(publishingIds, 100)

  for (const batch of batches) {
    const { data } = await nocobaseApi.get('/survey_responses:list', {
      params: {
        filter: JSON.stringify({
          publishing_id: { $in: batch },
        }),
        sort: '-submitted_at,id',
        pageSize: 100000,
      },
    })

    for (const response of data?.data || []) {
      const publishingId = Number(response?.publishing_id)
      if (!stats[publishingId]) {
        stats[publishingId] = {
          total: 0,
          submitted: 0,
          inProgress: 0,
          lastSubmittedAt: null,
        }
      }

      const current = stats[publishingId]
      current.total += 1

      if (response?.status === 'submitted') {
        current.submitted += 1
      } else if (response?.status === 'in_progress') {
        current.inProgress += 1
      }

      const submittedAt = response?.submitted_at || null
      if (submittedAt && (!current.lastSubmittedAt || submittedAt > current.lastSubmittedAt)) {
        current.lastSubmittedAt = submittedAt
      }
    }
  }

  statsByPublishing.value = stats
}

async function loadPublishings() {
  loading.value = true
  error.value = ''

  try {
    const { data } = await nocobaseApi.get('/survey_publishings:list', {
      params: {
        appends: 'survey,observers',
        pageSize: 1000,
      },
    })

    const items = (data?.data || [])
      .filter((item) => canViewPublishing(item))
      .slice()
      .sort((a, b) => {
        const activeDiff = Number(Boolean(b?.is_active)) - Number(Boolean(a?.is_active))
        if (activeDiff !== 0) return activeDiff

        const titleCompare = String(a?.title || a?.survey?.title || '').localeCompare(
          String(b?.title || b?.survey?.title || ''),
          'ru',
        )

        if (titleCompare !== 0) return titleCompare
        return Number(a?.id || 0) - Number(b?.id || 0)
      })

    publishings.value = items
    const publishingIds = items.map((item) => Number(item?.id)).filter(Boolean)
    await loadStats(publishingIds)
  } catch {
    error.value = 'Не удалось загрузить список публикаций'
  } finally {
    loading.value = false
  }
}

function getStats(publishingId) {
  return statsByPublishing.value[Number(publishingId)] || {
    total: 0,
    submitted: 0,
    inProgress: 0,
    lastSubmittedAt: null,
  }
}

function getPublicSurveyLink(publicToken) {
  if (!publicToken) return null

  if (typeof window !== 'undefined') {
    return `${window.location.origin}/s/${publicToken}`
  }

  return `/s/${publicToken}`
}

function isLinkCopied(publishingId) {
  return copiedLinks.value[Number(publishingId)] === true
}

async function copyPublicSurveyLink(publishingId, publicToken) {
  const url = getPublicSurveyLink(publicToken)
  if (!url || typeof window === 'undefined') return

  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(url)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = url
      textarea.setAttribute('readonly', '')
      textarea.style.position = 'absolute'
      textarea.style.left = '-9999px'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }

    const key = Number(publishingId)
    copiedLinks.value = { ...copiedLinks.value, [key]: true }
    window.setTimeout(() => {
      copiedLinks.value = { ...copiedLinks.value, [key]: false }
    }, 1800)
  } catch {
    // ignore copy errors
  }
}

onMounted(() => {
  loadPublishings()
})
</script>

<template>
  <div class="mx-auto w-full max-w-6xl px-4 py-6">
    <div class="mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-800">Личный кабинет Survey</h1>
        <p class="mt-1 text-sm text-muted">Просмотр результатов по публикациям опросов</p>
      </div>
    </div>

    <div v-if="loading" class="glass-panel p-8 text-center text-muted">Загрузка публикаций...</div>

    <div v-else-if="error" class="glass-panel p-8 text-center text-danger">
      {{ error }}
    </div>

    <div v-else-if="!publishings.length" class="glass-panel p-8 text-center text-muted">
      Нет публикаций опросов
    </div>

    <div v-else class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <article
        v-for="publishing in publishings"
        :key="publishing.id"
        class="glass-panel flex h-full flex-col p-5"
      >
        <div class="flex items-start justify-between gap-3">
          <h2 class="text-lg font-semibold text-slate-800">
            {{ publishing.title || publishing.survey?.title || `Публикация #${publishing.id}` }}
          </h2>
          <span
            class="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold"
            :class="publishing.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'"
          >
            {{ publishing.is_active ? 'Активна' : 'Неактивна' }}
          </span>
        </div>

        <p class="mt-1 text-sm text-slate-600">
          Опрос: {{ publishing.survey?.title || '—' }}
        </p>

        <p v-if="publishing.survey?.description" class="mt-2 line-clamp-3 text-sm text-muted">
          {{ publishing.survey.description }}
        </p>

        <div class="mt-4 space-y-1 text-sm text-slate-700">
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="inline-flex cursor-pointer items-center justify-center rounded-lg border px-3 py-1.5 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50"
              :class="isLinkCopied(publishing.id)
                ? 'border-emerald-700 bg-emerald-700 text-white'
                : 'border-primary text-primary hover:bg-primary/5'"
              :disabled="!publishing.public_token"
              @click="copyPublicSurveyLink(publishing.id, publishing.public_token)"
            >
              {{ publishing.public_token ? 'Копировать ссылку' : 'Нет ссылки' }}
            </button>
          </div>
          <p>
            <span class="text-muted">Количество ответов:</span>
            {{ getStats(publishing.id).total }}
          </p>
          <p>
            <span class="text-muted">Отправлено ответов:</span>
            {{ getStats(publishing.id).submitted }}
          </p>
          <p>
            <span class="text-muted">Последняя отправка:</span>
            {{ formatDate(getStats(publishing.id).lastSubmittedAt) }}
          </p>
        </div>

        <router-link
          :to="{ name: 'publishing-results', params: { publishingId: publishing.id } }"
          class="btn-primary mt-5 no-underline"
        >
          Смотреть результаты
        </router-link>
      </article>
    </div>
  </div>
</template>
