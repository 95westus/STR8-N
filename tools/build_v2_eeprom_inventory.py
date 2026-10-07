"""Build bounded read-only inventory probe; EEPROM data writes are absent."""
import hashlib,json,shutil
from pathlib import Path
import build_v2_config as compiler
from beta4_migration import s19
from build_bank_maint_v2 import long_branches

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-eeprom-inventory'


def main():
    stage=OUT/'source';stage.mkdir(parents=True,exist_ok=True);(OUT/'asm').mkdir(exist_ok=True)
    original=(ROOT/'tools/v2-rtc/rtc-service.asm').read_text()
    transport=original[original.index('\nINIT    '):original.index('\nBUSY DB')]
    start=transport.index('\nWRITE_REGS\n');end=transport.index('\nTRANS_OK',start)
    transport=transport[:start]+transport[end:]
    transport=transport.replace('#$DE','#$AE').replace('#$DF','#$AF')
    source='''        MODULE EEPROM_INVENTORY
        XDEF START
        XDEF APP_END
VDDR EQU $7FC3
VORA EQU $7FCF
RTC_BUS_BUSY EQU 1
RTC_NACK EQU 2
RTC_TIMEOUT EQU 3
        CODE
START:  SEI
        CLD
        LDA VDDR
        STA $2491
        LDA VORA
        STA $2493
        JSR INIT
        BCC DONE
        STZ BLOCK
BLOCK_NEXT:
        LDA BLOCK
        STA REGADDR
        LDA #16
        STA COUNT
        JSR READ_REGS
        BCC DONE
        LDY #0
COPY_BLOCK:
        TYA
        CLC
        ADC BLOCK
        TAX
        LDA READBUF,Y
        STA $2400,X
        INY
        CPY #16
        BNE COPY_BLOCK
        LDA BLOCK
        CLC
        ADC #16
        STA BLOCK
        CMP #$80
        BCC BLOCK_NEXT
        LDA #$FF
        STA REGADDR
        LDA #1
        STA COUNT
        JSR READ_REGS
        BCC DONE
        LDA READBUF
        STA $2480
        LDA #$F0
        STA REGADDR
        LDA #8
        STA COUNT
        JSR READ_REGS
        BCC DONE
        LDX #7
COPY_ID:
        LDA READBUF,X
        STA $2481,X
        DEX
        BPL COPY_ID
        LDA #0
DONE:   STA $2490
        JSR RESTORE
        LDA VDDR
        STA $2492
        LDA VORA
        STA $2494
        JMP $7E67
'''+transport+'''
SAVEORA DB 0
SAVEDDR DB 0
REGADDR DB 0
COUNT DB 0
INDEX DB 0
ERROR DB 0
BYTE DB 0
ACKBIT DB 0
BLOCK DB 0
READBUF DS 16
APP_END:
        ENDMOD
        END
'''
    path=stage/'eeprom-inventory.asm';path.write_text(long_branches(source))
    compiler.OUT,compiler.SOURCE=OUT,stage
    cells,symbols=compiler.assemble('eeprom-inventory',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    body=compiler.dense_image(cells,0x2000,symbols['APP_END']);assert symbols['APP_END']<0x2400
    (OUT/'probe.s19').write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
    (OUT/'build.json').write_text(json.dumps(dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),symbols=symbols),indent=2)+'\n')
    print('Read-only EEPROM inventory',len(body),'bytes; no write-data routine')


if __name__=='__main__':main()
