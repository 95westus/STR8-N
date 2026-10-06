"""Render beta4's public manuals using the established 3270 typography."""
from pathlib import Path
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,Preformatted
import build_v2_quick_start_pdf as renderer

ROOT=Path(__file__).resolve().parents[1]
GUIDES={
    'Quick-Start':'STR8N_V2_BETA4_QUICK_START.md',
    'Migration':'STR8N_V2_BETA4_MIGRATION.md',
    'Operator-Manual':'STR8N_V2_BETA4_MANUAL.md',
    'RST':'STR8N_V2_BETA4_RST.md',
    'Bank-Maintenance':'STR8N_BANK_MAINT_RECOVERY.md',
    'Release-Notes':'STR8N_V2_BETA4.md',
}
def contents(source,label):
    style=renderer.typography
    story=[Paragraph('STR8-N 2.0b4',style.TITLE),
           Paragraph(label.replace('-',' ')+' | C02 / 816',renderer.HEADING)]
    lines=source.read_text(encoding='utf-8').splitlines();index=0
    def special(line):
        return line.startswith(('#','|','```','- ')) or re.match(r'^\d+\. ',line)
    while index<len(lines):
        line=lines[index].strip();index+=1
        if not line or line.startswith('# '):continue
        if line.startswith('## '):story.append(Paragraph(style.inline(line[3:]),renderer.HEADING))
        elif line.startswith('```'):
            block=[]
            while index<len(lines) and not lines[index].startswith('```'):
                block.append(lines[index]);index+=1
            index+=1;story.append(Preformatted('\n'.join(block),renderer.CODE))
        elif line.startswith('|'):
            rows=[];index-=1
            while index<len(lines) and lines[index].startswith('|'):
                cells=[v.strip() for v in lines[index].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',v) for v in cells):
                    rows.append([Paragraph(style.inline(v),renderer.CELL) for v in cells])
                index+=1
            count=len(rows[0]);assert all(len(r)==count for r in rows)
            widths=[168,style.WIDTH-168] if count==2 else [style.WIDTH/count]*count
            table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([
                ('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eeeeee')),
                ('LINEBELOW',(0,0),(-1,0),.6,colors.black),
                ('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#aaaaaa')),
                ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
                ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
            story += [table,Spacer(1,4)]
        else:
            text=line
            while index<len(lines) and lines[index].strip() and not special(lines[index].strip()):
                text+=' '+lines[index].strip();index+=1
            paragraph_style=renderer.BODY
            following=index
            while following<len(lines) and not lines[following].strip():following+=1
            if following<len(lines) and lines[following].strip().startswith('```'):
                paragraph_style=ParagraphStyle('CodeIntro',parent=renderer.BODY,keepWithNext=True)
            story.append(Paragraph(style.inline(text),paragraph_style))
    return story
def footer(canvas,document):
    canvas.saveState();canvas.setStrokeColor(colors.HexColor('#888888'))
    canvas.line(42,35,A4[0]-42,35)
    canvas.setFont('IBM3270-Regular',8)
    canvas.drawString(42,21,'STR8-N 2.0b4 | C02 / 816')
    canvas.drawRightString(A4[0]-42,21,f'Page {document.page}')
    canvas.restoreState()
def main():
    output=ROOT/'output/pdf';output.mkdir(parents=True,exist_ok=True)
    for label,name in GUIDES.items():
        story=contents(ROOT/'docs'/name,label)
        target=output/('STR8N-2.0b4-'+label+'.pdf')
        doc=SimpleDocTemplate(str(target),pagesize=A4,leftMargin=42,rightMargin=42,
            topMargin=32,bottomMargin=46,title='STR8-N 2.0b4 '+label,author='STR8-N')
        def stable_canvas(*args,**kwargs):
            kwargs['invariant']=1
            return canvas.Canvas(*args,**kwargs)
        doc.build(story,onFirstPage=footer,onLaterPages=footer,canvasmaker=stable_canvas)
        print(target)
if __name__=='__main__':main()
