"""RAM-only RTC SRAM diagnostic, LED patterns and read-only bank-sector probe."""
import hashlib,json
from pathlib import Path
from build_v2_spi_resident import assemble
from build_bank_maint_v2 import long_branches
from beta4_migration import s19
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/beta23-soak-probes'

def main():
    original=(ROOT/'tools/v2-rtc/rtc-service.asm').read_text()
    low=original[original.index('\nINIT '):original.index('\nBUSY DB')]
    rtc='''        MODULE RTC_SRAM_SOAK
        XDEF START
        XDEF APP_END
VORA EQU $7FCF
VDDR EQU $7FC3
RTC_BUS_BUSY EQU 1
RTC_NACK EQU 2
RTC_TIMEOUT EQU 3
        CODE
START:  SEI
        CLD
        STZ $3004
        LDA $7D27
        CMP #1
        BNE UNAVAILABLE
        LDA $7D07
        AND #1
        BEQ UNAVAILABLE
        LDA $3001
        CMP #$20
        BCC BAD
        CMP #$60
        BCS BAD
        STA REGADDR
        LDA $3002
        BEQ BAD
        CMP #17
        BCS BAD
        STA COUNT
        CLC
        ADC REGADDR
        CMP #$61
        BCS BAD
        LDA $3000
        CMP #1
        BEQ READY
        CMP #2
        BNE BAD
READY:  STZ INDEX
        JSR INIT
        BCC CLEANUP
        LDA $3000
        CMP #1
        BEQ READ
        LDX #15
COPY_IN:
        LDA $3100,X
        STA WRITEBUF,X
        DEX
        BPL COPY_IN
        JSR WRITE_REGS
        BRA CLEANUP
READ:   JSR READ_REGS
        PHA
        LDX #15
COPY_OUT:
        LDA READBUF,X
        STA $3100,X
        DEX
        BPL COPY_OUT
        PLA
CLEANUP:
        STA $3003
        JSR RESTORE
        LDA INDEX
        STA $3004
        JMP $7E67
UNAVAILABLE:
        LDA #$80
        BRA FAIL
BAD:    LDA #9
FAIL:   STA $3003
        JMP $7E67
'''+low+'''
SAVEORA DB 0
SAVEDDR DB 0
REGADDR DB 0
COUNT DB 0
INDEX DB 0
ERROR DB 0
BYTE DB 0
ACKBIT DB 0
READBUF DS 16
WRITEBUF DS 16
APP_END:
        ENDMOD
        END
'''
    led='''        MODULE SOAK_LED
        XDEF START
        XDEF APP_END
        CODE
START:  SEI
        CLD
        LDA $7FA1
        AND #4
        BEQ DONE
        LDA $7FA0
        STA OLD_LED
        STZ INDEX
NEXT:   LDA #'~'
        JSR $7E6D
        LDX INDEX
        LDA $3200,X
        STA $7FA0
        JSR $7E70
        INC INDEX
        LDA INDEX
        CMP #8
        BNE NEXT
        LDA OLD_LED
        STA $7FA0
DONE:   JMP $7E67
OLD_LED DB 0
INDEX DB 0
APP_END:
        ENDMOD
        END
'''
    reports={}
    sector=(ROOT/'tools/v2-rtc/soak-sector-read.asm').read_text()
    for name,text in [('rtc-sram',rtc),('led',led),('sector-read',sector)]:
        stage=OUT/name/'source';stage.mkdir(parents=True,exist_ok=True)
        (stage/(name+'.asm')).write_text(long_branches(text))
        body,symbols,_=assemble(stage,name,0x4000,'APP_END',0x4000)
        assert symbols['APP_END']<0x5000
        (OUT/name/(name+'.bin')).write_bytes(body);(OUT/name/(name+'.s19')).write_bytes(s19(dict(enumerate(body,0x4000)),0x4000))
        reports[name]=dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),symbols=symbols)
    (OUT/'build.json').write_text(json.dumps(reports,indent=2)+'\n');print('BUILT RTC SRAM, LED and bank-sector RAM probes')

if __name__=='__main__':main()
