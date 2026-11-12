import { http } from 'sk-ui'

/** Ключ прохождения хранится в браузере по токену публикации: можно закрыть вкладку и продолжить. */
const storageKey = (token) => `sks-response:${token}`

export function savedResponseToken(publicToken) {
  try {
    return localStorage.getItem(storageKey(publicToken))
  } catch {
    return null
  }
}

export function rememberResponseToken(publicToken, responseToken) {
  try {
    localStorage.setItem(storageKey(publicToken), responseToken)
  } catch {
    // приватный режим: прохождение живёт до закрытия вкладки
  }
}

export function forgetResponseToken(publicToken) {
  try {
    localStorage.removeItem(storageKey(publicToken))
  } catch {
    // нечего удалять
  }
}

const completedKey = (token) => `sks-completed:${token}`

export function hasCompleted(publicToken) {
  try {
    return localStorage.getItem(completedKey(publicToken)) === 'yes'
  } catch {
    return false
  }
}

export function markCompleted(publicToken) {
  try {
    localStorage.setItem(completedKey(publicToken), 'yes')
    forgetResponseToken(publicToken)
  } catch {
    // Если отметку записать не удалось, оставляем ключ для проверки статуса.
  }
}

export async function fetchPreview(surveyId) {
  return (await http.get(`/v1/surveys/${surveyId}/preview`)).data
}

const withToken = (responseToken) => ({ headers: { 'X-Response-Token': responseToken } })

export async function fetchPublicSurvey(publicToken) {
  return (await http.get(`/v1/public/s/${publicToken}`)).data
}

export async function startResponse(publicToken) {
  return (await http.post(`/v1/public/s/${publicToken}/responses`)).data
}

export async function fetchResponse(responseToken) {
  return (await http.get('/v1/public/responses/current', withToken(responseToken))).data
}

export async function saveAnswer(responseToken, questionId, answer) {
  return (await http.put(`/v1/public/responses/current/answers/${questionId}`, answer, withToken(responseToken))).data
}

export async function submitResponse(responseToken) {
  return (await http.post('/v1/public/responses/current/submit', null, withToken(responseToken))).data
}
