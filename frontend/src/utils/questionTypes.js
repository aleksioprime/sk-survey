export const MATRIX_TYPES = ['matrix_single', 'matrix_multiple']

export const TEXT_LIST = 'text_list'
export const TEXT_LIST_MAX_ROWS = 50
export const TEXT_LIST_ROW_LENGTH = 500

export function countTextRows(rows = []) {
  return rows.filter((row) => row.trim()).length
}

export function textListError(question, answer) {
  const count = answer?.is_skipped ? 0 : countTextRows(answer?.text_rows)
  const min = question.min_rows ?? 1
  const max = question.max_rows ?? TEXT_LIST_MAX_ROWS
  if ((question.is_required || count) && count < min) return `Минимум заполненных строк: ${min}`
  if (count > max) return `Максимум заполненных строк: ${max}`
  return ''
}

export const QUESTION_TYPES = {
  single_choice: 'Один вариант',
  multiple_choice: 'Несколько вариантов',
  matrix_single: 'Матрица: один вариант в строке',
  matrix_multiple: 'Матрица: несколько вариантов в строке',
  scale: 'Шкала',
  text: 'Текст',
  [TEXT_LIST]: 'Список текстовых ответов',
  rich_text: 'Развёрнутый текст',
  number: 'Число',
  yes_no: 'Да / Нет',
  ranking: 'Расставить по порядку',
}
