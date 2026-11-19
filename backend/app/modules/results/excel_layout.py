"""Ширина столбцов и перенос текста в выгрузке Excel."""

from datetime import date, datetime
from math import ceil

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def _display_text(cell):
    if isinstance(cell.value, datetime):
        cell.number_format = 'dd.mm.yyyy hh:mm:ss'
        return cell.value.strftime('%d.%m.%Y %H:%M:%S')
    if isinstance(cell.value, date):
        cell.number_format = 'dd.mm.yyyy'
        return cell.value.strftime('%d.%m.%Y')
    return '' if cell.value is None else str(cell.value)


def format_sheet(sheet):
    header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill('solid', fgColor='166962')
    alignment = Alignment(wrap_text=True, vertical='top')
    for column, cells in enumerate(sheet.iter_cols(), 1):
        longest = max(
            (len(line.expandtabs(4)) for cell in cells for line in _display_text(cell).splitlines()), default=0
        )
        width = max(6, min(64, ceil(longest * 1.15) + 3))
        sheet.column_dimensions[get_column_letter(column)].width = width

    # Excel подбирает высоту по перенесённому тексту, если она не зафиксирована.
    for cells in sheet.iter_rows():
        for cell in cells:
            cell.alignment = alignment
            if cell.row == 1:
                cell.font = header_font
                cell.fill = header_fill
            if isinstance(cell.value, str):
                cell.data_type = 's'
