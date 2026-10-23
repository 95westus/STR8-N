; Modes 3=load SRAM manager for MAINT, 4=legacy S/R/T route, 5=auto flash.
; All callers are foreground in B3; the sealed asset is already validated.
V2_SELECTED EQU $F3
V2_ADDR EQU $E2
V2_COUNT EQU $EA
V2_BYTES EQU $7C80
V2_VALUE EQU $E8
V2_BUF_PTR EQU $E6
STORAGE:
        CMP #8
        BNE XIP_NOT_APPS
        LDX #4
        JSR V2_SKIP_SPACES
        BEQ XIP_APPS_OK
        JMP SR_CLI_BAD
XIP_APPS_OK:
        LDA #4
        STA $7D2D
        JMP XIP_LOAD
XIP_NOT_APPS:
        CMP #5
        BNE XIP_NOT_AUTO
        JMP AUTO_FIND
XIP_NOT_AUTO:
        CMP #3
        BNE XIP_NORMAL
        JMP XIP_FAIL
XIP_NORMAL:
        LDA $7C00
        CMP #'R'
        BEQ XIP_R
        JMP LEGACY_S
XIP_R:
        LDX #1
        JSR V2_SKIP_SPACES
        CMP #'2'
        BNE XIP_NAME_START
        INX
        JSR V2_SKIP_SPACES
XIP_NAME_START:
        STX $7D2C
        LDX $7D2C
        LDY #0
XIP_MATCH_0:
        LDA XIP_NAME_0,Y
        BEQ XIP_END_0
        CMP $7C00,X
        BNE XIP_NEXT_0
        INX
        INY
        BRA XIP_MATCH_0
XIP_END_0:
        JSR V2_SKIP_SPACES
        BEQ XIP_FOUND_0
        JMP SR_CLI_BAD
XIP_FOUND_0:
        LDA #0
        STA $7D2D
        JMP XIP_LOAD
XIP_NEXT_0:
        LDX $7D2C
        LDY #0
XIP_MATCH_1:
        LDA XIP_NAME_1,Y
        BEQ XIP_END_1
        CMP $7C00,X
        BNE XIP_NEXT_1
        INX
        INY
        BRA XIP_MATCH_1
XIP_END_1:
        JSR V2_SKIP_SPACES
        BEQ XIP_FOUND_1
        JMP SR_CLI_BAD
XIP_FOUND_1:
        LDA #1
        STA $7D2D
        JMP XIP_LOAD
XIP_NEXT_1:
        LDX $7D2C
        LDY #0
XIP_MATCH_2:
        LDA XIP_NAME_2,Y
        BEQ XIP_END_2
        CMP $7C00,X
        BNE XIP_NEXT_2
        INX
        INY
        BRA XIP_MATCH_2
XIP_END_2:
        JSR V2_SKIP_SPACES
        BEQ XIP_FOUND_2
        JMP SR_CLI_BAD
XIP_FOUND_2:
        LDA #2
        STA $7D2D
        JMP XIP_LOAD
XIP_NEXT_2:
        LDX $7D2C
        LDY #0
XIP_MATCH_3:
        LDA XIP_NAME_3,Y
        BEQ XIP_END_3
        CMP $7C00,X
        BNE XIP_NEXT_3
        INX
        INY
        BRA XIP_MATCH_3
XIP_END_3:
        JSR V2_SKIP_SPACES
        BEQ XIP_FOUND_3
        JMP SR_CLI_BAD
XIP_FOUND_3:
        LDA #3
        STA $7D2D
        JMP XIP_LOAD
XIP_NEXT_3:
        JMP LEGACY_R
LEGACY_R:
        JMP SR_CLI_RESTORE
LEGACY_S:
        CMP #'S'
                        BEQ SAVE_ROUTE
        JMP SR_CLI_TABLE
SAVE_ROUTE:
        LDX #1
        JSR SR_PARSE_BANK
                        BCS STOR_LONG_46
                        JMP SAVE_OLD
STOR_LONG_46:
        JSR V2_SKIP_SPACES
        STX AUTO_POS
        LDY #0
AUTO_MATCH:
        LDA $7C00,X
        CMP AUTO_WORD,Y
                        BEQ STOR_LONG_53
                        JMP SAVE_OLD
STOR_LONG_53:
        INX
        INY
        CPY #5
                        BNE AUTO_MATCH
        LDA $7D90
        STA $7D2C
        JSR V2_HEX_WORD
                        BCC SAVE_OLD
        LDA V2_VALUE
        STA RAM_FIRST
        LDA V2_VALUE+1
        STA RAM_FIRST+1
        JSR V2_HEX_WORD
                        BCC SAVE_OLD
        SEC
        LDA V2_VALUE
        SBC RAM_FIRST
        STA $7D2D
        LDA V2_VALUE+1
        SBC RAM_FIRST+1
                        BCC AUTO_CLI_BAD
        STA $7D2E
        CLC
        LDA $7D2D
        ADC #25
        STA $7D2D
                        BCC AUTO_SIZED
        INC $7D2E
                        BEQ AUTO_CLI_BAD
AUTO_SIZED:
        JSR AUTO_FIND
                        BCC AUTO_CLI_BAD
        STA RAM_FIRST
        STX RAM_FIRST+1
        LDX #<AUTO_TEXT
        LDY #>AUTO_TEXT
        JSR PRINT
        LDA $7D2C
        JSR $7E7C
        LDA #':'
        JSR $7E6D
        LDA RAM_FIRST+1
        JSR $7E7C
        LDA RAM_FIRST
        JSR $7E7C
        JSR $7E7F
        ; Replace AUTO in the original line; standard SAVE repeats every
        ; existing source/range/erased-space check and commits last.
        LDX AUTO_POS
        LDA RAM_FIRST+1
        JSR LINE_HEX
        LDA RAM_FIRST
        JSR LINE_HEX
        JMP SR_CLI_SAVE
SAVE_OLD:
        JMP SR_CLI_SAVE
AUTO_CLI_BAD:
        JMP SR_CLI_BAD
MANAGER_BAD_CLI:
        JMP SR_CLI_BAD
LINE_HEX:
        PHA
        LSR A
        LSR A
        LSR A
        LSR A
        JSR LINE_NIBBLE
        PLA
        AND #15
LINE_NIBBLE:
        CMP #10
                        BCC LINE_DIGIT
        ADC #6
LINE_DIGIT:
        ADC #'0'
        STA $7C00,X
        INX
        RTS
FLASH_BYTE:
        LDA #1
        STA V2_COUNT
        JSR V2W_READ
        LDA V2_BYTES
        RTS
; Finalizer borrows journal scratch only while copying; no bus calls occur.
AUTO_FIND:
        LDA $7D2C
        CMP #3
                        BCC STOR_LONG_216
                        JMP AUTO_NONE
STOR_LONG_216:
        STA V2_SELECTED
        LDA $7D2D
        PHA
        LDA #$FC
        STA V2_ADDR
        LDA #$FF
        STA V2_ADDR+1
        LDA #2
        STA V2_COUNT
        JSR V2W_READ
        LDA V2_BYTES+1
        CMP #$80
                        BCC AUTO_START
        CMP #$FF
                        BNE AUTO_REJECT
        LDA V2_BYTES
        CMP #$FF
                        BEQ AUTO_START
AUTO_REJECT:
        PLA
                        JMP AUTO_NONE
AUTO_START:
        PLA
        STA WANTED
        LDA $7D2E
        STA WANTED+1
        ORA WANTED
                        BNE STOR_LONG_244
                        JMP AUTO_NONE
STOR_LONG_244:
        STZ V2_ADDR
        LDA #$80
        STA V2_ADDR+1
        STZ RUN_SIZE
        STZ RUN_SIZE+1
AUTO_SCAN:
        LDA V2_ADDR+1
        CMP #$E0
                        BCC STOR_LONG_253
                        JMP AUTO_NONE
STOR_LONG_253:
        LDA $7D2C
        CMP #3
                        BCC STOR_LONG_256
                        JMP AUTO_NONE
STOR_LONG_256:
        CMP #2
                        BNE AUTO_READ
        LDA V2_ADDR+1
        CMP #$80
                        BCC AUTO_READ
        CMP #$E0
                        BCS STOR_LONG_263
                        JMP AUTO_SKIP_ASSET
STOR_LONG_263:
AUTO_READ:
        JSR FLASH_BYTE
        CMP #$FF
                        BNE AUTO_USED
        LDA RUN_SIZE
        ORA RUN_SIZE+1
                        BNE AUTO_EXTEND
        LDA V2_ADDR
        STA RUN_FIRST
        LDA V2_ADDR+1
        STA RUN_FIRST+1
AUTO_EXTEND:
        INC RUN_SIZE
                        BNE AUTO_COMPARE
        INC RUN_SIZE+1
AUTO_COMPARE:
        LDA RUN_SIZE
        CMP WANTED
                        BEQ STOR_LONG_282
                        JMP AUTO_NEXT
STOR_LONG_282:
        LDA RUN_SIZE+1
        CMP WANTED+1
                        BEQ STOR_LONG_285
                        JMP AUTO_NEXT
STOR_LONG_285:
        LDA RUN_FIRST
        LDX RUN_FIRST+1
        SEC
        RTS
AUTO_USED:
        STZ RUN_SIZE
        STZ RUN_SIZE+1
        CMP #'S'
                        BNE AUTO_NEXT
        ; Protect the entire extent of valid or pending SR v1 records, even
        ; when their payload contains long FF runs.
        LDA #16
        STA V2_COUNT
        JSR V2W_READ
        LDA V2_BYTES+1
        CMP #'R'
                        BNE AUTO_NEXT
        LDA V2_BYTES+2
        CMP #1
                        BNE AUTO_NEXT
        LDA V2_BYTES+3
        CMP #$3F
                        BEQ AUTO_RECORD
        CMP #$FF
                        BNE AUTO_NEXT
AUTO_RECORD:
        LDA V2_BYTES+6
        ORA V2_BYTES+7
                        BEQ AUTO_NEXT
        LDA V2_BYTES+5
        CMP #2
                        BCC AUTO_NEXT
        CMP #$67
                        BCS AUTO_NEXT
        LDA V2_BYTES+6
        CLC
        ADC #24
        STA V2_VALUE
        LDA V2_BYTES+7
        ADC #0
        STA V2_VALUE+1
                        BCS AUTO_NONE
        CLC
        LDA V2_VALUE
        ADC V2_ADDR
        STA V2_VALUE
        LDA V2_VALUE+1
        ADC V2_ADDR+1
                        BCS AUTO_NONE
        CMP #$E0
                        BCS AUTO_NONE
        STA V2_ADDR+1
        LDA V2_VALUE
        STA V2_ADDR
                        JMP AUTO_SCAN
AUTO_SKIP_ASSET:
        STZ V2_ADDR
        LDA #$E0
        STA V2_ADDR+1
        STZ RUN_SIZE
        STZ RUN_SIZE+1
                        JMP AUTO_SCAN
AUTO_NEXT:
        INC V2_ADDR
                        BEQ STOR_LONG_350
                        JMP AUTO_SCAN
STOR_LONG_350:
        INC V2_ADDR+1
                        JMP AUTO_SCAN
AUTO_NONE:
        LDA #0
        CLC
        RTS
; Encoded comparison bytes cannot masquerade as a saved SR record to TABLE.
AUTO_WORD DB "AUTO "
AUTO_TEXT DB "SAVE B",0
LEFT_SIZE DS 2
WANTED DS 2
RUN_SIZE DS 2
RUN_FIRST DS 2
AUTO_POS DB 0
RAM_FIRST DS 2
XIP_LOAD:
        LDA $7D2D
        CMP #1
        BNE XIP_VERIFY
        LDA $7D07
        AND #8
        BNE XIP_VERIFY
        JMP XIP_FAIL
XIP_VERIFY:
        LDA V2_SELECTED
        STA $7D2E
        LDA #2
        STA V2_SELECTED
        STZ V2_ADDR
        LDA #$80
        STA V2_ADDR+1
        LDA #4
        STA V2_COUNT
        JSR V2W_READ
        LDX #3
XIP_HEADER_CHECK:
        LDA V2_BYTES,X
        CMP XIP_MAGIC,X
        BNE XIP_FAIL
        DEX
        BPL XIP_HEADER_CHECK
        JSR AP_CRC_INIT
XIP_CRC:
        JSR FLASH_BYTE
        JSR AP_CRC_BYTE
        INC V2_ADDR
        BNE XIP_CRC
        INC V2_ADDR+1
        LDA V2_ADDR+1
        CMP #$D8
        BNE XIP_CRC
        LDA $7D38
        ORA $7D39
        BNE XIP_FAIL
        LDA #2
        JSR $7848
        LDX #67
XIP_GATE_COPY:
        LDA $8013,X
        STA $7B90,X
        DEX
        BPL XIP_GATE_COPY
        LDA #3
        STA $7BFA
        STA $7BFB
        STA V2_SELECTED
        LDA $7D2D
        CMP #2
        BNE XIP_ENTER
        LDX #63
XIP_STUB_COPY:
        LDA $8057,X
        STA $5000,X
        DEX
        BPL XIP_STUB_COPY
XIP_ENTER:
        LDA $7D2D
        ASL A
        TAX
        LDA XIP_ENTRIES,X
        STA $FE
        LDA XIP_ENTRIES+1,X
        STA $FF
        JMP ($00FE)
XIP_FAIL:
        INC $7EE7
        LDA #3
        STA V2_SELECTED
        JSR $7848
        JMP SR_CLI_BAD
XIP_ENTRIES:
        DW $8097
        DW $A94E
        DW $B741
        DW $CA1F
        DW $CFAE
XIP_NAME_0 DB "MAINT",0
XIP_NAME_1 DB "SRAM",0
XIP_NAME_2 DB "WORK",0
XIP_NAME_3 DB "EDU",0
XIP_MAGIC DB "UX",3,42
