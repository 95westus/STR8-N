; First b15 MAINT stage: no flash/config writer or arbitrary execution entry.
; Matching b15 private bank/line/read bindings; all banked work executes in RAM.
        MODULE RAM_MAINT_RO_B15
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "worker-public-symbols.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "maint-ro-params.inc"
MA_PTR EQU $E0
MA_BP EQU $E2
MA_BUF EQU $5000
        CODE
MA_START:
        SEI
        CLD
        STZ MA_HAVE
        STZ MA_ERROR
        ; No F/private call until exact immutable image, F and RAM guards pass.
        LDA $7E60
        CMP #'R'
        BNE MA_GUARD_BAD
        LDA $7E61
        CMP #'A'
        BNE MA_GUARD_BAD
        LDA $7E62
        CMP #1
        BNE MA_GUARD_BAD
        LDA $7E63
        CMP #$0D
        BNE MA_GUARD_BAD
        LDA #<MA_START
        STA MA_SRC
        LDA #>MA_START
        STA MA_SRC+1
        LDA #<(MA_IMM_END-MA_START)
        STA MA_COUNT
        LDA #>(MA_IMM_END-MA_START)
        STA MA_COUNT+1
        JSR MA_RAW_CRC
        LDA MA_CRC
        ORA MA_CRC+1
        BNE MA_GUARD_BAD
        LDA #$F0
        STA MA_SRC+1
        STZ MA_SRC
        LDA #$10
        STA MA_COUNT+1
        STZ MA_COUNT
        JSR MA_RAW_CRC
        LDA MA_CRC
        CMP #MA_F_CRC_LO
        BNE MA_GUARD_BAD
        LDA MA_CRC+1
        CMP #MA_F_CRC_HI
        BNE MA_GUARD_BAD
        LDX #0
MA_RAM_GUARD:
        LDA MA_GUARD_TABLE,X
        STA MA_SRC
        LDA MA_GUARD_TABLE+1,X
        STA MA_SRC+1
        LDA MA_GUARD_TABLE+2,X
        STA MA_COUNT
        LDA MA_GUARD_TABLE+3,X
        STA MA_COUNT+1
        STX MA_TABLE_INDEX
        JSR MA_RAW_CRC
        LDX MA_TABLE_INDEX
        LDA MA_CRC
        CMP MA_GUARD_TABLE+4,X
        BNE MA_GUARD_BAD
        LDA MA_CRC+1
        CMP MA_GUARD_TABLE+5,X
        BNE MA_GUARD_BAD
        TXA
        CLC
        ADC #6
        TAX
        CPX #12
        BNE MA_RAM_GUARD
        LDX #<MA_TITLE
        LDY #>MA_TITLE
        JSR MA_PRINT
MA_MENU:
        LDX #<MA_PROMPT
        LDY #>MA_PROMPT
        JSR MA_PRINT
        JSR BOOT_API_LINE
        BCC MA_BAD
        LDA #1
        STA MA_POS
        LDA STR8V2_LINE
        CMP #'M'
        BEQ MA_MAP
        CMP #'R'
        BEQ MA_READ
        CMP #'D'
        BEQ MA_DUMP
        CMP #'V'
        BEQ MA_COMPARE
        CMP #'K'
        BEQ MA_CHECKSUM
        JSR MA_ENDLINE
        BCC MA_BAD
        LDA STR8V2_LINE
        CMP #'?'
        BEQ MA_HELP
        CMP #'Q'
        BNE MA_BAD
        JMP STR8V2_RAM_RESET
MA_HELP:
        LDX #<MA_HELP_TEXT
        LDY #>MA_HELP_TEXT
        BRA MA_MESSAGE
MA_BAD:
        LDX #<MA_BAD_TEXT
        LDY #>MA_BAD_TEXT
MA_MESSAGE:
        JSR MA_PRINT
        JMP MA_MENU
MA_GUARD_BAD:
        LDA #1
        STA MA_ERROR
MA_HALT:
        JMP MA_HALT

; Tokens: exactly one bank character or four hex digits, space separated.
MA_NEED_SPACE:
        LDX MA_POS
        LDA STR8V2_LINE,X
        CMP #' '
        BNE MA_PARSE_BAD
MA_SKIP_SPACE:
        INX
        LDA STR8V2_LINE,X
        CMP #' '
        BEQ MA_SKIP_SPACE
        STX MA_POS
        CMP #0
        BEQ MA_PARSE_BAD
        SEC
        RTS
MA_ENDLINE:
        LDX MA_POS
MA_END_SKIP:
        LDA STR8V2_LINE,X
        BEQ MA_PARSE_OK
        CMP #' '
        BNE MA_PARSE_BAD
        INX
        BRA MA_END_SKIP
MA_BANK_TOKEN:
        JSR MA_NEED_SPACE
        BCC MA_PARSE_BAD
        LDA STR8V2_LINE,X
        CMP #'R'
        BNE MA_BANK_DIGIT
        LDA #4
        BRA MA_BANK_SAVE
MA_BANK_DIGIT:
        CMP #'0'
        BCC MA_PARSE_BAD
        CMP #'4'
        BCS MA_PARSE_BAD
        SEC
        SBC #'0'
MA_BANK_SAVE:
        PHA
        INX
        STX MA_POS
        LDA STR8V2_LINE,X
        BEQ MA_BANK_OK
        CMP #' '
        BNE MA_BANK_ERROR
MA_BANK_OK:
        PLA
        SEC
        RTS
MA_BANK_ERROR:
        PLA
MA_PARSE_BAD:
        CLC
        RTS
MA_PARSE_OK:
        SEC
        RTS
MA_WORD_TOKEN:
        JSR MA_NEED_SPACE
        BCC MA_PARSE_BAD
        STZ MA_VALUE
        STZ MA_VALUE+1
        LDA #4
        STA MA_DIGITS
MA_WORD_DIGIT:
        LDA STR8V2_LINE,X
        CMP #'0'
        BCC MA_PARSE_BAD
        CMP #'9'+1
        BCC MA_WORD_NUMBER
        CMP #'A'
        BCC MA_PARSE_BAD
        CMP #'F'+1
        BCS MA_PARSE_BAD
        SEC
        SBC #'A'-10
        BRA MA_WORD_NIBBLE
MA_WORD_NUMBER:
        SEC
        SBC #'0'
MA_WORD_NIBBLE:
        PHA
        ASL MA_VALUE
        ROL MA_VALUE+1
        ASL MA_VALUE
        ROL MA_VALUE+1
        ASL MA_VALUE
        ROL MA_VALUE+1
        ASL MA_VALUE
        ROL MA_VALUE+1
        PLA
        ORA MA_VALUE
        STA MA_VALUE
        INX
        DEC MA_DIGITS
        BNE MA_WORD_DIGIT
        STX MA_POS
        LDA STR8V2_LINE,X
        BEQ MA_PARSE_OK
        CMP #' '
        BEQ MA_PARSE_OK
        CLC
        RTS
MA_PARSE_RANGE:
        JSR MA_BANK_TOKEN
        BCC MA_PARSE_BAD
        STA MA_SB
        JSR MA_WORD_TOKEN
        BCC MA_PARSE_BAD
        LDA MA_VALUE
        STA MA_SRC
        LDA MA_VALUE+1
        STA MA_SRC+1
        JSR MA_WORD_TOKEN
        BCC MA_PARSE_BAD
        LDA MA_VALUE
        STA MA_LAST
        LDA MA_VALUE+1
        STA MA_LAST+1
        JSR MA_RANGE
        BCC MA_PARSE_BAD
        SEC
        LDA MA_LAST
        SBC MA_SRC
        STA MA_COUNT
        LDA MA_LAST+1
        SBC MA_SRC+1
        STA MA_COUNT+1
        INC MA_COUNT
        BNE MA_PARSE_OK
        INC MA_COUNT+1
        SEC
        RTS
MA_RANGE:
        LDA MA_LAST
        CMP MA_SRC
        LDA MA_LAST+1
        SBC MA_SRC+1
        BCC MA_PARSE_BAD
        LDA MA_SB
        CMP #4
        BEQ MA_RANGE_RAM
        LDA MA_SRC+1
        CMP #$80
        BCC MA_PARSE_BAD
        SEC
        RTS
MA_RANGE_RAM:
        LDA MA_SRC+1
        CMP #$20
        BCC MA_PARSE_BAD
        LDA MA_LAST+1
        CMP #$65
        BCS MA_PARSE_BAD
        SEC
        RTS

; Read-only bank selection: source reads happen in RAM; ROM calls see B3.
MA_SELECT_SOURCE:
        LDA MA_SB
        CMP #4
        BEQ MA_SELECTED
        JSR V2W_SELECT
MA_SELECTED:
        LDA MA_SRC
        STA MA_PTR
        LDA MA_SRC+1
        STA MA_PTR+1
        RTS
MA_HOME:
        LDA #3
        JMP V2W_SELECT
MA_NEXT_PTR:
        INC MA_PTR
        BNE MA_NEXT_DONE
        INC MA_PTR+1
MA_NEXT_DONE:
        RTS
MA_DEC_COUNT:
        LDA MA_COUNT
        BNE MA_DEC_LOW
        DEC MA_COUNT+1
MA_DEC_LOW:
        DEC MA_COUNT
        LDA MA_COUNT
        ORA MA_COUNT+1
        RTS

MA_READ:
        JSR MA_PARSE_RANGE
        BCC MA_BAD
        JSR MA_ENDLINE
        BCC MA_BAD
        LDA MA_COUNT+1
        CMP #$10
        BCC MA_READ_LENGTH_OK
        BNE MA_BAD
        LDA MA_COUNT
        BNE MA_BAD
MA_READ_LENGTH_OK:
        ; A read-to-buffer must not overlap and overwrite its own RAM source.
        LDA MA_SB
        CMP #4
        BNE MA_READ_READY
        LDA MA_SRC+1
        CMP #$60
        BCS MA_READ_READY
        LDA MA_LAST+1
        CMP #$50
        BCS MA_BAD
MA_READ_READY:
        LDA MA_COUNT
        STA MA_LENGTH
        LDA MA_COUNT+1
        STA MA_LENGTH+1
        STZ MA_BP
        LDA #$50
        STA MA_BP+1
        JSR MA_SELECT_SOURCE
MA_READ_BYTE:
        LDA (MA_PTR)
        STA (MA_BP)
        INC MA_BP
        BNE MA_READ_ADVANCE
        INC MA_BP+1
MA_READ_ADVANCE:
        JSR MA_NEXT_PTR
        JSR MA_DEC_COUNT
        BNE MA_READ_BYTE
        JSR MA_HOME
        LDA #1
        STA MA_HAVE
        LDX #<MA_BUFFER_TEXT
        LDY #>MA_BUFFER_TEXT
        JMP MA_MESSAGE

MA_DUMP:
        LDA MA_HAVE
        BEQ MA_BAD
        JSR MA_ENDLINE
        BCC MA_DUMP_ARGUMENTS
        STZ MA_OFFSET
        STZ MA_OFFSET+1
        LDA #15
        STA MA_LAST
        STZ MA_LAST+1
        LDA MA_LENGTH+1
        BNE MA_DUMP_GO
        LDA MA_LENGTH
        CMP #16
        BCS MA_DUMP_GO
        DEC A
        STA MA_LAST
        BRA MA_DUMP_GO
MA_DUMP_ARGUMENTS:
        JSR MA_WORD_TOKEN
        BCC MA_BAD
        LDA MA_VALUE
        STA MA_OFFSET
        LDA MA_VALUE+1
        STA MA_OFFSET+1
        JSR MA_ENDLINE
        BCC MA_DUMP_END
        LDA MA_OFFSET
        STA MA_LAST
        LDA MA_OFFSET+1
        STA MA_LAST+1
        BRA MA_DUMP_VALIDATE
MA_DUMP_END:
        JSR MA_WORD_TOKEN
        BCC MA_BAD
        LDA MA_VALUE
        STA MA_LAST
        LDA MA_VALUE+1
        STA MA_LAST+1
        JSR MA_ENDLINE
        BCC MA_BAD
MA_DUMP_VALIDATE:
        LDA MA_LAST
        CMP MA_OFFSET
        LDA MA_LAST+1
        SBC MA_OFFSET+1
        BCC MA_BAD
        LDA MA_LAST
        CMP MA_LENGTH
        LDA MA_LAST+1
        SBC MA_LENGTH+1
        BCS MA_BAD
MA_DUMP_GO:
        STZ MA_COLUMN
MA_DUMP_BYTE:
        LDA MA_COLUMN
        BNE MA_DUMP_VALUE
        LDA MA_OFFSET+1
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_OFFSET
        JSR STR8V2_RAM_HEX_OUT
        LDA #':'
        JSR STR8V2_RAM_PUTC
MA_DUMP_VALUE:
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA MA_OFFSET
        STA MA_PTR
        LDA MA_OFFSET+1
        CLC
        ADC #$50
        STA MA_PTR+1
        LDA (MA_PTR)
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_OFFSET
        CMP MA_LAST
        BNE MA_DUMP_MORE
        LDA MA_OFFSET+1
        CMP MA_LAST+1
        BEQ MA_DUMP_DONE
MA_DUMP_MORE:
        INC MA_OFFSET
        BNE MA_DUMP_COL
        INC MA_OFFSET+1
MA_DUMP_COL:
        INC MA_COLUMN
        LDA MA_COLUMN
        AND #15
        STA MA_COLUMN
        BNE MA_DUMP_BYTE
        JSR STR8V2_RAM_NEWLINE
        BRA MA_DUMP_BYTE
MA_DUMP_DONE:
        JSR STR8V2_RAM_NEWLINE
        JMP MA_MENU

MA_CHECKSUM:
        JSR MA_ENDLINE
        BCC MA_CHECKSUM_RANGE
        LDA MA_HAVE
        BEQ MA_BAD
        LDA #4
        STA MA_SB
        STZ MA_SRC
        LDA #$50
        STA MA_SRC+1
        LDA MA_LENGTH
        STA MA_COUNT
        LDA MA_LENGTH+1
        STA MA_COUNT+1
        BRA MA_CHECKSUM_GO
MA_CHECKSUM_RANGE:
        JSR MA_PARSE_RANGE
        BCC MA_BAD
        JSR MA_ENDLINE
        BCC MA_BAD
MA_CHECKSUM_GO:
        JSR MA_SELECT_SOURCE
        JSR MA_CRC_AT_PTR
        JSR MA_HOME
        LDX #<MA_CRC_TEXT
        LDY #>MA_CRC_TEXT
        JSR MA_PRINT
        LDA MA_CRC+1
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_CRC
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        JMP MA_MENU

MA_COMPARE:
        JSR MA_PARSE_RANGE
        BCC MA_BAD
        JSR MA_BANK_TOKEN
        BCC MA_BAD
        STA MA_DB
        JSR MA_WORD_TOKEN
        BCC MA_BAD
        LDA MA_VALUE
        STA MA_DST
        LDA MA_VALUE+1
        STA MA_DST+1
        JSR MA_ENDLINE
        BCC MA_BAD
        ; Check the complete destination span before performing any read.
        SEC
        LDA MA_COUNT
        SBC #1
        STA MA_VALUE
        LDA MA_COUNT+1
        SBC #0
        STA MA_VALUE+1
        CLC
        LDA MA_DST
        ADC MA_VALUE
        STA MA_VALUE
        LDA MA_DST+1
        ADC MA_VALUE+1
        BCS MA_BAD
        STA MA_VALUE+1
        LDA MA_DB
        CMP #4
        BEQ MA_COMPARE_RAM
        LDA MA_DST+1
        CMP #$80
        BCC MA_BAD
        BRA MA_COMPARE_LOOP
MA_COMPARE_RAM:
        LDA MA_DST+1
        CMP #$20
        BCC MA_BAD
        LDA MA_VALUE+1
        CMP #$65
        BCS MA_BAD
MA_COMPARE_LOOP:
        JSR MA_SELECT_SOURCE
        LDA (MA_PTR)
        STA MA_BYTE
        JSR MA_HOME
        LDA MA_DB
        CMP #4
        BEQ MA_COMPARE_DST
        JSR V2W_SELECT
MA_COMPARE_DST:
        LDA MA_DST
        STA MA_PTR
        LDA MA_DST+1
        STA MA_PTR+1
        LDA (MA_PTR)
        CMP MA_BYTE
        PHP
        JSR MA_HOME
        PLP
        BNE MA_DIFFERENT
        INC MA_SRC
        BNE MA_COMPARE_SRC_NEXT
        INC MA_SRC+1
MA_COMPARE_SRC_NEXT:
        INC MA_DST
        BNE MA_COMPARE_DST_NEXT
        INC MA_DST+1
MA_COMPARE_DST_NEXT:
        JSR MA_DEC_COUNT
        BNE MA_COMPARE_LOOP
        LDX #<MA_MATCH_TEXT
        LDY #>MA_MATCH_TEXT
        JMP MA_MESSAGE
MA_DIFFERENT:
        LDX #<MA_DIFFERENT_TEXT
        LDY #>MA_DIFFERENT_TEXT
        JSR MA_PRINT
        LDA MA_DB
        JSR MA_SPACE_NAME
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA MA_DST+1
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_DST
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        JMP MA_MENU

; Local CRC16-CCITT-FALSE: seed FFFF, polynomial 1021, no final XOR.
MA_RAW_CRC:
        LDA MA_SRC
        STA MA_PTR
        LDA MA_SRC+1
        STA MA_PTR+1
MA_CRC_AT_PTR:
        LDA #$FF
        STA MA_CRC
        STA MA_CRC+1
MA_CRC_LOOP:
        LDA (MA_PTR)
        JSR MA_CRC_BYTE
        JSR MA_NEXT_PTR
        JSR MA_DEC_COUNT
        BNE MA_CRC_LOOP
        RTS
MA_CRC_BYTE:
        EOR MA_CRC+1
        STA MA_CRC+1
        LDX #8
MA_CRC_BIT:
        ASL MA_CRC
        ROL MA_CRC+1
        BCC MA_CRC_NO_XOR
        LDA MA_CRC
        EOR #$21
        STA MA_CRC
        LDA MA_CRC+1
        EOR #$10
        STA MA_CRC+1
MA_CRC_NO_XOR:
        DEX
        BNE MA_CRC_BIT
        RTS

MA_MAP:
        LDA #2
        STA MA_VIEW
        JSR MA_ENDLINE
        BCS MA_MAP_READY
        JSR MA_NEED_SPACE
        BCC MA_BAD
        LDA STR8V2_LINE,X
        CMP #'1'
        BCC MA_BAD
        CMP #'4'
        BCS MA_BAD
        SEC
        SBC #'0'
        STA MA_VIEW
        INC MA_POS
        JSR MA_ENDLINE
        BCC MA_BAD
MA_MAP_READY:
        JSR MA_READ_JOURNAL
        STZ MA_MAP_INDEX
        STZ MA_MB
        LDA #$80
        STA MA_MS
        LDA MA_VIEW
        CMP #1
        BNE MA_MAP_ROW
        LDX #<MA_GRID_TITLE
        LDY #>MA_GRID_TITLE
        JSR MA_PRINT
MA_MAP_ROW:
        LDA MA_MB
        JSR V2W_SELECT
        STZ MA_PTR
        LDA MA_MS
        STA MA_PTR+1
        STZ MA_COUNT
        LDA #$10
        STA MA_COUNT+1
        LDA #'E'
        STA MA_STATUS
MA_SCAN:
        LDA (MA_PTR)
        CMP #$FF
        BNE MA_USED
        JSR MA_NEXT_PTR
        JSR MA_DEC_COUNT
        BNE MA_SCAN
        BRA MA_SCAN_DONE
MA_USED:
        LDA #'U'
        STA MA_STATUS
MA_SCAN_DONE:
        JSR MA_HOME
        LDA MA_VIEW
        CMP #1
        BNE MA_MAP_DETAIL
        LDA MA_MS
        CMP #$80
        BNE MA_GRID_CELL
        LDA MA_MB
        JSR MA_SPACE_NAME
MA_GRID_CELL:
        JSR MA_SPACE
        LDA MA_STATUS
        JSR STR8V2_RAM_PUTC
        LDA MA_MS
        CMP #$F0
        BNE MA_MAP_NEXT
        JSR STR8V2_RAM_NEWLINE
        BRA MA_MAP_NEXT
MA_MAP_DETAIL:
        LDA MA_MB
        JSR MA_SPACE_NAME
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA MA_MS
        LSR A
        LSR A
        LSR A
        LSR A
        JSR MA_NIBBLE_OUT
        JSR MA_SPACE
        LDA MA_STATUS
        JSR STR8V2_RAM_PUTC
        JSR MA_SPACE
        LDA MA_VIEW
        CMP #3
        BNE MA_MAP_ROLE
        JSR MA_MAP_COUNT
        JSR MA_SPACE
MA_MAP_ROLE:
        JSR MA_ROLE
        JSR MA_PRINT
        JSR STR8V2_RAM_NEWLINE
MA_MAP_NEXT:
        INC MA_MAP_INDEX
        CLC
        LDA MA_MS
        ADC #$10
        STA MA_MS
        BNE MA_MAP_ROW
        LDA #$80
        STA MA_MS
        INC MA_MB
        LDA MA_MB
        CMP #4
        BNE MA_MAP_ROW
        LDX #<MA_MAP_LEGEND
        LDY #>MA_MAP_LEGEND
        JSR MA_PRINT
        LDA MA_JVALID
        BEQ MA_MAP_NO_JOURNAL
        LDX #<MA_SEQUENCE_TEXT
        LDY #>MA_SEQUENCE_TEXT
        JSR MA_PRINT
        LDX #11
MA_SEQ_BYTE:
        LDA MA_JOURNAL,X
        PHX
        JSR STR8V2_RAM_HEX_OUT
        PLX
        DEX
        CPX #7
        BNE MA_SEQ_BYTE
        LDX #<MA_DEFAULT_TEXT
        LDY #>MA_DEFAULT_TEXT
        JSR MA_PRINT
        LDA MA_JOURNAL+7
        JSR STR8V2_RAM_PUTC
        LDX #<MA_MASK_TEXT
        LDY #>MA_MASK_TEXT
        JSR MA_PRINT
        LDA MA_JOURNAL+13
        JSR STR8V2_RAM_HEX_OUT
        LDX #<MA_UNKNOWN_TEXT
        LDY #>MA_UNKNOWN_TEXT
        JSR MA_PRINT
        LDX #163
MA_UNKNOWN_BYTE:
        LDA MA_JOURNAL,X
        PHX
        JSR STR8V2_RAM_HEX_OUT
        PLX
        DEX
        CPX #159
        BNE MA_UNKNOWN_BYTE
        JSR STR8V2_RAM_NEWLINE
        JMP MA_MENU
MA_MAP_NO_JOURNAL:
        LDX #<MA_NO_JOURNAL_TEXT
        LDY #>MA_NO_JOURNAL_TEXT
        JMP MA_MESSAGE
MA_MAP_COUNT:
        LDA MA_JVALID
        BNE MA_MAP_COUNT_VALID
        LDX #<MA_UNKNOWN_COUNT
        LDY #>MA_UNKNOWN_COUNT
        JMP MA_PRINT
MA_MAP_COUNT_VALID:
        LDA MA_MAP_INDEX
        ASL A
        CLC
        ADC MA_MAP_INDEX
        TAX
        LDA MA_JOURNAL+66,X
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_MAP_INDEX
        ASL A
        CLC
        ADC MA_MAP_INDEX
        TAX
        LDA MA_JOURNAL+65,X
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_MAP_INDEX
        ASL A
        CLC
        ADC MA_MAP_INDEX
        TAX
        LDA MA_JOURNAL+64,X
        JMP STR8V2_RAM_HEX_OUT
MA_ROLE:
        LDA MA_MB
        BEQ MA_ROLE_BACKUP
        CMP #3
        BNE MA_ROLE_OWNER
        LDA MA_MS
        CMP #$A0
        BCC MA_ROLE_OWNER
        CMP #$C0
        BCC MA_ROLE_MON
        CMP #$E0
        BCC MA_ROLE_JOURNAL
        BEQ MA_ROLE_VX
        LDX #<MA_ROLE_F_TEXT
        LDY #>MA_ROLE_F_TEXT
        RTS
MA_ROLE_VX:
        LDX #<MA_ROLE_VX_TEXT
        LDY #>MA_ROLE_VX_TEXT
        RTS
MA_ROLE_JOURNAL:
        LDX #<MA_ROLE_JOURNAL_TEXT
        LDY #>MA_ROLE_JOURNAL_TEXT
        RTS
MA_ROLE_MON:
        LDX #<MA_ROLE_MON_TEXT
        LDY #>MA_ROLE_MON_TEXT
        RTS
MA_ROLE_BACKUP:
        LDX #<MA_ROLE_BACKUP_TEXT
        LDY #>MA_ROLE_BACKUP_TEXT
        RTS
MA_ROLE_OWNER:
        LDX #<MA_ROLE_OWNER_TEXT
        LDY #>MA_ROLE_OWNER_TEXT
        RTS

; Copy and admit the current snapshot without linking any journal writer.
MA_READ_JOURNAL:
        STZ MA_JVALID
        JSR BOOT_READ_RECORD
        BCC MA_JOURNAL_DONE
        STZ MA_PTR
        LDA J_BEST+1
        STA MA_PTR+1
        LDY #0
MA_JCOPY:
        LDA (MA_PTR),Y
        STA MA_JOURNAL,Y
        INY
        BNE MA_JCOPY
        LDA #<MA_JOURNAL
        STA MA_SRC
        LDA #>MA_JOURNAL
        STA MA_SRC+1
        LDA #252
        STA MA_COUNT
        STZ MA_COUNT+1
        JSR MA_RAW_CRC
        LDA MA_CRC
        CMP MA_JOURNAL+252
        BNE MA_JOURNAL_DONE
        LDA MA_CRC+1
        CMP MA_JOURNAL+253
        BNE MA_JOURNAL_DONE
        LDA MA_JOURNAL+254
        CMP #$FF
        BNE MA_JOURNAL_DONE
        JSR MA_CHECK_DUPLICATES
        BCC MA_JOURNAL_DONE
        INC MA_JVALID
MA_JOURNAL_DONE:
        RTS
        INCLUDE "maint-ro-duplicates.inc"

MA_SPACE:
        LDA #' '
        JMP STR8V2_RAM_PUTC
MA_NIBBLE_OUT:
        CMP #10
        BCC MA_NIBBLE_DIGIT
        CLC
        ADC #'A'-10
        JMP STR8V2_RAM_PUTC
MA_NIBBLE_DIGIT:
        CLC
        ADC #'0'
        JMP STR8V2_RAM_PUTC
MA_SPACE_NAME:
        CMP #4
        BEQ MA_NAME_RAM
        PHA
        LDA #'B'
        JSR STR8V2_RAM_PUTC
        PLA
        ORA #'0'
        JMP STR8V2_RAM_PUTC
MA_NAME_RAM:
        LDA #'R'
        JMP STR8V2_RAM_PUTC
MA_PRINT:
        STX MA_PTR
        STY MA_PTR+1
        LDY #0
MA_PRINT_NEXT:
        LDA (MA_PTR),Y
        BEQ MA_PRINT_DONE
        JSR STR8V2_RAM_PUTC
        INY
        BNE MA_PRINT_NEXT
        INC MA_PTR+1
        BRA MA_PRINT_NEXT
MA_PRINT_DONE:
        RTS
MA_TITLE: DB "2609 RAM MAINT / b15 / READ ONLY",13,10,0
MA_PROMPT: DB "MAINT RO> ",0
MA_HELP_TEXT:
        DB "M [1|2|3] grid / sectors (default) / wear",13,10
        DB "R src first last  Read 1-4096 bytes into buffer 5000-5FFF",13,10
        DB "D [offset [end]]  Display valid buffer bytes",13,10
        DB "K [src first last]  CRC16 of buffer or range",13,10
        DB "V src first last dst start  Compare; no copy/write",13,10
        DB "Q Restart F; ? Help. src/dst=R or bank 0-3; hex addresses.",13,10
        DB "RAM 2000-64FF; flash 8000-FFFF. R rejects buffer overlap.",13,10
        DB "No write, erase, edit, init, CONFIG-save or execution commands.",13,10,0
MA_BAD_TEXT: DB "REFUSED: command/range/buffer; ? for help",13,10,0
MA_BUFFER_TEXT: DB "BUFFER LOADED; D displays; K CRC; no write command",13,10,0
MA_CRC_TEXT: DB "CRC16=",0
MA_MATCH_TEXT: DB "MATCH",13,10,0
MA_DIFFERENT_TEXT: DB "DIFFERENT AT DEST ",0
MA_GRID_TITLE: DB "BANK 8 9 A B C D E F",13,10,0
MA_MAP_LEGEND: DB "E=all FF; U=programmed. Roles are policy, not image validation. READ ONLY.",13,10,0
MA_SEQUENCE_TEXT: DB "SNBT SEQ=",0
MA_DEFAULT_TEXT: DB " DEFAULT=",0
MA_MASK_TEXT: DB " BANKS=",0
MA_UNKNOWN_TEXT: DB " UNKNOWN=",0
MA_NO_JOURNAL_TEXT: DB "SNBT unavailable/ambiguous; wear counts unknown",13,10,0
MA_UNKNOWN_COUNT: DB "??????",0
MA_ROLE_BACKUP_TEXT: DB "WDC-BACKUP PROTECTED",0
MA_ROLE_OWNER_TEXT: DB "OWNER/UNCLASSIFIED",0
MA_ROLE_MON_TEXT: DB "MON-SLOT PROTECTED",0
MA_ROLE_JOURNAL_TEXT: DB "JOURNAL PROTECTED",0
MA_ROLE_VX_TEXT: DB "VX1-SLOT PROTECTED",0
MA_ROLE_F_TEXT: DB "BOOT-F PROTECTED",0
MA_GUARD_TABLE:
        INCLUDE "maint-ro-ram-guards.inc"
MA_IMAGE_CRC: DW 0
MA_IMM_END:
; Disposable app-owned state, excluded from its immutable-code CRC.
MA_STATE_BEGIN:
MA_HAVE: DB 0
MA_ERROR: DB 0
MA_POS: DB 0
MA_DIGITS: DB 0
MA_SB: DB 0
MA_DB: DB 0
MA_SRC: DW 0
MA_LAST: DW 0
MA_DST: DW 0
MA_COUNT: DW 0
MA_VALUE: DW 0
MA_OFFSET: DW 0
MA_LENGTH: DW 0
MA_CRC: DW 0
MA_COLUMN: DB 0
MA_BYTE: DB 0
MA_VIEW: DB 0
MA_MB: DB 0
MA_MS: DB 0
MA_STATUS: DB 0
MA_MAP_INDEX: DB 0
MA_TABLE_INDEX: DB 0
MA_JVALID: DB 0
MA_JOURNAL: DS 256
MA_END:
        ENDMOD
        END
