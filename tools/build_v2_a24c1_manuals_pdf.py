"""Render the current a24c1 manual and maps using the quick-start typography."""
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.pagesizes import A4
import build_v2_quick_start_pdf as renderer


def main():
    for stem, subtitle in (
        ('MANUAL', 'Operator and technical manual | C02 / 816'),
        ('MAPS', 'Maps diagrams and charts | C02 / 816'),
    ):
        renderer.SOURCE = renderer.ROOT / f'docs/STR8N_V2_A24C1_{stem}.md'
        output = renderer.ROOT / f'output/pdf/STR8N-A24C1-{stem.title()}.pdf'
        story = renderer.contents()
        story[1] = Paragraph(subtitle, renderer.HEADING)
        document = SimpleDocTemplate(
            str(output), pagesize=A4, leftMargin=42, rightMargin=42,
            topMargin=32, bottomMargin=46, title=f'STR8-N a24c1 {subtitle}',
            author='STR8-N')
        document.build(story, onFirstPage=renderer.typography.footer,
                       onLaterPages=renderer.typography.footer)
        print(output)


if __name__ == '__main__':
    main()
