        MODULE WORK_XIP_STUB
        XDEF STUB_END
        INCLUDE "kernel.inc"
        CODE
        JMP STUB_CONSOLE
        JMP STUB_API
        DB "WK",1,2
STUB_API:
        SEI
        PHA
        LDA $7FEC
        PHA
        PHX
        LDA #2
        JSR K_V2W_SELECT
        LDX #67
STUB_COPY:
        LDA $8013,X
        STA $7B90,X
        DEX
        BPL STUB_COPY
        PLX
        PLA
        STA STUB_OLD_BANK
        PLA
        JSR $B789
        PHP
        PHA
        LDA STUB_OLD_BANK
        STA $7FEC
        PLA
        PLP
        RTS
STUB_CONSOLE:
        LDA #2
        JSR K_V2W_SELECT
        JMP $B741
STUB_OLD_BANK DB 0
STUB_END:
        ENDMOD
