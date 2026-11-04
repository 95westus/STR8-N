; Pre-WB large flash Store and load-only Restore. All code runs above owner RAM.
; SR01 format retained; no erase, SPI, RTC, boot setting or journal writes.
; Explicit targets are deliberate; AUTO admits the saved structural AREA.
        MODULE FLASH_RECORD
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "worker-public-symbols.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "batch-interface.inc"
        CODE
FR_BEGIN:
        DB "FR",1,9,"PR05"
        JMP FR_COMMAND
FR_LINE EQU $7C00
FR_HEADER EQU $6900
FR_BANK EQU $6920
FR_TARGET EQU $6921
FR_SOURCE EQU $6923
FR_LENGTH EQU $6925
FR_END EQU $6927
FR_NEXT EQU $6929
FR_RECORD_END EQU $692B
FR_LEFT EQU $692D
FR_VALUE EQU V2_VALUE
FR_DIGITS EQU $6931
FR_AUTO EQU $6932
FR_ONLY EQU $6933
FR_FOUND EQU $6934
FR_MATCHED EQU $6935
FR_NAME EQU $6940
FR_TEMP_HEADER EQU $6960
FR_RESULT EQU $6978
FR_OLD_HOLD EQU $6979
FR_PTR EQU $E0
FR_SRC EQU $E2
; E4 is the frozen worker's flash pointer.
FR_COMMAND:
        SEI
        CLD
        LDA V2_NMI_HOLD
        STA FR_OLD_HOLD
        STX FR_PTR
        STY FR_PTR+1
        LDY #0
FR_LINE_COPY:
        LDA (FR_PTR),Y
        STA FR_LINE,Y
        BEQ FR_PARSE
        INY
        CPY #41
        BCC FR_LINE_COPY
        JMP FR_BAD
FR_PARSE:
        STZ FR_RUN
        STZ FR_ONLY
        STZ FR_AUTO
        STZ FR_FOUND
        STZ FR_RESULT
        LDA V2_NMI_HOLD
        STA FR_OLD_HOLD
        LDX #0
        JSR FR_SKIP
        CMP #'S'
        BEQ FR_STORE_VERB
        CMP #'R'
        BNE FR_BAD
        INC FR_ONLY
        LDA #<FR_RESTORE_WORD
        LDY #>FR_RESTORE_WORD
        BRA FR_VERB
FR_STORE_VERB:
        LDA #<FR_STORE_WORD
        LDY #>FR_STORE_WORD
FR_VERB:
        STA FR_PTR
        STY FR_PTR+1
        LDY #0
        LDA FR_LINE+1,X
        CMP #' '
        BNE FR_VERB_BYTE
        INX
        BRA FR_VERB_END
FR_VERB_BYTE:
        LDA (FR_PTR),Y
        BEQ FR_VERB_END
        CMP FR_LINE,X
        BNE FR_BAD
        INX
        INY
        BRA FR_VERB_BYTE
FR_VERB_END:
        LDA FR_LINE,X
        CMP #' '
        BNE FR_BAD
        JSR FR_SKIP
        SEC
        SBC #'0'
        CMP #2
        BCS FR_BAD
        STA FR_BANK
        INX
        LDA FR_LINE,X
        CMP #' '
        BNE FR_BAD
        LDA FR_ONLY
        BNE FR_RESTORE_PARSE
        JSR FR_SKIP
        CMP #'A'
        BNE FR_EXPLICIT
        LDY #0
FR_AUTO_TOKEN:
        LDA FR_LINE,X
        CMP FR_AUTO_WORD,Y
        BNE FR_BAD
        INX
        INY
        CPY #4
        BCC FR_AUTO_TOKEN
        LDA FR_LINE,X
        CMP #' '
        BNE FR_BAD
        INC FR_AUTO
        BRA FR_START
FR_EXPLICIT:
        JSR FR_WORD
        BCC FR_BAD
        LDA FR_VALUE
        STA FR_TARGET
        LDA FR_VALUE+1
        STA FR_TARGET+1
        CMP #$80
        BCC FR_BAD
        CMP #$E0
        BCS FR_BAD
FR_START:
        STX FR_PARSE_INDEX
        LDX #23
FR_CLEAR:
        STZ FR_HEADER,X
        DEX
        BPL FR_CLEAR
        ; Recover the parse position saved by FR_WORD/FR_SKIP callers.
        LDX FR_PARSE_INDEX
        JSR FR_WORD
        BCC FR_BAD
        LDA FR_VALUE
        STA FR_SOURCE
        STA FR_HEADER+4
        LDA FR_VALUE+1
        STA FR_SOURCE+1
        STA FR_HEADER+5
        CMP #2
        BCC FR_BAD
        JSR FR_WORD
        BCC FR_BAD
        LDA FR_VALUE+1
        CMP #$67
        BCS FR_BAD
        SEC
        LDA FR_VALUE
        SBC FR_SOURCE
        STA FR_LENGTH
        LDA FR_VALUE+1
        SBC FR_SOURCE+1
        BCC FR_BAD
        STA FR_LENGTH+1
        INC FR_LENGTH
        BNE FR_STORE_NAME
        INC FR_LENGTH+1
FR_STORE_NAME:
        JSR FR_PARSE_NAME
        BCC FR_BAD
        JSR FR_SKIP
        BNE FR_BAD
        LDA FR_LENGTH
        STA FR_HEADER+6
        LDA FR_LENGTH+1
        STA FR_HEADER+7
        LDA #'S'
        STA FR_HEADER
        LDA #'R'
        STA FR_HEADER+1
        LDA #1
        STA FR_HEADER+2
        LDA #$FF
        STA FR_HEADER+3
        LDX #15
FR_NAME_COPY:
        LDA FR_NAME,X
        STA FR_HEADER+8,X
        DEX
        BPL FR_NAME_COPY
        JSR FR_SCAN
        BCC FR_REFUSED
        JSR FR_TARGET_END
        BCC FR_REFUSED
        LDA FR_TARGET
        STA V2_FLASH_PTR
        LDA FR_TARGET+1
        STA V2_FLASH_PTR+1
        LDA FR_BANK
        JSR V2W_SELECT
FR_BLANK:
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS FR_CANCEL_BANK
        LDA (V2_FLASH_PTR)
        CMP #$FF
        BNE FR_REFUSED_BANK
        JSR FR_ADVANCE
        LDA V2_FLASH_PTR
        CMP FR_END
        BNE FR_BLANK
        LDA V2_FLASH_PTR+1
        CMP FR_END+1
        BNE FR_BLANK
        LDA #3
        JSR V2W_SELECT
        LDX #<FR_CONFIRM_TEXT
        LDY #>FR_CONFIRM_TEXT
        JSR FR_PRINT
        JSR BOOT_READ_LINE
        BCC FR_CANCEL
        LDA V2_LINE
        CMP #'Y'
        BNE FR_CANCEL
        LDA V2_LINE+1
        CMP #'E'
        BNE FR_CANCEL
        LDA V2_LINE+2
        CMP #'S'
        BNE FR_CANCEL
        LDA V2_LINE+3
        BNE FR_CANCEL
        JSR FR_DRAIN
        LDA FR_TARGET
        STA V2_FLASH_PTR
        LDA FR_TARGET+1
        STA V2_FLASH_PTR+1
        LDA #1
        STA V2_NMI_HOLD
        LDA FR_BANK
        JSR V2W_SELECT
        LDY #0
FR_WRITE_HEADER:
        LDA FR_HEADER,Y
        PHY
        JSR FR_BYTE
        PLY
        JSR FR_ADVANCE
        INY
        CPY #24
        BCC FR_WRITE_HEADER
        LDA FR_SOURCE
        STA FR_SRC
        LDA FR_SOURCE+1
        STA FR_SRC+1
        LDA FR_LENGTH
        STA FR_LEFT
        LDA FR_LENGTH+1
        STA FR_LEFT+1
FR_WRITE_DATA:
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS FR_PARTIAL_BANK
        LDA (FR_SRC)
        JSR FR_BYTE
        JSR FR_ADVANCE
        INC FR_SRC
        BNE FR_WRITE_LEFT
        INC FR_SRC+1
FR_WRITE_LEFT:
        JSR FR_DEC_LEFT
        BNE FR_WRITE_DATA
        CLC
        LDA FR_TARGET
        ADC #3
        STA V2_FLASH_PTR
        LDA FR_TARGET+1
        ADC #0
        STA V2_FLASH_PTR+1
        ; Every programmed byte was read back; commit is the final write.
        LDA #$3F
        JSR FR_BYTE
        JMP FR_OK_BANK
FR_PARSE_INDEX EQU $697A
FR_RUN EQU $697B
FR_RESTORE_PARSE:
        JSR FR_PARSE_NAME
        BCC FR_BAD
        JSR FR_SKIP
        BEQ FR_RUN_REQUEST
        CMP #'L'
        BNE FR_BAD
        INX
        JSR FR_SKIP
        BNE FR_BAD
        BRA FR_LOOKUP
FR_RUN_REQUEST:
        INC FR_RUN
FR_LOOKUP:
        ; Named lookup skips complete/pending payloads and rejects duplicates.
        JSR FR_SCAN
        BCC FR_REFUSED
        LDA FR_FOUND
        CMP #1
        BNE FR_REFUSED
        CLC
        LDA FR_TARGET
        ADC #24
        STA V2_FLASH_PTR
        LDA FR_TARGET+1
        ADC #0
        STA V2_FLASH_PTR+1
        LDA FR_HEADER+4
        STA FR_SRC
        LDA FR_HEADER+5
        STA FR_SRC+1
        LDA FR_HEADER+6
        STA FR_LEFT
        LDA FR_HEADER+7
        STA FR_LEFT+1
        LDA FR_BANK
        JSR V2W_SELECT
FR_LOAD:
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS FR_PARTIAL_BANK
        LDA (V2_FLASH_PTR)
        STA (FR_SRC)
        CMP (FR_SRC)
        BNE FR_PARTIAL_BANK
        JSR FR_ADVANCE
        INC FR_SRC
        BNE FR_LOAD_LEFT
        INC FR_SRC+1
FR_LOAD_LEFT:
        JSR FR_DEC_LEFT
        BNE FR_LOAD
        JMP FR_OK_BANK
FR_SCAN:
        ; Preserve the new Store header while inspecting existing records.
        LDX #23
FR_SAVE_HEADER:
        LDA FR_HEADER,X
        STA FR_TEMP_HEADER,X
        DEX
        BPL FR_SAVE_HEADER
        JSR FA_SETUP
        BCC FR_SCAN_BAD
        STZ V2_FLASH_PTR
        LDA #$80
        STA V2_FLASH_PTR+1
        LDA FR_BANK
        JSR V2W_SELECT
FR_SCAN_BYTE:
        LDA V2_FLASH_PTR+1
        CMP #$E0
        BCS FR_SCAN_DONE
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS FR_SCAN_BAD
        LDA (V2_FLASH_PTR)
        CMP #$FF
        BEQ FR_SCAN_ADVANCE
        CMP #'S'
        BNE FR_SCAN_UNKNOWN
        JSR FR_CHECK_RECORD
        BCC FR_SCAN_UNKNOWN
        LDA FR_ONLY
        BNE FR_SCAN_RESTORE
        LDA FR_AUTO
        BEQ FR_SCAN_OVERLAP
        JSR FA_RECORD
        BCC FR_SCAN_BAD
        BRA FR_SCAN_SKIP
FR_SCAN_OVERLAP:
        JSR FR_TARGET_END
        BCC FR_SCAN_BAD
        ; [record,recordEnd) intersects [target,targetEnd)?
        LDA V2_FLASH_PTR
        CMP FR_END
        LDA V2_FLASH_PTR+1
        SBC FR_END+1
        BCS FR_SCAN_SKIP
        LDA FR_TARGET
        CMP FR_RECORD_END
        LDA FR_TARGET+1
        SBC FR_RECORD_END+1
        BCC FR_SCAN_BAD
        BRA FR_SCAN_SKIP
FR_SCAN_RESTORE:
        LDA FR_HEADER+3
        CMP #$3F
        BNE FR_SCAN_SKIP
        LDY #15
FR_NAME_MATCH:
        LDA FR_HEADER+8,Y
        CMP FR_NAME,Y
        BNE FR_SCAN_SKIP
        DEY
        BPL FR_NAME_MATCH
        INC FR_FOUND
        LDA FR_FOUND
        CMP #2
        BCS FR_SCAN_BAD
        LDA V2_FLASH_PTR
        STA FR_TARGET
        LDA V2_FLASH_PTR+1
        STA FR_TARGET+1
        LDX #23
FR_MATCH_SAVE:
        LDA FR_HEADER,X
        STA FR_TEMP_HEADER,X
        DEX
        BPL FR_MATCH_SAVE
FR_SCAN_SKIP:
        LDA FR_RECORD_END
        STA V2_FLASH_PTR
        LDA FR_RECORD_END+1
        STA V2_FLASH_PTR+1
        BRA FR_SCAN_BYTE
FR_SCAN_UNKNOWN:
        LDA FR_AUTO
        BEQ FR_SCAN_ADVANCE
        JSR FA_IN_AREA
        BCS FR_SCAN_BAD
FR_SCAN_ADVANCE:
        JSR FR_ADVANCE
        BRA FR_SCAN_BYTE
FR_SCAN_DONE:
        LDA FR_AUTO
        BEQ FR_SCAN_RETURN
        LDA FR_NEXT
        STA FR_TARGET
        LDA FR_NEXT+1
        STA FR_TARGET+1
FR_SCAN_RETURN:
        LDX #23
FR_HEADER_RESTORE:
        LDA FR_TEMP_HEADER,X
        STA FR_HEADER,X
        DEX
        BPL FR_HEADER_RESTORE
        LDA #3
        JSR V2W_SELECT
        SEC
        RTS
FR_SCAN_BAD:
        LDA #3
        JSR V2W_SELECT
        CLC
        RTS
FR_CHECK_RECORD:
        ; A full24-byte header must fit before E000, then validate all bounds.
        CLC
        LDA V2_FLASH_PTR
        ADC #24
        STA FR_RECORD_END
        LDA V2_FLASH_PTR+1
        ADC #0
        STA FR_RECORD_END+1
        CMP #$E0
        BCS FR_CHECK_BAD
        LDY #23
FR_READ_HEADER:
        LDA (V2_FLASH_PTR),Y
        STA FR_HEADER,Y
        DEY
        BPL FR_READ_HEADER
        LDA FR_HEADER+1
        CMP #'R'
        BNE FR_CHECK_BAD
        LDA FR_HEADER+2
        CMP #1
        BNE FR_CHECK_BAD
        LDA FR_HEADER+3
        CMP #$FF
        BEQ FR_HEADER_STATE
        CMP #$3F
        BNE FR_CHECK_BAD
FR_HEADER_STATE:
        LDA FR_HEADER+5
        CMP #2
        BCC FR_CHECK_BAD
        LDA FR_HEADER+6
        ORA FR_HEADER+7
        BEQ FR_CHECK_BAD
        CLC
        LDA FR_HEADER+4
        ADC FR_HEADER+6
        LDA FR_HEADER+5
        ADC FR_HEADER+7
        BCS FR_CHECK_BAD
        CMP #$67
        BCC FR_HEADER_LENGTH
        BNE FR_CHECK_BAD
        CLC
        LDA FR_HEADER+4
        ADC FR_HEADER+6
        BNE FR_CHECK_BAD
FR_HEADER_LENGTH:
        CLC
        LDA FR_RECORD_END
        ADC FR_HEADER+6
        STA FR_RECORD_END
        LDA FR_RECORD_END+1
        ADC FR_HEADER+7
        BCS FR_CHECK_BAD
        STA FR_RECORD_END+1
        CMP #$E0
        BCC FR_HEADER_NAME_CHECK
        BNE FR_CHECK_BAD
        LDA FR_RECORD_END
        BNE FR_CHECK_BAD
FR_HEADER_NAME_CHECK:
        LDY #0
        STZ FR_MATCHED
FR_HEADER_NAME_BYTE:
        LDA FR_HEADER+8,Y
        BEQ FR_HEADER_NAME_ZERO
        LDX FR_MATCHED
        BNE FR_CHECK_BAD
        CMP #$21
        BCC FR_CHECK_BAD
        CMP #$7F
        BCS FR_CHECK_BAD
        BRA FR_HEADER_NAME_NEXT
FR_HEADER_NAME_ZERO:
        INC FR_MATCHED
FR_HEADER_NAME_NEXT:
        INY
        CPY #16
        BCC FR_HEADER_NAME_BYTE
        SEC
        RTS
FR_CHECK_BAD:
        CLC
        RTS
FR_TARGET_END:
        CLC
        LDA FR_TARGET
        ADC #24
        STA FR_END
        LDA FR_TARGET+1
        ADC #0
        STA FR_END+1
        CLC
        LDA FR_END
        ADC FR_LENGTH
        STA FR_END
        LDA FR_END+1
        ADC FR_LENGTH+1
        BCS FR_CHECK_BAD
        STA FR_END+1
        CMP #$E0
        BCC FR_TARGET_GOOD
        BNE FR_CHECK_BAD
        LDA FR_END
        BNE FR_CHECK_BAD
FR_TARGET_GOOD:
        LDA FR_AUTO
        BEQ FR_TARGET_PLAIN
        JMP FA_FITS
FR_TARGET_PLAIN:
        SEC
        RTS
FR_BYTE:
        STA V2_FLASH_DATA
        CMP #$FF
        BEQ FR_BYTE_DONE
        JSR V2W_BYTE+2
        BCC FR_FATAL
        LDA (V2_FLASH_PTR)
        CMP V2_FLASH_DATA
        BNE FR_FATAL
FR_BYTE_DONE:
        RTS
FR_FATAL:
        ; Chip state is uncertain: remain in RAM, never execute flash ROM.
        LDA #1
        STA V2_LED
        LDA #'!'
        JSR STR8V2_RAM_PUTC
FR_HALT:
        BRA FR_HALT
FR_ADVANCE:
        INC V2_FLASH_PTR
        BNE FR_ADVANCE_DONE
        INC V2_FLASH_PTR+1
FR_ADVANCE_DONE:
        RTS
FR_DEC_LEFT:
        LDA FR_LEFT
        BNE FR_DEC_LOW
        DEC FR_LEFT+1
FR_DEC_LOW:
        DEC FR_LEFT
        LDA FR_LEFT
        ORA FR_LEFT+1
        RTS
FR_PARSE_NAME:
        JSR FR_SKIP
        LDY #0
        LDA #0
FR_NAME_CLEAR:
        STA FR_NAME,Y
        INY
        CPY #16
        BCC FR_NAME_CLEAR
        LDY #0
FR_NAME_READ:
        LDA FR_LINE,X
        BEQ FR_NAME_END
        CMP #' '
        BEQ FR_NAME_END
        CPY #16
        BCS FR_NAME_BAD
        CMP #$21
        BCC FR_NAME_BAD
        CMP #$7F
        BCS FR_NAME_BAD
        STA FR_NAME,Y
        INY
        INX
        BRA FR_NAME_READ
FR_NAME_END:
        CPY #0
        BEQ FR_NAME_BAD
        SEC
        RTS
FR_NAME_BAD:
        CLC
        RTS
FR_SKIP:
        LDA FR_LINE,X
        CMP #' '
        BNE FR_SKIP_END
        INX
        BRA FR_SKIP
FR_SKIP_END:
        STX FR_PARSE_INDEX
        CMP #0
        RTS
        INCLUDE "flash-record-number.inc"
FR_PRINT:
        STX FR_PTR
        STY FR_PTR+1
        LDY #0
FR_PRINT_BYTE:
        LDA (FR_PTR),Y
        BEQ FR_PRINT_END
        JSR STR8V2_RAM_PUTC
        INY
        BRA FR_PRINT_BYTE
FR_PRINT_END:
        RTS
FR_CANCEL_BANK:
        LDA #3
        JSR V2W_SELECT
FR_CANCEL:
        LDX #<FR_CANCEL_TEXT
        LDY #>FR_CANCEL_TEXT
        BRA FR_MESSAGE
FR_PARTIAL_BANK:
        LDA #3
        JSR V2W_SELECT
        LDX #<FR_PARTIAL_TEXT
        LDY #>FR_PARTIAL_TEXT
        BRA FR_MESSAGE
FR_REFUSED_BANK:
        LDA #3
        JSR V2W_SELECT
FR_REFUSED:
        LDX #<FR_REFUSED_TEXT
        LDY #>FR_REFUSED_TEXT
        BRA FR_MESSAGE
FR_BAD:
        LDX #<FR_BAD_TEXT
        LDY #>FR_BAD_TEXT
        BRA FR_MESSAGE
FR_OK_BANK:
        LDA #3
        JSR V2W_SELECT
        LDX #<FR_OK_TEXT
        LDY #>FR_OK_TEXT
        LDA FR_RUN
        BEQ FR_MESSAGE
        JSR FR_PRINT
        JSR FR_DRAIN
        LDA FR_OLD_HOLD
        STA V2_NMI_HOLD
        LDA FR_HEADER+4
        STA V2_VECTOR
        LDA FR_HEADER+5
        STA V2_VECTOR+1
        LDA FR_BANK
        STA V2_SELECTED
        JMP V2W_EXECUTE
FR_MESSAGE:
        LDA FR_OLD_HOLD
        STA V2_NMI_HOLD
        LDA #1
        STA V2_LED
        JSR FR_PRINT
        JSR FR_DRAIN
        RTS
FR_DRAIN:
        JSR STR8V2_RAM_RX_RESET
FR_DRAIN_RESTART:
        LDX #0
        LDY #$20
FR_DRAIN_POLL:
        JSR STR8V2_RAM_RAW_POLL
        BCS FR_DRAIN_RESTART
        DEX
        BNE FR_DRAIN_POLL
        DEY
        BNE FR_DRAIN_POLL
        JMP STR8V2_RAM_RX_RESET
FR_STORE_WORD: DB "STORE",0
FR_RESTORE_WORD: DB "RESTORE",0
FR_AUTO_WORD: DB "AUTO"
FR_CONFIRM_TEXT: DB "Flash STORE; no erase; type YES: ",0
FR_CANCEL_TEXT: DB "Canceled; flash unchanged.",13,10,0
FR_PARTIAL_TEXT: DB "Partial; Store not committed.",13,10,0
FR_REFUSED_TEXT: DB "REFUSED: AREA/bounds/occupied/records/name",13,10,0
FR_BAD_TEXT: DB "Use STORE bank AUTO|addr start end name; RESTORE bank name L",13,10,0
FR_OK_TEXT: DB "Flash record OK (SR01; no payload CRC).",13,10,0
        INCLUDE "flash-auto.inc"
FR_END_CODE:
        ENDMOD
        END
