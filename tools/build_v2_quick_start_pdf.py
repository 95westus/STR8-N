"""Render the two-page a24c1 how-to using the checklist's 3270 typography."""
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table,
                               TableStyle, Spacer, PageBreak, Preformatted)
import v2_pdf_style as typography

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/STR8N_V2_A24C1_QUICK_START.md'
OUTPUT = ROOT / 'output/pdf/STR8N-A24C1-C02-816-Quick-Start.pdf'
BODY = ParagraphStyle('QuickBody', parent=typography.BODY,
                      fontSize=9.3, leading=11.2, spaceAfter=4)
HEADING = ParagraphStyle('QuickHeading', parent=typography.HEADING,
                         spaceBefore=7, spaceAfter=5)
CELL = ParagraphStyle('QuickCell', parent=BODY, fontSize=9,
                      leading=10.5, spaceAfter=0)
CODE = ParagraphStyle('QuickCode', parent=BODY, fontSize=8.3,
                      leading=10, spaceBefore=2, spaceAfter=6)


def contents():
    lines = SOURCE.read_text(encoding='utf-8').splitlines()
    story = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if not line:
            continue
        if line == '<!-- pagebreak -->':
            story.append(PageBreak())
        elif line.startswith('# '):
            story.append(Paragraph('STR8-N 2.0a24c1', typography.TITLE))
            story.append(Paragraph('Quick start | C02 / 816', HEADING))
        elif line.startswith('## '):
            story.append(Paragraph(typography.inline(line[3:]), HEADING))
        elif line.startswith('```'):
            code = []
            while index < len(lines) and not lines[index].startswith('```'):
                code.append(lines[index])
                index += 1
            index += 1
            # Preformatted preserves PowerShell quoting and continuation marks.
            story.append(Preformatted('\n'.join(code), CODE))
        elif line.startswith('|'):
            rows = []
            index -= 1
            while index < len(lines) and lines[index].startswith('|'):
                cells = [value.strip() for value in lines[index].strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', value) for value in cells):
                    rows.append([Paragraph(typography.inline(value), CELL) for value in cells])
                index += 1
            table = Table(rows, colWidths=[168, typography.WIDTH - 168], repeatRows=1)
            table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee')),
                ('LINEBELOW', (0, 0), (-1, 0), .6, colors.black),
                ('LINEBELOW', (0, 1), (-1, -1), .3, colors.HexColor('#aaaaaa')),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.extend([table, Spacer(1, 4)])
        else:
            bullet = line.startswith('- ')
            text = line[2:] if bullet else line
            while (index < len(lines) and lines[index].strip()
                   and not lines[index].lstrip().startswith(('#', '- ', '|', '```', '<!--'))):
                text += ' ' + lines[index].strip()
                index += 1
            style = ParagraphStyle('Step', parent=BODY, leftIndent=12,
                                   firstLineIndent=-12) if bullet else BODY
            story.append(Paragraph(('- ' if bullet else '') + typography.inline(text), style))
    return story


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(OUTPUT), pagesize=A4,
                                 leftMargin=42, rightMargin=42,
                                 topMargin=32, bottomMargin=46,
                                 title='STR8-N a24c1 C02/816 quick start',
                                 author='STR8-N')
    document.build(contents(), onFirstPage=typography.footer,
                   onLaterPages=typography.footer)
    print(OUTPUT)


if __name__ == '__main__':
    main()
