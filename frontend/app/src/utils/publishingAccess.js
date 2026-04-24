function normalizeNumericId(value) {
  if (value == null) return null

  if (typeof value === 'number') {
    return Number.isNaN(value) ? null : Number(value)
  }

  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isNaN(parsed) ? null : parsed
  }

  const parsed = Number(value?.id ?? value?.user_id)
  return Number.isNaN(parsed) ? null : parsed
}

export function getObserverIds(publishing) {
  const observers = Array.isArray(publishing?.observers) ? publishing.observers : []
  return observers
    .map((observer) => normalizeNumericId(observer))
    .filter((id) => id != null)
}

export function canUserViewPublishing(publishing, { currentUserId, isAdmin = false } = {}) {
  if (isAdmin) return true

  const normalizedUserId = normalizeNumericId(currentUserId)
  if (normalizedUserId == null) return false

  return getObserverIds(publishing).includes(normalizedUserId)
}
