"""Print the two source-development Markdown documents as US Letter PDFs."""
import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re
import textwrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'output/pdf'
DOCUMENTS = {
    'SOURCE_DEVELOPMENT_WORKBOOK.md': 'STR8N-Source-Development-Workbook.pdf',
    'SOURCE_HARDWARE_TEST_PLAN.md': 'STR8N-Source-Hardware-Test-Plan.pdf',
}
WIDTH = letter[0]-96
INK = colors.HexColor('#18232d')


def fonts():
    directory = Path('C:/Windows/Fonts')
    for name, filename in [('PrintBody','Carlito-Regular.ttf'), ('PrintBold','Carlito-Bold.ttf'),
                           ('PrintItalic','Carlito-Italic.ttf'), ('PrintBoldItalic','Carlito-BoldItalic.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(directory/filename)))
    pdfmetrics.registerFontFamily('PrintBody', normal='PrintBody', bold='PrintBold',
                                  italic='PrintItalic', boldItalic='PrintBoldItalic')
    pdfmetrics.registerFont(TTFont('PrintCode', str(directory/'consola.ttf')))


def normalize(text):
    return text.translate(str.maketrans({'\u2010':'-', '\u2011':'-', '\u2012':'-',
        '\u2013':'-', '\u2014':'-', '\u2212':'-', '\u00a0':' '}))


class Renderer:
    def __init__(self, source):
        self.source = source
        self.references = []
        self.body = ParagraphStyle('Body', fontName='PrintBody', fontSize=11, leading=14.8,
                                   spaceAfter=7, textColor=INK, splitLongWords=True,
                                   allowWidows=False, allowOrphans=False)
        self.title = ParagraphStyle('Title', parent=self.body, fontName='PrintBold',
                                    fontSize=23, leading=26, spaceAfter=15)
        self.h2 = ParagraphStyle('H2', parent=self.body, fontName='PrintBold', fontSize=14,
                                 leading=17, spaceBefore=12, spaceAfter=7, keepWithNext=True)
        self.h3 = ParagraphStyle('H3', parent=self.h2, fontSize=11.5, leading=14)
        self.cell = ParagraphStyle('Cell', parent=self.body, fontSize=9.4, leading=12, spaceAfter=0)
        self.code = ParagraphStyle('Code', fontName='PrintCode', fontSize=9, leading=12,
                                   backColor=colors.HexColor('#f1f3f5'), borderPadding=7,
                                   spaceBefore=3, spaceAfter=11)

    def inline(self, text):
        text = normalize(text)
        placeholders = {}
        def protect(markup):
            key = f'ZZINLINE{len(placeholders)}ZZ'
            placeholders[key] = markup
            return key
        # Protect code before applying Markdown emphasis; paths contain '*'.
        text = re.sub(r'`([^`]+)`', lambda m: protect(
            '<font name="PrintCode" size="9.3">'+escape(m[1])+'</font>'), text)
        def link(match):
            label, target = match.groups()
            if target not in [r[1] for r in self.references]:
                self.references.append((label,target))
            number = next(i for i,r in enumerate(self.references,1) if r[1] == target)
            path = (self.source.parent/target).resolve()
            url = DOCUMENTS.get(path.name, path.as_uri())
            return protect(f'<link href="{escape(url,quote=True)}"><u>{escape(label)}</u></link>'
                           f'<super><font size="7"> [{number}]</font></super>')
        text = re.sub(r'\[([^]]+)\]\(([^)]+)\)', link, text)
        text = escape(text)
        text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)
        for key, markup in placeholders.items(): text = text.replace(key,markup)
        return text

    def paragraph(self, text, indent=0, marker=None):
        style = self.body
        if indent or marker or text.endswith(':'):
            style = ParagraphStyle('Indented', parent=style, leftIndent=indent,
                                   firstLineIndent=-indent if marker else 0,
                                   keepWithNext=text.endswith(':'))
        return Paragraph((escape(marker)+' ' if marker else '')+self.inline(text),style)

    def table(self, rows):
        n = len(rows[0])
        header = rows[0]
        if header == ['No.','Pattern','No.','Pattern']:
            widths = [32,226,32,226]
        elif header[0] == 'Physical board':
            widths = [65,85,211,155]
        elif n == 3:
            widths = [118,168,230] if header[0] == 'Sample' else [145,255,116]
        else:
            widths = [176,340]
        data = [[Paragraph(self.inline('**'+c+'**' if i == 0 else c),self.cell)
                 for c in row] for i,row in enumerate(rows)]
        table = Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4e9ed')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f8f9')]),
            ('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#8b969e')),
            ('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#d5dce1')),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
        ]))
        return table

    def story(self):
        lines = self.source.read_text(encoding='utf-8').splitlines()
        result = []; i = 0
        def special(s): return s.startswith(('#','|','```','- ')) or re.match(r'^\d+\. ',s)
        while i < len(lines):
            raw = lines[i]; line = raw.strip(); i += 1
            if not line: continue
            if line.startswith('#'):
                level = len(line)-len(line.lstrip('#'))
                result.append(Paragraph(self.inline(line[level:].strip()),
                                        self.title if level == 1 else self.h2 if level == 2 else self.h3))
            elif line.startswith('```'):
                block = []
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    block.append(lines[i]); i += 1
                i += 1
                code = textwrap.dedent('\n'.join(block)); wrapped = []
                max_chars = int((WIDTH-18-14)/pdfmetrics.stringWidth('M','PrintCode',9))
                for command in code.splitlines():
                    wrapped.extend(textwrap.wrap(normalize(command),width=max_chars,
                        subsequent_indent='    ',break_long_words=True,break_on_hyphens=False) or [''])
                result.append(Preformatted('\n'.join(wrapped),self.code))
            elif line.startswith('|'):
                rows = []; i -= 1
                while i < len(lines) and lines[i].strip().startswith('|'):
                    cells = [v.strip() for v in lines[i].strip().strip('|').split('|')]
                    if not all(re.fullmatch(r':?-+:?',v) for v in cells): rows.append(cells)
                    i += 1
                table = self.table(rows)
                previous = []
                if result and isinstance(result[-1],Paragraph) and result[-1].getKeepWithNext():
                    previous = [result.pop()]
                result.append(KeepTogether(previous+[table,Spacer(1,9)]))
            else:
                marker = None; indent = 18 if raw.startswith('   ') else 0
                match = re.match(r'^(\d+\.|-) (.*)',line)
                if match:
                    marker, line = match.groups(); indent = 18
                while i < len(lines) and lines[i].strip() and not special(lines[i].strip()):
                    line += ' '+lines[i].strip(); i += 1
                result.append(self.paragraph(line,indent,marker))
        if self.references:
            references = [Paragraph('Referenced files',self.h2),
                self.paragraph('Repository paths below remain useful on paper. '
                               'The digital PDF also retains clickable links.')]
            reference_style = ParagraphStyle('Reference',parent=self.body,fontSize=9.5,
                                             leading=12,spaceAfter=5)
            for number,(label,target) in enumerate(self.references,1):
                path = (self.source.parent/target).resolve()
                try: path_text = path.relative_to(ROOT).as_posix()
                except ValueError: path_text = str(path)
                references.append(Paragraph(f'<b>[{number}] {escape(label)}</b><br/>'
                    f'<font name="PrintCode" size="8.5">{escape(path_text)}</font>',reference_style))
            result.append(KeepTogether(references))
        return result


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#b4bdc5')); canvas.setLineWidth(.4)
    canvas.line(48,40,letter[0]-48,40)
    canvas.setFillColor(colors.HexColor('#485762')); canvas.setFont('PrintBody',8)
    canvas.drawString(48,27,'STR8-N | rc1 source development')
    canvas.drawRightString(letter[0]-48,27,f'Page {doc.page}')
    canvas.restoreState()


def source_appendices(renderer):
    """Join exact source lines to observed pass-two addresses and bytes."""
    folder = ROOT/'BUILD/rc1-dev-samples/listings'
    receipt = json.loads((folder/'listing-report.json').read_text())
    assert receipt['passed'] and not receipt['board_access']
    for name,digest in receipt['files'].items():
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest() == digest
    specs = [
        ('A', 'SXB CS0-CS3 patterns', 'sxb-cs-patterns',
         'Ready BRK: line 530. Step the NOP at line 540. Finished BRK: line 770. '
         'Dwell edit: line 170 (BURST_BATCHES = $40 to $20).', '170 BURST_BATCHES = $40'),
        ('B', 'EDU: 31 LED patterns', 'edu-led31',
         'Ready BRK: line 1420. Step the NOP at line 1430. Finished BRK: line 1680. '
         'Dwell edit: line 290 (DWELL_OUTER = $FF to $80).', '290 DWELL_OUTER = $FF'),
    ]
    result = []; provenance = []
    style = ParagraphStyle('SourceListing', fontName='PrintCode', fontSize=8.2,
                           leading=11, spaceBefore=4, spaceAfter=0, textColor=INK)
    for letter_id, title, stem, guide, edit_line in specs:
        numbered = ROOT/'examples/source-cycle'/(stem+'.numbered.txt')
        assembly = numbered.with_name(stem+'.asm')
        lines = numbered.read_text(encoding='utf-8').splitlines()
        assert lines == [f'{(i+1)*10} {line}' for i,line in
                         enumerate(assembly.read_text(encoding='utf-8').splitlines())]
        assert edit_line in lines, 'Workbook edit example no longer matches source'
        report = json.loads((folder/(stem+'.json')).read_text())
        assert report['source_sha256'] == hashlib.sha256(assembly.read_bytes()).hexdigest()
        rows = report['records']
        assert [f'{r["line"]} {r["source"]}' for r in rows] == lines
        formatted = (folder/(stem+'.lst')).read_text().splitlines()[2:]
        assert max(pdfmetrics.stringWidth(line,'PrintCode',8.2) for line in formatted) <= WIDTH-12
        start = 0
        while start < len(rows):
            stop = min(start+(44 if start == 0 else 50),len(rows))
            chunk = formatted[start:stop]
            first = rows[start]['line']; last = rows[stop-1]['line']
            result.append(PageBreak())
            result.append(Paragraph(f'Appendix {letter_id}: {escape(title)}'+
                (' (continued)' if start else ''),renderer.h2))
            result.append(renderer.paragraph(
                f'Editor lines {first}-{last} | `{stem}.numbered.txt`'))
            if not start:
                result.append(renderer.paragraph(
                    'LINE is the decimal editor number. ADDR and bytes are hexadecimal, observed '
                    'from ASM pass 2 and checked against the tested binary. Comments and constant definitions emit no bytes. '
                    'For definitions, ADDR is the current assembly PC; the value is the expression on the right. '
                    'Use the plain numbered text for editor input; this listing has extra columns.'))
                result.append(renderer.paragraph(guide))
            result.append(Preformatted('LINE ADDR MACHINE CODE             SOURCE\n'
                                      '---- ---- -----------------------  ------\n'+'\n'.join(chunk),style))
            start = stop
        provenance.append(dict(source=str(numbered),lines=len(lines),
            source_sha256=hashlib.sha256(numbered.read_bytes()).hexdigest(),
            listing=str(folder/(stem+'.lst')),image_sha256=report['image_sha256']))
    result.extend(debug_reports(renderer,folder))
    return result, provenance


def debug_reports(renderer, folder):
    result = []
    mono = ParagraphStyle('DebugReport',fontName='PrintCode',fontSize=8.5,leading=10.5,
                           spaceAfter=7)
    for stem,title in [('sxb-cs-patterns','SXB'),('edu-led31','EDU')]:
        report = json.loads((folder/(stem+'.json')).read_text())
        symbols = {s['name'].lower():s for s in report['symbols']}
        result += [PageBreak(),Paragraph(f'Appendix C: {title} debugger address guide',renderer.h2)]
        result.append(renderer.paragraph(
            'All addresses below are CPU RAM addresses. BRK is two bytes: the debugger stops '
            'with PC pointing after the signature byte. The listing shows the BRK opcode address.'))
        ready = symbols['ready']['address']; done = symbols['done']['address']
        dwell = symbols['burst' if stem == 'sxb-cs-patterns' else 'delay']['address']
        delta = report['edit_delta'][0]
        constant='BURST_BATCHES' if stem=='sxb-cs-patterns' else 'DWELL_OUTER'
        definition=next(r['line'] for r in report['records'] if r['source'].startswith(constant+' ='))
        rows = [['Debugger reference','Address / expected bytes'],
            ['Entry / emitted image',f'$0200 / ${report["origin"]:04X}-${report["end"]:04X}; {report["code_bytes"]} bytes'],
            ['Ready BRK opcode',f'${ready:04X}: 00 01'],
            ['First DBG> PC / NOP',f'${ready+2:04X}: EA'],
            ['PC after S on the NOP',f'${ready+3:04X}'],
            ['Finished BRK opcode',f'${done:04X}: 00 02'],
            ['Finished DBG> PC / HOLD',f'${done+2:04X}: 4C 67 7E'],
            ['Dwell LDX instruction',f'${dwell:04X}: A2 {delta["before"]:02X}'],
            [f'Edit definition line {definition}',
             f'${delta["address"]:04X}: {delta["before"]:02X} -> {delta["after"]:02X} (operand only)'],
            ['Pattern table',f'${symbols["patterns"]["address"]:04X}-${symbols["frame"]["address"]-1:04X}'],
            ['Source/example sizes',f'{len(report["records"])} numbered lines; {report["code_bytes"]} emitted bytes']]
        result += [renderer.table(rows),Spacer(1,8)]
        result.append(renderer.paragraph(
            'The edited version has the same length, code/data labels and instruction addresses; exactly one '
            'operand byte changes. These addresses apply to both the original and dwell-edited versions. '
            'Setting a breakpoint on pattern bytes or state is not an instruction breakpoint.'))
        result.append(Paragraph('Code/data labels (actual ASM RAM symbol records)',renderer.h3))
        result.append(Preformatted((folder/(stem+'.sym.txt')).read_text().rstrip(),mono))
        result.append(renderer.paragraph('Symbol and listing files: '
            f'`BUILD/rc1-dev-samples/listings/{stem}.sym.txt` and `{stem}.lst`.'))
    for stem,title in [('sxb-cs-patterns','SXB'),('edu-led31','EDU')]:
        result += [PageBreak(),Paragraph(f'Appendix D: {title} image and S-record export',renderer.h2)]
        result.append(renderer.paragraph(
            'Baseline image before the dwell edit. The dump is the assembled RAM image, including '
            'pattern data and state. S-record addresses, checksums and entry $0200 are preserved.'))
        result.append(Paragraph('RAM dump: address, hexadecimal bytes, ASCII',renderer.h3))
        result.append(Preformatted((folder/(stem+'.hex.txt')).read_text().rstrip(),mono))
        result.append(Paragraph('S19 loader text',renderer.h3))
        result.append(Preformatted((folder/(stem+'.s19')).read_text().rstrip(),mono))
    status = json.loads((folder.parent/'development-status.json').read_text())
    receipt = json.loads((folder/'listing-report.json').read_text())
    result += [PageBreak(),Paragraph('Appendix E: original prototype qualification',renderer.h2)]
    result.append(renderer.paragraph(
        'The address/byte listings were collected by observing the linked ASM 0.5 second pass '
        'in the CPU models. Symbols were read from its resulting RAM symbol table. '
        'No alternate assembler or guessed instruction lengths were used.'))
    rows = [['Check','Result'],
        ['Listing capture','PASS: original and dwell-edited sources on both CPU models; 8 assemblies'],
        ['Binary identity','PASS: both baseline images match all 16 previously qualified binaries'],
        ['Source coverage','PASS: all 123 SXB and 243 EDU lines mapped, including constants/comments/data/END'],
        ['Edited variant','PASS: exactly one operand byte changes per sample; no addresses move'],
        ['CPU / monitor / EDU matrix','65C02 and 65C816 E=1; MON A/B; EDU OFF/ON'],
        ['Source-development cases',f'PASS: {status["sample_cases"]} cases'],
        ['Complete display executions',f'PASS: {status["full_display_executions"]}; dwell loops reduced for long runs'],
        ['Full original dwell routines',f'PASS: {status["full_dwell_instruction_cases"]} single-dwell instruction checks'],
        ['EDU-absent paths',f'PASS: {status["EDU_absent_refusals"]} refusals without sample PIA access'],
        ['S19 exports',f'PASS: {status["checked_S19_exports"]} original exports checked'],
        ['Preserving installer',f'PASS: {status["installer_checks"]} offline checks; hardware admission remains held']]
    result += [renderer.table(rows),Spacer(1,9)]
    for stem in ('sxb-cs-patterns','edu-led31'):
        sample = json.loads((folder/(stem+'.json')).read_text())
        result.append(renderer.paragraph(f'**{stem}:** {sample["code_bytes"]} bytes. Baseline SHA-256:'))
        result.append(Preformatted(sample['image_sha256'],mono))
    result.append(renderer.paragraph('Original prototype firmware SHA-256 (historical listing provenance):'))
    result.append(Preformatted(receipt['firmware_sha256'],mono))
    result.append(renderer.paragraph(
        'The companion `STR8N-Source-Debug-Listings.zip` contains plain source, numbered input, '
        'original and edited .lst/.bin files, symbol maps, RAM dumps, S19 exports and JSON receipts. '
        'The existing edit-save-load-debug tests are summarized here; they were not repeated merely '
        'to format this document. Listing capture and both edit deltas were newly checked.'))
    result.append(renderer.paragraph(
        'These original prototype checks used no boards. The current combined candidate and '
        'the separately authorized board 2604 trial are recorded in Appendix G.'))
    result.extend(walkthrough_appendices(renderer))
    return result


def walkthrough_appendices(renderer):
    folder=ROOT/'BUILD/rc1-dev-samples'
    proof=json.loads((folder/'walkthroughs.json').read_text())
    assert proof['passed']
    mono=ParagraphStyle('Walkthrough',fontName='PrintCode',fontSize=9,leading=13,spaceAfter=9)
    result=[]
    for stem,title,ready,bp,dump in [
        ('sxb-cs-patterns','SXB CS0-CS3','021E','0241','02C7: 01 01'),
        ('edu-led31','EDU 31 patterns','0252','0272','0391: 01 00')]:
        rows=next(c['commands'] for c in proof['cases'] if c['cpu']=='65c02' and c['slot']=='B' and c['sample']==stem)
        result += [PageBreak(),Paragraph('Appendix F: '+title+' debugger walkthrough',renderer.h2)]
        result.append(renderer.paragraph(
            'Use the original bounded binary in Appendix A/B, assembled at $0200. For the looping '
            'EDU program on 2604 use Appendix J instead. SXB CS windows have no '
            'external hardware attached. EDU must be enabled for its sample. Commands below are '
            'entered individually; addresses, bytes and registers are hexadecimal. Editor line numbers '
            'are decimal. S is the stack pointer. Type text after the prompt and before any semicolon; '
            'semicolon suffixes below are explanatory notes.'))
        name='E311' if stem=='edu-led31' else 'CS1'
        size=403 if stem=='edu-led31' else 201
        result.append(Preformatted(
            f'B3> ASM\nASM> LOAD FLASH {name}   ; expect Source loaded\n'
            f'ASM> ASM               ; expect OK {size} bytes\nASM> QUIT\n'
            f'B3> G 0200             ; ready BRK: PC={ready}',mono))
        result.append(renderer.paragraph(
            'If the document is dirty, answer YES to the load confirmation. The launch registers can '
            'inherit monitor state. Set a repeatable starting context at the ready stop:'))
        result.append(Preformatted('DBG> R A=00\nDBG> R X=00\nDBG> R Y=00\nDBG> R P=24\nDBG> R S=FF',mono))
        table=['COMMAND          PC    A  X  Y  P  S','---------------  ----  -- -- -- -- --']
        for row in rows[6:]:
            cmd=row['command'];regs=row['registers']
            if regs:table.append(f'{cmd:<15}  '+ '  '.join(regs[k] for k in ('PC','A','X','Y','P','S')))
            else:
                text=('B3> (HOLD returns)' if row['context']=='monitor' else
                      'set persistent breakpoint' if cmd.startswith('B ') else
                      'clear persistent breakpoint' if cmd.startswith('BC ') else
                      dump if cmd.startswith('D ') else 'disassemble four instructions')
                table.append(f'{cmd:<15}  {text}')
        result.append(Preformatted('\n'.join(table),mono))
        result.append(renderer.paragraph(
            ('B 0272 stops before the LED write with A=$01. S writes the first frame; N runs the '
             'complete delay and returns to $0278. The final C finishes all 248 frames and stops at '
             '$028B after BRK $02; A=$00 shows the sampled entry value has been restored.'
             if stem=='edu-led31' else
             'B 0241 stops before JSR burst with mask=$01. N runs the complete burst and returns to '
             '$0244. The following S commands increment and load frame 1. The final C finishes '
             'all 64 frames and stops at $0251 after BRK $02.')))
        result.append(renderer.paragraph(
            'BRK consumes its signature byte, so the saved PC is two bytes after the BRK opcode. '
            'P=$34/$36/$37 includes the BRK status bit. Clearing the persistent breakpoint before '
            'the final C avoids stopping on every frame. The last C executes JMP HOLD and returns '
            'to B3>. Both CPU models and both monitor slots produce these normalized states.'))
    result += [PageBreak(),Paragraph('Appendix F: edit, reassemble and repeat',renderer.h2)]
    result.append(renderer.paragraph(
        'The hardware trial leaves CS1/CS2 and E311/E312 in flash. LOAD can reuse those names. '
        'A new SAVE needs a fresh name and erased space: one sector for SXB, two consecutive sectors for EDU. The commands '
        'below use CS3/E313 for the next edit. Use another unused name if those already exist. '
        'Type only the command before each semicolon; the remaining text is a note.'))
    for stem,title,original,fresh,edit,operand,value,size,ready in [
        ('sxb-cs-patterns','SXB','CS1','CS3','170 BURST_BATCHES = $20','0255','20',201,'021E'),
        ('edu-led31','EDU','E311','E313','290 DWELL_OUTER = $80','028F','80',403,'0252')]:
        result.extend([Spacer(1,7),Paragraph(title,renderer.h3)])
        result.append(Preformatted(
            f'B3> ASM\nASM> NEW\nASM> PASTE              ; current host source, then .\nASM> {edit}\n'
            f'ASM> SAVE FLASH {fresh}   ; Source saved\nASM> NEW\n'
            f'ASM> LOAD FLASH {fresh}   ; discard confirmation follows\n'
            f'     YES                ; answer Type YES; Source loaded\nASM> ASM                ; OK {size} bytes\n'
            f'ASM> QUIT\nB3> D {operand} {operand}       ; {operand}: {value}\n'
            f'B3> G 0200              ; PC={ready}',mono))
    result.append(renderer.paragraph(
        'Existing CS1/CS2 and E311/E312 records contain the earlier source edition and line numbers. '
        'Use current host source for this exercise. Board 2604 has only B0:C/D erased: choose '
        'either save exercise; both together need three sectors. '
        'Repeat the five R assignments and the preceding debugger table. Only the dwell operand '
        'changes; all stop addresses and normalized registers remain the same. Baseline/edited '
        'listings and exact changed bytes appear in Appendix C. SAVE and LOAD use output RAM as '
        'scratch, so always assemble after the last SAVE or LOAD.'))
    result.append(renderer.paragraph(
        'Status $50 means the flash name already exists. LOAD it, or choose a new name; do not '
        'erase a source sector to repeat this exercise. During the running EDU animation, Ctrl-C '
        'requests cleanup at a frame boundary and stops at $028B with A=$00. Its frame counter '
        'then records a partial pass. If only DBG> appears after Ctrl-C, enter R to display the '
        'saved registers. C returns to the monitor.'))
    result.extend(hardware_report_appendix(renderer,mono,proof))
    result.extend(console_edit_appendix(renderer,mono))
    result.extend(looping_edu_appendix(renderer))
    return result


def hardware_report_appendix(renderer,mono,proof):
    run=Path((ROOT/'BUILD/rc1-maint-source-active-run.txt').read_text().strip())
    build=json.loads((ROOT/'BUILD/rc1-maint-source/maint-source-build.json').read_text())
    result=[PageBreak(),Paragraph('Appendix G: combined build and board 2604 trial',renderer.h2)]
    result.append(renderer.paragraph(
        'Combined MAINT/ASM candidate: named source save/load plus DEBUG/source CRC map labels '
        'and MAINT source/firmware range protection. Existing private utility entry addresses stay '
        'fixed. Menu alignment spaces were reclaimed to keep the image within its original domain.'))
    result.append(renderer.table([['Item','Actual size / location'],
        ['Source extension','2,661 code/data bytes + 2-byte CRC in B1:$9000-$9FFF; 1,433 bytes free'],
        ['Storage adapter','95 bytes in the B2 utility image'],
        ['MAINT net growth',f'{build["maintenance_added_bytes"]} bytes versus source prototype; {build["utility_free_bytes"]} bytes free before $D7FE CRC'],
        ['Total feature growth','2,790 bytes including the source-sector CRC versus released v1g'],
        ['Preserving install','8 firmware sectors + 2 wear/config journal sectors; B0 and B3:9 retained']]))
    result.append(renderer.paragraph('Combined MAINT/ASM trial image SHA-256 (before the Appendix H update):'))
    result.append(Preformatted(build['firmware_sha256'],mono))
    path=run/'hardware-test/report.json'
    if path.exists():
        report=json.loads(path.read_text());install=json.loads((run/'flash-report.json').read_text())
        assert report['passed'] and install['passed'] and proof['firmware_sha256']==build['firmware_sha256']
        result.append(renderer.table([['Hardware check','Result'],
            ['Board / CPU / monitor','2604 / 65C02 / MON B generation 50'],
            ['Flash verification','PASS: all four banks match the preserving transaction'],
            ['Preserved owner data','PASS: startup settings, preference, B0 before source tests, RTC TZ history'],
            ['MAINT','PASS: map and reserved source/firmware erase refusals'],
            ['Source cycles','PASS: CS1/CS2 and E311/E312 save/load, edit, exact onboard ASM'],
            ['Saved source documents','E311/E312 at B0:8/9; CS1/CS2 at B0:A/B. B0:C/D remain erased.'],
            ['Debugger walkthroughs','PASS: both samples; normalized register stops match the CPU models'],
            ['EDU LED test','PASS: 31 patterns / 248 writes and LED-port readbacks; original dwell'],
            ['EDU cancellation','PASS: Ctrl-C cleanup and entry LED restoration before finished BRK'],
            ['Original application RAM','PASS: restored in full and reread twice after each trial'],
            ['2609 / bare SXB','Offline CPU/peripheral models only; no physical trial in this request']]))
        result.append(renderer.paragraph(
            'The unmodified EDU sample completed first. A separate temporary RAM probe captured '
            'every LED write and data-port readback plus CRA, with no control/DDR writes. This proves '
            'the port values; visible light was not independently observed. CS windows had no '
            'external hardware attached. All probe RAM was restored. No RTC or soak campaign resumed.'))
        result.append(renderer.paragraph('Hardware receipt: `'+str(path.relative_to(ROOT)).replace('\\','/')+'`'))
    else:result.append(renderer.paragraph('Board trial pending; do not interpret offline checks as completed hardware testing.'))
    return result


def console_edit_appendix(renderer,mono):
    run=Path((ROOT/'BUILD/rc1-console-edit-active-run.txt').read_text().strip())
    install=json.loads((run/'flash-report.json').read_text())
    keys=json.loads((run/'hardware-key-tests.json').read_text())
    build=json.loads((ROOT/'BUILD/rc1-console-edit/console-edit-build.json').read_text())
    marker=json.loads((ROOT/'output/qualification/device-operations/2604.json').read_text())
    demo_path=Path(marker['owner_application_run'])/'report.json'
    demo=json.loads(demo_path.read_text())
    assert install['passed'] and keys['passed'] and demo['passed']
    assert install['firmware_sha256']==build['firmware_sha256']
    result=[PageBreak(),Paragraph('Appendix H: Backspace and Delete',renderer.h2)]
    result.append(renderer.paragraph(
        'Installed and tested on board 2604, 21 October 2026 (65C02, EDU enabled, '
        'Monitor B generation 50). Both ASM and DBG now support the same end-of-line '
        'deletion. The version titles remain 2.0rc1 and ASM 0.5.'))
    result.append(renderer.table([['Input','Behavior in ASM and DBG'],
        ['Backspace / ASCII 08','Remove the last entered character'],
        ['DEL / ASCII 7F','Remove the last entered character'],
        ['Terminal Delete / Esc [ 3 ~','Remove the last entered character'],
        ['Visible erase','Echo 08 20 08: backspace, space, backspace'],
        ['Empty input','Deletion does nothing; no error or erase echo']]))
    result.append(renderer.paragraph(
        'These keys edit the end of the input line. They do not move a cursor or recall '
        'history. Other CSI escape sequences are ignored. Deletion can recover from an '
        'overlong input line; ASM paste input is edited without screen-erasure echo. '
        'These additional cases passed offline on both CPU configurations and both monitor slots.'))
    result.append(Paragraph('Try a source correction',renderer.h3))
    result.append(renderer.paragraph(
        'Start at an idle B3 monitor. In the example below, [BS] means press Backspace; '
        'do not type the brackets or letters. Press Enter only after the final 3. '
        'Substitute DEL or terminal Delete to repeat the same correction.'))
    result.append(Preformatted('B3> ASM\nASM> NEW\nASM> 10 LDA #$12[BS]3\nASM> LIST\n      10 LDA #$13',mono))
    result.append(renderer.paragraph(
        'The final 2 is erased before the 3 is entered. LIST must show LDA #$13. '
        'NEW replaces the current working source, so save any wanted edits first. '
        'This exercise writes no flash. Reassemble after any source change.'))
    result.append(Paragraph('Try a debugger correction',renderer.h3))
    result.append(Preformatted('DBG> R A=13[BS]2     ; A=12\nDBG> R X=34[DEL]5    ; X=35\nDBG> R Y=67[Delete]8 ; Y=68\nDBG> R',mono))
    result.append(renderer.paragraph(
        'Bracketed names mean key presses. The physical test stopped a six-byte test '
        'program at PC=$0203. Final saved state: PC=0203 A=12 X=35 Y=68 P=B4 S=FF. '
        'Your PC and flags depend on the program you stopped; the R assignments change '
        'only their named register.'))
    result.extend([PageBreak(),Paragraph('Appendix H: 2604 verification results',renderer.h2)])
    result.append(renderer.table([['Check','Verified result'],
        ['Preserving flash update','PASS: four firmware sectors, six transfers including two journal sectors'],
        ['Full flash readback','PASS: all four banks match the planned transaction'],
        ['Saved source records','PASS: B0 unchanged, including E311/E312 and CS1/CS2'],
        ['Owner state','PASS: settings, monitor preference and RTC TZ history preserved'],
        ['ASM keyboard tests','PASS: BS, DEL and terminal Delete; edited source, visible erase, empty input'],
        ['DBG keyboard tests','PASS: all three inputs; register corrections, visible erase, empty input'],
        ['After keyboard tests','PASS: flash unchanged and original application RAM restored'],
        ['EDU loop restart','PASS: exact onboard assembly, cancellation, full 31-pattern pass and wrap'],
        ['Current timing','Approximately 82 ms/frame, 20.4 seconds per 248-frame pass'],
        ['Other board / models','2609 unchanged; offline checks cover bare SXB/EDU and both CPU configurations']]))
    result.append(renderer.paragraph(
        'The console editing patch adds 85 ASM bytes and 81 debugger bytes: 166 bytes '
        'total. Existing entry addresses remain fixed; the debugger sector has 38 bytes '
        'free. Updated sectors: B1:$A000, B1:$E000, B1:$F000 and B3:$E000. '
        'Named constants continue to use name = expression; EQU support is not included.'))
    result.append(renderer.paragraph('Installed firmware image SHA-256:'))
    result.append(Preformatted(build['firmware_sha256'],mono))
    result.append(renderer.paragraph(
        'The earlier appendices retain the original bounded sample listings and their '
        'stop addresses. The restarted looping EDU variant is 430 bytes at $0200-$03AD, '
        'with DWELL_CHUNKS=$02. Its ready stop is $0252; Ctrl-C requests cleanup and '
        'stops at $0293 with A=$00. If only DBG> appears, enter R. Then C returns to B3. '
        'Use these loop addresses rather than the bounded sample finished stop $028B.'))
    result.append(renderer.paragraph(
        'The loop was left running at the test handoff. A complete pass and wrap were '
        'verified from serial output; this restart did not repeat the earlier independent '
        '248-write LED-port trace. No CS-window hardware was attached. No RTC or soak '
        'campaign resumed.'))
    for title,path in [('Preserving install',run/'flash-report.json'),
                       ('Six physical key tests',run/'hardware-key-tests.json'),
                       ('Loop restart',demo_path)]:
        result.append(renderer.paragraph(title+': `'+path.relative_to(ROOT).as_posix()+'`'))
    return result


def looping_edu_appendix(renderer):
    folder=ROOT/'BUILD/rc1-edu-loop/workbook'
    report=json.loads((folder/'listing.json').read_text())
    proof=json.loads((folder/'walkthrough.json').read_text())
    assert proof['passed'] and proof['image_sha256']==report['image_sha256']
    source=ROOT/'examples/source-cycle/edu-led31-loop.asm'
    assert proof['source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert [r['source'] for r in report['records']]==source.read_text().splitlines()
    rows=report['records'];formatted=(folder/'edu-led31-loop.lst').read_text().splitlines()[2:]
    style=ParagraphStyle('LoopListing',fontName='PrintCode',fontSize=8.2,leading=11,spaceAfter=0)
    mono=ParagraphStyle('LoopDebug',fontName='PrintCode',fontSize=8.5,leading=11,spaceAfter=8)
    result=[];start=0
    while start<len(rows):
        stop=min(start+(40 if start==0 else 50),len(rows))
        result.extend([PageBreak(),Paragraph('Appendix I: current looping EDU source'+(' (continued)' if start else ''),renderer.h2)])
        result.append(renderer.paragraph(f'Editor lines {rows[start]["line"]}-{rows[stop-1]["line"]} | `edu-led31-loop.numbered.txt`'))
        if start==0:
            result.append(renderer.paragraph(
                'This is the named-constant source sent to board 2604 and left looping. '
                'It emits 430 bytes at $0200-$03AD, with DWELL_CHUNKS=$02: about 82 ms/frame '
                'and 20.4 seconds/pass. All lines, addresses and bytes were observed from '
                'linked onboard ASM pass 2 on both CPU models and match the hardware run image. '
                'Definitions emit no bytes; their ADDR is the current assembly PC.'))
        result.append(Preformatted('LINE ADDR MACHINE CODE             SOURCE\n---- ---- -----------------------  ------\n'+'\n'.join(formatted[start:stop]),style))
        start=stop
    result.extend([PageBreak(),Paragraph('Appendix J: current EDU debugger walkthrough',renderer.h2)])
    result.append(renderer.paragraph(
        'Use this walkthrough for the looping program running on 2604. Appendix F describes '
        'the earlier bounded samples. The loop never reaches its finished stop by completing '
        'one pass: it returns to frame zero and repeats. Ctrl-C requests cleanup.'))
    result.append(renderer.paragraph(
        'To begin from the live display, press Ctrl-C, wait for DBG>, enter R and confirm '
        'PC=0293 A=00. Enter C to return to B3. Then reload the pristine current source so '
        'the frame, entry and ticks state bytes start at zero:'))
    result.append(Preformatted('B3> ASM\nASM> NEW\nASM> PASTE       ; send edu-led31-loop.asm, then .\nASM> ASM         ; OK 430 bytes\nASM> QUIT\nB3> G 0200       ; ready stop PC=0252',mono))
    result.append(renderer.paragraph(
        'Do not LOAD FLASH E311/E312 for this walkthrough: those records contain the older '
        'bounded source. At the ready stop, normalize the saved context with these commands:'))
    result.append(Preformatted('R A=00\nR X=00\nR Y=00\nR P=24\nR S=FF',mono))
    table=['COMMAND          PC    A  X  Y  P  S','---------------  ----  -- -- -- -- --']
    commands=proof['cases'][0]['commands']
    for row in commands[6:]:
        if row['command']=='C then Ctrl-C':break
        reg=row['registers'];cmd=row['command']
        if reg:table.append(f'{cmd:<15}  '+'  '.join(reg[k] for k in ('PC','A','X','Y','P','S')))
        else:table.append(f'{cmd:<15}  '+('set LED-write breakpoint' if cmd.startswith('B ') else 'clear LED-write breakpoint' if cmd.startswith('BC ') else '03AB: 01 00 00' if cmd.startswith('D ') else 'disassemble four instructions'))
    result.append(Preformatted('\n'.join(table),mono))
    result.append(renderer.paragraph(
        'B 0272 stops before STA LED_DATA with A=01. S writes frame zero. N executes '
        'the complete two-chunk delay and returns to $0278; S tests cancellation and '
        'the next S increments frame to 1. Both CPU models execute the original delay '
        'without acceleration and produce the same normalized register states.'))
    result.extend([PageBreak(),Paragraph('Appendix J: loop, cancellation and addresses',renderer.h2)])
    result.append(renderer.table([['Reference','Address / expected bytes'],
        ['Ready BRK / saved PC','$0250: 00 01 / PC=$0252'],
        ['LED write / step return','$0272: 8D A0 7F / PC=$0275'],
        ['Delay call / return','$0275: 20 96 02 / PC=$0278'],
        ['Pass wrap: reset frame','$0284: 9C AB 03 (STZ frame)'],
        ['Pass wrap: restart','$0287: 4C 53 02 (JMP next)'],
        ['Cleanup / restore LEDs','$028A: EA; $028B: AD AC 03; $028E: 8D A0 7F'],
        ['Finished BRK / saved PC','$0291: 00 02 / PC=$0293'],
        ['Return through HOLD','$0293: 4C 67 7E'],
        ['Pattern table','$02B3-$03AA; 248 bytes'],
        ['State bytes','frame=$03AB, entry=$03AC, ticks=$03AD']]))
    result.append(Paragraph('Continue the loop, stop cleanly, restart',renderer.h3))
    result.append(Preformatted('DBG> C           ; after BC 0272; display loops\n                 ; 01 through 1F, then 01 again\n[press Ctrl-C]   ; request cleanup\nDBG> R           ; PC=0293 A=00 for zero entry LEDs\nDBG> D 03AB 03AD  ; partial frame, entry LED, ticks\nDBG> C           ; execute JMP HOLD; return B3>',mono))
    result.append(renderer.paragraph(
        'Cancellation timing determines the partial frame, X, Y and flags. A=00 is the '
        'expected restored entry LED value for the tested zero-entry setup; generally A '
        'equals the value saved at $03AC. Do not expect the normalized stepping table '
        'to describe arbitrary live-launch or cancellation registers. If only DBG> '
        'appears, R displays the saved context. Avoid X during LED output because it '
        'bypasses application cleanup.'))
    result.append(renderer.paragraph(
        'To restart a fresh complete loop, repeat the source assembly and G 0200 above, '
        'then C at the ready stop. A full pass and wrap plus cancellation were verified '
        'on board 2604 at the unchanged two-chunk delay. The current source and binary '
        'SHA-256 values match that run; this workbook update accessed no board.'))
    result.append(renderer.paragraph('Current program SHA-256:'))
    result.append(Preformatted(report['image_sha256'],mono))
    result.append(renderer.paragraph('Hardware run: `'+Path(proof['current_board_run']).relative_to(ROOT).as_posix()+'/report.json`'))
    result.append(renderer.paragraph('Offline listing and walkthrough: `BUILD/rc1-edu-loop/workbook/`'))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workbook-only', action='store_true')
    args = ap.parse_args()
    fonts(); OUTPUT.mkdir(parents=True,exist_ok=True)
    manifest = OUTPUT/'source-development-pdfs.json'
    records = json.loads(manifest.read_text()) if args.workbook_only and manifest.exists() else []
    for source_name, output_name in DOCUMENTS.items():
        if args.workbook_only and source_name != 'SOURCE_DEVELOPMENT_WORKBOOK.md': continue
        source = ROOT/'docs/rc1'/source_name; target = OUTPUT/output_name
        doc = SimpleDocTemplate(str(target),pagesize=letter,leftMargin=48,rightMargin=48,
            topMargin=43,bottomMargin=54,title=source.read_text().splitlines()[0][2:],
            author='STR8-N',pageCompression=1)
        renderer = Renderer(source); story = renderer.story(); listings = []
        if source_name == 'SOURCE_DEVELOPMENT_WORKBOOK.md':
            appendices,listings = source_appendices(renderer); story.extend(appendices)
        doc.build(story,onFirstPage=footer,onLaterPages=footer)
        records = [r for r in records if r['pdf'] != str(target)]
        records.append(dict(source=str(source),pdf=str(target),listings=listings,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            pdf_sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
        print(target)
    manifest.write_text(json.dumps(records,indent=2)+'\n')


if __name__ == '__main__': main()
