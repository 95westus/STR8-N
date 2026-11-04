"""Package accepted developer bytes locally; no compilation, serial or publish."""
import hashlib,json,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
OUT=ROOT/'BUILD/devtools-g2-candidate2-20261102-r2'
LABEL='STR8N-DEVTOOLS-g2-candidate2'
sha=lambda b:hashlib.sha256(b).hexdigest()

def run():
 out=OUT;out.mkdir();stage=out/LABEL;stage.mkdir()
 f=json.loads((REPO/'F_FREEZE.json').read_text())
 assert all(sha((REPO/n).read_bytes())==h for n,h in f['sources'].items())
 assert sha((REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==f['sha256']
 installed=ROOT/'output/qualification/2512-DBG-g2-installed-20261102-r1'
 receipt=json.loads((installed/'completion.json').read_text());assert receipt['passed']
 bank=(installed/'B0-after.bin').read_bytes()
 def put(name,body):
  dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(body)
 def text(name,body):put(name,body.encode('utf-8'))
 inputs={}
 for build,names in [('asm-flash-source-g2-r4',('ASM-RAM.bin','ASM-FLASH.bin','FLASH-SOURCE-7000.bin')),('dbg-base1-g2-r1',('DBG-RAM.bin','DBG-FLASH.bin'))]:
  folder=ROOT/'BUILD'/build;m=json.loads((folder/'manifest.json').read_text())
  for name in names:
   body=(folder/name).read_bytes();assert sha(body)==m['artifacts'][name]['sha256']
   put('payload/'+name,body);inputs[name]=dict(build=build,sha256=sha(body))
  put('provenance/'+build+'-manifest.json',(folder/'manifest.json').read_bytes())
 assert (stage/'payload/ASM-FLASH.bin').read_bytes()==bank[0x2000:0x4000]
 assert (stage/'payload/DBG-FLASH.bin').read_bytes()==bank[0x4000:0x6000]
 assert (stage/'payload/FLASH-SOURCE-7000.bin').read_bytes()==bank[0x5800:0x6000]
 for name in ('nf_console.py','console_core.py'):put('terminal/'+name,(REPO/'tools'/name).read_bytes())
 put('terminal/requirements.txt',(REPO/'requirements-console.txt').read_bytes())
 for name in ('SERIAL_CONSOLE.md','DBG_BROAD_2512_RAM.md','DBG_G2_2512_INSTALLED_ACCEPTANCE.md'):
  put('docs/'+name,(REPO/'docs'/name).read_bytes())
 put('LICENSE',(REPO/'LICENSE').read_bytes())
 for p in (REPO/'monitors/devtools/base1').rglob('*'):
  if p.is_file() and p.suffix in ('.asm','.inc'):
   put('source/'+p.relative_to(REPO/'monitors/devtools/base1').as_posix(),p.read_bytes())
 text('examples/HELLO.asm','''; Numbered source for the resident editor. Hexadecimal addresses use $.
10 ; Print a marker, then return through Foundation HOLD.
20 ORG $0200
30 LDA #$23
40 JSR $7E6D
50 JMP $7E67
60 END
''')
 text('README.md','''# STR8-N developer tools g2: local candidate2

Optional ASM/DBG tools above STR8N-F 0.3.0 g1 / BASE1 / PR05 and MON g10.
The exact flash images are installed/accepted on2512/65C02. This ZIP has
not yet passed live acceptance after extraction. 816 emulation and native
developer operation are not qualified. Published downloads are unchanged.

Start with docs/DEVELOPER-MANUAL.md. Run python verify_kit.py after extraction;
that verifies files without opening a port. The Python terminal is included:
python -m pip install -r terminal/requirements.txt
python terminal/nf_console.py --port COM4

This is an add-on, not a complete Foundation/monitor installer or migrator.
Existing Foundation, MON and matching PROGRAM/dispatcher services are required.
F is not included for reprogramming. Never send an AP/02 flash image as a RAM
BIN. Installation requires a fresh target/erase/history review; this package
does not grant permission to replace any occupied sectors. No installer runs
automatically. Owner RAM is borrowed by interactive tools; save it first.

RAM payloads and AP/02 flash images reuse the accepted bytes; no firmware
was rebuilt. The source snapshot is included for reference. A complete
source-only rebuild from this extracted kit has not been qualified.
''')
 text('docs/DEVELOPER-MANUAL.md','''# ASM and DBG operator manual

## Installed tools on the qualified 2512 profile

At REC>, enter B. At B3>, APPS lists ASM and DBG. R ASM / APP ASM launches
the editor; R DBG / APP DBG launches the debugger. Q cancels DBG's start
prompt. ASM uses QUIT; a stopped DBG uses X. Interactive apps are not
returning BATCH commands. F and its ABI remain unchanged.

## Assemble, inspect, run and debug

In R ASM, type the numbered lines in examples/HELLO.asm (omit its first
unnumbered comment), then ASM, LST, SYMS and DUMP. The expected bytes at
$0200 are A9 23 20 6D 7E 4C 67 7E. QUIT returns to MON. G 0200 prints #
and returns through HOLD. Re-enter R ASM only if the source is needed again;
each RAM tool borrows overlapping code/cache regions.

The assembler stages output at $0200 even if ORG differs. This example
uses ORG $0200 so its logical and staging addresses agree. For another
origin, load the S19 output or deliberately copy the staged bytes before
running there. Logical LST/DUMP addresses do not prove physical placement.

To debug that same RAM program, R DBG, then 0200. R displays registers;
U 0200 3 disassembles. S executes LDA, leaving PC=0202. N executes the
nonblocking public PUTC call, prints # and leaves PC=0205. C runs the HOLD
return. For an early exit use X. B addr sets a breakpoint; B lists them;
BC or BC * clears all; BC addr clears one. D/M inspect/edit admitted RAM.
Hooks and patched bytes are restored on X/HOLD. Keep IRQ masked; C is not
a sandbox for arbitrary code. Hardware IRQ debugging/native816 is excluded.

## Source persistence

SAVE SRAM name / LOAD SRAM name use formatted PROGRAM storage (AS/1).
SAVE FLASH name / LOAD FLASH name use paired SF/1 source storage. FLASH
save proposes a specific blank extent and requires YES; no erase/overwrite
is implicit. A blank-looking sector is not permission to use owner space.
Use new names for revisions. A save stages over the output buffer, so ASM
again before running output. Dirty LOAD asks before discarding edits.
WORKSPACE is not used. Persistence writes need an admitted test extent.

## RAM loads and ownership

In the terminal, F2 chooses a RAM BIN; F3 sends at SEND BIN. F4 starts L
from REC> and sends the selected BIN. ASM-RAM.bin starts
the editor. DBG-RAM.bin is the qualification entry packet: it stops at its
seed BRK near $1000; use M to install a RAM fixture and R PC to choose it.
It is not the installed DBG start-address chooser. AP/02 launch provides
that chooser. Cancel a pending transfer with Ctrl-C before sending a file.

ASM: output0200-1FFF, source2000-37FF, symbols3800-3FFF, code4000-63B7,
state6500-66FF. DBG: targets0200-3FFF, code4000-508A, tables5F00-6407,
state7000-744F. Launch uses6700-69FF; PROGRAM uses6B00-77FF. The exact
paired FLASH provider is at B0:D800-DFFF and runs at7000-77FF. The raw
provider is not a standalone RAM BIN. ASM-RAM source FLASH operations
require that installed paired provider; they are not self-contained.

Preserve owner RAM/ZP/full cache and BRK/HOLD hooks before tests; restore
and verify afterward. No test in this candidate is allowed to change F,
boot settings/history, RTC calibration/history or unrelated images.

## Qualification status

2512/65C02 core and installed launch checks passed before packaging.
After-extraction RAM acceptance, 816 emulation, and a complete source-only
rebuild remain separate. Native816 is outside the current feature scope.
''')
 text('verify_kit.py','''import hashlib,json
from pathlib import Path
r=Path(__file__).resolve().parent;m=json.loads((r/'KIT-MANIFEST.json').read_text())
files={p.relative_to(r).as_posix() for p in r.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert files==set(m['files'])|{'KIT-MANIFEST.json'}
for name,info in m['files'].items():
 p=(r/name).resolve();assert p.is_relative_to(r)
 b=p.read_bytes();assert len(b)==info['bytes'] and hashlib.sha256(b).hexdigest()==info['sha256'],name
assert (r/'payload/DBG-FLASH.bin').read_bytes()[0x1800:]==(r/'payload/FLASH-SOURCE-7000.bin').read_bytes()
print('PASS developer kit file set, hashes and paired provider; no device access')
''')
 qualification=dict(board='2512',CPU='65C02',DBG_installed_generation=2,core_RAM_groups=17,installed_checkpoints=13,installed_receipt_sha256=sha((installed/'report.json').read_bytes()),F_sha256=f['sha256'],extracted_live_acceptance=False,emulation_816_accepted=False,native_816_in_scope=False)
 text('provenance/QUALIFICATION.json',json.dumps(qualification,indent=2)+'\n')
 manifest=dict(schema=1,label=LABEL,status='LOCAL_CANDIDATE_NOT_EXTRACTED_LIVE_ACCEPTED',F_sha256=f['sha256'],inputs=inputs,firmware_builds=0,board_access=False,published=False,qualification=qualification,files={p.relative_to(stage).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(stage.rglob('*')) if p.is_file()})
 text('KIT-MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
 path=out/(LABEL+'.zip')
 with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(stage.rglob('*')):
   if p.is_file():z.write(p,Path(LABEL)/p.relative_to(stage))
 extracted=out/'extracted';extracted.mkdir()
 with zipfile.ZipFile(path) as z:
  for member in z.infolist():
   dest=(extracted/member.filename).resolve();assert dest.is_relative_to(extracted.resolve())
   dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(member))
 for cmd in ([sys.executable,'verify_kit.py'],[sys.executable,'terminal/nf_console.py','--help']):
  result=subprocess.run(cmd,cwd=extracted/LABEL,capture_output=True,text=True)
  assert result.returncode==0,result.stdout+result.stderr
 (out/'SHA256SUMS.txt').write_text(sha(path.read_bytes())+'  '+path.name+'\n')
 result=dict(passed=True,ZIP=str(path),ZIP_sha256=sha(path.read_bytes()),files=len(manifest['files'])+1,extraction_verified=True,terminal_help_passed=True,firmware_builds=0,board_access=False,live_acceptance_pending=True)
 (out/'packaging-receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':run()
