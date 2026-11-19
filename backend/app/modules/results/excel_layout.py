"""Размеры столбцов Excel в знаках, высота строк в пунктах."""

from datetime import date, datetime
from math import ceil
from textwrap import TextWrapper

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
    wrappers = []
    for column, cells in enumerate(sheet.iter_cols(), 1):
        longest = max(
            (len(line.expandtabs(4)) for cell in cells for line in _display_text(cell).splitlines()), default=0
        )
        width = max(6, min(64, ceil(longest * 1.15) + 3))
        sheet.column_dimensions[get_column_letter(column)].width = width
        wrappers.append(TextWrapper(width=max(1, int((width - 2) / 1.15)), tabsize=4))

    for cells in sheet.iter_rows():
        lines = 1
        for cell, wrapper in zip(cells, wrappers, strict=True):
            cell.alignment = alignment
            if cell.row == 1:
                cell.font = header_font
                cell.fill = header_fill
            if isinstance(cell.value, str):
                cell.data_type = 's'
                wrapped = sum(max(1, len(wrapper.wrap(line))) for line in cell.value.split('\n'))
                lines = max(lines, wrapped)
        # Excel ограничивает высоту одной строки 409 пунктами.
        sheet.row_dimensions[cells[0].row].height = min(409, 16 * lines + (8 if cells[0].row == 1 else 4))
