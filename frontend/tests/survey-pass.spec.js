import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '@/api/public'
import SurveyPassView from '@/views/public/SurveyPassView.vue'

vi.mock('vue-router', () => ({ useRoute: () => ({ fullPath: '/s/public' }) }))
vi.mock('@/api/public', { spy: true })

const questions = [1, 2, 3].map((id) => ({
  id,
  text: `Вопрос ${id}?`,
  question_type: 'text',
  is_required: true,
  section_id: null,
  options: [],
}))

describe('возобновление опроса', () => {
  let wrapper
  let scrollIntoView

  beforeEach(() => {
    localStorage.clear()
    vi.mocked(api.fetchPublicSurvey).mockResolvedValue({
      title: 'Опрос',
      intro_text: 'Вступление',
      thank_you_text: 'Спасибо!',
      is_anonymous: true,
      questions,
      sections: [],
      one_question_per_page: true,
    })
    vi.mocked(api.fetchResponse).mockResolvedValue({
      response_id: 42,
      status: 'in_progress',
      answers: [{ question_id: 1, text_value: 'Ответ' }],
    })
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
    scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    api.rememberResponseToken('public', 'draft')
  })

  afterEach(() => {
    wrapper?.unmount()
    delete Element.prototype.scrollIntoView
    vi.restoreAllMocks()
  })

  async function openSurvey() {
    wrapper = mount(SurveyPassView, {
      attachTo: document.body,
      props: { token: 'public' },
      global: { stubs: { SchoolFooter: true } },
    })
    await flushPromises()
  }

  it.each([true, false])('пропускает вступление для старого черновика (анонимный: %s)', async (isAnonymous) => {
    const survey = await api.fetchPublicSurvey('public')
    vi.mocked(api.fetchPublicSurvey).mockResolvedValue({ ...survey, is_anonymous: isAnonymous })
    await openSurvey()
    expect(wrapper.text()).not.toContain('Вступление')
    expect(wrapper.get('article').text()).toContain('Вопрос 2?')
  })

  it('возвращает к частично заполненной матрице без сохранённой позиции', async () => {
    const survey = await api.fetchPublicSurvey('public')
    vi.mocked(api.fetchPublicSurvey).mockResolvedValue({
      ...survey,
      questions: [
        questions[0],
        {
          ...questions[1],
          question_type: 'matrix_single',
          matrix_rows: [{ id: 'a', title: 'Строка А' }, { id: 'b', title: 'Строка Б' }],
          options: [{ id: 10, title: 'Да' }, { id: 11, title: 'Нет' }],
        },
        questions[2],
      ],
    })
    vi.mocked(api.fetchResponse).mockResolvedValue({
      response_id: 42,
      status: 'in_progress',
      answers: [{ question_id: 1, text_value: 'Ответ' }, { question_id: 2, matrix_choices: { a: [10] } }],
    })
    await openSurvey()
    expect(wrapper.get('article').text()).toContain('Вопрос 2?')
    expect(wrapper.findAll('input:checked')).toHaveLength(1)
  })

  it('восстанавливает страницу после возврата назад', async () => {
    await openSurvey()
    await wrapper.findAll('button').find((button) => button.text() === 'Назад').trigger('click')
    wrapper.unmount()
    await openSurvey()
    expect(wrapper.get('article').text()).toContain('Вопрос 1?')
    expect(wrapper.get('textarea').element.value).toBe('Ответ')
  })

  it('прокручивает страницу с несколькими вопросами к месту остановки', async () => {
    const survey = await api.fetchPublicSurvey('public')
    vi.mocked(api.fetchPublicSurvey).mockResolvedValue({ ...survey, one_question_per_page: false })
    api.rememberQuestion(42, 3)
    await openSurvey()
    expect(scrollIntoView.mock.contexts).toEqual([wrapper.get('#survey-question-3').element])
  })

  it('показывает вступление, если сохранилась только пустая запись', async () => {
    vi.mocked(api.fetchResponse).mockResolvedValue({
      response_id: 42,
      status: 'in_progress',
      answers: [{ question_id: 1, text_value: null }],
    })
    await openSurvey()
    expect(wrapper.text()).toContain('Вступление')
  })

  it('показывает подтверждение для отправленного прохождения', async () => {
    vi.mocked(api.fetchResponse).mockResolvedValue({ response_id: 42, status: 'submitted', answers: [] })
    await openSurvey()
    expect(wrapper.text()).toContain('Ответы отправлены')
    expect(api.hasCompleted('public')).toBe(true)
  })
})
