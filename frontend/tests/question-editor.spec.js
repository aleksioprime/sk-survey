import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import QuestionEditor from '@/components/editor/QuestionEditor.vue'

const question = { text: 'Насколько понятно?', question_type: 'scale', options: [], ranges: [] }

describe('редактор вопроса', () => {
  it('вопрос со шкалой не сохраняется без выбранной шкалы', async () => {
    const wrapper = mount(QuestionEditor, { props: { question } })
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('save')).toBeUndefined()
    expect(wrapper.get('[role="alert"]').text()).toBe('Выберите шкалу')
    expect(wrapper.get('#q-scale').attributes('aria-invalid')).toBe('true')
  })

  it('сохраняет вопрос с выбранной шкалой', async () => {
    const wrapper = mount(QuestionEditor, { props: { question, scales: [{ id: 5, title: 'Согласие 1-5' }] } })
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('save')[0][0]).toMatchObject({ question_type: 'scale', scale_id: 5 })
  })
})
