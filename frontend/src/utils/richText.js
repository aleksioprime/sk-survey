/** Форматированный ответ хранится как HTML с абзацами; в поле ввода - обычный текст. */

const escape = (text) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

export function textToHtml(text) {
  const paragraphs = (text || '').split(/\n{2,}/).map((p) => p.trim()).filter(Boolean)
  return paragraphs.map((p) => `<p>${escape(p).replace(/\n/g, '<br>')}</p>`).join('')
}

export function htmlToText(html) {
  if (!html) return ''
  const doc = new DOMParser().parseFromString(html.replace(/<br\s*\/?>/gi, '\n').replace(/<\/p>/gi, '\n\n'), 'text/html')
  return (doc.body.textContent || '').replace(/\n{3,}/g, '\n\n').trim()
}

/** Простой текст из конструктора с переносами строк → абзацы. Для intro и благодарности. */
export function paragraphs(text) {
  return (text || '').split(/\n{2,}/).map((p) => p.trim()).filter(Boolean)
}
