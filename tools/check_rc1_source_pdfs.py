import collections
import hashlib
import json
from pathlib import Path
import re
import zipfile

import pdfplumber
from pypdf import PdfReader

root = Path('C:/SRC/STR8-N')
out = root/'output/pdf'
folder = root/'BUILD/rc1-dev-samples/listings'
pdf = out/'STR8N-Source-Development-Workbook.pdf'
reader = PdfReader(pdf)
assert len(reader.pages) >= 19
text = [p.extract_text() or '' for p in reader.pages]
normal = lambda value: ' '.join(value.split())
def pages_with(title):return [i+1 for i,p in enumerate(text) if title in normal(p)]
def page_with(title):
    matches=pages_with(title);assert len(matches)==1,(title,matches);return matches[0]
a_pages=pages_with('Appendix A: SXB CS0-CS3 patterns')
b_pages=pages_with('Appendix B: EDU: 31 LED patterns')
guides=[page_with('Appendix C: '+s+' debugger address guide') for s in ('SXB','EDU')]
dumps=[page_with('Appendix D: '+s+' image and S-record export') for s in ('SXB','EDU')]
reports = []
for stem,first,last,guide,dump in [
    ('sxb-cs-patterns',min(a_pages),max(a_pages),guides[0],dumps[0]),
    ('edu-led31',min(b_pages),max(b_pages),guides[1],dumps[1])]:
    report = json.loads((folder/(stem+'.json')).read_text())
    expected = (folder/(stem+'.lst')).read_text().splitlines()[2:]
    actual = [line for page in text[first-1:last] for line in page.splitlines()
              if re.match(r'^\s*\d+\s+(?:[0-9A-F]{4}|----)\s+',line)]
    assert list(map(normal,actual)) == list(map(normal,expected)),stem
    assert len(actual) == len(report['records'])
    image = (folder/(stem+'.bin')).read_bytes()
    assert hashlib.sha256(image).hexdigest() == report['image_sha256']
    assert b''.join(bytes.fromhex(r['bytes']) for r in report['records']) == image
    sy = {s['name'].lower():s['address'] for s in report['symbols']}
    for name,signature in [('ready',1),('done',2)]:
        address = sy[name]
        assert image[address-0x200:address-0x200+2] == bytes((0,signature))
        assert f'${address:04X}: 00 {signature:02X}' in text[guide-1]
    assert image[sy['ready']+2-0x200] == 0xEA
    assert image[sy['done']+2-0x200:sy['done']+5-0x200] == bytes.fromhex('4C 67 7E')
    for line in (folder/(stem+'.sym.txt')).read_text().splitlines():
        assert normal(line) in normal(text[guide-1]),line
    for line in (folder/(stem+'.hex.txt')).read_text().splitlines():
        assert normal(line) in normal(text[dump-1]),line
    rows = [line for line in text[dump-1].splitlines() if re.fullmatch(r'S[019](?:[0-9A-F]{2}){4,}',line)]
    assert rows == (folder/(stem+'.s19')).read_text().splitlines()
    cells = {}
    for row in rows:
        raw = bytes.fromhex(row[2:]); assert len(raw) == raw[0]+1 and sum(raw) & 255 == 255
        address = int.from_bytes(raw[1:3],'big')
        if row.startswith('S1'):
            for i,b in enumerate(raw[3:-1],address):
                assert i not in cells; cells[i] = b
        elif row.startswith('S9'): assert address == 0x200
    assert set(cells) == set(range(0x200,0x200+len(image)))
    assert bytes(cells[i] for i in sorted(cells)) == image
    reports.append(dict(sample=stem,source_lines=len(actual),listing_pages=[first,last],
        addresses_and_bytes_exact=True,symbol_table_exact=True,ram_dump_exact=True,
        printed_S19_checksums_and_image_verified=True,debugger_BRK_and_PC_addresses_verified=True))
source = (root/'docs/rc1/SOURCE_DEVELOPMENT_WORKBOOK.md').read_text()
source = re.sub(r'\[([^]]+)\]\([^)]+\)',r'\1',source)
source = re.sub(r'```[^\n]*','',source)
words = lambda s: collections.Counter(re.findall(r'[A-Za-z0-9_]+',s))
assert not (words(source)-words('\n'.join(text[:min(a_pages)-1])))
with pdfplumber.open(pdf) as doc:
    assert all(float(p.width) == 612 and float(p.height) == 792 for p in doc.pages)
    assert all(min(c['x0'] for c in p.chars)>=42 and max(c['x1'] for c in p.chars)<=576
               and min(c['top'] for c in p.chars)>=40 and max(c['bottom'] for c in p.chars)<=772
               for p in doc.pages)
assert all(f'Page {i+1}' in p for i,p in enumerate(text))
archive = out/'STR8N-Source-Debug-Listings.zip'
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for p in folder.iterdir():
        if p.is_file(): assert z.read('listings/'+p.name) == p.read_bytes()
prior = json.loads((out/'source-development-pdf-checks.json').read_text())
walkthrough = json.loads((root/'BUILD/rc1-dev-samples/walkthroughs.json').read_text())
assert walkthrough['passed']
walk_pages=[page_with('Appendix F: '+s+' debugger walkthrough') for s in ('SXB CS0-CS3','EDU 31 patterns')]
for stem,page in zip(('sxb-cs-patterns','edu-led31'),walk_pages):
    case=next(c for c in walkthrough['cases'] if c['cpu']=='65c02' and c['slot']=='B' and c['sample']==stem)
    printed=normal(text[page-1])
    for row in case['commands'][6:]:
        assert normal(row['command']) in printed
        if row['registers']:
            expected=row['command']+' '+' '.join(row['registers'][k] for k in ('PC','A','X','Y','P','S'))
            assert normal(expected) in printed,expected
    for command in ('R A=00','R X=00','R Y=00','R P=24','R S=FF'):
        assert command in text[page-1]
edit_page=page_with('Appendix F: edit, reassemble and repeat')
assert all(s in text[edit_page-1] for s in ('CS3','E313','D 0255 0255','D 028F 028F','170 BURST_BATCHES','290 DWELL_OUTER'))
g_page=page_with('Appendix G: combined build and board 2604 trial')
run=Path((root/'BUILD/rc1-maint-source-active-run.txt').read_text().strip())
assert json.loads((run/'flash-report.json').read_text())['passed']
assert json.loads((run/'hardware-test/report.json').read_text())['passed']
assert '248 writes and LED-port readbacks' in normal('\n'.join(text[g_page-1:]))
console=Path((root/'BUILD/rc1-console-edit-active-run.txt').read_text().strip())
assert json.loads((console/'flash-report.json').read_text())['passed']
key_report=json.loads((console/'hardware-key-tests.json').read_text())
assert key_report['passed'] and len(key_report['cases'])==6
added=normal('\n'.join(text[page_with('Appendix H: Backspace and Delete')-1:]))
for phrase in ('Appendix H: Backspace and Delete','08 20 08','166 bytes',
               'PC=0203 A=12 X=35 Y=68 P=B4 S=FF','20.4 seconds',
               '$0293','2609 unchanged','hardware-key-tests.json'):
    assert phrase in added,phrase
assert json.loads((root/'BUILD/rc1-console-edit/console-edit-build.json').read_text())['firmware_sha256'] in added
hardware=out/'STR8N-Source-Hardware-Test-Plan.pdf'
hr=PdfReader(hardware);ht=[p.extract_text() or '' for p in hr.pages]
md=(root/'docs/rc1/SOURCE_HARDWARE_TEST_PLAN.md').read_text()
md=re.sub(r'\[([^]]+)\]\([^)]+\)',r'\1',md)
md=re.sub(r'```[^\n]*','',md)
assert not (words(md)-words('\n'.join(ht)))
with pdfplumber.open(hardware) as doc:
    for p in doc.pages:
        assert float(p.width)==612 and float(p.height)==792
        assert min(c['x0'] for c in p.chars)>=42 and max(c['x1'] for c in p.chars)<=576
        assert min(c['top'] for c in p.chars)>=40 and max(c['bottom'] for c in p.chars)<=772
prior[1].update(pages=len(ht),pdf_sha256=hashlib.sha256(hardware.read_bytes()).hexdigest(),source_words_preserved=True,
    letter_size=True,text_within_print_margins=True,visual_review_passed=True)

loop_pages=pages_with('Appendix I: current looping EDU source')
loop_folder=root/'BUILD/rc1-edu-loop/workbook'
loop_listing=json.loads((loop_folder/'listing.json').read_text())
loop_proof=json.loads((loop_folder/'walkthrough.json').read_text())
assert loop_proof['passed'] and loop_proof['full_original_delay']
actual=[line for i in loop_pages for line in text[i-1].splitlines()
        if re.match(r'^\s*\d+\s+(?:[0-9A-F]{4}|----)\s+',line)]
assert list(map(normal,actual))==list(map(normal,(loop_folder/'edu-led31-loop.lst').read_text().splitlines()[2:]))
assert len(actual)==len(loop_listing['records'])
assert b''.join(bytes.fromhex(r['bytes']) for r in loop_listing['records'])==(root/'BUILD/rc1-edu-loop/program.bin').read_bytes()
assert loop_proof['source_sha256']==hashlib.sha256((root/'examples/source-cycle/edu-led31-loop.asm').read_bytes()).hexdigest()
current_walk=page_with('Appendix J: current EDU debugger walkthrough')
for row in loop_proof['cases'][0]['commands'][6:]:
    if row['command']=='C then Ctrl-C':break
    if row['registers']:
        expected=row['command']+' '+' '.join(row['registers'][k] for k in ('PC','A','X','Y','P','S'))
        assert normal(expected) in normal(text[current_walk-1]),expected
control=page_with('Appendix J: loop, cancellation and addresses')
for phrase in ('$0284: 9C AB 03','$0287: 4C 53 02','$0291: 00 02','PC=0293','DWELL_CHUNKS'):
    assert phrase in normal('\n'.join(text[min(loop_pages)-1:])),phrase
reports.append(dict(sample='edu-led31-loop',source_lines=len(actual),listing_pages=loop_pages,
                    addresses_and_bytes_exact=True,hardware_run_image_and_source_match=True,
                    full_delay_walkthrough_pages=[current_walk,control]))

prior[0].update(pages=len(text),pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),
    numbered_source_listings=reports,source_words_preserved=True,letter_size=True,
    text_within_print_margins=True,visual_review_passed=True,listing_bundle_verified=True,
    listing_bundle_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    guide_pages=guides,memory_dump_and_export_pages=dumps,qualification_report_page=page_with('Appendix E: original prototype qualification'),walkthrough_pages=walk_pages+[edit_page],current_hardware_report_pages=list(range(g_page,len(text)+1)),exact_debugger_commands_and_registers_verified=True)
(out/'source-development-pdf-checks.json').write_text(json.dumps(prior,indent=2)+'\n')
print(json.dumps(prior[0],indent=2))
