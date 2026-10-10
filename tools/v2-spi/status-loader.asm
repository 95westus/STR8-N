; Fixed E entries, common formatter B2:C900-CCFF -> staging 7000-73FF.
        MODULE STATUS_LOADER
        XDEF START
        XDEF AUX_END
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "status-links.inc"
        CODE
START:  JMP CONFIG_VALID ; EF00
        JMP TIME_HOOK    ; EF03
        JMP BOOT_FRAME   ; EF06
        JMP EDU_FRAME    ; EF09
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
        LDX #4
MATCH:  LDA V2_LINE,X
        CMP TIME_WORD,X
        BNE INVALID
        DEX
        BPL MATCH
        LDA #2
        BRA LOAD
INVALID:
        CLC
        RTS
BOOT_FRAME:
        LDA #0
        BRA LOAD
EDU_FRAME:
        LDA #1
LOAD:   STA $7D2B
        LDA V2_SELECTED
        PHA
        LDA #2
        STA V2_SELECTED
        STZ V2_ADDR
        LDA #$C9
        STA V2_ADDR+1
        STZ V2_BUF_PTR
        LDA #$70
        STA V2_BUF_PTR+1
READ:   LDA #16
        STA V2_COUNT
        JSR V2W_READ
        LDY #15
COPY:   LDA V2_BYTES,Y
        STA (V2_BUF_PTR),Y
        DEY
        BPL COPY
        LDA V2_ADDR
        CLC
        ADC #16
        STA V2_ADDR
        BCC ADVANCE
        INC V2_ADDR+1
ADVANCE:
        LDA V2_BUF_PTR
        CLC
        ADC #16
        STA V2_BUF_PTR
        BCC READ
        INC V2_BUF_PTR+1
        LDA V2_BUF_PTR+1
        CMP #$74
        BNE READ
        PLA
        STA V2_SELECTED
        JSR AP_CRC_INIT
        STZ V2_PTR
        LDA #$70
        STA V2_PTR+1
        LDY #0
CRC:    LDA (V2_PTR),Y
        JSR AP_CRC_BYTE
        INY
        BNE CRC
        INC V2_PTR+1
        LDA V2_PTR+1
        CMP #$74
        BNE CRC
        LDA J_CRC
        ORA J_CRC+1
        BNE BAD
        LDX #3
HEADER: LDA $7000,X
        CMP MAGIC,X
        BNE BAD
        DEX
        BPL HEADER
        LDA $7D2B
        JMP $7004
BAD:    LDX #<ERROR_TEXT
        LDY #>ERROR_TEXT
        JSR PRINT
        SEC
        RTS
TIME_WORD DB "TIME",0
MAGIC DB "BS",1,1
ERROR_TEXT DB 13,10,"Status unavailable",13,10,0
AUX_END:
        ENDMOD
