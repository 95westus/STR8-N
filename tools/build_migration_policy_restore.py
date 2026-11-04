"""Build a source-bound original-policy append for the reviewed 2512 WDC case.

Private escrow bytes and expected snapshots live only in ignored build output.
This restores a saved legacy choice without qualifying or executing that MON.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from build import cells,db

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'migration-host'))
import nf_migrate as p
sha=lambda body:hashlib.sha256(body).hexdigest()


def build(out,original_file,migration_file):
    out=Path(out).resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    original=Path(original_file).read_bytes();migration=Path(migration_file).read_bytes()
    before,after=p.classify_journal(original),p.classify_journal(migration)
    assert before['sequence']==961 and before['default']=='B' and before['entries']==[8]*4
    assert after['sequence']==964 and after['default']=='S' and after['enabled_mask']==0
    assert after['counts'][28]==49 and after['counts'][29]==29 and after['counts'][31]==24
    original_row=original[0x5c00:0x5d00];expected=migration[0x4000:0x4100]
    assert p.valid_snapshot(original_row) and p.valid_snapshot(expected)
    assert p.sha(original[-4096:])==p.sha(migration[-4096:])==p.F_SHA256
    lock=json.loads((ROOT/'F_FREEZE.json').read_text())
    for name,digest in lock['sources'].items():assert sha((ROOT/name).read_bytes())==digest
    assembler,linker=shutil.which('wdc02as'),shutil.which('wdcln')
    assert assembler and linker
    out.mkdir(parents=True)
    shutil.copytree(ROOT/'src/core',out/'core');shutil.copytree(ROOT/'src/include',out/'include')
    core=out/'core';db(core/'policy-escrow-private.inc',original_row);db(core/'expected-record-private.inc',expected)
    source=(core/'ram-config.asm').read_text()
    source=source.replace('CONFIG_START:\n','CONFIG_START:\n        JMP MP_START\n')
    code='''MP_START:
        SEI
        CLD
        LDA #3
        JSR V2W_SELECT
        STZ DC_BINARY
        STZ V2_NMI_HOLD
        JSR JE_READ
        BCS MP_READ_OK
        JMP MP_BAD
MP_READ_OK:
        LDA J_BEST+1
        CMP #$C0
        BEQ MP_PAGE_OK
        JMP MP_BAD
MP_PAGE_OK:
        LDX #0
MP_EXPECT:
        LDA JE_FRAME,X
        CMP MP_EXPECTED,X
        BEQ MP_BYTE_OK
        JMP MP_BAD
MP_BYTE_OK:
        INX
        BNE MP_EXPECT
        LDA MP_ORIGINAL+7
        STA JE_FRAME+7
        LDX #9
MP_HEADER:
        LDA MP_ORIGINAL+12,X
        STA JE_FRAME+12,X
        DEX
        BPL MP_HEADER
        LDX #15
MP_CONFIG:
        LDA MP_ORIGINAL+32,X
        STA JE_FRAME+32,X
        DEX
        BPL MP_CONFIG
        JSR BOOT_CHECK_FIELDS
        BCS MP_FIELDS_OK
        JMP MP_BAD
MP_FIELDS_OK:
        LDA #$C1
        STA JE_DEST
        JSR JE_PAGE_BLANK
        BCS MP_SPACE_OK
        JMP MP_BAD
MP_SPACE_OK:
        JSR JE_SEAL
        BCS MP_SEALED
        JMP MP_BAD
MP_SEALED:
        JSR JE_WRITE
        BCS MP_WRITTEN
        JMP MP_BAD
MP_WRITTEN:
        LDX #<MP_OK_TEXT
        LDY #>MP_OK_TEXT
        BRA MP_PRINT
MP_BAD:
        LDX #<MP_BAD_TEXT
        LDY #>MP_BAD_TEXT
MP_PRINT:
        JSR BOOT_PRINT
        JMP BOOT_RECOVERY
MP_OK_TEXT: DB "MIGRATION POLICY RESTORED; COUNTERS RETAINED; MON EXECUTION UNQUALIFIED",13,10,0
MP_BAD_TEXT: DB "REFUSED: migration policy source/append guard",13,10,0
MP_EXPECTED:
        INCLUDE "expected-record-private.inc"
MP_ORIGINAL:
        INCLUDE "policy-escrow-private.inc"
'''
    source=source.replace('        INCLUDE "config-engine.inc"',code+'\n        INCLUDE "config-engine.inc"')
    (core/'ram-config.asm').write_text(source,encoding='utf-8',newline='\n')
    logs=[]
    for command in ([assembler,'-G','-L','-S','-W','-I',str(core),'ram-config.asm'],
                    [linker,'-g','-s','-t','-c0200','-hm19','-j','-o','ram-config.s19','ram-config.obj']):
        result=subprocess.run(command,cwd=core,capture_output=True,text=True)
        logs.append(dict(command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n',encoding='utf-8')
        if result.returncode:raise RuntimeError('Inspect build-log.json')
    symbols={n:int(v,16) for v,n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',(core/'ram-config.map').read_text(),re.M)}
    memory=cells(core/'ram-config.s19');assert set(memory)==set(range(0x200,symbols['CONFIG_END']))
    body=bytes(memory[n] for n in range(0x200,symbols['CONFIG_END']))
    assert symbols['CONFIG_END']<0x6500
    (out/'2512-MIGRATION-POLICY-RESTORE-RAM.bin').write_bytes(body)
    restored=bytearray(expected);restored[7]=original_row[7]
    restored[12:22]=original_row[12:22];restored[32:48]=original_row[32:48]
    restored[8:12]=(965).to_bytes(4,'little')
    restored[30:32]=p.crc(restored[:30]).to_bytes(2,'little')
    restored[252:254]=p.crc(restored[:252]).to_bytes(2,'little')
    assert p.valid_snapshot(restored)
    final=bytearray(migration);assert final[0x4100:0x4200]==b'\xff'*256
    final[0x4100:0x4200]=restored
    (out/'expected-final-b3.bin').write_bytes(final)
    report=dict(image_sha256=sha(body),bytes=len(body),expected_latest_record_sha256=sha(expected),
        original_escrow_record_sha256=sha(original_row),expected_final_b3_sha256=sha(final),
        allowed_latest='C000 seq964; all 256 expected bytes must match',append='C100 seq965',
        desired_policy='Exact original B/0F/all8000 and original config/pinned generation',
        F_rebuilt=False,CD_erases=0,CPU_simulations=0,hardware_qualified=False)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--original-b3',type=Path,required=True)
    parser.add_argument('--migration-b3',type=Path,required=True)
    args=parser.parse_args();build(args.out,args.original_b3,args.migration_b3)
