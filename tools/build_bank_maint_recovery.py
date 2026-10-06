"""Build maintenance for the recovery layout, with accounting and guards."""
import hashlib
import json
from pathlib import Path
import shutil

import build_v2_config as link
import build_v2_recovery as fw
from build_bank_maint_v2 import long_branches

OUT = fw.ROOT/'BUILD/bank-maint-recovery'
NAME = 'str8n-bank-maint-recovery-2000'
VERSION = '1.5'


def main():
    report=json.loads((fw.OUT/'build.json').read_text())
    stage=OUT/'asm'; stage.mkdir(parents=True,exist_ok=True)
    (OUT/'manifest.json').unlink(missing_ok=True)
    for p in fw.SOURCE.glob('*.inc'): shutil.copyfile(p,stage/p.name)
    shutil.copyfile(fw.OUT/'asm/boot-symbols.inc',stage/'boot-symbols.inc')
    text=(fw.ROOT/'tools/bank-maint-v2/bank-maint.asm').read_text()
    text=text.replace('1.0',VERSION).replace('CMP #$69','CMP #$67').replace('ADC #$69','ADC #$68')
    text=text.replace('INCLUDE "str8n-v2-eq.inc"','INCLUDE "str8n-v2-eq.inc"\n                        INCLUDE "boot-symbols.inc"')
    text=text.replace('                        CMP #\'E\'\n                        BEQ BM_ERASE',
                      '                        CMP #\'T\'\n                        BEQ BM_TABLE\n                        CMP #\'E\'\n                        BEQ BM_ERASE')
    # One-shot monitor M loads this saved utility and returns after drawing.
    text=text.replace('                        LDX #<TITLE', '''                        STZ MAP_ONCE
                        LDA $7DFC
                        CMP #$4D
                        BNE BM_NORMAL_START
                        STZ $7DFC
                        LDA $7DFD
                        STA MAP_VIEW
                        INC MAP_ONCE
                        JMP BM_MAP_START
BM_NORMAL_START:        LDX #<TITLE''',1)
    text=text.replace('Writes: Y to confirm. B3:F also requires B3F.',
                      'Writes: Y to confirm. B3:A-F are protected.')
    text=text.replace('MAP_HEADER:             DB "SECTORS 8 9 A B C D E F (E=erased U=used)",$0D,$0A,0',
                      'MAP_HEADER:             DB "SECTORS 8 9 A B C D E F (E=erased U=used)",$0D,$0A\n'
                      '                        DB "B3: A/B monitors; C/D journals; E S/R/T; F recovery (protected)",$0D,$0A,0')
    begin=text.index('BM_MAP:');end=text.index('BM_QUIT:',begin)
    text=text[:begin]+(fw.ROOT/'tools/bank-maint-recovery-views.inc').read_text()+'\n'+text[end:]
    text=text.replace('M                           Map banks and sectors',
                      'M [1|2|3]                   Grid / ranges (default) / wear')
    text=text.replace('                        DB "  J bank',
                      '                        DB "  T [bank|first-last]          Stored records",$0D,$0A\n                        DB "  J bank')
    helpers=(fw.ROOT/'tools/bank-maint-recovery-map.inc').read_text()
    helpers='MAP_STATUS EQU $6128\nMAP_OWNER_END EQU $6130\nMAP_OWNER_LABEL EQU $6132\n'+helpers[helpers.index('MAP_RECORD_HEADER:'):]
    text=text.replace('TITLE:                  DB',
                      helpers+'\nTITLE:                  DB')
    app_helpers=''.join(f'MAP_{name} EQU ${report["boot"]["J_"+name]:04X}\n'
                        for name in ('CRC_INIT','CRC_BYTE'))
    app_helpers+=(fw.ROOT/'tools/bank-maint-recovery-apps.inc').read_text()
    text=text.replace('TITLE:                  DB',app_helpers+'\nTITLE:                  DB')
    start=text.index('                        LDA V2_RESIDENT')
    descriptor=report['boot']['BOOT_WEAR_DESCRIPTOR']
    compatibility=report['boot_compatibility'].to_bytes(4,'little')
    identity=''.join(f'                        LDA ${report["boot"]["BOOT_COMPAT_DATA"]+i:04X}\n                        CMP #${value:02X}\n                        BNE BM_UNSUPPORTED\n' for i,value in enumerate(compatibility))
    text=text[:start]+f'''                        LDA ${descriptor:04X}
                        CMP #'W'
                        BNE BM_UNSUPPORTED
                        LDA ${descriptor+1:04X}
                        CMP #'R'
                        BNE BM_UNSUPPORTED
                        LDA ${descriptor+2:04X}
                        CMP #$01
                        BNE BM_UNSUPPORTED
'''+identity+text[start:]
    text=text.replace('CONFIRM:                STZ DANGER', '''CONFIRM:                LDA DB
                        CMP #$03
                        BNE CONFIRM_ALLOWED
                        LDA TOEND+1
                        CMP #$A0
                        BCS CONFIRM_NO
CONFIRM_ALLOWED:        STZ DANGER''')
    worker=(fw.SOURCE/'str8n-v2-worker.asm').read_text()
    account=worker[worker.index('V2W_ACCOUNT:'):worker.index('V2W_END:')]
    text=text.replace('TITLE:                  DB',account+'\nTITLE:                  DB')
    source=OUT/(NAME+'.asm'); source.write_text(long_branches(text),encoding='ascii')
    link.OUT=OUT; link.SOURCE=stage
    memory,sym=link.assemble(NAME,0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=source)
    memory,sym=fw.relax_branches(source,memory,sym,lambda:link.assemble(NAME,0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source_file=source))
    end=sym['BM_END']
    if end>0x4000: raise ValueError('Maintenance overlaps workspace')
    data=link.dense_image(memory,0x2000,end)
    lines=[link.record('0',0,f'STR8-N recovery bank maintenance {VERSION}'.encode())]
    lines += [link.record('1',a,data[a-0x2000:a-0x2000+32]) for a in range(0x2000,end,32)]
    lines += [link.record('9',0x2000)]
    target=OUT/(NAME+'.s19'); target.write_text('\n'.join(lines)+'\n')
    (OUT/'manifest.json').write_text(json.dumps(dict(version=VERSION,bytes=len(data),symbols=sym,
        boot_compatibility=report['boot_compatibility'],s19_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),hardware_tested=False),indent=2)+'\n')
    print(f'{target}: {len(data)} bytes; wear-accounted writes; B3:A-F protected')


if __name__=='__main__': main()
