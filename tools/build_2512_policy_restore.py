"""Build the guarded 2512 acceptance-policy restorer; F stays frozen.

Normal CONFIG correctly refuses selecting an incompatible old monitor. This
test-only helper restores the exact original policy from retained D300, while
keeping the latest counters. It never executes that monitor or erases C/D.
The two allowed append positions belong only to this recorded hardware case.
Private original bytes are embedded only in ignored build output, never source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from build import cells, db

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'migration-host'))
import nf_migrate as planning
sha = lambda body: hashlib.sha256(body).hexdigest()


def build(out, backup):
    out = Path(out).resolve()
    if out.exists(): raise ValueError('Fresh output directory required')
    original = Path(backup).read_bytes()
    assert len(original) == 32768
    row = original[0x5300:0x5400]
    assert planning.valid_snapshot(row)
    assert int.from_bytes(row[8:12], 'little') == 952
    assert row[7] == ord('B') and row[13:18] == bytes([15,8,8,8,8])
    assert int.from_bytes(row[67:70], 'little') == 5
    freeze = json.loads((ROOT/'F_FREEZE.json').read_text())
    for name,digest in freeze['sources'].items(): assert sha((ROOT/name).read_bytes()) == digest
    assert sha(original[-4096:]) == freeze['sha256']
    assembler,linker = shutil.which('wdc02as'),shutil.which('wdcln')
    assert assembler and linker
    out.mkdir(parents=True)
    shutil.copytree(ROOT/'src/core',out/'core')
    shutil.copytree(ROOT/'src/include',out/'include')
    core = out/'core'
    db(core/'policy-original-private.inc',row)
    source = (core/'ram-config.asm').read_text()
    assert source.count('CONFIG_START:\n') == 1
    source = source.replace('CONFIG_START:\n','CONFIG_START:\n        JMP PR_START\n')
    code = '''; Test-only escrow restoration, never a request to select new MON firmware.
PR_START:
        SEI
        CLD
        LDA #3
        JSR V2W_SELECT
        STZ DC_BINARY
        STZ V2_NMI_HOLD
        LDX #0
PR_ORIGINAL:
        LDA $D300,X
        CMP PR_REFERENCE,X
        BEQ PR_ORIGINAL_OK
        JMP PR_BAD
PR_ORIGINAL_OK:
        INX
        BNE PR_ORIGINAL
        JSR JE_READ
        BCS PR_READ_OK
        JMP PR_BAD
PR_READ_OK:
        LDA J_BEST+1
        CMP #$D6
        BEQ PR_FIRST
        CMP #$DB
        BEQ PR_SECOND
        JMP PR_BAD
PR_FIRST:
        LDA JE_FRAME+8
        CMP #$BB
        BEQ PR_SEQ_HIGH
        JMP PR_BAD
PR_SECOND:
        LDA JE_FRAME+8
        CMP #$C0
        BEQ PR_SEQ_HIGH
        JMP PR_BAD
PR_SEQ_HIGH:
        LDA JE_FRAME+9
        CMP #3
        BEQ PR_SEQ_TOP
        JMP PR_BAD
PR_SEQ_TOP:
        LDA JE_FRAME+10
        ORA JE_FRAME+11
        BEQ PR_POLICY
        JMP PR_BAD
PR_POLICY:
        LDA PR_REFERENCE+7
        STA JE_FRAME+7
        LDX #9
PR_HEADER:
        LDA PR_REFERENCE+12,X
        STA JE_FRAME+12,X
        DEX
        BPL PR_HEADER
        LDX #15
PR_CONFIG:
        LDA PR_REFERENCE+32,X
        STA JE_FRAME+32,X
        DEX
        BPL PR_CONFIG
        JSR BOOT_CHECK_FIELDS
        BCS PR_FIELDS_OK
        JMP PR_BAD
PR_FIELDS_OK:
        LDA J_BEST+1
        INC A
        STA JE_DEST
        JSR JE_PAGE_BLANK
        BCS PR_BLANK_OK
        JMP PR_BAD
PR_BLANK_OK:
        JSR JE_SEAL
        BCS PR_SEALED
        JMP PR_BAD
PR_SEALED:
        JSR JE_WRITE
        BCS PR_WRITTEN
        JMP PR_BAD
PR_WRITTEN:
        LDX #<PR_OK_TEXT
        LDY #>PR_OK_TEXT
        BRA PR_PRINT
PR_BAD:
        LDX #<PR_BAD_TEXT
        LDY #>PR_BAD_TEXT
PR_PRINT:
        JSR BOOT_PRINT
        JMP BOOT_RECOVERY
PR_OK_TEXT:
        DB "POLICY ESCROW RESTORED; COUNTERS RETAINED; MON EXECUTION UNQUALIFIED",13,10,0
PR_BAD_TEXT:
        DB "REFUSED: policy escrow/source/append guard",13,10,0
PR_REFERENCE:
        INCLUDE "policy-original-private.inc"
'''
    source = source.replace('        INCLUDE "config-engine.inc"',code+'\n        INCLUDE "config-engine.inc"')
    (core/'ram-config.asm').write_text(source,encoding='utf-8',newline='\n')
    logs = []
    for command in ([assembler,'-G','-L','-S','-W','-I',str(core),'ram-config.asm'],
                    [linker,'-g','-s','-t','-c0200','-hm19','-j','-o','ram-config.s19','ram-config.obj']):
        process = subprocess.run(command,cwd=core,capture_output=True,text=True)
        logs.append(dict(command=command,returncode=process.returncode,stdout=process.stdout,stderr=process.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n',encoding='utf-8')
        if process.returncode: raise RuntimeError('Inspect build-log.json')
    symbols = {name:int(value,16) for value,name in re.findall(
        r'^\s*([0-9A-Fa-f]{8}) (\w+)\s*$',(core/'ram-config.map').read_text(),re.M)}
    memory = cells(core/'ram-config.s19')
    assert set(memory) == set(range(0x200,symbols['CONFIG_END']))
    assert symbols['CONFIG_END'] < 0x6500
    body = bytes(memory[n] for n in range(0x200,symbols['CONFIG_END']))
    (out/'2512-POLICY-ESCROW-RESTORE-RAM.bin').write_bytes(body)
    report = dict(image_sha256=sha(body),bytes=len(body),F_rebuilt=False,CPU_simulations=0,
                  private_record_sha256=sha(row),allowed_latest_pages=['D600 seq955','DB00 seq960'],
                  changes='Restore original policy, sequence and CRC only; preserve latest wear counters',
                  CD_erase=False,slot_validation_bypassed='Only to restore exact retained original policy; no MON execution')
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--bank3-backup',type=Path,required=True)
    args=parser.parse_args();build(args.out,args.bank3_backup)
