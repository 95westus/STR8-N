; Sector-aligned opaque entry. No F ROM call while the application bank hides F.
; F cold boot or MON Bn/Gentry has already installed the RAM ABI and worker.
        MODULE BANK_MONITOR_ENTRY
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "bank-monitor-layout.inc"
        CODE
BM_ROM_START:
        SEI
        CLD
        LDX #3
BM_ABI_CHECK:
        LDA $7E60,X
        CMP BM_ABI,X
        BNE BM_ROM_STOP
        DEX
        BPL BM_ABI_CHECK
        LDA #<(BM_ROM_START+$80)
        STA V2_PTR
        LDA #>(BM_ROM_START+$80)
        STA V2_PTR+1
        STZ V2_ADDR
        LDA #2
        STA V2_ADDR+1
        LDX #BM_COPY_PAGES
        LDY #0
BM_ROM_COPY:
        LDA (V2_PTR),Y
        STA (V2_ADDR),Y
        INY
        BNE BM_ROM_COPY
        INC V2_PTR+1
        INC V2_ADDR+1
        DEX
        BNE BM_ROM_COPY
        LDA V2_SELECTED
        STA BM_HOME_ADDRESS
        JMP $0200
BM_ROM_STOP:
        JMP BM_ROM_STOP
BM_ABI: DB $52,$41,1,13
BM_ROM_END:
        ENDMOD
        END
