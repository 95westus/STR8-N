; Fixed EF entry table. VERSION uses the reserved tail of B2:E.
        MODULE STATUS_LOADER
        XDEF START
        XDEF AUX_END
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "status-links.inc"
LIMIT EQU $7D2F
        CODE
START:  JMP CONFIG_VALID
        JMP TIME_HOOK
        JMP BOOT_FRAME
        JMP EDU_FRAME
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
        LDX #7
VMATCH: LDA V2_LINE,X
        CMP VERSION_WORD,X
        BNE TRY_TIME
        DEX
        BPL VMATCH
        LDA #7
        BRA LOAD
TRY_TIME:
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
EDU_FRAME:
LOAD:   STA $7D2B
        LDX #$D8
        LDY #$78
        CMP #8
        BCS RANGE_READY
        CMP #6
        BCC RANGE_READY
        LDX #$F8
        LDY #$76
        CMP #7
        BEQ RANGE_READY
        LDX #$E2
        LDY #$78
RANGE_READY:
        STY LIMIT
        STX V2_ADDR+1
        STZ V2_ADDR
        LDA V2_SELECTED
        PHA
        LDA #2
        STA V2_SELECTED
        STZ V2_BUF_PTR
        LDA #$6E
        STA V2_BUF_PTR+1
        JSR AP_CRC_INIT
READ:   LDA #16
        STA V2_COUNT
        JSR V2W_READ
        LDY #0
COPY:   LDA V2_BYTES,Y
        STA (V2_BUF_PTR),Y
        JSR AP_CRC_BYTE
        INY
        CPY #16
        BNE COPY
        LDA V2_ADDR
        CLC
        ADC #16
        STA V2_ADDR
        STA V2_BUF_PTR
        BCC READ
        INC V2_ADDR+1
        INC V2_BUF_PTR+1
        LDA V2_BUF_PTR+1
        CMP LIMIT
        BNE READ
        PLA
        STA V2_SELECTED
        LDA J_CRC
        ORA J_CRC+1
        BNE BAD
        LDX #3
HEADER: LDA $6E00,X
        CMP MAGIC,X
        BNE BAD
        DEX
        BPL HEADER
        LDA $7D2B
        JMP $6E04
BAD:    JMP STORAGE_ASSET_FAIL
TIME_WORD DB "TIME",0
VERSION_WORD DB "VERSION",0
MAGIC DB "BS",1,3
AUX_END:
        ENDMOD
