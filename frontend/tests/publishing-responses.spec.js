import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import * as api from '@/api/surveys'
import PublishingResultsView from '@/views/publishings/PublishingResultsView.vue'

vi.mock('@/api/surveys', async (importOriginal) => ({
  ...await importOriginal(),
  deleteIndividualResponse: vi.fn(),
  getIndividualResponses: vi.fn(),
  getPublishing: vi.fn(),
  getResults: vi.fn(),
  getReportOptions: vi.fn(),
}))

const answer = { publishing_id: '5', id: '9007199254740993', number: 1, submitted: true, answers: [] }
const list = (items) => ({ items, responses: items.length, in_progress: 0, page: 1, page_size: 20 })

async function openResults(canEdit) {
  vi.mocked(api.getReportOptions).mockResolvedValue({
    publications: [{ id: '5', title: 'Весна' }, { id: '8', title: 'Осень' }],
    questions: [{ id: '9', text: 'Класс', options: [{ id: '91', title: 'Десятый' }, { id: '92', title: 'Девятый' }] }],
  })
  vi.mocked(api.getPublishing).mockResolvedValue({ can_edit: canEdit, submitted_count: 1 })
  vi.mocked(api.getIndividualResponses).mockResolvedValue(list([answer]))
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/publishings/:id', name: 'publishing', component: PublishingResultsView }],
  })
  await router.push('/publishings/5?view=responses')
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
      expect(wrapper.get('a[href$=".docx"]').attributes('href')).toBe(
        '/api/v1/publishings/5/responses/9007199254740993/export.docx',
      )
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
    await panel.get('input[value="91"]').setValue(true)
    vi.mocked(api.getIndividualResponses).mockResolvedValue(list([{ ...answer, publishing_id: '8' }]))
    await panel.trigger('submit')
    await flushPromises()
    const selection = { publications: ['8'], options: ['91'] }
    expect(api.getIndividualResponses).toHaveBeenLastCalledWith('5', false, 1, selection)
    expect(wrapper.get('h1').text()).toBe('Общая статистика')
    expect(wrapper.get('a[href$=".docx"]').attributes('href')).toContain('/publishings/8/')
    expect(wrapper.get('a[href*="export.xlsx"]').attributes('href')).toContain('publication=8&option=91')
    expect(wrapper.text()).toContain('Класс: Десятый')
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
