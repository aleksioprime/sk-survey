function normalizeNumericId(value) {
  if (value == null) return null

  if (typeof value === 'number') {
    return Number.isNaN(value) ? null : Number(value)
  }

  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isNaN(parsed) ? null : parsed
  }

  const parsed = Number(value?.user_id ?? value?.user?.id ?? value?.id)
  return Number.isNaN(parsed) ? null : parsed
}

function getObserverUserIds(publishing) {
  const observers = Array.isArray(publishing?.observers) ? publishing.observers : []
  return observers
    .map((observer) => {
      if (observer == null) return null
      if (typeof observer === 'number' || typeof observer === 'string') {
        return normalizeNumericId(observer)
      }
      return normalizeNumericId(observer?.user_id ?? observer?.user?.id)
    })
    .filter((id) => id != null)
}

function getObserverPersonIds(publishing) {
  const observers = Array.isArray(publishing?.observers) ? publishing.observers : []
  return observers
    .map((observer) => {
      if (observer == null) return null
      if (typeof observer === 'number' || typeof observer === 'string') {
        return normalizeNumericId(observer)
      }
      return normalizeNumericId(observer?.id ?? observer?.person_id ?? observer?.person?.id)
    })
    .filter((id) => id != null)
}

function normalizeCurrentPersonIds(currentPerson) {
  const raw = Array.isArray(currentPerson) ? currentPerson : [currentPerson]
  return raw
    .map((person) => {
      if (person == null) return null
      if (typeof person === 'number' || typeof person === 'string') {
        return normalizeNumericId(person)
      }
      return normalizeNumericId(person?.id ?? person?.person_id)
    })
    .filter((id) => id != null)
}

export function canUserViewPublishing(
  publishing,
  {
    currentUserId,
    currentPerson,
    isAdmin = false,
  } = {},
) {
  if (isAdmin) return true

  const normalizedUserId = normalizeNumericId(currentUserId)
  const observerUserIds = getObserverUserIds(publishing)
  if (normalizedUserId != null && observerUserIds.includes(normalizedUserId)) {
    return true
  }

  const currentPersonIds = normalizeCurrentPersonIds(currentPerson)
  if (!currentPersonIds.length) return false

  const observerPersonIds = getObserverPersonIds(publishing)
  return currentPersonIds.some((personId) => observerPersonIds.includes(personId))
}
