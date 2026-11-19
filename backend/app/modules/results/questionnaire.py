"""Печатная анкета одного участника."""

from collections import defaultdict
from io import BytesIO

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from app.modules.responses.models import STATUS_SUBMITTED
from app.modules.results.office_text import rich_text_to_text, xml_text
from app.modules.results.service import MOSCOW, Dataset, answer_text, matrix_values
from app.modules.surveys.models import MATRIX_TYPES


def _document():
    doc = Document()
    page = doc.sections[0]
    page.page_width, page.page_height = Cm(21), Cm(29.7)
    page.top_margin = page.bottom_margin = Cm(2)
    page.left_margin = page.right_margin = Cm(2.3)
    normal = doc.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.15

    title = doc.styles['Title']
    title.font.size = Pt(24)
    title.font.bold = True
    title.font.color.rgb = RGBColor.from_string('171E22')
    border = title.element.find('.//' + qn('w:pBdr'))
    if border is not None:
        border.getparent().remove(border)

    section = doc.styles['Heading 1']
    section.font.size = Pt(15)
    section.font.color.rgb = RGBColor.from_string('146861')
    question = doc.styles.add_style('Question', WD_STYLE_TYPE.PARAGRAPH)
    question.base_style = normal
    question.font.bold = True
    question.paragraph_format.space_before = Pt(9)
    question.paragraph_format.space_after = Pt(3)
    question.paragraph_format.keep_with_next = True
    answer = doc.styles.add_style('Answer', WD_STYLE_TYPE.PARAGRAPH)
    answer.base_style = normal
    answer.paragraph_format.left_indent = Cm(0.55)
    doc.core_properties.author = 'SK Survey'
    doc.core_properties.comments = ''
    return doc


def export_docx(data: Dataset) -> bytes:
    (response,) = data.responses
    publishing = data.publishing
    survey = publishing.survey
    doc = _document()
    doc.add_paragraph(xml_text(survey.title), 'Title')
    if publishing.title != survey.title:
        doc.add_paragraph(xml_text(publishing.title), 'Subtitle')
    user = data.users.get(response.user_id) if not publishing.is_anonymous else None
    if publishing.is_anonymous:
        participant = 'Анонимный ответ'
    elif user:
        person = user.person
        participant = 'Участник: ' + ((person.full_name if person else '') or user.email)
        if person and person.study_class:
            participant += f' · Класс: {person.study_class.name}'
    else:
        participant = 'Участник не указан'
    doc.add_paragraph(xml_text(participant))
    status = 'Отправлен' if response.status == STATUS_SUBMITTED else 'Не отправлен'
    meta = doc.add_paragraph(f'Статус: {status}')
    for label, value in [('Начало', response.created_at), ('Отправка', response.submitted_at)]:
        if value:
            meta.add_run(f'\n{label}: {value.astimezone(MOSCOW):%d.%m.%Y %H:%M} МСК')

    answers = {answer.question_id: answer for answer in response.answers}
    groups = defaultdict(list)
    for question in data.questions:
        groups[question.section_id].append(question)
    number = 0
    for section in [None, *survey.sections]:
        questions = groups.get(section.id if section else None, [])
        if section and not section.is_active:
            questions = [q for q in questions if q.id in answers]
        if questions and section and section.show_heading:
            if section.title:
                doc.add_paragraph(xml_text(section.title), 'Heading 1')
            if section.description:
                doc.add_paragraph(xml_text(section.description))
        for question in questions:
            number += 1
            doc.add_paragraph(f'{number}. {xml_text(question.text)}', 'Question')
            if question.description:
                doc.add_paragraph(xml_text(question.description))
            answer = answers.get(question.id)
            if question.question_type in MATRIX_TYPES and answer and not answer.is_skipped:
                for row, value in zip(question.matrix_rows, matrix_values(question, answer), strict=True):
                    p = doc.add_paragraph(style='Answer')
                    p.add_run(xml_text(row['title']) + ': ').bold = True
                    p.add_run(xml_text(value) or 'Нет ответа')
                continue
            value = answer_text(question, answer, data.scales.get(question.scale_id), separator='\n')
            if question.question_type == 'rich_text':
                value = rich_text_to_text(value)
            doc.add_paragraph(xml_text(value) or 'Нет ответа', 'Answer')
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
