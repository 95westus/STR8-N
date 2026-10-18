"""Build a bounded read-only RTC/SRAM/EEPROM archive client; no hardware access."""
import hashlib,json,shutil
from pathlib import Path
import build_v2_config as c
from beta4_migration import s19
from build_bank_maint_v2 import long_branches

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/board-state-reader'

def main():
    original=(ROOT/'tools/v2-rtc/rtc-service.asm').read_text()
    transport=original[original.index('\nINIT    '):original.index('\nBUSY DB')]
    start=transport.index('\nWRITE_REGS\n');end=transport.index('\nTRANS_OK',start)
    transport=transport[:start]+transport[end:]
    transport=transport.replace('LDA #$DE','LDA DEVICE_WRITE').replace('LDA #$DF','LDA DEVICE_WRITE\n        ORA #1')
    source='''        MODULE BOARD_STATE_READER
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
        STA $2F11
        LDA VORA
        STA $2F13
        STZ $2F15
        LDA $2F00
        STA DEVICE_WRITE
        LDA $2F01
        STA REGADDR
        LDA $2F02
        STA COUNT
        BEQ BAD
        CMP #129
        BCS BAD
        DEC A
        CLC
        ADC REGADDR
        BCS BAD
        TAX
        LDA DEVICE_WRITE
        CMP #$DE
        BEQ CHECK_RTC
        CMP #$AE
        BNE BAD
        LDA REGADDR
        CMP #$F0
        BEQ CHECK_EUI
        CMP #$FF
        BEQ CHECK_STATUS
        TXA
        CMP #$80
        BCS BAD
        BRA VALID
CHECK_EUI:
        TXA
        CMP #$F8
        BCS BAD
        BRA VALID
CHECK_STATUS:
        LDA COUNT
        CMP #1
        BNE BAD
        BRA VALID
CHECK_RTC:
        TXA
        CMP #$60
        BCS BAD
VALID:  JSR INIT
        BCC COMPLETE
        JSR READ_REGS
        BCC COMPLETE
        LDY #0
COPY:   LDA READBUF,Y
        STA $3000,Y
        INY
        CPY COUNT
        BNE COPY
        STY $2F15
        LDA #0
COMPLETE:
        STA $2F10
        JSR RESTORE
        BRA RETURN
BAD:    LDA #9
        STA $2F10
RETURN: LDA VDDR
        STA $2F12
        LDA VORA
        STA $2F14
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
DEVICE_WRITE DB 0
READBUF DS 128
APP_END:
        ENDMOD
        END
'''
    stage=OUT/'source';stage.mkdir(parents=True,exist_ok=True);(OUT/'asm').mkdir(exist_ok=True)
    (stage/'board-state-reader.asm').write_text(long_branches(source))
    c.OUT=OUT;c.SOURCE=stage
    cells,sy=c.assemble('board-state-reader',0x2000,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    body=c.dense_image(cells,0x2000,sy['APP_END']);assert sy['APP_END']<0x2F00
    (OUT/'reader.bin').write_bytes(body);(OUT/'reader.s19').write_bytes(s19(dict(enumerate(body,0x2000)),0x2000))
    (OUT/'build.json').write_text(json.dumps(dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),symbols=sy,
        writes_device_data=False,allowed_devices=[0x57,0x6F],outputs=[0x2F10,0x2F15,0x3000,0x307F]),indent=2)+'\n')
    print('BUILT read-only board-state client',len(body),'bytes')

if __name__=='__main__':main()
