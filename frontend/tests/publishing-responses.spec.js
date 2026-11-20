import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import * as api from '@/api/surveys'
import PublishingResultsView from '@/views/publishings/PublishingResultsView.vue'

vi.mock('@/api/surveys', async (importOriginal) => ({
  ...await importOriginal(),
  deleteIndividualResponse: vi.fn(),
  downloadExcel: vi.fn(),
  downloadResponseWord: vi.fn(),
  getIndividualResponses: vi.fn(),
  getPublishing: vi.fn(),
  getResults: vi.fn(),
  getReportOptions: vi.fn(),
}))

const answer = { publishing_id: '5', id: '9007199254740993', number: 1, submitted: true, answers: [] }
const list = (items) => ({ items, responses: items.length, in_progress: 0, page: 1, page_size: 20 })

async function openResults(canEdit, query = '?view=responses') {
  vi.mocked(api.getReportOptions).mockResolvedValue({
    publications: [{ id: '5', title: 'Весна' }, { id: '8', title: 'Осень' }],
    questions: [{
      id: '9', text: 'Подразделение',
      options: Array.from({ length: 20 }, (_, i) => ({ id: String(91 + i), title: `Отдел №${i + 1}` })),
    }],
  })
  vi.mocked(api.getPublishing).mockResolvedValue({ can_edit: canEdit, submitted_count: 1 })
  vi.mocked(api.getIndividualResponses).mockResolvedValue(list([answer]))
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/publishings/:id', name: 'publishing', component: PublishingResultsView }],
  })
  await router.push(`/publishings/5${query}`)
  const wrapper = mount(PublishingResultsView, {
    props: { id: '5' },
    global: { plugins: [router], stubs: { Teleport: true, UiBreadcrumbs: true } },
  })
  await flushPromises()
  return wrapper
}

function button(wrapper, label) {
  return wrapper.findAll('button').find((item) => item.text() === label)
}

describe('удаление ответа в результатах', () => {
  it('отправляет запрос только после подтверждения и обновляет список', async () => {
    vi.mocked(api.deleteIndividualResponse).mockClear().mockResolvedValue(undefined)
    const wrapper = await openResults(true)
    try {
      await button(wrapper, 'Удалить ответ').trigger('click')
      expect(wrapper.get('dialog').text()).toContain('Ответ № 1')
      await button(wrapper, 'Отмена').trigger('click')
      expect(wrapper.find('dialog').exists()).toBe(false)
      expect(api.deleteIndividualResponse).not.toHaveBeenCalled()

      await button(wrapper, 'Удалить ответ').trigger('click')
      vi.mocked(api.getIndividualResponses).mockResolvedValueOnce(list([]))
      await button(wrapper, 'Удалить').trigger('click')
      await flushPromises()
      expect(api.deleteIndividualResponse).toHaveBeenCalledExactlyOnceWith('5', answer.id)
      expect(wrapper.text()).toContain('Ответов: 0')
      expect(wrapper.text()).toContain('Ответов пока нет.')
    } finally {
      wrapper.unmount()
    }
  })

  it('не показывает кнопку удаления наблюдателю', async () => {
    const wrapper = await openResults(false)
    try {
      expect(wrapper.text()).toContain('Ответ 1')
      await button(wrapper, 'Скачать анкету в Word').trigger('click')
      expect(api.downloadResponseWord).toHaveBeenLastCalledWith('5', answer.id)
      expect(button(wrapper, 'Удалить ответ')).toBeUndefined()
    } finally {
      wrapper.unmount()
    }
  })
})

it('применяет выбор публикаций и вариантов к списку, сводке и Excel', async () => {
  const wrapper = await openResults(false)
  try {
    const panel = wrapper.get('form')
    await panel.get('input[value="8"]').setValue(true)
    await button(panel, 'Добавить фильтр').trigger('click')
    await panel.get('[role="combobox"]').trigger('click')
    await panel.get('[role="option"]:not([aria-disabled])').trigger('click')
    const departments = panel.get('#report-options-9[role="combobox"]')
    expect(departments.attributes('aria-expanded')).toBe('false')
    await departments.trigger('click')
    const search = panel.get('input[type="search"]')
    for (const name of ['Отдел №11', 'Отдел №19']) {
      await search.setValue(name)
      const matches = panel.findAll('[role="option"]')
      expect(matches.map((item) => item.text())).toEqual([name])
      await matches[0].trigger('click')
    }
    await search.trigger('keydown', { key: 'Escape' })
    vi.mocked(api.getIndividualResponses).mockResolvedValue(list([{ ...answer, publishing_id: '8' }]))
    await panel.trigger('submit')
    await flushPromises()
    const selection = { publications: ['8'], options: ['101', '109'] }
    expect(api.getIndividualResponses).toHaveBeenLastCalledWith('5', false, 1, selection)
    expect(wrapper.get('h1').text()).toBe('Общая статистика')
    await button(wrapper, 'Скачать анкету в Word').trigger('click')
    expect(api.downloadResponseWord).toHaveBeenLastCalledWith('8', answer.id)
    await button(wrapper, 'Скачать Excel').trigger('click')
    expect(api.downloadExcel).toHaveBeenLastCalledWith('5', false, selection)
    expect(wrapper.text()).toContain('Подразделение: Отдел №11, Отдел №19')
    vi.mocked(api.getResults).mockResolvedValue({ responses: 0, in_progress: 0, questions: [] })
    await button(wrapper, 'Сводка').trigger('click')
    await flushPromises()
    expect(api.getResults).toHaveBeenLastCalledWith('5', false, selection)
    expect(wrapper.text()).toContain('По выбранным условиям ответов нет.')
    await button(panel, 'Сбросить').trigger('click')
    await flushPromises()
    expect(api.getResults).toHaveBeenLastCalledWith('5', false, { publications: [], options: [] })
  } finally {
    wrapper.unmount()
  }
})

it('показывает пометку о скрытых вариантах только у вопроса с фильтром', async () => {
  const choice = { question_type: 'single_choice', answered: 2, skipped: 0, is_active: true, matrix_rows: [], ranking: [], texts: [] }
  vi.mocked(api.getResults).mockResolvedValue({
    responses: 2,
    in_progress: 0,
    questions: [
      {
        ...choice, question_id: 9, text: 'Подразделение', hidden_options_count: 18, options: [],
        comparison: {
          base: 0,
          options: [{ id: 109, title: 'Отдел №19', count: 0, percent: 0 }],
          excluded: [{ id: 101, title: 'Отдел №11', count: 2, percent: 100 }],
        },
      },
      {
        ...choice, question_id: 10, text: 'Понравилось?',
        options: [{ id: 62, title: 'Да', count: 2, percent: 100 }, { id: 63, title: 'Нет', count: 0, percent: 0 }],
      },
    ],
  })
  const wrapper = await openResults(false, '?option=101&option=109')
  try {
    const note = wrapper.findAll('p').filter((p) => p.text() === 'Остальные варианты скрыты фильтром.')
    expect(note).toHaveLength(1)
    expect(note[0].element.parentElement.textContent).toContain('Подразделение')
    expect(wrapper.text()).toContain('Отдел №11')
    expect(wrapper.text()).toContain('Отдел №19')
    expect(wrapper.findAll('span').map((item) => item.text())).toContain('Нет')
  } finally {
    wrapper.unmount()
  }
})


it('позволяет исключить исходную публикацию из отчёта', async () => {
  const wrapper = await openResults(false)
  try {
    const panel = wrapper.get('form')
    await panel.get('input[value="5"]').setValue(false)
    expect(button(panel, 'Применить').element.disabled).toBe(true)
    await panel.get('input[value="8"]').setValue(true)
    await panel.trigger('submit')
    await flushPromises()
    expect(wrapper.vm.$route.path).toBe('/publishings/8')
    expect(wrapper.vm.$route.query.view).toBe('responses')
    expect(wrapper.vm.$route.query.publication).toBeUndefined()
  } finally {
    wrapper.unmount()
  }
})
