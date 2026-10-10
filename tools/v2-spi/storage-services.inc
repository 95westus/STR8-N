; Modes 3=load SRAM manager for MAINT, 4=legacy S/R/T route, 5=auto flash.
; All callers are foreground in B3; the sealed asset is already validated.
V2_SELECTED EQU $F3
V2_ADDR EQU $E2
V2_COUNT EQU $EA
V2_BYTES EQU $7C80
V2_VALUE EQU $E8
V2_BUF_PTR EQU $E6
STORAGE:
        CMP #3
        BEQ LOAD_MANAGER
        CMP #5
        BEQ AUTO_FIND
        LDA $7C00
        CMP #'R'
        BNE LEGACY_S
        LDX #1
        JSR V2_SKIP_SPACES
        CMP #'2'
        BNE SRAM_NAME
        INX
        JSR V2_SKIP_SPACES
SRAM_NAME:
        LDY #0
NAME_MATCH:
        LDA $7C00,X
        CMP MANAGER_NAME,Y
        BNE LEGACY_R
        INX
        INY
        CPY #4
        BNE NAME_MATCH
        JSR V2_SKIP_SPACES
        BNE MANAGER_BAD_CLI
        LDA #6
        STA $7D2B
        BRA LOAD_MANAGER
LEGACY_R:
        JMP SR_CLI_RESTORE
LEGACY_S:
        CMP #'S'
        BEQ SAVE_ROUTE
        JMP SR_CLI_TABLE
SAVE_ROUTE:
        LDX #1
        JSR SR_PARSE_BANK
        BCC SAVE_OLD
        JSR V2_SKIP_SPACES
        STX AUTO_POS
        LDY #0
AUTO_MATCH:
        LDA $7C00,X
        CMP AUTO_WORD,Y
        BNE SAVE_OLD
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
LOAD_MANAGER:
        LDA V2_SELECTED
        STA $7D2A
        LDA $7D07
        AND #8
        BEQ MANAGER_BAD
        LDA #2
        STA V2_SELECTED
        STZ V2_ADDR
        LDA #$A0
        STA V2_ADDR+1
        LDA #16
        STA V2_COUNT
        JSR V2W_READ
        LDX #7
MANAGER_HEADER:
        LDA V2_BYTES,X
        EOR #$80
        CMP MANAGER_EXPECTED,X
        BNE MANAGER_BAD
        DEX
        BPL MANAGER_HEADER
        JSR AP_CRC_INIT
        LDA #$18
        STA V2_ADDR
        LDA #$A0
        STA V2_ADDR+1
        LDA #<SRAM_IMAGE_BYTES
        STA LEFT_SIZE
        LDA #>SRAM_IMAGE_BYTES
        STA LEFT_SIZE+1
MANAGER_CRC:
        JSR FLASH_BYTE
        JSR AP_CRC_BYTE
        INC V2_ADDR
        BNE MANAGER_NEXT
        INC V2_ADDR+1
MANAGER_NEXT:
        LDA LEFT_SIZE
        BNE MANAGER_LOW
        DEC LEFT_SIZE+1
MANAGER_LOW:
        DEC LEFT_SIZE
        LDA LEFT_SIZE
        ORA LEFT_SIZE+1
        BNE MANAGER_CRC
        LDA $7D38
        ORA $7D39
        BNE MANAGER_BAD
        LDX #FINAL_END-FINALIZER-1
INSTALL_FINAL:
        LDA FINALIZER,X
        STA $6B00,X
        DEX
        CPX #$FF
        BNE INSTALL_FINAL
        JMP $6B00
MANAGER_BAD:
        LDA $7D2A
        STA V2_SELECTED
        LDX #<MANAGER_ERROR
        LDY #>MANAGER_ERROR
        JSR PRINT
        LDA #$80
        LDX $7D2B
        CPX #6
        BEQ MANAGER_BAD_CLI
        CLC
        RTS
FLASH_BYTE:
        LDA #1
        STA V2_COUNT
        JSR V2W_READ
        LDA V2_BYTES
        RTS
; Finalizer borrows journal scratch only while copying; no bus calls occur.
FINALIZER:
        STZ $7D2F
FINAL_SEGMENT:
        LDX $7D2F
        LDA $6B00+FINAL_TABLE-FINALIZER,X
        STA V2_ADDR
        LDA $6B01+FINAL_TABLE-FINALIZER,X
        STA V2_ADDR+1
        LDA $6B02+FINAL_TABLE-FINALIZER,X
        STA V2_BUF_PTR
        LDA $6B03+FINAL_TABLE-FINALIZER,X
        STA V2_BUF_PTR+1
        LDA $6B04+FINAL_TABLE-FINALIZER,X
        STA V2_VALUE
        LDA $6B05+FINAL_TABLE-FINALIZER,X
        STA V2_VALUE+1
FINAL_COPY:
        LDA #16
        STA V2_COUNT
        JSR V2W_READ
        LDY #15
FINAL_BYTES:
        LDA V2_BYTES,Y
        STA (V2_BUF_PTR),Y
        DEY
        BPL FINAL_BYTES
        LDA V2_ADDR
        CLC
        ADC #16
        STA V2_ADDR
        BCC FINAL_DEST
        INC V2_ADDR+1
FINAL_DEST:
        LDA V2_BUF_PTR
        CLC
        ADC #16
        STA V2_BUF_PTR
        BCC FINAL_COUNT
        INC V2_BUF_PTR+1
FINAL_COUNT:
        SEC
        LDA V2_VALUE
        SBC #16
        STA V2_VALUE
        BCS FINAL_LEFT
        DEC V2_VALUE+1
FINAL_LEFT:
        ORA V2_VALUE+1
        BNE FINAL_COPY
        LDA $7D2F
        CLC
        ADC #6
        STA $7D2F
        CMP #24
        BNE FINAL_SEGMENT
        LDA $7D2A
        STA V2_SELECTED
        LDA $7D2B
        CMP #6
        BNE FINAL_RETURN
        JMP $6C00
FINAL_RETURN:
        LDA #0
        SEC
        RTS
FINAL_TABLE:
        DW SRAM_CORE_SOURCE,$6C00,SRAM_CORE_BYTES
        DW SRAM_DATA_SOURCE,$6700,256
        DW SRAM_AUX_SOURCE,$6800,256
        DW SRAM_EXT_SOURCE,$7B90,96
FINAL_END:
; Count bytes including flash header. Caller selects bank at 7D2C and size
; at 7D2D/2E. Result A/X is the header address; carry clear means no safe run.
AUTO_FIND:
        LDA $7D2C
        CMP #3
        BCS AUTO_NONE
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
        BRA AUTO_NONE
AUTO_START:
        PLA
        STA WANTED
        LDA $7D2E
        STA WANTED+1
        ORA WANTED
        BEQ AUTO_NONE
        STZ V2_ADDR
        LDA #$80
        STA V2_ADDR+1
        STZ RUN_SIZE
        STZ RUN_SIZE+1
AUTO_SCAN:
        LDA V2_ADDR+1
        CMP #$E0
        BCS AUTO_NONE
        LDA $7D2C
        CMP #3
        BCS AUTO_NONE
        CMP #2
        BNE AUTO_READ
        LDA V2_ADDR+1
        CMP #$C8
        BCC AUTO_READ
        CMP #$D0
        BCC AUTO_SKIP_ASSET
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
        BNE AUTO_NEXT
        LDA RUN_SIZE+1
        CMP WANTED+1
        BNE AUTO_NEXT
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
        BRA AUTO_SCAN
AUTO_SKIP_ASSET:
        STZ V2_ADDR
        LDA #$D0
        STA V2_ADDR+1
        STZ RUN_SIZE
        STZ RUN_SIZE+1
        BRA AUTO_SCAN
AUTO_NEXT:
        INC V2_ADDR
        BNE AUTO_SCAN
        INC V2_ADDR+1
        BRA AUTO_SCAN
AUTO_NONE:
        LDA #0
        CLC
        RTS
MANAGER_NAME DB "SRAM",0
; Encoded comparison bytes cannot masquerade as a saved SR record to TABLE.
MANAGER_EXPECTED DB $D3,$D2,$81,$BF,$80,$C0,SRAM_LENGTH_LO_MASK,SRAM_LENGTH_HI_MASK
MANAGER_ERROR DB "SRAM loader unavailable",13,10,0
AUTO_WORD DB "AUTO "
AUTO_TEXT DB "SAVE B",0
LEFT_SIZE DS 2
WANTED DS 2
RUN_SIZE DS 2
RUN_FIRST DS 2
AUTO_POS DB 0
RAM_FIRST DS 2
