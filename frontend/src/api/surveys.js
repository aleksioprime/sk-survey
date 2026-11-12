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

export const cabinetPublishings = (surveyId) => get('/v1/publishings', { params: { survey_id: surveyId } })
export const surveyPublishings = (surveyId) => get(`/v1/surveys/${surveyId}/publishings`)
export const createPublishing = (surveyId, body) => post(`/v1/surveys/${surveyId}/publishings`, body)
export const getPublishing = (id) => get(`/v1/publishings/${id}`)
export const updatePublishing = (id, body) => patch(`/v1/publishings/${id}`, body)
export const deletePublishing = (id) => http.delete(`/v1/publishings/${id}`)

export const getResults = (id, includeInProgress = false) =>
  get(`/v1/publishings/${id}/results`, { params: { include_in_progress: includeInProgress } })
export const exportUrl = (id, includeInProgress = false) =>
  `/api/v1/publishings/${id}/export.xlsx?include_in_progress=${includeInProgress}`

export const searchEmployees = (q, surveyId) => get('/v1/directory/employees', { params: { q, survey_id: surveyId } })
