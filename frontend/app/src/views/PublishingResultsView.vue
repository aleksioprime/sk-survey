<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import nocobaseApi from '@/api/nocobase'
import { useAuthStore } from '@/stores/auth'
import { canUserViewPublishing } from '@/utils/publishingAccess'

const props = defineProps({
  publishingId: {
    type: [String, Number],
    required: true,
  },
})
const auth = useAuthStore()

const MAX_TEXT_ANSWERS_PREVIEW = 200

const loading = ref(true)
const error = ref('')
const statusFilter = ref('submitted')
const activeTab = ref('summary')
const expandedTextQuestions = ref({})
const exporting = ref(false)
const exportError = ref('')
let XLSX = null

const EXCEL_THIN_BORDER = {
  top: { style: 'thin', color: { rgb: '1F2937' } },
  right: { style: 'thin', color: { rgb: '1F2937' } },
  bottom: { style: 'thin', color: { rgb: '1F2937' } },
  left: { style: 'thin', color: { rgb: '1F2937' } },
}

const publishing = ref(null)
const sections = ref([])
const questions = ref([])
const options = ref([])
const scaleItems = ref([])
const responses = ref([])
const answers = ref([])
const rankingItems = ref([])

const statusOptions = [
  { value: 'submitted', label: 'Только отправленные' },
  { value: 'in_progress', label: 'Только в процессе' },
  { value: 'all', label: 'Все статусы' },
]

const hasSections = computed(() => sections.value.length > 0)

const sectionGroups = computed(() => {
  const bySection = new Map()

  for (const section of sections.value) {
    bySection.set(section.id, {
      id: section.id,
      title: section.title || `Раздел #${section.id}`,
      questions: [],
    })
  }

  const unsectioned = {
    id: 'without-section',
    title: hasSections.value ? 'Без раздела' : '',
    questions: [],
  }

  for (const question of questions.value) {
    if (question.section_id && bySection.has(question.section_id)) {
      bySection.get(question.section_id).questions.push(question)
      continue
    }
    unsectioned.questions.push(question)
  }

  const groups = Array.from(bySection.values())
  if (unsectioned.questions.length) {
    groups.push(unsectioned)
  }

  return groups.filter((group) => group.questions.length > 0)
})

const optionTitleById = computed(() => {
  const map = {}
  for (const option of options.value) {
    if (option?.id != null) {
      map[Number(option.id)] = option.title || option.value || `Вариант #${option.id}`
    }
  }
  return map
})

const scaleItemTitleById = computed(() => {
  const map = {}
  for (const item of scaleItems.value) {
    if (item?.id != null) {
      map[Number(item.id)] = item.title || item.value || `Пункт шкалы #${item.id}`
    }
  }
  return map
})

const answerByResponseAndQuestion = computed(() => {
  const map = {}
  for (const answer of answers.value) {
    const responseId = Number(answer?.response_id)
    const questionId = Number(answer?.question_id)
    if (!responseId || !questionId) continue

    if (!map[responseId]) {
      map[responseId] = {}
    }
    map[responseId][questionId] = answer
  }
  return map
})

const rankingByAnswerId = computed(() => {
  const map = {}
  for (const row of rankingItems.value) {
    const answerId = Number(row?.answer_id)
    if (!answerId) continue

    if (!map[answerId]) {
      map[answerId] = []
    }
    map[answerId].push(row)
  }

  for (const answerId of Object.keys(map)) {
    map[answerId].sort((a, b) => Number(a?.rank || 0) - Number(b?.rank || 0))
  }

  return map
})

function formatDate(value) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString('ru-RU')
  } catch {
    return '—'
  }
}

function formatPercent(value) {
  return `${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}%`
}

function getUserLabel(response) {
  if (response?.user?.nickname) return response.user.nickname
  if (response?.user?.email) return response.user.email
  if (response?.user_id) return `Пользователь #${response.user_id}`

  if (publishing.value?.is_anonymous) {
    return `Аноним (${String(response?.token || '').slice(0, 8)}...)`
  }

  return 'Пользователь не указан'
}

function normalizeRichText(value) {
  return String(value || '')
    .replace(/<br\s*\/?\s*>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+\n/g, '\n')
    .replace(/\n\s+/g, '\n')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function resolveOptionTitle(optionLike) {
  const optionId = Number(optionLike?.id || optionLike?.option_id || optionLike)
  if (!optionId) return null
  return optionTitleById.value[optionId] || `Вариант #${optionId}`
}

function getAnswerForResponse(responseId, questionId) {
  return answerByResponseAndQuestion.value[Number(responseId)]?.[Number(questionId)] || null
}

function resolveAnswer(question, answer) {
  if (!answer) {
    return { type: 'empty', text: 'Нет ответа' }
  }

  if (answer.is_skipped) {
    return { type: 'empty', text: 'Пропущен' }
  }

  switch (question.question_type) {
    case 'text': {
      const value = String(answer.text_value || '').trim()
      return value ? { type: 'text', text: value } : { type: 'empty', text: 'Нет ответа' }
    }
    case 'rich_text': {
      const value = normalizeRichText(answer.rich_text_value)
      return value ? { type: 'text', text: value } : { type: 'empty', text: 'Нет ответа' }
    }
    case 'number':
      return answer.number_value != null
        ? { type: 'text', text: String(answer.number_value) }
        : { type: 'empty', text: 'Нет ответа' }
    case 'yes_no':
      return answer.boolean_value != null
        ? { type: 'text', text: answer.boolean_value ? 'Да' : 'Нет' }
        : { type: 'empty', text: 'Нет ответа' }
    case 'single_choice': {
      const optionTitle = resolveOptionTitle(answer.option || answer.option_id)
      return optionTitle
        ? { type: 'text', text: optionTitle }
        : { type: 'empty', text: 'Нет ответа' }
    }
    case 'multiple_choice': {
      const values = (answer.options || [])
        .map((option) => resolveOptionTitle(option))
        .filter(Boolean)
      return values.length
        ? { type: 'list', items: values }
        : { type: 'empty', text: 'Нет ответа' }
    }
    case 'scale': {
      if (question?.scale?.scale_type === 'generated') {
        return answer.number_value != null
          ? { type: 'text', text: String(answer.number_value) }
          : { type: 'empty', text: 'Нет ответа' }
      }

      const scaleItemId = Number(answer.scale_item?.id || answer.scale_item_id)
      const title = scaleItemId ? scaleItemTitleById.value[scaleItemId] : null
      return title
        ? { type: 'text', text: title }
        : { type: 'empty', text: 'Нет ответа' }
    }
    case 'ranking': {
      const rows = rankingByAnswerId.value[Number(answer.id)] || []
      const items = rows
        .map((row, index) => {
          const title = resolveOptionTitle(row.option || row.option_id)
          if (!title) return null
          return `${index + 1}. ${title}`
        })
        .filter(Boolean)

      return items.length
        ? { type: 'list', items }
        : { type: 'empty', text: 'Нет ответа' }
    }
    default:
      return { type: 'empty', text: 'Нет ответа' }
  }
}

const resolvedAnswerMap = computed(() => {
  const map = {}

  for (const response of responses.value) {
    const responseId = Number(response?.id)
    if (!responseId) continue

    for (const question of questions.value) {
      const questionId = Number(question?.id)
      if (!questionId) continue

      map[`${responseId}:${questionId}`] = resolveAnswer(
        question,
        getAnswerForResponse(responseId, questionId),
      )
    }
  }

  return map
})

function getResolvedAnswer(responseId, questionId) {
  const key = `${Number(responseId)}:${Number(questionId)}`
  return resolvedAnswerMap.value[key] || { type: 'empty', text: 'Нет ответа' }
}

function getSingleOptionId(answer) {
  return Number(answer?.option_id || answer?.option?.id || 0) || null
}

function getScaleItemId(answer) {
  return Number(answer?.scale_item_id || answer?.scale_item?.id || 0) || null
}

function toTextAnswer(question, answer) {
  if (question.question_type === 'text') {
    const text = String(answer?.text_value || '').trim()
    return text || null
  }

  if (question.question_type === 'rich_text') {
    const text = normalizeRichText(answer?.rich_text_value)
    return text || null
  }

  if (question.question_type === 'number') {
    return answer?.number_value != null ? String(answer.number_value) : null
  }

  if (question.question_type === 'scale' && question?.scale?.scale_type === 'generated') {
    return answer?.number_value != null ? String(answer.number_value) : null
  }

  return null
}

function buildDistributionRows(counter, answeredCount) {
  const rows = []

  for (const [label, count] of counter.entries()) {
    const percent = answeredCount > 0
      ? Math.round((Number(count) / Number(answeredCount)) * 1000) / 10
      : 0

    rows.push({
      label,
      count,
      percent,
    })
  }

  rows.sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count
    return String(a.label).localeCompare(String(b.label), 'ru')
  })

  return rows
}

function normalizeNumericValue(value) {
  return Math.round(Number(value) * 1000000) / 1000000
}

function formatNumericLabel(value) {
  return Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 6 })
}

function uniqueSortedNumeric(values) {
  const unique = [...new Set(values.map((value) => normalizeNumericValue(value)))]
  unique.sort((a, b) => a - b)
  return unique
}

function getGeneratedScalePossibleValues(question, observedValues) {
  const minValue = Number(question?.scale?.min_value)
  const maxValue = Number(question?.scale?.max_value)
  const step = Number(question?.scale?.step)

  if (
    Number.isNaN(minValue)
    || Number.isNaN(maxValue)
    || Number.isNaN(step)
    || step <= 0
    || maxValue < minValue
  ) {
    return uniqueSortedNumeric(observedValues)
  }

  const maxSteps = Math.floor((maxValue - minValue) / step + 0.000001)
  if (maxSteps > 1000) {
    return uniqueSortedNumeric(observedValues)
  }

  const values = []
  for (let i = 0; i <= maxSteps; i++) {
    values.push(normalizeNumericValue(minValue + (step * i)))
  }

  const normalizedMax = normalizeNumericValue(maxValue)
  if (values[values.length - 1] !== normalizedMax) {
    values.push(normalizedMax)
  }

  return values
}

function buildNumericDistributionRows(question, rawValues) {
  const counts = new Map()
  for (const value of rawValues) {
    const normalized = normalizeNumericValue(value)
    counts.set(normalized, (counts.get(normalized) || 0) + 1)
  }

  const possibleValues = (question.question_type === 'scale' && question?.scale?.scale_type === 'generated')
    ? getGeneratedScalePossibleValues(question, rawValues)
    : uniqueSortedNumeric(rawValues)

  return possibleValues.map((value) => {
    const count = counts.get(value) || 0
    const percent = rawValues.length > 0
      ? Math.round((count / rawValues.length) * 1000) / 10
      : 0

    return {
      value,
      label: formatNumericLabel(value),
      count,
      percent,
    }
  })
}

const summaryByQuestion = computed(() => {
  const result = {}

  for (const question of questions.value) {
    const answeredResponses = []

    for (const response of responses.value) {
      const answer = getAnswerForResponse(response.id, question.id)
      if (!answer || answer.is_skipped) continue
      answeredResponses.push({ response, answer })
    }

    const totalResponses = responses.value.length
    const answeredCount = answeredResponses.length

    if (!answeredCount) {
      result[question.id] = {
        kind: 'empty',
        answeredCount: 0,
        totalResponses,
      }
      continue
    }

    if (['text', 'rich_text'].includes(question.question_type)) {
      const values = answeredResponses
        .map(({ answer }) => toTextAnswer(question, answer))
        .filter(Boolean)

      result[question.id] = {
        kind: values.length ? 'text-list' : 'empty',
        answeredCount: values.length,
        totalResponses,
        values,
      }
      continue
    }

    if (question.question_type === 'number' || (question.question_type === 'scale' && question?.scale?.scale_type === 'generated')) {
      const rawValues = answeredResponses
        .map(({ answer }) => Number(answer?.number_value))
        .filter((value) => !Number.isNaN(value))

      if (!rawValues.length) {
        result[question.id] = {
          kind: 'empty',
          answeredCount: 0,
          totalResponses,
        }
        continue
      }

      const sum = rawValues.reduce((acc, value) => acc + value, 0)
      const avg = sum / rawValues.length
      const min = Math.min(...rawValues)
      const max = Math.max(...rawValues)

      result[question.id] = {
        kind: 'number-stats',
        answeredCount: rawValues.length,
        totalResponses,
        avg,
        min,
        max,
        rows: buildNumericDistributionRows(question, rawValues),
      }
      continue
    }

    if (question.question_type === 'yes_no') {
      const counter = new Map([
        ['Да', 0],
        ['Нет', 0],
      ])

      for (const { answer } of answeredResponses) {
        if (answer?.boolean_value === true) {
          counter.set('Да', (counter.get('Да') || 0) + 1)
        } else if (answer?.boolean_value === false) {
          counter.set('Нет', (counter.get('Нет') || 0) + 1)
        }
      }

      result[question.id] = {
        kind: 'distribution',
        answeredCount,
        totalResponses,
        rows: buildDistributionRows(counter, answeredCount),
      }
      continue
    }

    if (question.question_type === 'single_choice') {
      const counter = new Map()

      for (const { answer } of answeredResponses) {
        const optionId = getSingleOptionId(answer)
        if (!optionId) continue
        const label = optionTitleById.value[optionId] || `Вариант #${optionId}`
        counter.set(label, (counter.get(label) || 0) + 1)
      }

      result[question.id] = {
        kind: 'distribution',
        answeredCount,
        totalResponses,
        rows: buildDistributionRows(counter, answeredCount),
      }
      continue
    }

    if (question.question_type === 'multiple_choice') {
      const counter = new Map()

      for (const { answer } of answeredResponses) {
        const selected = Array.isArray(answer?.options) ? answer.options : []
        for (const option of selected) {
          const optionId = Number(option?.id)
          if (!optionId) continue
          const label = optionTitleById.value[optionId] || `Вариант #${optionId}`
          counter.set(label, (counter.get(label) || 0) + 1)
        }
      }

      result[question.id] = {
        kind: 'distribution',
        answeredCount,
        totalResponses,
        rows: buildDistributionRows(counter, answeredCount),
      }
      continue
    }

    if (question.question_type === 'scale') {
      const counter = new Map()

      for (const { answer } of answeredResponses) {
        const scaleItemId = getScaleItemId(answer)
        if (!scaleItemId) continue
        const label = scaleItemTitleById.value[scaleItemId] || `Пункт шкалы #${scaleItemId}`
        counter.set(label, (counter.get(label) || 0) + 1)
      }

      result[question.id] = {
        kind: 'distribution',
        answeredCount,
        totalResponses,
        rows: buildDistributionRows(counter, answeredCount),
      }
      continue
    }

    if (question.question_type === 'ranking') {
      const counter = new Map()
      let firstPlaceCount = 0

      for (const { answer } of answeredResponses) {
        const rows = rankingByAnswerId.value[Number(answer.id)] || []
        if (!rows.length) continue

        const first = rows.find((row) => Number(row?.rank) === 1) || rows[0]
        const optionId = Number(first?.option_id || first?.option?.id)
        if (!optionId) continue

        const label = optionTitleById.value[optionId] || `Вариант #${optionId}`
        counter.set(label, (counter.get(label) || 0) + 1)
        firstPlaceCount += 1
      }

      result[question.id] = {
        kind: 'distribution',
        answeredCount: firstPlaceCount,
        totalResponses,
        distributionLabel: 'Распределение 1-го места',
        rows: buildDistributionRows(counter, firstPlaceCount),
      }
      continue
    }

    result[question.id] = {
      kind: 'empty',
      answeredCount: 0,
      totalResponses,
    }
  }

  return result
})

function getQuestionSummary(questionId) {
  return summaryByQuestion.value[Number(questionId)] || {
    kind: 'empty',
    answeredCount: 0,
    totalResponses: responses.value.length,
  }
}

function getPreviewTextAnswers(summary) {
  if (!summary?.values?.length) return []
  return summary.values.slice(0, MAX_TEXT_ANSWERS_PREVIEW)
}

function getHiddenTextAnswersCount(summary) {
  const total = summary?.values?.length || 0
  return Math.max(total - MAX_TEXT_ANSWERS_PREVIEW, 0)
}

function isTextAnswersExpanded(questionId) {
  return expandedTextQuestions.value[Number(questionId)] === true
}

function toggleTextAnswers(questionId) {
  const key = Number(questionId)
  expandedTextQuestions.value = {
    ...expandedTextQuestions.value,
    [key]: !isTextAnswersExpanded(key),
  }
}

function sanitizeFilePart(value) {
  return String(value || '')
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

async function loadXlsxLibrary() {
  if (XLSX) return XLSX
  const mod = await import('xlsx-js-style')
  XLSX = mod
  return XLSX
}

function sanitizeSheetName(value) {
  const cleaned = String(value || '')
    .replace(/[:\\/?*\[\]]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  return (cleaned || 'Лист').slice(0, 31)
}

function makeUniqueSheetName(baseName, usedNames) {
  const base = sanitizeSheetName(baseName)
  if (!usedNames.has(base)) {
    usedNames.add(base)
    return base
  }

  for (let i = 2; i < 1000; i++) {
    const suffix = ` (${i})`
    const candidate = base.slice(0, Math.max(1, 31 - suffix.length)) + suffix
    if (!usedNames.has(candidate)) {
      usedNames.add(candidate)
      return candidate
    }
  }

  const fallback = `Лист ${usedNames.size + 1}`.slice(0, 31)
  usedNames.add(fallback)
  return fallback
}

function computeColumnWidths(aoa, minWidth = 10, maxWidth = 80) {
  const totalCols = aoa.reduce((max, row) => Math.max(max, Array.isArray(row) ? row.length : 0), 0)
  const widths = Array.from({ length: totalCols }, () => minWidth)

  for (const row of aoa) {
    if (!Array.isArray(row)) continue

    for (let i = 0; i < totalCols; i++) {
      const value = row[i]
      const text = value == null ? '' : String(value)
      const lineMax = text
        .split('\n')
        .reduce((max, line) => Math.max(max, line.length), 0)

      widths[i] = Math.min(maxWidth, Math.max(widths[i], lineMax + 2))
    }
  }

  return widths.map((wch) => ({ wch }))
}

function setAutoFilter(sheet, rowCount, colCount) {
  if (!sheet || rowCount < 1 || colCount < 1) return
  const endCol = XLSX.utils.encode_col(colCount - 1)
  sheet['!autofilter'] = { ref: `A1:${endCol}${rowCount}` }
}

function setTableAutoFilter(sheet, headerRowIndexZeroBased, totalRows, colCount) {
  if (!sheet || totalRows < 1 || colCount < 1) return
  const start = { r: headerRowIndexZeroBased, c: 0 }
  const end = { r: totalRows - 1, c: colCount - 1 }
  sheet['!autofilter'] = { ref: XLSX.utils.encode_range({ s: start, e: end }) }
}

function buildCellStyle({ header = false, bordered = false, wrap = true } = {}) {
  return {
    font: {
      name: 'Calibri',
      sz: 11,
      bold: header,
    },
    alignment: {
      vertical: 'top',
      wrapText: wrap,
    },
    fill: header
      ? {
        patternType: 'solid',
        fgColor: { rgb: 'E9F6F3' },
      }
      : undefined,
    border: bordered ? EXCEL_THIN_BORDER : undefined,
  }
}

function ensureCell(sheet, rowIndex, colIndex) {
  const address = XLSX.utils.encode_cell({ r: rowIndex, c: colIndex })
  if (!sheet[address]) {
    sheet[address] = { t: 's', v: '' }
  }
  return sheet[address]
}

function applyStyleRange(
  sheet,
  startRow,
  endRow,
  startCol,
  endCol,
  styleFactory,
) {
  for (let r = startRow; r <= endRow; r++) {
    for (let c = startCol; c <= endCol; c++) {
      const cell = ensureCell(sheet, r, c)
      cell.s = styleFactory(r, c)
    }
  }
}

function applyBorderedTableStyle(sheet, headerRow, dataStartRow, dataEndRow, colCount) {
  if (!sheet || colCount < 1) return

  applyStyleRange(sheet, headerRow, headerRow, 0, colCount - 1, () => (
    buildCellStyle({ header: true, bordered: true, wrap: true })
  ))

  if (dataEndRow >= dataStartRow) {
    applyStyleRange(sheet, dataStartRow, dataEndRow, 0, colCount - 1, () => (
      buildCellStyle({ header: false, bordered: true, wrap: true })
    ))
  }
}

function applyBorderToNonEmptyCells(sheet, aoa, colCount) {
  if (!sheet || !Array.isArray(aoa) || colCount < 1) return

  for (let r = 0; r < aoa.length; r++) {
    const row = Array.isArray(aoa[r]) ? aoa[r] : []
    for (let c = 0; c < colCount; c++) {
      const value = row[c]
      if (value == null || String(value).trim() === '') continue

      const cell = ensureCell(sheet, r, c)
      cell.s = {
        ...(cell.s || {}),
        border: EXCEL_THIN_BORDER,
      }
    }
  }
}

function wrapAndTrimExcelText(value, { maxChars = 1200, maxLine = 80 } = {}) {
  let text = value == null ? '' : String(value)
  text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim()

  if (text.length > maxChars) {
    text = `${text.slice(0, Math.max(0, maxChars - 1)).trimEnd()}…`
  }

  const wrappedLines = []
  for (const sourceLine of text.split('\n')) {
    let line = sourceLine.trim()
    if (!line) {
      wrappedLines.push('')
      continue
    }

    while (line.length > maxLine) {
      let cut = line.lastIndexOf(' ', maxLine)
      if (cut < Math.floor(maxLine * 0.5)) cut = maxLine
      wrappedLines.push(line.slice(0, cut).trimEnd())
      line = line.slice(cut).trimStart()
    }

    wrappedLines.push(line)
  }

  return wrappedLines.join('\n')
}

function getQuestionOptions(questionId) {
  return options.value
    .filter((option) => Number(option?.question_id) === Number(questionId))
    .slice()
    .sort((a, b) => {
      const orderA = Number(a?.order ?? Number.MAX_SAFE_INTEGER)
      const orderB = Number(b?.order ?? Number.MAX_SAFE_INTEGER)
      if (orderA !== orderB) return orderA - orderB
      return Number(a?.id || 0) - Number(b?.id || 0)
    })
}

function formatAnswerForExport(question, answer) {
  if (!question || !answer || answer.is_skipped) return ''

  switch (question.question_type) {
    case 'text':
      return wrapAndTrimExcelText(answer?.text_value, { maxChars: 1600, maxLine: 90 })
    case 'rich_text':
      return wrapAndTrimExcelText(normalizeRichText(answer?.rich_text_value), { maxChars: 1600, maxLine: 90 })
    case 'number':
      return answer?.number_value ?? ''
    case 'yes_no':
      return answer?.boolean_value == null ? '' : (answer.boolean_value ? 'Да' : 'Нет')
    case 'single_choice': {
      const title = resolveOptionTitle(answer.option || answer.option_id)
      return title || ''
    }
    case 'multiple_choice': {
      const values = (answer.options || [])
        .map((option) => resolveOptionTitle(option))
        .filter(Boolean)
      return wrapAndTrimExcelText(values.join('; '), { maxChars: 800, maxLine: 80 })
    }
    case 'scale': {
      if (question?.scale?.scale_type === 'generated') {
        return answer?.number_value ?? ''
      }
      const scaleItemId = Number(answer?.scale_item?.id || answer?.scale_item_id || 0)
      return scaleItemTitleById.value[scaleItemId] || ''
    }
    default:
      return ''
  }
}

function buildExportFileName(suffix) {
  const title = sanitizeFilePart(publishing.value?.title || publishing.value?.survey?.title || 'Публикация')
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
  return `${title}_${suffix}_${timestamp}.xlsx`
}

function exportResponsesToExcel() {
  const questionById = new Map(questions.value.map((question) => [Number(question.id), question]))

  const columns = [
    {
      key: 'submitted_at',
      title: 'Дата отправки',
      type: 'meta',
      widthHint: 22,
    },
  ]

  for (const question of questions.value) {
    const qId = Number(question.id)
    if (question.question_type === 'ranking') {
      const rankingOptions = getQuestionOptions(qId)
      for (const option of rankingOptions) {
        columns.push({
          key: `q_${qId}_rank_${option.id}`,
          title: wrapAndTrimExcelText(option.title || `Вариант #${option.id}`, { maxChars: 180, maxLine: 40 }),
          type: 'ranking',
          questionId: qId,
          optionId: Number(option.id),
          widthHint: 16,
        })
      }
      continue
    }

    columns.push({
      key: `q_${qId}`,
      title: wrapAndTrimExcelText(question.text || `Вопрос #${qId}`, { maxChars: 280, maxLine: 45 }),
      type: 'question',
      questionId: qId,
      widthHint: ['text', 'rich_text'].includes(question.question_type) ? 45 : 24,
    })
  }

  const aoa = [columns.map((column) => column.title)]

  for (const response of responses.value) {
    const row = []

    for (const column of columns) {
      if (column.type === 'meta') {
        row.push(formatDate(response?.submitted_at))
        continue
      }

      if (column.type === 'ranking') {
        const answer = getAnswerForResponse(response.id, column.questionId)
        if (!answer) {
          row.push('')
          continue
        }

        const rankingRows = rankingByAnswerId.value[Number(answer.id)] || []
        const matched = rankingRows.find((rankingRow) => {
          const optionId = Number(rankingRow?.option_id || rankingRow?.option?.id || 0)
          return optionId === Number(column.optionId)
        })
        row.push(matched?.rank ?? '')
        continue
      }

      const question = questionById.get(Number(column.questionId))
      const answer = getAnswerForResponse(response.id, column.questionId)
      row.push(formatAnswerForExport(question, answer))
    }

    aoa.push(row)
  }

  const sheet = XLSX.utils.aoa_to_sheet(aoa)
  setAutoFilter(sheet, aoa.length, columns.length)
  applyBorderedTableStyle(sheet, 0, 1, aoa.length - 1, columns.length)

  const autoCols = computeColumnWidths(aoa, 10, 55)
  sheet['!cols'] = autoCols.map((col, index) => ({
    wch: Math.max(col.wch || 12, columns[index]?.widthHint || 12),
  }))

  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, sheet, 'Ответы')
  XLSX.writeFile(workbook, buildExportFileName('responses'))
}

function exportSummaryToExcel() {
  const workbook = XLSX.utils.book_new()
  const usedNames = new Set()

  questions.value.forEach((question, index) => {
    const summary = getQuestionSummary(question.id)
    const aoa = []
    const mergeRows = []
    let tableHeaderRow = null
    let tableDataStartRow = null
    let tableDataEndRow = null

    const isTextList = summary.kind === 'text-list'
    const tableColumns = isTextList ? 1 : 3

    aoa.push([wrapAndTrimExcelText(`Вопрос: ${question.text || `Вопрос #${question.id}`}`, { maxChars: 600, maxLine: 90 })])
    mergeRows.push(0)

    if (summary.kind === 'number-stats') {
      aoa.push([
        `Среднее: ${Number(summary.avg).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} | Минимум: ${summary.min} | Максимум: ${summary.max}`,
      ])
      mergeRows.push(aoa.length - 1)
    }

    if (summary.kind === 'distribution') {
      if (summary.distributionLabel) {
        aoa.push([summary.distributionLabel])
        mergeRows.push(aoa.length - 1)
      }

      aoa.push([])
      tableHeaderRow = aoa.length
      aoa.push(['Вариант', 'Количество', 'Процент'])
      tableDataStartRow = aoa.length
      for (const row of summary.rows || []) {
        aoa.push([
          wrapAndTrimExcelText(row.label, { maxChars: 400, maxLine: 60 }),
          row.count,
          formatPercent(row.percent),
        ])
      }
      tableDataEndRow = aoa.length - 1
    } else if (summary.kind === 'number-stats') {
      aoa.push([])
      tableHeaderRow = aoa.length
      aoa.push(['Значение', 'Количество', 'Процент'])
      tableDataStartRow = aoa.length
      for (const row of summary.rows || []) {
        aoa.push([row.label, row.count, formatPercent(row.percent)])
      }
      tableDataEndRow = aoa.length - 1
    } else if (summary.kind === 'text-list') {
      aoa.push([])
      tableHeaderRow = aoa.length
      aoa.push(['Текст ответа'])
      tableDataStartRow = aoa.length
      for (const value of summary.values || []) {
        aoa.push([wrapAndTrimExcelText(value, { maxChars: 2000, maxLine: 90 })])
      }
      if (!(summary.values || []).length) {
        aoa.push(['Нет текстовых ответов'])
      }
      tableDataEndRow = aoa.length - 1
    } else {
      aoa.push([])
      aoa.push(['Нет ответов'])
      mergeRows.push(aoa.length - 1)
    }

    const sheet = XLSX.utils.aoa_to_sheet(aoa)

    if (tableColumns > 1) {
      sheet['!merges'] = sheet['!merges'] || []
      for (const mergeRow of mergeRows) {
        sheet['!merges'].push({
          s: { r: mergeRow, c: 0 },
          e: { r: mergeRow, c: tableColumns - 1 },
        })
      }
    }

    applyStyleRange(sheet, 0, aoa.length - 1, 0, tableColumns - 1, (r) => (
      buildCellStyle({
        header: r === 0,
        bordered: false,
        wrap: true,
      })
    ))

    if (tableHeaderRow != null && tableDataStartRow != null && tableDataEndRow != null) {
      applyBorderedTableStyle(
        sheet,
        tableHeaderRow,
        tableDataStartRow,
        tableDataEndRow,
        tableColumns,
      )
    }

    applyBorderToNonEmptyCells(sheet, aoa, tableColumns)

    if (summary.kind === 'number-stats') {
      sheet['!cols'] = [{ wch: 12 }, { wch: 12 }, { wch: 12 }]
    } else if (summary.kind === 'distribution') {
      sheet['!cols'] = [{ wch: 36 }, { wch: 12 }, { wch: 12 }]
    } else if (summary.kind === 'text-list') {
      sheet['!cols'] = [{ wch: 70 }]
    } else {
      sheet['!cols'] = [{ wch: 30 }, { wch: 30 }, { wch: 30 }].slice(0, tableColumns)
    }

    const sheetName = makeUniqueSheetName(`${index + 1}. ${question.text || `Вопрос ${question.id}`}`, usedNames)
    XLSX.utils.book_append_sheet(workbook, sheet, sheetName)
  })

  XLSX.writeFile(workbook, buildExportFileName('summary'))
}

async function exportCurrentTab() {
  exportError.value = ''
  exporting.value = true

  try {
    await loadXlsxLibrary()

    if (activeTab.value === 'responses') {
      exportResponsesToExcel()
    } else {
      exportSummaryToExcel()
    }
  } catch {
    exportError.value = 'Не удалось сформировать Excel-файл'
  } finally {
    exporting.value = false
  }
}

async function loadResponsesByStatus(publishingId) {
  const filter = {
    publishing_id: Number(publishingId),
  }

  if (statusFilter.value !== 'all') {
    filter.status = statusFilter.value
  }

  const params = {
    filter: JSON.stringify(filter),
    appends: [
      'survey_answers',
      'survey_answers.option',
      'survey_answers.options',
      'survey_answers.scale_item',
      'survey_answers.survey_answer_ranking_items',
      'survey_answers.survey_answer_ranking_items.option',
    ].join(','),
    sort: '-submitted_at,id',
    pageSize: 10000,
  }

  const response = await nocobaseApi.get('/survey_responses:list', { params })
  const responseRows = response?.data?.data || []

  const flatAnswers = []
  const flatRankingItems = []

  for (const responseRow of responseRows) {
    const responseAnswers = Array.isArray(responseRow?.survey_answers)
      ? responseRow.survey_answers
      : []

    for (const answer of responseAnswers) {
      flatAnswers.push({
        ...answer,
        response_id: answer?.response_id ?? responseRow.id,
      })

      const answerRankingRows = Array.isArray(answer?.survey_answer_ranking_items)
        ? answer.survey_answer_ranking_items
        : []

      for (const rankingRow of answerRankingRows) {
        flatRankingItems.push({
          ...rankingRow,
          answer_id: rankingRow?.answer_id ?? answer.id,
        })
      }
    }
  }

  return {
    responses: responseRows,
    answers: flatAnswers,
    rankingItems: flatRankingItems,
  }
}

async function loadResults() {
  loading.value = true
  error.value = ''

  publishing.value = null
  sections.value = []
  questions.value = []
  options.value = []
  scaleItems.value = []
  responses.value = []
  answers.value = []
  rankingItems.value = []

  try {
    const publishingRes = await nocobaseApi.get('/survey_publishings:get', {
      params: {
        filterByTk: props.publishingId,
        appends: 'survey,observers',
      },
    })

    const currentPublishing = publishingRes?.data?.data
    if (!currentPublishing?.id) {
      throw new Error('PUBLISHING_NOT_FOUND')
    }

    if (!canUserViewPublishing(currentPublishing, {
      currentUserId: auth.user?.id,
      isAdmin: auth.isAdmin,
    })) {
      throw new Error('PUBLISHING_FORBIDDEN')
    }

    publishing.value = currentPublishing

    const surveyId = Number(currentPublishing?.survey_id || currentPublishing?.survey?.id)
    if (!surveyId) {
      throw new Error('SURVEY_NOT_FOUND')
    }

    const [sectionsRes, questionsRes, responsesData] = await Promise.all([
      nocobaseApi.get('/survey_sections:list', {
        params: {
          filter: JSON.stringify({ survey_id: surveyId }),
          sort: 'order,id',
          pageSize: 1000,
        },
      }),
      nocobaseApi.get('/survey_questions:list', {
        params: {
          filter: JSON.stringify({ survey_id: surveyId }),
          sort: 'order,id',
          appends: 'scale',
          pageSize: 2000,
        },
      }),
      loadResponsesByStatus(currentPublishing.id),
    ])

    sections.value = sectionsRes?.data?.data || []
    questions.value = questionsRes?.data?.data || []
    responses.value = responsesData?.responses || []
    answers.value = responsesData?.answers || []
    rankingItems.value = responsesData?.rankingItems || []

    const questionIds = questions.value.map((q) => Number(q?.id)).filter(Boolean)
    const scaleIds = [...new Set(questions.value.map((q) => Number(q?.scale_id)).filter(Boolean))]

    const metaRequests = []
    if (questionIds.length) {
      metaRequests.push(
        nocobaseApi.get('/survey_question_options:list', {
          params: {
            filter: JSON.stringify({ question_id: { $in: questionIds } }),
            sort: 'order,id',
            pageSize: 10000,
          },
        }),
      )
    }

    if (scaleIds.length) {
      metaRequests.push(
        nocobaseApi.get('/survey_scale_items:list', {
          params: {
            filter: JSON.stringify({ scale_id: { $in: scaleIds } }),
            sort: 'order,id',
            pageSize: 10000,
          },
        }),
      )
    }

    const metaResults = await Promise.all(metaRequests)
    let metaIndex = 0

    if (questionIds.length) {
      options.value = metaResults[metaIndex]?.data?.data || []
      metaIndex += 1
    }

    if (scaleIds.length) {
      scaleItems.value = metaResults[metaIndex]?.data?.data || []
      metaIndex += 1
    }
  } catch (e) {
    if (e?.message === 'PUBLISHING_FORBIDDEN') {
      error.value = 'У вас нет доступа к результатам этой публикации'
    } else {
      error.value = 'Не удалось загрузить результаты публикации'
    }
  } finally {
    loading.value = false
  }
}

async function reloadResponsesOnly() {
  if (!publishing.value?.id) return

  loading.value = true
  error.value = ''
  responses.value = []
  answers.value = []
  rankingItems.value = []

  try {
    const responsesData = await loadResponsesByStatus(publishing.value.id)
    responses.value = responsesData?.responses || []
    answers.value = responsesData?.answers || []
    rankingItems.value = responsesData?.rankingItems || []
  } catch {
    error.value = 'Не удалось загрузить результаты публикации'
  } finally {
    loading.value = false
  }
}

watch(() => props.publishingId, () => {
  loadResults()
})

watch(statusFilter, () => {
  reloadResponsesOnly()
})

onMounted(() => {
  loadResults()
})
</script>

<template>
  <div class="mx-auto w-full max-w-6xl px-4 py-6">
    <router-link to="/cabinet" class="mb-4 inline-block text-sm text-primary no-underline hover:underline">
      &larr; К списку публикаций
    </router-link>

    <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-800">
          {{ publishing?.title || publishing?.survey?.title || 'Результаты публикации' }}
        </h1>
        <p class="mt-1 text-sm text-muted">
          Ответов в выборке: {{ responses.length }}
        </p>
      </div>

      <label class="block text-sm text-slate-700">
        <span class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Статус ответов</span>
        <select
          v-model="statusFilter"
          class="field-input !py-2 !text-sm"
        >
          <option v-for="status in statusOptions" :key="status.value" :value="status.value">
            {{ status.label }}
          </option>
        </select>
      </label>
    </div>

    <div class="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-3">
      <div class="flex flex-wrap gap-2">
        <button
          class="cursor-pointer rounded-xl border px-4 py-2 text-sm font-medium transition"
          :class="activeTab === 'summary'
            ? 'border-primary bg-primary text-white'
            : 'border-slate-300 bg-white text-slate-700 hover:border-primary/40 hover:bg-primary/5'"
          @click="activeTab = 'summary'"
        >
          Общие результаты
        </button>

        <button
          class="cursor-pointer rounded-xl border px-4 py-2 text-sm font-medium transition"
          :class="activeTab === 'responses'
            ? 'border-primary bg-primary text-white'
            : 'border-slate-300 bg-white text-slate-700 hover:border-primary/40 hover:bg-primary/5'"
          @click="activeTab = 'responses'"
        >
          Ответы
        </button>
      </div>

      <div class="flex flex-col items-start gap-2 sm:items-end">
        <button
          class="btn-outline !px-4 !py-2"
          :disabled="exporting"
          @click="exportCurrentTab"
        >
          {{
            exporting
              ? 'Формирование...'
              : (activeTab === 'responses'
                ? 'Экспорт ответов в Excel'
                : 'Экспорт общих результатов в Excel')
          }}
        </button>
        <p v-if="exportError" class="text-xs text-danger">{{ exportError }}</p>
      </div>
    </div>

    <div v-if="loading" class="glass-panel p-8 text-center text-muted">Загрузка результатов...</div>

    <div v-else-if="error" class="glass-panel p-8 text-center text-danger">
      {{ error }}
    </div>

    <div v-else-if="!responses.length" class="glass-panel p-8 text-center text-muted">
      Для выбранного статуса пока нет ответов
    </div>

    <div v-else-if="activeTab === 'summary'" class="space-y-4">
      <section v-for="group in sectionGroups" :key="`summary-${group.id}`" class="glass-panel p-5">
        <h2 v-if="group.title" class="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-600">
          {{ group.title }}
        </h2>

        <div class="space-y-4">
          <article
            v-for="question in group.questions"
            :key="`summary-q-${question.id}`"
            class="rounded-xl border border-slate-200/80 bg-white/70 p-4"
          >
            <p class="text-sm font-semibold text-slate-800">{{ question.text }}</p>
            <p v-if="question.description" class="mt-1 text-xs text-muted">
              {{ question.description }}
            </p>

            <p class="mt-2 text-xs text-muted">
              Отвечено: {{ getQuestionSummary(question.id).answeredCount }} из {{ getQuestionSummary(question.id).totalResponses }}
            </p>

            <div class="mt-3">
              <template v-if="getQuestionSummary(question.id).kind === 'distribution'">
                <p v-if="getQuestionSummary(question.id).distributionLabel" class="mb-2 text-xs text-slate-500">
                  {{ getQuestionSummary(question.id).distributionLabel }}
                </p>

                <div class="space-y-2">
                  <div
                    v-for="row in getQuestionSummary(question.id).rows"
                    :key="`${question.id}-${row.label}`"
                    class="rounded-lg border border-slate-200 bg-white p-2"
                  >
                    <div class="mb-1 flex items-center justify-between gap-3 text-sm">
                      <span class="text-slate-700">{{ row.label }}</span>
                      <span class="text-slate-500">{{ row.count }} · {{ formatPercent(row.percent) }}</span>
                    </div>
                    <div class="h-2 overflow-hidden rounded bg-slate-200">
                      <div
                        class="h-full rounded bg-primary transition-all"
                        :style="{ width: `${Math.max(Math.min(row.percent, 100), 0)}%` }"
                      ></div>
                    </div>
                  </div>
                </div>
              </template>

              <template v-else-if="getQuestionSummary(question.id).kind === 'number-stats'">
                <div class="mb-3 grid gap-2 sm:grid-cols-3">
                  <div class="rounded-lg border border-slate-200 bg-white p-2 text-sm">
                    <p class="text-xs text-muted">Среднее</p>
                    <p class="font-semibold text-slate-700">
                      {{ Number(getQuestionSummary(question.id).avg).toLocaleString('ru-RU', { maximumFractionDigits: 2 }) }}
                    </p>
                  </div>
                  <div class="rounded-lg border border-slate-200 bg-white p-2 text-sm">
                    <p class="text-xs text-muted">Минимум</p>
                    <p class="font-semibold text-slate-700">{{ getQuestionSummary(question.id).min }}</p>
                  </div>
                  <div class="rounded-lg border border-slate-200 bg-white p-2 text-sm">
                    <p class="text-xs text-muted">Максимум</p>
                    <p class="font-semibold text-slate-700">{{ getQuestionSummary(question.id).max }}</p>
                  </div>
                </div>

                <p class="mb-2 text-xs text-slate-500">
                  Распределение по значениям
                </p>
                <div class="space-y-2">
                  <div
                    v-for="row in getQuestionSummary(question.id).rows"
                    :key="`${question.id}-num-${row.value}`"
                    class="rounded-lg border border-slate-200 bg-white p-2"
                  >
                    <div class="mb-1 flex items-center justify-between gap-3 text-sm">
                      <span class="text-slate-700">{{ row.label }}</span>
                      <span class="text-slate-500">{{ row.count }} · {{ formatPercent(row.percent) }}</span>
                    </div>
                    <div class="h-2 overflow-hidden rounded bg-slate-200">
                      <div
                        class="h-full rounded bg-primary transition-all"
                        :style="{ width: `${Math.max(Math.min(row.percent, 100), 0)}%` }"
                      ></div>
                    </div>
                  </div>
                </div>
              </template>

              <template v-else-if="getQuestionSummary(question.id).kind === 'text-list'">
                <div class="mb-2 flex items-center justify-between gap-3">
                  <p class="text-xs text-slate-500">
                    Текстовых ответов: {{ getQuestionSummary(question.id).values.length }}
                  </p>
                  <button
                    class="cursor-pointer rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-primary/50 hover:bg-primary/5"
                    @click="toggleTextAnswers(question.id)"
                  >
                    {{ isTextAnswersExpanded(question.id) ? 'Скрыть ответы' : 'Показать ответы' }}
                  </button>
                </div>

                <div v-if="isTextAnswersExpanded(question.id)">
                  <ul class="space-y-2">
                    <li
                      v-for="(value, idx) in getPreviewTextAnswers(getQuestionSummary(question.id))"
                      :key="`${question.id}-text-${idx}`"
                      class="rounded-lg border border-slate-200 bg-white p-2 text-sm text-slate-700"
                    >
                      {{ value }}
                    </li>
                  </ul>

                  <p v-if="getHiddenTextAnswersCount(getQuestionSummary(question.id)) > 0" class="mt-2 text-xs text-muted">
                    Показаны первые {{ MAX_TEXT_ANSWERS_PREVIEW }} ответов из {{ getQuestionSummary(question.id).values.length }}.
                  </p>
                </div>
              </template>

              <p v-else class="text-sm text-muted">Нет ответов по этому вопросу.</p>
            </div>
          </article>
        </div>
      </section>
    </div>

    <div v-else class="space-y-4">
      <article
        v-for="response in responses"
        :key="response.id"
        class="glass-panel overflow-hidden"
      >
        <div class="border-b border-slate-200/70 bg-white/70 px-5 py-4">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="font-semibold text-slate-800">{{ getUserLabel(response) }}</p>
            <p class="text-sm text-muted">Отправлено: {{ formatDate(response.submitted_at) }}</p>
          </div>
          <p class="mt-1 text-xs text-muted">Ответ #{{ response.id }}</p>
        </div>

        <div class="space-y-6 px-5 py-5">
          <section v-for="group in sectionGroups" :key="group.id" class="space-y-3">
            <h3 v-if="group.title" class="text-sm font-semibold uppercase tracking-wide text-slate-600">
              {{ group.title }}
            </h3>

            <div
              v-for="question in group.questions"
              :key="question.id"
              class="rounded-xl border border-slate-200/80 bg-white/70 px-4 py-3"
            >
              <p class="text-sm font-medium text-slate-800">{{ question.text }}</p>
              <p v-if="question.description" class="mt-1 text-xs text-muted">
                {{ question.description }}
              </p>

              <div class="mt-2">
                <template v-if="getResolvedAnswer(response.id, question.id).type === 'list'">
                  <ul class="list-inside list-disc space-y-1 text-sm text-slate-700">
                    <li
                      v-for="item in getResolvedAnswer(response.id, question.id).items"
                      :key="item"
                    >
                      {{ item }}
                    </li>
                  </ul>
                </template>

                <p
                  v-else
                  class="text-sm"
                  :class="getResolvedAnswer(response.id, question.id).type === 'empty' ? 'text-muted' : 'text-slate-700'"
                >
                  {{ getResolvedAnswer(response.id, question.id).text }}
                </p>
              </div>
            </div>
          </section>
        </div>
      </article>
    </div>
  </div>
</template>
