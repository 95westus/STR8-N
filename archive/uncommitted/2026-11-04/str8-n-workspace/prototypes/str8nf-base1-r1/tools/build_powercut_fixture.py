"""Build a B0:9-only interrupted-image fixture; never rebuild frozen F.

The extra RAM checkpoint verifies a half-programmed sector, selects B3 and
halts with the chip idle. This tests reset recovery of an incomplete opaque
transaction; it does not qualify brownout during a flash pulse or torn SNBT.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from build import cells

ROOT = Path(__file__).resolve().parents[1]
sha = lambda data: hashlib.sha256(data).hexdigest()


def build(out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Fresh output directory required')
    lock = json.loads((ROOT/'F_FREEZE.json').read_text())
    for name, digest in lock['sources'].items():
        assert sha((ROOT/name).read_bytes()) == digest, name
    assert sha((ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()) == lock['sha256']
    assembler, linker = shutil.which('wdc02as'), shutil.which('wdcln')
    if not assembler or not linker:
        raise ValueError('WDC tools required')
    out.mkdir(parents=True)
    shutil.copytree(ROOT/'src/core', out/'core')
    shutil.copytree(ROOT/'src/include', out/'include')
    core = out/'core'
    source = (core/'ram-installer.asm').read_text()
    original = sha(source.encode())
    # Reject any other target before the ordinary wear-reservation path.
    anchor = 'OI_LONG_13:\n'
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor + '''        LDA OI_HEADER+6
        BEQ PC_BANK_OK
        JMP OI_FRAME_BAD
PC_BANK_OK:
        LDA OI_HEADER+7
        CMP #$90
        BEQ PC_SECTOR_OK
        JMP OI_FRAME_BAD
PC_SECTOR_OK:
''')
    anchor = '''OI_LONG_32:
        INC V2_BUF_PTR+1
        INC V2_FLASH_PTR+1
        DEC OI_PAGES
'''
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor + '''        LDA OI_PAGES
        CMP #8
        BNE PC_CONTINUE
        JMP PC_CHECKPOINT
PC_CONTINUE:
        LDA OI_PAGES
''')
    checkpoint = '''; All completed byte-program calls have returned before this checkpoint.
; Verify A5 in 9000-97FF and erased FF in 9800-9FFF before announcing readiness.
PC_CHECKPOINT:
        STZ V2_FLASH_PTR
        LDA #$90
        STA V2_FLASH_PTR+1
PC_VERIFY:
        LDA V2_FLASH_PTR+1
        CMP #$98
        BCS PC_EXPECT_FF
        LDA #$A5
        BRA PC_COMPARE
PC_EXPECT_FF:
        LDA #$FF
PC_COMPARE:
        CMP (V2_FLASH_PTR)
        BEQ PC_BYTE_OK
        JMP OI_FLASH_BAD
PC_BYTE_OK:
        INC V2_FLASH_PTR
        BNE PC_VERIFY
        INC V2_FLASH_PTR+1
        LDA V2_FLASH_PTR+1
        CMP #$A0
        BNE PC_VERIFY
        LDA #3
        JSR V2W_SELECT
        STZ V2_NMI_HOLD
        STZ DC_BINARY
        LDX #<PC_READY_TEXT
        LDY #>PC_READY_TEXT
        JSR BOOT_PRINT
PC_HALT:
        BRA PC_HALT
PC_READY_TEXT:
        DB "POWER CUT READY: B0:9000 A5x2048 FFx2048; CHIP IDLE",13,10,0
'''
    source = source.replace('OI_SIGNATURE:', checkpoint+'\nOI_SIGNATURE:')
    (core/'ram-installer.asm').write_text(source, encoding='utf-8', newline='\n')
    logs = []
    for command in ([assembler, '-G', '-L', '-S', '-W', '-I', str(core), 'ram-installer.asm'],
                    [linker, '-g', '-s', '-t', '-c0200', '-hm19', '-j', '-o',
                     'ram-installer.s19', 'ram-installer.obj']):
        result = subprocess.run(command, cwd=core, capture_output=True, text=True)
        logs.append(dict(command=command, returncode=result.returncode,
                         stdout=result.stdout, stderr=result.stderr))
        (out/'build-log.json').write_text(json.dumps(logs, indent=2)+'\n', encoding='utf-8')
        if result.returncode:
            raise RuntimeError('Build failed; inspect build-log.json')
    symbols = {name:int(value,16) for value,name in re.findall(
        r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$', (core/'ram-installer.map').read_text(), re.M)}
    memory = cells(core/'ram-installer.s19')
    assert set(memory) == set(range(0x200, symbols['INSTALLER_END']))
    assert symbols['INSTALLER_END'] < 0x6500
    body = bytes(memory[n] for n in range(0x200, symbols['INSTALLER_END']))
    (out/'BASE1-B0-9000-POWERCUT-RAM.bin').write_bytes(body)
    report = dict(schema=1, image_sha256=sha(body), bytes=len(body),
                  source_before_patch_sha256=original,
                  generated_source_sha256=sha(source.encode()), F_rebuilt=False,
                  frozen_F_sha256=lock['sha256'], CPU_simulations=0,
                  target='B0:9000 only', checkpoint='2048 programmed bytes; chip idle',
                  qualifies='incomplete opaque transaction across real power loss',
                  does_not_qualify=['flash-pulse brownout', 'torn journal append', 'partial F'])
    (out/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    build(parser.parse_args().out)
