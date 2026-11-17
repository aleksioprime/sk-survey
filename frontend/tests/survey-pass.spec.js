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

  it('восстанавливает дату и сохраняет ответ из однострочного поля', async () => {
    const survey = await api.fetchPublicSurvey('public')
    vi.mocked(api.fetchPublicSurvey).mockResolvedValueOnce({
      ...survey,
      questions: [
        { ...questions[0], question_type: 'date' },
        { ...questions[1], question_type: 'short_text' },
      ],
    })
    vi.mocked(api.fetchResponse).mockResolvedValueOnce({
      response_id: 42,
      status: 'in_progress',
      answers: [{ question_id: 1, date_value: '2024-02-29' }],
    })
    vi.mocked(api.saveAnswer).mockResolvedValueOnce({})
    vi.mocked(api.submitResponse).mockResolvedValueOnce({ status: 'submitted', thank_you_text: 'Спасибо!' })
    await openSurvey()
    expect(wrapper.get('article').text()).toContain('Вопрос 2?')
    await wrapper.findAll('button').find((button) => button.text() === 'Назад').trigger('click')
    expect(wrapper.get('input[type="date"]').element.value).toBe('2024-02-29')
    await wrapper.findAll('button').find((button) => button.text() === 'Далее').trigger('click')
    await wrapper.get('input[type="text"]').setValue('Учитель')
    await wrapper.findAll('button').find((button) => button.text() === 'Отправить ответы').trigger('click')
    await flushPromises()
    expect(api.saveAnswer).toHaveBeenCalledWith('draft', 2, expect.objectContaining({ text_value: 'Учитель' }))
    expect(wrapper.text()).toContain('Ответы отправлены')
  })

  it('сохраняет переносы при наборе развёрнутого ответа', async () => {
    const survey = await api.fetchPublicSurvey('public')
    vi.mocked(api.fetchPublicSurvey).mockResolvedValueOnce({
      ...survey,
      questions: [{ ...questions[0], question_type: 'rich_text' }],
    })
    vi.mocked(api.fetchResponse).mockResolvedValueOnce({
      response_id: 42,
      status: 'in_progress',
      answers: [{ question_id: 1, rich_text_value: '<p>Первая строка</p>' }],
    })
    vi.mocked(api.saveAnswer).mockResolvedValueOnce({})
    vi.mocked(api.submitResponse).mockResolvedValueOnce({ status: 'submitted', thank_you_text: 'Спасибо!' })

    await openSurvey()
    const field = wrapper.get('textarea')
    await field.setValue('Первая строка\n')
    expect(field.element.value).toBe('Первая строка\n')
    await field.setValue('Первая строка\nВторая строка\n\n')
    expect(field.element.value).toBe('Первая строка\nВторая строка\n\n')
    await field.setValue('Первая строка\nВторая строка\n\nНовый абзац')
    await wrapper.findAll('button').find((button) => button.text() === 'Отправить ответы').trigger('click')
    await flushPromises()
    expect(api.saveAnswer).toHaveBeenCalledWith('draft', 1, expect.objectContaining({
      rich_text_value: '<p>Первая строка<br>Вторая строка</p><p>Новый абзац</p>',
    }))
  })

  it('находит вариант в выпадающем списке и сохраняет его как одиночный выбор', async () => {
    const survey = await api.fetchPublicSurvey('public')
    vi.mocked(api.fetchPublicSurvey).mockResolvedValueOnce({
      ...survey,
      questions: [{
        ...questions[0],
        question_type: 'single_choice',
        is_dropdown: true,
        options: Array.from({ length: 10 }, (_, i) => ({ id: i + 10, title: `Подразделение ${i + 1}` })),
      }],
    })
    vi.mocked(api.fetchResponse).mockResolvedValueOnce({
      response_id: 42,
      status: 'in_progress',
      answers: [{ question_id: 1, option_id: 10 }],
    })
    vi.mocked(api.saveAnswer).mockResolvedValueOnce({})
    vi.mocked(api.submitResponse).mockResolvedValueOnce({ status: 'submitted', thank_you_text: 'Спасибо!' })

    await openSurvey()
    const dropdown = wrapper.get('[role="combobox"]')
    await dropdown.trigger('click')
    expect(document.querySelector('[role="option"][aria-selected="true"]').textContent).toContain('Подразделение 1')
    const search = document.querySelector('input[type="search"]')
    search.value = 'Подразделение 8'
    search.dispatchEvent(new Event('input'))
    await flushPromises()
    const matches = document.querySelectorAll('[role="option"]')
    expect(matches).toHaveLength(1)
    matches[0].click()
    await wrapper.findAll('button').find((button) => button.text() === 'Отправить ответы').trigger('click')
    await flushPromises()
    expect(api.saveAnswer).toHaveBeenCalledWith('draft', 1, expect.objectContaining({ option_id: 17 }))
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
    expect(api.savedResponseToken('public')).toBe('draft')
  })

  it('после удаления отправленной попытки позволяет начать заново', async () => {
    vi.mocked(api.fetchResponse).mockResolvedValueOnce({ response_id: 42, status: 'submitted', answers: [] })
    await openSurvey()
    expect(wrapper.text()).toContain('Ответы отправлены')
    wrapper.unmount()

    vi.mocked(api.fetchResponse).mockRejectedValueOnce({ response: { status: 401 } })
    vi.mocked(api.startResponse).mockResolvedValueOnce({
      response_id: 43, response_token: 'new-draft', status: 'in_progress', answers: [],
    })
    await openSurvey()
    expect(wrapper.text()).toContain('Вступление')
    expect(api.savedResponseToken('public')).toBeNull()
    await wrapper.findAll('button').find((button) => button.text() === 'Начать').trigger('click')
    await flushPromises()
    expect(wrapper.get('article').text()).toContain('Вопрос 1?')
    expect(api.savedResponseToken('public')).toBe('new-draft')
  })

  it('не использует старую отметку без ключа попытки', async () => {
    api.forgetResponseToken('public')
    localStorage.setItem('sks-completed:public', 'yes')
    await openSurvey()
    expect(wrapper.text()).toContain('Вступление')
    expect(wrapper.text()).not.toContain('Ответы отправлены')
  })

  it('сохраняет ключ после отправки анонимной попытки', async () => {
    const survey = await api.fetchPublicSurvey('public')
    vi.mocked(api.fetchPublicSurvey).mockResolvedValueOnce({ ...survey, questions: [questions[0]] })
    vi.mocked(api.submitResponse).mockResolvedValueOnce({ status: 'submitted', thank_you_text: 'Спасибо!' })
    await openSurvey()
    await wrapper.findAll('button').find((button) => button.text() === 'Отправить ответы').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Ответы отправлены')
    expect(api.savedResponseToken('public')).toBe('draft')
  })
})
