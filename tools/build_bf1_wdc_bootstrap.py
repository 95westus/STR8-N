"""Build a project-only factory-WDC bootstrap guard/template. No vendor input.

This template admits no journal assumption. Its caller binds all source banks
and every transfer, and initializes a declared migration wear baseline.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
import beta4_migration as wire
from build_bf1_2512_legacy_installer import linked_cells

ROOT=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
GUARD='''; STR8-N project code: read-only preflight, no ROM calls or flash mutation.
 MODULE FACTORY_GUARD
 XDEF G_END
 INCLUDE "str8n-v2-eq.inc"
 INCLUDE "reservation-links.inc"
G_BANK EQU $6230
G_HASHES EQU $3500
G_INPUT_HASH EQU $3512
 CODE
G_ENTRY:
 SEI
 CLD
 STZ G_BANK
G_BANK_LOOP:
 LDA G_BANK
 STA V2_SELECTED
 JSR V2W_SELECT
 STZ V2_PTR
 LDA #$80
 STA V2_PTR+1
 STZ $620C
 JSR MIG_HASH_RANGE
 LDA G_BANK
 ASL A
 ASL A
 TAX
 LDY #0
G_COMPARE:
 LDA G_HASHES,X
 CMP $6204,Y
 BNE G_BAD
 INX
 INY
 CPY #4
 BNE G_COMPARE
 INC G_BANK
 LDA G_BANK
 CMP #4
 BNE G_BANK_LOOP
 STZ V2_PTR
 LDA #$36
 STA V2_PTR+1
 LDA #$37
 STA $620C
 JSR MIG_HASH_RANGE
 LDX #3
G_INPUT_LOOP:
 LDA G_INPUT_HASH,X
 CMP $6204,X
 BNE G_BAD
 DEX
 BPL G_INPUT_LOOP
 JSR G_CLEANUP
 SEC
 RTS
G_BAD:
 JSR G_CLEANUP
 CLC
 RTS
G_CLEANUP:
 LDA #3
 STA V2_SELECTED
 JSR V2W_SELECT
 RTS
G_END:
 ENDMOD
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();assert out.is_relative_to(ROOT) and not out.exists() and len(str(out))<60
    out.mkdir(parents=True);stage=out/'asm';stage.mkdir()
    prior=ROOT/'tmp/blg4';mf=json.loads((prior/'manifest.json').read_text(encoding='utf-8'))
    for name in ('str8n-v2-eq.inc','reservation-links.inc'):shutil.copyfile(prior/'asm'/name,stage/name)
    (stage/'factory-guard.asm').write_text(GUARD,encoding='ascii')
    logs=[]
    for command in ([shutil.which('wdc02as'),'-G','-L','-S','-W','-I',str(stage),'factory-guard.asm'],
                    [shutil.which('wdcln'),'-g','-s','-t','-c3000','-hm19','-j','-o','factory-guard.s19','factory-guard.obj']):
        result=subprocess.run(command,cwd=stage,capture_output=True,text=True)
        logs.append(dict(command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n',encoding='utf-8')
        if result.returncode:raise RuntimeError('Guard build failed; see retained log')
    guard=linked_cells(stage/'factory-guard.s19');assert min(guard)==0x3000 and max(guard)<0x3300
    image=wire.read_s19(prior/'integrated-template.s19')[0]
    assert sha((prior/'integrated-template.s19').read_bytes())==mf['integrated_sha256']
    image.update({a:0 for a in range(0x3000,0x3300)});image.update(guard)
    # Optional 65C816-only entry: SEC/XCE, SEI/CLD, LDX #FF/TXS,
    # PEA 0000/PLD, PHK/PLB, JMP 2007. Bank-zero GO makes PHK publish DBR=0.
    # This establishes E=1, DP=0, DBR=0 before the common 65C02 worker body.
    prologue=bytes.fromhex('38 FB 78 D8 A2 FF 9A F4 00 00 2B 4B AB 4C 07 20')
    image.update(dict(enumerate(prologue,0x3700)))
    image={a:image.get(a,0) for a in range(0x2000,0x3800)}
    raw=wire.s19(image,0x2000);(out/'bootstrap-template.s19').write_bytes(raw)
    mf.update(kind='factory-no-journal-bootstrap',integrated_sha256=sha(raw),entry_65C02=0x2000,
              entry_65C816=0x3700,guard_sha256=sha(bytes(guard[a] for a in sorted(guard))),guard_bytes=len(guard),
              native_entry_bytes=prologue.hex(),passed=True,model_qualified=False,hardware_qualified=False,
              vendor_code_or_images_input=False,board_access=False)
    (out/'manifest.json').write_text(json.dumps(mf,indent=2)+'\n',encoding='utf-8')
    print('PASS project-only no-journal bootstrap template built; qualification pending')


if __name__=='__main__':main()
