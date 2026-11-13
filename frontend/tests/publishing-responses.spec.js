import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import * as api from '@/api/surveys'
import PublishingResultsView from '@/views/publishings/PublishingResultsView.vue'

vi.mock('@/api/surveys', () => ({
  deleteIndividualResponse: vi.fn(),
  getIndividualResponses: vi.fn(),
  getPublishing: vi.fn(),
  exportUrl: vi.fn(),
}))

const answer = { id: '9007199254740993', number: 1, submitted: true, answers: [] }
const list = (items) => ({ items, responses: items.length, in_progress: 0, page: 1, page_size: 20 })

async function openResults(canEdit) {
  vi.mocked(api.getPublishing).mockResolvedValue({ can_edit: canEdit, submitted_count: 1 })
  vi.mocked(api.getIndividualResponses).mockResolvedValue(list([answer]))
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/publishings/:id', component: PublishingResultsView }],
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
      expect(button(wrapper, 'Удалить ответ')).toBeUndefined()
    } finally {
      wrapper.unmount()
    }
  })
})
