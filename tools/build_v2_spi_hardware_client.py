"""Build preserving resident-SPI and workspace qualification clients."""
import argparse,hashlib,json
from pathlib import Path
from build_v2_spi_resident import assemble
from build_bank_maint_v2 import long_branches
from beta4_migration import s19
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-spi-resident/hardware-client'

def main():
    global OUT
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,default=ROOT/'BUILD/v2-spi-resident');a=p.parse_args();OUT=a.build.resolve()/'hardware-client'
    wm=json.loads((OUT.parent/'workspace/build.json').read_text())
    stage=OUT/'source';stage.mkdir(parents=True,exist_ok=True);(OUT/'asm').mkdir(exist_ok=True)
    text=(ROOT/'tools/v2-spi/spi-client.asm').read_text()
    text=text.replace('LDA $3000,X','LDA $6646,X').replace('LDA $3007,X','LDA $66A2,X')
    text=text.replace('        LDA MANAGER\n        STA $3DF0\n','')
    text=text.replace('        JSR $300B','''        LDA MANAGER
        CMP #$A5
        BNE QUAL_PUBLIC
        STZ $66AE
QUAL_PUBLIC:
        JSR $66A6
        PHA
        LDA #1
        STA $66AE
        PLA''').replace('JSR $3004','JSR $664A')
    # Third front door calls the normal application WORK ABI at 4003.
    text=text.replace('        JMP BULK\n','        JMP BULK\n        JMP WORK_CALL\n',1)
    work='''WORK_CALL:
        SEI
        CLD
        LDA PCR
        STA OLDPCR
        LDX BANK
        CPX #4
        BCS BAD
        AND #$11
        ORA BANK_BITS,X
        STA PCR
        STA BEFORE_PCR
        LDX #31
WORK_COPY_IN:
        LDA $3E40,X
        STA $2400,X
        DEX
        BPL WORK_COPY_IN
        LDA #0
        LDX #$24
        JSR $4003
        STA RETURN_STATUS
        PHP
        PLA
        STA FLAGS
        LDA PCR
        STA AFTER_PCR
        LDX #31
WORK_COPY_OUT:
        LDA $2400,X
        STA $3E60,X
        DEX
        BPL WORK_COPY_OUT
        JMP FINISH
'''
    text=text.replace('EXPECTED DB',work.replace('JSR $4003',f'JSR ${wm["api"]:04X}')+'EXPECTED DB',1)
    (stage/'hardware-client.asm').write_text(long_branches(text))
    body,sym,_=assemble(stage,'hardware-client',0x2000,'APP_END',0x2009)
    assert body[:1]==b'\x4c' and body[3:4]==b'\x4c' and body[6:7]==b'\x4c'
    assert sym['APP_END']<=0x2400
    (OUT/'client.bin').write_bytes(body);(OUT/'client.s19').write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
    (OUT/'build.json').write_text(json.dumps(dict(bytes=len(body),symbols=sym,sha256=hashlib.sha256(body).hexdigest()),indent=2)+'\n')
    print('Resident qualification client:',len(body),'bytes; single/bulk/work entries 2000/2003/2006')

if __name__=='__main__':main()
