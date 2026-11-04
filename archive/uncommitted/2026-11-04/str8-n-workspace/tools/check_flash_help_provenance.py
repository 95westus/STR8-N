"""Resolve the help-only install question from exact existing artifacts; no port/build."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'release/str8nf-v0.2.0'
sha=lambda b:hashlib.sha256(b).hexdigest()

def run():
    out=ROOT/'output/qualification/2512-FLASH-help-provenance-20261101-r1';out.mkdir(exist_ok=False)
    (out/'.gitignore').write_text('*\n')
    marker=json.loads((ROOT/'output/qualification/device-operations/2512.json').read_text())
    bank=(ROOT/'output/qualification/2512-startup-traditional-scope-20261101-r1/B2-target.bin').read_bytes()
    assert sha(bank)==marker['current_physical_bank_sha256']['B2']
    old='BOOT OFF bank; BOOT RUN bank; BOOT DELAY hex-ticks (0.1s)'
    new='BOOT OFF/RUN bank; BOOT DELAY 0A-FF stored; F fixed 3s'
    source=(REPO/'monitors/native/board-tool.asm').read_text();assert source.count(new)==1 and old not in source
    original=source.replace(new,old)
    mf=json.loads((ROOT/'BUILD/flash-status-correction-r4/manifest.json').read_text())
    assert sha(original.encode())==mf['source_sha256']['monitors/native/board-tool.asm']
    compact='''FT_HELP_TEXT:
        DB "BANK READ VIEW EDIT WRITE BYTE ERASE",13,10
        DB "I first last (S19)",13,10
        DB "BOOT B/C/OFF/RUN/DELAY; B/C/W/?",13,10
        DB "HOST; VERSION; Q; B3:C/D/F protected",13,10,0
'''
    recipe=(REPO/'tools/build_flash_status_correction.py').read_text()
    assert "a=core.index('FT_HELP_TEXT:');b=core.index('FT_VALID:',a)" in recipe and compact in recipe
    def replace_help(text):
        a=text.index('FT_HELP_TEXT:');b=text.index('FT_VALID:',a)
        return text[:a]+compact+text[b:]
    assert replace_help(source)==replace_help(original)
    stage=(ROOT/'BUILD/flash-status-correction-r4/board-tool.asm').read_text()
    assert compact in stage
    neutral=b'BOOT B/C/OFF/RUN/DELAY; B/C/W/?\r\n'
    assert bank.count(neutral)==1 and b'hex-ticks' not in bank and b'(0.1s)' not in bank
    f=json.loads((REPO/'F_FREEZE.json').read_text())
    assert sha((REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==f['sha256']
    assert all(sha((REPO/n).read_bytes())==h for n,h in f['sources'].items())
    report=dict(passed=True,status='NO_HELP_ONLY_INSTALL_NEEDED',board='2512',source_help_corrected=True,
      installed_compact_help=neutral.decode().strip(),installed_B2_sha256=sha(bank),
      builder_replaces_entire_changed_help_region=True,transformed_sources_identical=True,
      correction='Earlier closeout assumed the full-source help paragraph was installed; actual compact menu omits the tick claim',
      firmware_builds=0,CPU_simulations=0,serial_access=False,flash_erases=0,journal_appends=0,F_writes=0,
      F_sha256=f['sha256'],published_changes=False,
      limit='Existing current-hash artifact provenance; no fresh board dump or live command was needed')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('CLOSED help wording: current compact FLASH has no tick claim; transformed sources identical; zero build/port/erase')

if __name__=='__main__':run()
