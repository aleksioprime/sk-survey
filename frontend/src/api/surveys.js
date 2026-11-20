import { http } from 'sk-ui'

const get = async (url, config) => (await http.get(url, config)).data
const post = async (url, body) => (await http.post(url, body)).data
const put = async (url, body) => (await http.put(url, body)).data
const patch = async (url, body) => (await http.patch(url, body)).data

export const listSurveys = () => get('/v1/surveys', { params: { include_observed: true } })
export const createSurvey = (body) => post('/v1/surveys', body)
export const getSurvey = (id) => get(`/v1/surveys/${id}`)
export const updateSurvey = (id, body) => patch(`/v1/surveys/${id}`, body)
export const deleteSurvey = (id) => http.delete(`/v1/surveys/${id}`)
export const copySurvey = (id) => post(`/v1/surveys/${id}/copy`)
export const setSurveyAccess = (id, members, expectedUserIds) => put(
  `/v1/surveys/${id}/access`, { members, expected_user_ids: expectedUserIds },
)
export const reorder = (id, body) => put(`/v1/surveys/${id}/order`, body)

export const addSection = (surveyId, body) => post(`/v1/surveys/${surveyId}/sections`, body)
export const updateSection = (id, body) => patch(`/v1/sections/${id}`, body)
export const deleteSection = (id) => http.delete(`/v1/sections/${id}`)

export const addQuestion = (surveyId, body) => post(`/v1/surveys/${surveyId}/questions`, body)
export const updateQuestion = (id, body) => put(`/v1/questions/${id}`, body)
export const deleteQuestion = (id) => http.delete(`/v1/questions/${id}`)

export const listScales = (params) => get('/v1/scales', { params })
export const createScale = (body) => post('/v1/scales', body)
export const updateScale = (id, body) => put(`/v1/scales/${id}`, body)
export const deleteScale = (id) => http.delete(`/v1/scales/${id}`)

export const cabinetPublishings = (surveyId) => get('/v1/publishings', { params: { survey_id: surveyId } })
export const surveyPublishings = (surveyId) => get(`/v1/surveys/${surveyId}/publishings`)
export const createPublishing = (surveyId, body) => post(`/v1/surveys/${surveyId}/publishings`, body)
export const getPublishing = (id) => get(`/v1/publishings/${id}`)
export const updatePublishing = (id, body) => patch(`/v1/publishings/${id}`, body)
export const deletePublishing = (id) => http.delete(`/v1/publishings/${id}`)

export const getReportOptions = (id) => get(`/v1/publishings/${id}/report-options`)

function reportParams(includeInProgress, selection = {}, page) {
  const params = new URLSearchParams({ include_in_progress: String(includeInProgress) })
  for (const id of selection.publications || []) params.append('publication', id)
  for (const id of selection.options || []) params.append('option', id)
  if (page) params.set('page', page)
  return params
}

export const getResults = (id, includeInProgress = false, selection) =>
  get(`/v1/publishings/${id}/results`, { params: reportParams(includeInProgress, selection) })
export const getIndividualResponses = (id, includeInProgress, page, selection) =>
  get(`/v1/publishings/${id}/responses`, { params: reportParams(includeInProgress, selection, page) })
export const deleteIndividualResponse = (id, responseId) => http.delete(`/v1/publishings/${id}/responses/${responseId}`)

async function downloadExport(path, fallbackName, params) {
  const response = await http.get(path, { params, responseType: 'blob' })
  const encodedName = response.headers['content-disposition']?.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  const filename = encodedName ? decodeURIComponent(encodedName) : fallbackName
  const objectUrl = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

export const downloadResponseWord = (id, responseId) =>
  downloadExport(`/v1/publishings/${id}/responses/${responseId}/export.docx`, 'Анкета.docx')
export const downloadExcel = (id, includeInProgress = false, selection) =>
  downloadExport(`/v1/publishings/${id}/export.xlsx`, 'Результаты.xlsx', reportParams(includeInProgress, selection))

export const searchEmployees = (q, surveyId) => get('/v1/directory/employees', { params: { q, survey_id: surveyId } })
