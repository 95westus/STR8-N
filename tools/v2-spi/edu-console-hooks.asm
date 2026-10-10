; Fixed helpers in the existing E help pocket, covered by the complete E seal.
        MODULE EDU_HOOKS
        XDEF START
        XDEF AUX_END
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "edu-links.inc"
PTR EQU $E0
        CODE
START:  JMP CONFIG_VALID ; EF50
        JMP TIME_HOOK    ; EF53
        JMP OFF_BANNER   ; EF56
CONFIG_VALID:
        LDA V2_CONFIG
        CMP #1
        BNE INVALID
        STZ V2_CFG_SUM
        STZ V2_CFG_SUM2
        LDX #0
SUM:    LDA V2_CONFIG,X
        CLC
        ADC V2_CFG_SUM
        STA V2_CFG_SUM
        CLC
        ADC V2_CFG_SUM2
        STA V2_CFG_SUM2
        INX
        CPX #14
        BNE SUM
        LDA V2_CFG_SUM
        CMP V2_CONFIG+14
        BNE INVALID
        LDA V2_CFG_SUM2
        CMP V2_CONFIG+15
        BNE INVALID
        SEC
        RTS
TIME_HOOK:
        LDA $7D27
        CMP #2
        BEQ OFF_TIME
        LDA SVC_BANNER_PTR+1
        BEQ INVALID
        JMP $890A
OFF_TIME:
        LDX #3
MATCH:  LDA V2_LINE,X
        CMP TIME_WORD,X
        BNE INVALID
        DEX
        BPL MATCH
        LDA V2_LINE+4
        BNE INVALID
        LDX #<UNAVAILABLE
        LDY #>UNAVAILABLE
        JSR PRINT
        SEC
        RTS
INVALID:
        CLC
        RTS
OFF_BANNER:
        LDX #<OFF_TEXT
        LDY #>OFF_TEXT
PRINT:  STX PTR
        STY PTR+1
        LDY #0
NEXT:   LDA (PTR),Y
        BEQ RETURN
        JSR $7E6D
        INY
        BRA NEXT
RETURN: RTS
TIME_WORD DB "TIME"
UNAVAILABLE DB "RTCC: unavailable",13,10,0
AUX_END:
        ENDMOD
