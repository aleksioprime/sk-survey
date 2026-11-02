import { describe, expect, it } from 'vitest'
import { htmlToText, textToHtml } from '@/utils/richText'
import { seededShuffle } from '@/utils/shuffle'

describe('richText', () => {
  it('абзацы туда и обратно, без HTML из ввода', () => {
    const html = textToHtml('Первый <b>абзац</b>\n\nВторой\nстрока')
    expect(html).toBe('<p>Первый &lt;b&gt;абзац&lt;/b&gt;</p><p>Второй<br>строка</p>')
    expect(htmlToText(html)).toBe('Первый <b>абзац</b>\n\nВторой\nстрока')
  })
})

describe('seededShuffle', () => {
  it('один и тот же порядок для одного прохождения', () => {
    const items = [1, 2, 3, 4, 5, 6]
    expect(seededShuffle(items, '123')).toEqual(seededShuffle(items, '123'))
    expect([...seededShuffle(items, '123')].sort()).toEqual(items)
  })
})
