"""Shared a24c1 PDF typography and inline formatting."""
from pathlib import Path
import re
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics, pdfdoc
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table,
                               TableStyle, Spacer, PageBreak, Flowable, Preformatted)

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / 'tools/pdf-fonts/ibm3270'
for face in ('Regular', 'Bold', 'Italic', 'BoldItalic'):
    pdfmetrics.registerFont(TTFont('IBM3270-' + face, str(FONTS / f'STR8N3270-{face}.ttf')))
pdfmetrics.registerFontFamily('IBM3270-Regular', normal='IBM3270-Regular',
                              bold='IBM3270-Bold', italic='IBM3270-Italic',
                              boldItalic='IBM3270-BoldItalic')
WIDTH = A4[0] - 84
BODY = ParagraphStyle('Body', fontName='IBM3270-Regular', fontSize=9.5,
                      leading=11.6, spaceAfter=3.5)
HEADING = ParagraphStyle('Heading', parent=BODY, fontName='IBM3270-Bold',
                         fontSize=11, leading=14, spaceBefore=7, spaceAfter=5,
                         keepWithNext=True)
TITLE = ParagraphStyle('Title', parent=BODY, fontName='IBM3270-Bold',
                       fontSize=17, leading=21, spaceAfter=10)
CELL = ParagraphStyle('Cell', parent=BODY, fontSize=9, leading=11, spaceAfter=0)
CODE = ParagraphStyle('Code', parent=BODY, fontSize=8.3, leading=10,
                      spaceAfter=6)


class Box(Flowable):
    def __init__(self):
        Flowable.__init__(self)
        self.width, self.height = 9, 12

    def draw(self):
        self.canv.setStrokeColor(colors.black)
        self.canv.setLineWidth(.65)
        self.canv.rect(0, 1, 8, 8, stroke=1, fill=0)


def inline(text):
    text = text.replace('\u2014', '-').replace('\u2013', '-')
    text = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', text)
    text = escape(text)
    text = re.sub(r'`([^`]+)`', r'<font name="IBM3270-Regular" size="8.5">\1</font>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    # Dark print colors retain contrast on white paper; console colors are brighter.
    for label, ink in {'cyan': '#007A87', 'yellow': '#8A6500',
                       'green': '#176D30', 'red': '#B02020'}.items():
        text = text.replace(f'<b>{label}</b>', f'<font color="{ink}"><b>{label}</b></font>')
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)
    return text


def footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#888888'))
    canvas.line(42, 35, A4[0] - 42, 35)
    canvas.setFont('IBM3270-Regular', 8)
    canvas.drawString(42, 21, 'STR8-N 2.0a24c1 | C02 / 816')
    canvas.drawRightString(A4[0] - 42, 21, f'Page {document.page}')
    canvas.restoreState()
