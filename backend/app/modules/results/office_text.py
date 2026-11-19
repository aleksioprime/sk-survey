"""Подготовка пользовательского текста для файлов Office."""

import re
from html.parser import HTMLParser

_INVALID_XML = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]')


def xml_text(value: str) -> str:
    return _INVALID_XML.sub('', value)


class _RichTextReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.lists = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag == 'br':
            self.parts.append('\n')
        elif tag in ('ol', 'ul'):
            self.lists.append(1 if tag == 'ol' else None)
        elif tag == 'li':
            if self.lists and self.lists[-1] is not None:
                self.parts.append(f'{self.lists[-1]}. ')
                self.lists[-1] += 1
            else:
                self.parts.append('• ')

    def handle_endtag(self, tag):
        if tag in ('ol', 'ul') and self.lists:
            self.lists.pop()
        if tag in ('p', 'blockquote', 'h3', 'h4'):
            self.parts.append('\n\n')
        elif tag == 'li':
            self.parts.append('\n')


def rich_text_to_text(value: str) -> str:
    reader = _RichTextReader()
    reader.feed(value)
    reader.close()
    return ''.join(reader.parts).strip()
