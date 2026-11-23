import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import QuestionField from '@/components/questions/QuestionField.vue'

it('показывает поле для выбранного варианта и очищает уточнение при снятии выбора', async () => {
  const options = [{ id: 1, title: 'Другое', allows_text: true }, { id: 2, title: 'Готовый вариант' }]
  const wrapper = mount(QuestionField, {
    props: {
      question: { text: 'Что используете?', question_type: 'multiple_choice' },
      options,
      modelValue: { option_ids: [], option_texts: {} },
      'onUpdate:modelValue': (value) => wrapper.setProps({ modelValue: value }),
    },
  })
  const other = wrapper.findAll('input[type="checkbox"]')[0]
  expect(wrapper.find('input[maxlength="1000"]').exists()).toBe(false)
  await other.setValue(true)
  await wrapper.get('input[maxlength="1000"]').setValue('Свой инструмент')
  expect(wrapper.props('modelValue').option_texts).toEqual({ 1: 'Свой инструмент' })
  await other.setValue(false)
  expect(wrapper.find('input[maxlength="1000"]').exists()).toBe(false)
  expect(wrapper.props('modelValue').option_texts).toEqual({})
})
