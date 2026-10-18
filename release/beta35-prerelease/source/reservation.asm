; Offline/model-only append helper. The caller has initialized the frozen
; migrator's RAM worker and hash routines. No sector erase or ROM calls.
        MODULE RESERVATION
        XDEF R_END
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "reservation-links.inc"
R_BANK EQU $6230
R_INDEX EQU $6231
R_CRC_LO EQU $6232
R_CRC_HI EQU $6233
R_SUM_A EQU $6234
R_SUM_B EQU $6235
R_STATUS EQU $6236
R_HASHES EQU $3500
R_DEST EQU $3510
R_RECORD_HASH EQU $3512
R_RECORD EQU $3600
        CODE
R_ENTRY:
        SEI
        CLD
        STZ R_STATUS
        JSR R_PREFLIGHT
        BCC R_BAD
        JSR R_VALIDATE
        BCC R_BAD
        JSR R_CONFIG
        BCC R_BAD
        JSR R_ERASED
        BCC R_BAD
        LDA #1
        STA V2_NMI_HOLD
        JSR R_PROGRAM
        BCC R_BAD
        JSR R_VERIFY_PREFIX
        BCC R_BAD
        LDY #127
        LDA (V2_FLASH_PTR),Y
        CMP #$FF
        BNE R_BAD
        LDA R_DEST
        ORA #127
        STA V2_FLASH_PTR
        STZ V2_FLASH_DATA
        JSR V2W_BYTE
        BCC R_BAD
        JSR R_VERIFY_PREFIX
        BCC R_BAD
        LDY #127
        LDA (V2_FLASH_PTR),Y
        BNE R_BAD
        JSR R_CLEANUP
        SEC
        RTS
R_BAD:
        INC R_STATUS
        JSR R_CLEANUP
        CLC
        RTS
R_CLEANUP:
        LDA #3
        STA V2_SELECTED
        JSR V2W_SELECT
        STZ V2_NMI_HOLD
        RTS
R_PREFLIGHT:
        STZ R_BANK
R_BANK_LOOP:
        LDA R_BANK
        STA V2_SELECTED
        JSR V2W_SELECT
        STZ V2_PTR
        LDA #$80
        STA V2_PTR+1
        STZ $620C
        JSR MIG_HASH_RANGE
        LDA R_BANK
        ASL A
        ASL A
        TAX
        LDY #0
R_HASH_LOOP:
        LDA R_HASHES,X
        CMP $6204,Y
        BNE R_HASH_BAD
        INX
        INY
        CPY #4
        BNE R_HASH_LOOP
        INC R_BANK
        LDA R_BANK
        CMP #4
        BNE R_BANK_LOOP
        ; Also bind the complete 256-byte record input page, including padding.
        STZ V2_PTR
        LDA #$36
        STA V2_PTR+1
        LDA #$37
        STA $620C
        JSR MIG_HASH_RANGE
        LDX #3
R_RECORD_HASH_LOOP:
        LDA R_RECORD_HASH,X
        CMP $6204,X
        BNE R_HASH_BAD
        DEX
        BPL R_RECORD_HASH_LOOP
        SEC
        RTS
R_HASH_BAD: CLC
        RTS
R_VALIDATE:
        LDA R_DEST
        AND #$7F
        BNE R_INVALID
        LDA R_DEST+1
        AND #$E0
        CMP #$C0
        BNE R_INVALID
        LDA R_RECORD
        CMP #'W'
        BNE R_INVALID
        LDA R_RECORD+1
        CMP #'C'
        BNE R_INVALID
        LDA R_RECORD+2
        CMP #1
        BNE R_INVALID
        LDA R_RECORD+3
        ORA R_RECORD+127
        BNE R_INVALID
        LDA R_RECORD+4
        ORA R_RECORD+5
        ORA R_RECORD+6
        ORA R_RECORD+7
        BEQ R_INVALID
        LDA #$FF
        STA R_CRC_LO
        STA R_CRC_HI
        LDX #0
R_CRC_BYTE:
        LDA R_RECORD,X
        EOR R_CRC_HI
        STA R_CRC_HI
        LDY #8
R_CRC_BIT:
        ASL R_CRC_LO
        ROL R_CRC_HI
        BCC R_CRC_NEXT
        LDA R_CRC_LO
        EOR #$21
        STA R_CRC_LO
        LDA R_CRC_HI
        EOR #$10
        STA R_CRC_HI
R_CRC_NEXT:
        DEY
        BNE R_CRC_BIT
        INX
        CPX #120
        BNE R_CRC_BYTE
        LDA R_CRC_LO
        CMP R_RECORD+120
        BNE R_INVALID
        LDA R_CRC_HI
        CMP R_RECORD+121
        BNE R_INVALID
        SEC
        RTS
R_INVALID: CLC
        RTS
R_CONFIG:
        LDA R_RECORD+8
        CMP #1
        BNE R_CONFIG_BAD
        LDA R_RECORD+9
        CMP #2
        BCS R_CONFIG_BAD
        LDA R_RECORD+10
        CMP #4
        BCS R_CONFIG_BAD
        LDA R_RECORD+13
        CMP #10
        BCC R_CONFIG_BAD
        LDA R_RECORD+14
        CMP #2
        BCS R_CONFIG_BAD
        LDA R_RECORD+21
        BEQ R_CONFIG_TAG_OK
        CMP #$A5
        BNE R_CONFIG_BAD
R_CONFIG_TAG_OK:
        LDA R_RECORD+15
        CMP #'P'
        BNE R_CONFIG_BAD
        LDA R_RECORD+16
        CMP #$A0
        BNE R_CONFIG_BAD
        LDX #3
R_CONFIG_GENERATION:
        LDA R_RECORD+17,X
        CMP $A008,X
        BNE R_CONFIG_BAD
        DEX
        BPL R_CONFIG_GENERATION
        STZ R_SUM_A
        STZ R_SUM_B
        LDX #8
R_CONFIG_SUM:
        LDA R_SUM_A
        CLC
        ADC R_RECORD,X
        STA R_SUM_A
        CLC
        ADC R_SUM_B
        STA R_SUM_B
        INX
        CPX #22
        BNE R_CONFIG_SUM
        LDA R_SUM_A
        CMP R_RECORD+22
        BNE R_CONFIG_BAD
        LDA R_SUM_B
        CMP R_RECORD+23
        BNE R_CONFIG_BAD
        SEC
        RTS
R_CONFIG_BAD: CLC
        RTS
R_SET_PTR:
        LDA R_DEST
        STA V2_FLASH_PTR
        LDA R_DEST+1
        STA V2_FLASH_PTR+1
        RTS
R_ERASED:
        JSR R_SET_PTR
        LDY #127
R_ERASED_LOOP:
        LDA (V2_FLASH_PTR),Y
        CMP #$FF
        BNE R_NOT_ERASED
        DEY
        BPL R_ERASED_LOOP
        SEC
        RTS
R_NOT_ERASED: CLC
        RTS
R_PROGRAM:
        STZ R_INDEX
R_PROGRAM_LOOP:
        LDX R_INDEX
        LDA R_RECORD,X
        CMP #$FF
        BEQ R_PROGRAM_NEXT
        STA V2_FLASH_DATA
        LDA R_DEST
        CLC
        ADC R_INDEX
        STA V2_FLASH_PTR
        LDA R_DEST+1
        STA V2_FLASH_PTR+1
        JSR V2W_BYTE
        BCC R_PROGRAM_BAD
R_PROGRAM_NEXT:
        INC R_INDEX
        LDA R_INDEX
        CMP #127
        BNE R_PROGRAM_LOOP
        SEC
        RTS
R_PROGRAM_BAD: CLC
        RTS
R_VERIFY_PREFIX:
        JSR R_SET_PTR
        LDY #126
R_VERIFY_LOOP:
        LDA (V2_FLASH_PTR),Y
        CMP R_RECORD,Y
        BNE R_VERIFY_BAD
        DEY
        BPL R_VERIFY_LOOP
        SEC
        RTS
R_VERIFY_BAD: CLC
        RTS
R_END:
        ENDMOD
