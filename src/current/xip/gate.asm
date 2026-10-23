        MODULE XIP_GATE
        XDEF G_END
        INCLUDE "kernel.inc"
        CODE
G_START:
        PHP
        PHA
        PHX
        LDA X28_CALL_BANK
        JSR K_V2W_SELECT
        PLX
        PLA
        PLP
G_CALL: JSR $FFFF
        PHP
        PHA
        PHX
        LDA #2
        JSR K_V2W_SELECT
        PLX
        PLA
        PLP
        RTS
G_READ:
        PHP
        PHX
        LDA X28_BANK
        JSR K_V2W_SELECT
        PLX
        PLP
        LDA (X28_PTR),Y
        PHP
        PHA
        PHX
        LDA #2
        JSR K_V2W_SELECT
        PLX
        PLA
        PLP
        RTS
G_EXEC:
        LDA #3
        JSR K_V2W_SELECT
        JMP ($00FE)
G_TAIL:
        LDA X28_CALL_BANK
        JSR K_V2W_SELECT
        JMP (X28_CALL+1)
G_END:
        ENDMOD
