"""Build an offline-only rc1 debugger candidate. Never accesses a board.

The frozen rc1 tree is copied and patched in the build directory; it is not
modified. WDC02AS/WDCLN are required. --out must not already exist.
"""
import argparse
import binascii
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'rc1'
ROOT = HERE.parents[2]
BOOT_COMPATIBILITY = 0x44424731


def replace(path, old, new):
    s = path.read_text()
    assert s.count(old) == 1, (path, old[:70], s.count(old))
    path.write_text(s.replace(old, new))


def install_header(slot, symbols):
    page = slot[3]
    stub = bytes.fromhex('48 DA 5A AD EC 7F 48 A9 01 20 48 78 4C 10 A0')
    init = bytes([0xA2,14,0xBD,0x6C,page,0x9D,0x81,0x7B,0xCA,0x10,0xF7])
    init += bytes.fromhex('A9 81 8D 02 7E A9 7B 8D 03 7E')
    init += b''.join(bytes([0x9C,a,0x7B]) for a in range(0xFC,0x100))
    init += b'\x4C' + symbols['V2_RESET'].to_bytes(2,'little')
    hook = bytes.fromhex('00 FF 4C') + symbols['V2_REENTER'].to_bytes(2,'little')
    assert len(init) == 36 and len(stub) == 15 and len(hook) == 5
    slot[72:128] = init + stub + hook


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    out = a.out.resolve()
    assert not out.exists(), out
    stage = out.parent / (out.name + '-src')
    assert not stage.exists(), stage
    shutil.copytree(BASE,stage,ignore=shutil.ignore_patterns('__pycache__'))
    src = stage/'source'
    # Keep MAINT's strict guard synchronized with this candidate's boot marker.
    # Same-size immediate replacements preserve every utility entry/address.
    legacy = json.loads((stage/'release.json').read_text())['boot_compatibility']
    for index, (old, new) in enumerate(zip(legacy.to_bytes(4,'little'),
                                         BOOT_COMPATIBILITY.to_bytes(4,'little'))):
        replace(src/'xip/utilities.asm',
                f'JSR X28_R{9+index}\n                        CMP #${old:02X}',
                f'JSR X28_R{9+index}\n                        CMP #${new:02X}')
    # Monitor payload sizes/addresses are unchanged. Header code installs BRK
    # automatically and intercepts the existing HOLD entry for cleanup.
    replace(src/'core/monitor-b0.asm','START:                 JMP     V2_RESET',
            'START:                 JMP     V2_IMAGE_PAGE*$100+$48')
    replace(src/'core/monitor-b0.asm','V2_PROMPT_ENTRY:        JMP     V2_REENTER',
            'V2_PROMPT_ENTRY:        JMP     V2_IMAGE_PAGE*$100+$7B')
    # Guard flash mutation BEFORE command sequences, without using the sector
    # buffer. Same-size BRK/NOP replacements retain every worker address.
    replace(src/'core/str8n-v2-flash-worker.inc',
            '                        STZ     V2_FLASH_ERROR',
            '                        DB $00,$FC')
    for label in ('V2W_BYTE:', 'V2W_ERASE_RAW:'):
        p = src/'core/str8n-v2-worker.asm'
        text = p.read_text()
        pattern = label + ('               ' if label=='V2W_BYTE:' else '          ') + 'STZ V2_FLASH_ERROR'
        if pattern not in text:
            pattern = re.search(re.escape(label)+r'\s+STZ\s+V2_FLASH_ERROR',text)[0]
        replace(p, pattern, label+' DB $00,$FC')
    replace(src/'core/str8n-v2-sr.asm',
            'SR_VALID_NONRESIDENT:        LDX     #$00',
            'SR_VALID_NONRESIDENT:        DB $00,$FD')
    asm = src/'assembler/asm-app.asm'
    replace(asm,'BM_LONG_1440:\n LDA MODE', '''BM_LONG_1440:
 LDA OPCODE
 BNE DBG_NOT_BRK
 STZ OPERAND
 JSR SPACES
 BEQ DBG_EMIT_BRK
 CMP #';'
 BEQ DBG_EMIT_BRK
 CMP #'#'
 BNE DBG_BRK_EXPRESSION
 INX
DBG_BRK_EXPRESSION:
 JSR EXPRESSION
 JSR END_LINE
 LDA VAL+1
 BEQ DBG_BRK_BYTE
 JMP CORE_RANGE
DBG_BRK_BYTE:
 LDA VAL
 STA OPERAND
DBG_EMIT_BRK:
 JMP EMIT_INSTRUCTION
DBG_NOT_BRK:
 LDA MODE''')
    replace(asm,'; BRK consumes its signature byte; bare BRK emits a zero signature.\n LDA #$00',
            '; BRK consumes its signature byte; bare BRK emits zero.\n LDA OPERAND')
    meta=json.loads((stage/'release.json').read_text())
    meta['generation']=50
    meta['candidate_id']='rc1-debugger-v1'
    meta['boot_compatibility']=BOOT_COMPATIBILITY
    meta['expected_changed']=list(meta['baseline_expected'])
    (stage/'release.json').write_text(json.dumps(meta,indent=2)+'\n')
    provenance={}
    for p in sorted(src.rglob('*')):
        if p.is_file():
            provenance[p.relative_to(stage).as_posix()]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    (stage/'source-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    spec=importlib.util.spec_from_file_location('rc1_build',BASE/'build.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.HERE=stage
    oldargv=sys.argv
    sys.argv=[str(BASE/'build.py'),'--out',str(out)]
    try:
        module.main()
    finally:
        sys.argv=oldargv
    symbols=json.loads((out/'symbols.json').read_text())
    payload=out/'payload'
    for name in ('a0','b0'):
        path=payload/f'str8n-v2-recovery-slot-{name}.bin'
        slot=bytearray(path.read_bytes())
        install_header(slot,symbols['core/monitor-'+name])
        slot[18:20]=module.crc(slot[:18]+slot[32:]).to_bytes(2,'little')
        path.write_bytes(slot)
    debug=out/'debugger';shutil.copytree(HERE/'source',debug)
    sy=symbols['assembler/asm-app'];mon=symbols['core/monitor-b0'];sr=symbols['core/str8n-v2-sr'];worker=symbols['core/str8n-v2-worker']
    generated=dict(AS_OP_TABLE=sy['OP_TABLE'],AS_OP_END=sy['OP_END'],AS_LENGTHS=sy['MODE_LENGTHS'],
                   MON_D=mon['V2_COMMAND_D']&4095,MON_M=mon['V2_M_EDIT']&4095,
                   SR_GUARD=sr['SR_VALID_NONRESIDENT']+2,SR_INVALID=sr['SR_INVALID'],
                   MUTATE_GUARD=worker['V2W_MUTATE']+3,BYTE_GUARD=worker['V2W_BYTE']+2,
                   ERASE_GUARD=worker['V2W_ERASE_RAW']+2,WORKER_FAILURE=worker['V2W_FAIL'],
                   MUTATE_FAILURE=worker['V2W_NORMAL_RESULT'])
    (debug/'generated.inc').write_text(''.join(f'{k} EQU ${v:04X}\n' for k,v in generated.items()))
    assembler=shutil.which('wdc02as');linker=shutil.which('wdcln')
    for command in ([assembler,'-G','-L','-S','-W','debugger.asm'],
                    [linker,'-g','-s','-t','-cA000','-hm19','-j','-o','debugger.s19','debugger.obj']):
        r=subprocess.run(command,cwd=debug,capture_output=True,text=True)
        print(r.stdout,flush=True)
        if r.returncode:raise RuntimeError(r.stderr+r.stdout)
    cells=module.read_s19(debug/'debugger.s19')
    ds={n:int(v,16) for v,n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',(debug/'debugger.map').read_text(),re.M)}
    body=bytes(cells[i] for i in range(0xA000,ds['DEBUG_END']))
    assert len(body)<=4094, f'Debugger exceeds sector: {len(body)}'
    component=module.sealed(body,4096)
    (payload/'debugger-a000.bin').write_bytes(component)
    # Compose from source-built payloads, then insert the existing credited
    # UCHESS record and the new debugger sector.
    spec=importlib.util.spec_from_file_location('compose',ROOT/'release/rc1-build/build_full_image.py')
    composer=importlib.util.module_from_spec(spec);spec.loader.exec_module(composer)
    image=bytearray(b'\xff'*98304)
    for bank,address,file,offset,size in composer.SEGMENTS:
        first=(bank-1)*32768+address-0x8000
        image[first:first+size]=(payload/file).read_bytes()[offset:offset+size]
    record=(ROOT/'release/rc1-migration-r1/applications/uchess-record.bin').read_bytes()
    image[:len(record)]=record
    image[0x2000:0x3000]=component
    # EDU OFF fresh defaults keep the standalone offline boot bounded; the
    # normal ON configuration is also tested separately.
    config=bytearray([1,0,3,7,0xF0,10,0]+[0]*9);config[7:13]=b'P\xA0'+(50).to_bytes(4,'little')
    config[13]=0xA5
    aa=bb=0
    for v in config[:14]:aa=(aa+v)&255;bb=(bb+aa)&255
    config[14:]=bytes([aa,bb]);wc=bytearray(b'\xff'*128)
    wc[:8]=b'WC\x01\0\x01\0\0\0';wc[8:24]=config;wc[24:120]=bytes(96)
    wc[120:122]=module.crc(wc[:120]).to_bytes(2,'little');wc[127]=0
    image[0x14000:0x14080]=wc
    (out/'firmware.bin').write_bytes(image)
    report=dict(candidate='rc1-debugger-v1',generation=50,offline_only=True,board_access=False,
                application_ram_end_unchanged=True,debugger_bank=1,debugger_address=0xA000,
                debugger_code_bytes=len(body),sector_bytes=4096,remaining_bytes=4094-len(body),
                debugger_symbols=ds,generated_symbols=generated,firmware_sha256=module.sha(image),
                source_sha256={p.name:module.sha(p.read_bytes()) for p in (HERE/'source').iterdir() if p.is_file()})
    (out/'debugger-build.json').write_text(json.dumps(report,indent=2)+'\n')
    base_report=json.loads((out/'build-report.json').read_text())
    base_report['artifacts']={p.relative_to(payload).as_posix():dict(bytes=p.stat().st_size,sha256=module.sha(p.read_bytes())) for p in sorted(payload.rglob('*')) if p.is_file()}
    base_report['candidate_id']='rc1-debugger-v1'
    base_report['generation']=50
    base_report['debugger_build']='debugger-build.json'
    base_report['baseline_payload_comparison_is_qualification']=False
    for name, row in base_report['comparison'].items():
        row['actual']=base_report['artifacts'][name]
        row['match']=row['expected']==row['actual']
    allowed={'assembler/asm-e000.bin','assembler/vectors-f000.bin',
             'str8n-v2-recovery-e000-efff.bin','str8n-v2-recovery-f000-ffff.bin',
             'str8n-v2-recovery-slot-a0.bin','str8n-v2-recovery-slot-b0.bin',
             'xip/utilities.bin'}
    assert all(row['match'] or name in allowed for name,row in base_report['comparison'].items())
    (out/'build-report.json').write_text(json.dumps(base_report,indent=2)+'\n')
    print(f'PASS debugger candidate: {len(body)} / 4094 code bytes; application RAM intact',flush=True)


if __name__=='__main__':main()
