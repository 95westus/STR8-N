; Shared MON A/B core: explicit owner-RAM Modify and guarded force writes.
        MODULE MONITOR
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "layout.inc"
        INCLUDE "foundation.inc"
        INCLUDE "monitor-ui.inc"
        CODE
        INCLUDE "entry.inc"
M_START:
        SEI
        CLD
        LDX #$FF
        TXS
        LDA #0
        TAX
M_CLEAR:
        STA M_STATE,X
        INX
        BNE M_CLEAR
        LDA #3
        STA M_BANK
; Only entered by a CRC-admitted UI/1 tool, with monitor state preserved.
M_WARM_ENTRY:
        SEI
        CLD
        LDX #$FF
        TXS
        LDX #3
M_RA_CHECK:
        LDA STR8V2_RAM_SIGNATURE,X
        CMP M_RA,X
        BNE M_LOCK
        DEX
        BPL M_RA_CHECK
        JSR M_CHECK_F
        BCC M_BAD_F
        JSR M_BIND
        JSR STR8V2_RAM_RX_RESET
        JSR M_STATUS
M_PROMPT:
        STZ M_FORCE
        LDA #'B'
        JSR STR8V2_RAM_PUTC
        LDA M_BANK
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        LDX #<M_PROMPT_TEXT
        LDY #>M_PROMPT_TEXT
        JSR M_PUTS
        JSR M_READ_LINE
        BCC M_INPUT_BAD
        LDX #0
        JSR M_SKIP
        BEQ M_PROMPT
        INX
        CMP #'!'
        BEQ M_FORCE_NAME
        CMP #'?'
        BEQ M_HELP
        CMP #'V'
        BEQ M_VERSION
        CMP #'T'
        BEQ M_TIME_NAME
        CMP #'B'
        BEQ M_BANK_COMMAND
        CMP #'D'
        BEQ M_DUMP
        CMP #'M'
        BEQ M_MODIFY
        CMP #'G'
        BEQ M_GO
        CMP #'L'
        BEQ M_LOAD
        CMP #'Q'
        BEQ M_QUIT
M_MODULE:
        JSR M_SERVICE_CHECK
        BCC M_MODULE_MISSING
        ; A RAM-loaded monitor must not be overwritten by a module Restore.
        LDA #MON_SLOT_PAGE
        BEQ M_MODULE_RAM
        LDA #2
        BRA M_MODULE_FLOOR
M_MODULE_RAM:
        LDA #MON_RAM_FLOOR
M_MODULE_FLOOR:
        STA SB_CLIENT_FLOOR
        LDA M_BANK
        LDX #<M_LINE
        LDY #>M_LINE
        JSR MON_SERVICE_BASE+8
        BCC M_SYNTAX
        STA M_BANK
        JMP M_PROMPT
M_MODULE_MISSING:
        LDX #<M_MODULE_TEXT
        LDY #>M_MODULE_TEXT
        JMP M_MESSAGE
M_SYNTAX:
        LDX #<M_SYNTAX_TEXT
        LDY #>M_SYNTAX_TEXT
        JMP M_MESSAGE
M_FORCE_NAME:
        LDA M_LINE,X
        CMP #'M'
        BNE M_SYNTAX
        INX
        INC M_FORCE
        JMP M_MODIFY
M_INPUT_BAD:
        JSR STR8V2_RAM_RX_RESET
        LDX #<M_INPUT_TEXT
        LDY #>M_INPUT_TEXT
        JMP M_MESSAGE
M_HELP:
        JSR M_END_ARGS
        BCC M_SYNTAX
        LDX #<M_HELP_TEXT
        LDY #>M_HELP_TEXT
        JMP M_MESSAGE
M_VERSION:
        ; V and VERSION are exact aliases; a V-prefixed typo is not accepted.
        LDA M_LINE,X
        BEQ M_VERSION_ARGS
        CMP #' '
        BEQ M_VERSION_ARGS
        LDY #0
M_VERSION_MATCH:
        LDA M_LINE,X
        CMP M_VERSION_SUFFIX,Y
        BNE M_SYNTAX
        INX
        INY
        CPY #6
        BCC M_VERSION_MATCH
M_VERSION_ARGS:
        JSR M_END_ARGS
        BCC M_SYNTAX
        JSR M_STATUS
        JMP M_PROMPT
M_TIME_NAME:
        LDA M_LINE,X
        CMP #'I'
        BNE M_MODULE
        LDY #0
M_TIME_MATCH:
        LDA M_LINE,X
        CMP M_TIME_SUFFIX,Y
        BNE M_SYNTAX
        INX
        INY
        CPY #3
        BCC M_TIME_MATCH
M_TIME_COMMAND:
        JSR M_END_ARGS
        BCC M_SYNTAX
        JSR M_SHARED_TIME
        JMP M_PROMPT
M_SHARED_TIME:
        JSR MR_SAMPLE
        STA MR_RESULT
        BEQ M_TIME_SHOW
        LDX #<M_TIME_ERROR_TEXT
        LDY #>M_TIME_ERROR_TEXT
        JSR M_PUTS
        LDA MR_RESULT
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
M_TIME_SHOW:
        JSR MR_DISPLAY
        LDA MR_RESULT
        RTS
M_QUIT:
        JSR M_END_ARGS
        BCC M_SYNTAX
        JMP M_RECOVERY
M_LOAD:
        JSR M_END_ARGS
        BCC M_SYNTAX
        LDA #MON_SLOT_PAGE
        BEQ M_RANGE
        ; Tail-enter the exact frozen loader. Its optional-LF/owner handling
        ; and first-byte Ctrl-C semantics remain intact. RAM smoke refuses L.
        LDA M_SKIP_LF
        STA F_DC_SKIP
        LDX #$FF
        TXS
        JMP MON_F_LOAD
M_BANK_COMMAND:
        JSR M_SKIP
        BEQ M_SHOW_BANK
        CMP #'A'
        BEQ M_MODULE
        SEC
        SBC #'0'
        CMP #4
        BCS M_SYNTAX
        STA M_CHAR
        INX
        JSR M_END_ARGS
        BCC M_SYNTAX
        LDA M_CHAR
        STA M_BANK
M_SHOW_BANK:
        LDX #<M_BANK_TEXT
        LDY #>M_BANK_TEXT
        JSR M_PUTS
        LDA M_BANK
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        JSR STR8V2_RAM_NEWLINE
        JMP M_PROMPT
M_DUMP:
        JSR M_HEX_WORD
        BCC M_SYNTAX
        LDA M_VALUE
        STA M_FIRST
        STA M_ADDR
        LDA M_VALUE+1
        STA M_FIRST+1
        STA M_ADDR+1
        JSR M_SKIP
        BNE M_DUMP_END
        CLC
        LDA M_FIRST
        ADC #15
        STA M_VALUE
        LDA M_FIRST+1
        ADC #0
        STA M_VALUE+1
        BCS M_RANGE
        BRA M_DUMP_PREFLIGHT
M_DUMP_END:
        JSR M_HEX_WORD
        BCC M_SYNTAX
        JSR M_END_ARGS
        BCC M_SYNTAX
M_DUMP_PREFLIGHT:
        LDA M_VALUE
        STA M_LAST
        SEC
        SBC M_FIRST
        STA M_LEFT
        LDA M_VALUE+1
        STA M_LAST+1
        SBC M_FIRST+1
        BCC M_RANGE
        STA M_LEFT+1
        INC M_LEFT
        BNE M_DUMP_IO
        INC M_LEFT+1
M_DUMP_IO:
        LDA M_FIRST+1
        CMP #$80
        BCS M_DUMP_ROW
        LDA M_LAST+1
        CMP #$7F
        BCS M_RANGE
M_DUMP_ROW:
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS M_DUMP_CANCEL
        LDA #16
        LDX M_LEFT+1
        BNE M_HAVE_ROW
        CMP M_LEFT
        BCC M_HAVE_ROW
        LDA M_LEFT
M_HAVE_ROW:
        STA M_ROW
        JSR M_READ_BYTES
        LDA M_ADDR+1
        JSR STR8V2_RAM_HEX_OUT
        LDA M_ADDR
        JSR STR8V2_RAM_HEX_OUT
        LDA #':'
        JSR STR8V2_RAM_PUTC
        STZ M_INDEX
M_DUMP_BYTE:
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDX M_INDEX
        LDA M_BUFFER,X
        JSR STR8V2_RAM_HEX_OUT
        INC M_INDEX
        LDA M_INDEX
        CMP M_ROW
        BCC M_DUMP_BYTE
M_DUMP_PAD:
        LDA M_INDEX
        CMP #16
        BCS M_DUMP_ASCII
        LDA #' '
        JSR STR8V2_RAM_PUTC
        JSR STR8V2_RAM_PUTC
        JSR STR8V2_RAM_PUTC
        INC M_INDEX
        BRA M_DUMP_PAD
M_DUMP_ASCII:
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA #'|'
        JSR STR8V2_RAM_PUTC
        STZ M_INDEX
M_ASCII_BYTE:
        LDX M_INDEX
        LDA M_BUFFER,X
        CMP #32
        BCC M_ASCII_DOT
        CMP #127
        BCC M_ASCII_OUT
M_ASCII_DOT:
        LDA #'.'
M_ASCII_OUT:
        JSR STR8V2_RAM_PUTC
        INC M_INDEX
        LDA M_INDEX
        CMP M_ROW
        BCC M_ASCII_BYTE
        LDA #'|'
        JSR STR8V2_RAM_PUTC
        JSR STR8V2_RAM_NEWLINE
        CLC
        LDA M_ADDR
        ADC M_ROW
        STA M_ADDR
        BCC M_DUMP_REMAIN
        INC M_ADDR+1
M_DUMP_REMAIN:
        SEC
        LDA M_LEFT
        SBC M_ROW
        STA M_LEFT
        LDA M_LEFT+1
        SBC #0
        STA M_LEFT+1
        ORA M_LEFT
        BNE M_DUMP_ROW
        JMP M_PROMPT
M_DUMP_CANCEL:
        JSR STR8V2_RAM_RX_RESET
        LDX #<M_CANCEL_TEXT
        LDY #>M_CANCEL_TEXT
        JMP M_MESSAGE
M_RANGE:
        LDX #<M_RANGE_TEXT
        LDY #>M_RANGE_TEXT
        JMP M_MESSAGE
; Parse and stage the complete edit before its first target write.
; RAM is common to all banks. ROM, I/O, stack and system state are excluded.
M_MODIFY:
        JSR M_SKIP
        BEQ M_MODULE
        CMP #'A'
        BNE M_MODIFY_NUMERIC
        LDA M_LINE+1,X
        CMP #'I'
        BEQ M_MODULE
M_MODIFY_NUMERIC:
        JSR M_HEX_WORD
        BCC M_SYNTAX
        JSR M_SKIP
        BEQ M_MODULE
        LDA M_VALUE
        STA M_ADDR
        LDA M_VALUE+1
        STA M_ADDR+1
        STZ M_ROW
M_EDIT_PARSE:
        JSR M_HEX_WORD
        BCC M_SYNTAX
        LDA M_DIGITS
        CMP #3
        BCS M_SYNTAX
        LDY M_ROW
        LDA M_VALUE
        STA M_EDIT,Y
        INC M_ROW
        JSR M_SKIP
        BEQ M_EDIT_RANGE
        LDA M_ROW
        CMP #8
        BCS M_SYNTAX
        BRA M_EDIT_PARSE
M_EDIT_RANGE:
        LDA M_ROW
        DEC A
        CLC
        ADC M_ADDR
        STA M_LAST
        LDA M_ADDR+1
        ADC #0
        STA M_LAST+1
        BCS M_RANGE
        LDA M_FORCE
        BNE MF_PREFLIGHT
        LDA M_ADDR+1
        BEQ M_EDIT_ZP
        CMP #2
        BCC M_RANGE
        CMP #$67
        BCS M_RANGE
        LDA M_LAST+1
        CMP #$67
        BCS M_RANGE
        ; The RAM smoke image additionally protects its complete code pages.
        LDA #MON_SLOT_PAGE
        BNE M_EDIT_READY
        LDA M_ADDR+1
        CMP #MON_RAM_FLOOR
        BCC M_RANGE
        BRA M_EDIT_READY
M_EDIT_ZP:
        LDA M_LAST+1
        BNE M_RANGE
        LDA M_LAST
        CMP #$E0
        BCS M_RANGE
M_EDIT_READY:
        ; Admitted WB2 borrows through66FF; ordinary Modify respects its base.
        LDA M_LAST+1
        CMP #>WB_ORIGIN
        BCC M_EDIT_CANCEL
        JSR M_MODULE_CHECK
        BCS M_RANGE
M_EDIT_CANCEL:
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS M_INPUT_BAD
        LDA M_ADDR
        STA M_PTR
        LDA M_ADDR+1
        STA M_PTR+1
        LDA F_NMI_HOLD
        PHA
        LDA #1
        STA F_NMI_HOLD
        LDY #0
M_EDIT_COPY:
        LDA M_EDIT,Y
        STA (M_PTR),Y
        CMP (M_PTR),Y
        BNE M_EDIT_FAILED
        INY
        CPY M_ROW
        BCC M_EDIT_COPY
        PLA
        STA F_NMI_HOLD
        LDA M_ROW
        STA M_LEFT
        STZ M_LEFT+1
        ; Echo independently read bytes, using the normal hex/ASCII row.
        JMP M_HAVE_ROW
M_EDIT_FAILED:
        PLA
        STA F_NMI_HOLD
        LDX #<M_VERIFY_TEXT
        LDY #>M_VERIFY_TEXT
        JMP M_MESSAGE
M_GO:
        JSR M_HEX_WORD
        BCC M_SYNTAX
        JSR M_END_ARGS
        BCC M_SYNTAX
        LDA #MON_SLOT_PAGE
        BEQ M_RANGE
        LDA M_VALUE+1
        BMI M_GO_FLASH
        CMP #2
        BCC M_RANGE
        CMP #$67
        BCS M_RANGE
        BRA M_GO_READY
M_GO_FLASH:
        LDA M_BANK
        CMP #3
        BNE M_GO_READY
        LDA M_VALUE+1
        CMP #$F0
        BCS M_RANGE
        CMP #$C0
        BCC M_GO_READY
        CMP #$E0
        BCC M_RANGE
M_GO_READY:
        JMP M_EXECUTE

; X indexes the bounded line. Carry set means a complete valid hex token.
M_SKIP:
        LDA M_LINE,X
        CMP #' '
        BNE M_SKIP_DONE
        INX
        BRA M_SKIP
M_SKIP_DONE:
        CMP #0
        RTS
M_END_ARGS:
        JSR M_SKIP
        BNE M_END_BAD
        SEC
        RTS
M_UNSUPPORTED:
M_END_BAD:
        CLC
        RTS
M_HEX_WORD:
        JSR M_SKIP
        STZ M_VALUE
        STZ M_VALUE+1
        STZ M_DIGITS
M_HEX_NEXT:
        LDA M_LINE,X
        BEQ M_HEX_END
        CMP #' '
        BEQ M_HEX_END
        JSR STR8V2_RAM_HEX_NIBBLE
        BCC M_HEX_BAD
        STA M_NIB
        INC M_DIGITS
        LDA M_DIGITS
        CMP #5
        BCS M_HEX_BAD
        LDY #4
M_HEX_SHIFT:
        ASL M_VALUE
        ROL M_VALUE+1
        DEY
        BNE M_HEX_SHIFT
        LDA M_NIB
        ORA M_VALUE
        STA M_VALUE
        INX
        BRA M_HEX_NEXT
M_HEX_END:
        LDA M_DIGITS
        BEQ M_HEX_BAD
        SEC
        RTS
M_HEX_BAD:
        CLC
        RTS

M_READ_LINE:
        STZ M_LEN
        LDA F_RX_BAD
        STA M_BAD
        ORA F_RX_COUNT
        BNE M_KEEP_OWNER
        STZ F_DC_OWNER
M_KEEP_OWNER:
        STZ F_RX_BAD
M_LINE_BYTE:
        JSR STR8V2_RAM_GETC
        STA M_CHAR
        LDA F_RX_BAD
        BEQ M_LINE_CHAR
        LDA #1
        STA M_BAD
        STZ F_RX_BAD
M_LINE_CHAR:
        LDA M_CHAR
        CMP #10
        BNE M_NOT_LF
        LDA F_DC_LAST
        AND M_SKIP_LF
        BNE M_LINE_BYTE
        BRA M_LINE_END
M_NOT_LF:
        LDA F_DC_LAST
        TRB M_SKIP_LF
        LDA M_CHAR
        CMP #13
        BNE M_NOT_CR
        LDA F_DC_LAST
        TSB M_SKIP_LF
        BRA M_LINE_END
M_NOT_CR:
        CMP #3
        BEQ M_LINE_CANCEL
        CMP #27
        BEQ M_LINE_CANCEL
        LDA M_BAD
        BNE M_LINE_BYTE
        LDA M_CHAR
        CMP #8
        BEQ M_BACKSPACE
        CMP #127
        BEQ M_BACKSPACE
        CMP #9
        BNE M_NOT_TAB
        LDA #' '
M_NOT_TAB:
        CMP #32
        BCC M_BAD_CHAR
        CMP #127
        BCS M_BAD_CHAR
        CMP #'a'
        BCC M_STORE_CHAR
        CMP #'z'+1
        BCS M_STORE_CHAR
        AND #$DF
M_STORE_CHAR:
        LDX M_LEN
        CPX #M_LINE_LIMIT
        BCS M_BAD_CHAR
        STA M_LINE,X
        INC M_LEN
        JSR STR8V2_RAM_PUTC
        BRA M_LINE_BYTE
M_BAD_CHAR:
        LDA #1
        STA M_BAD
        BRA M_LINE_BYTE
M_BACKSPACE:
        LDA M_LEN
        BEQ M_LINE_BYTE
        DEC M_LEN
        LDA #8
        JSR STR8V2_RAM_PUTC
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA #8
        JSR STR8V2_RAM_PUTC
        BRA M_LINE_BYTE
M_LINE_CANCEL:
        LDA #1
        STA M_BAD
        STZ M_LEN
M_LINE_END:
        LDX M_LEN
        STZ M_LINE,X
        JSR STR8V2_RAM_NEWLINE
        LDA M_BAD
        BNE M_END_BAD
        SEC
        RTS

M_STATUS:
        LDX #<M_TITLE
        LDY #>M_TITLE
        JSR M_PUTS
        JSR STR8V2_RAM_BOARD_QUERY
        STX M_CPU
        JSR STR8V2_RAM_CAPS_QUERY
        STX M_CAPS
        LDX #<M_CPU_TEXT
        LDY #>M_CPU_TEXT
        JSR M_PUTS
        LDA M_CPU
        JSR STR8V2_RAM_HEX_OUT
        LDX #<M_CAPS_TEXT
        LDY #>M_CAPS_TEXT
        JSR M_PUTS
        LDA M_CAPS
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        LDX #<M_OPTIONAL_TEXT
        LDY #>M_OPTIONAL_TEXT
        JSR M_PUTS
        JSR MR_DISPLAY
        LDX #<M_BATTERY_TEXT
        LDY #>M_BATTERY_TEXT
        JSR M_PUTS
        JSR M_WEAR
        LDX #<M_LIMIT_TEXT
        LDY #>M_LIMIT_TEXT
        JMP M_PUTS
M_WEAR:
        LDX #<M_WEAR_TEXT
        LDY #>M_WEAR_TEXT
        JSR M_PUTS
        JSR M_READ_WEAR
        BCC M_WEAR_NONE
        LDA #'B'
        JSR STR8V2_RAM_PUTC
        LDA M_MAX_ROW
        LSR A
        LSR A
        LSR A
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA M_MAX_ROW
        AND #7
        CLC
        ADC #8
        TAX
        LDA M_HEX_DIGITS,X
        JSR STR8V2_RAM_PUTC
        LDX #<M_MAX_TEXT
        LDY #>M_MAX_TEXT
        JSR M_PUTS
        LDA M_MAX+2
        JSR STR8V2_RAM_HEX_OUT
        LDA M_MAX+1
        JSR STR8V2_RAM_HEX_OUT
        LDA M_MAX
        JSR STR8V2_RAM_HEX_OUT
        LDA #'*'
        JSR STR8V2_RAM_PUTC
        JMP STR8V2_RAM_NEWLINE
M_WEAR_NONE:
        LDX #<M_NO_WEAR_TEXT
        LDY #>M_NO_WEAR_TEXT
        JMP M_PUTS

M_MESSAGE:
        JSR M_PUTS
        JMP M_PROMPT
M_PUTS:
        STX M_PTR
        STY M_PTR+1
        LDY #0
M_PUTS_NEXT:
        LDA (M_PTR),Y
        BEQ M_PUTS_DONE
        JSR STR8V2_RAM_PUTC
        INC M_PTR
        BNE M_PUTS_NEXT
        INC M_PTR+1
        BRA M_PUTS_NEXT
M_PUTS_DONE:
        RTS
M_BAD_F:
        LDX #<M_BAD_F_TEXT
        LDY #>M_BAD_F_TEXT
        JSR M_PUTS
M_LOCK:
        JMP M_LOCK
        INCLUDE "rtc-read.inc"
        INCLUDE "force.inc"
        INCLUDE "adapter.inc"
M_RA: DB "RA",1,13
M_HEX_DIGITS: DB "0123456789ABCDEF"
M_VERSION_SUFFIX: DB "ERSION"
M_TIME_SUFFIX: DB "IME"
M_PROMPT_TEXT: DB "> ",0
M_TITLE:
        DB 13,10,"STR8-N 0.1.0-dev gMON_GENERATION_TEXT / ",MON_SLOT_LABEL,13,10
        DB "N-F 0.3.0 g00000001 / BASE1 / PR05",13,10,0
M_CPU_TEXT: DB "CPU $",0
M_CAPS_TEXT: DB "  caps $",0
M_OPTIONAL_TEXT:
        DB "EDU/SSRAM: MAINT",13,10,0
M_BATTERY_TEXT: DB "Battery: --*",13,10,0
M_TIME_ERROR_TEXT: DB "RTCC read refused/failed $",0
M_WEAR_TEXT: DB "Wear: ",0
M_MAX_TEXT: DB " tracked max $",0
M_NO_WEAR_TEXT: DB "--*",13,10,0
M_LIMIT_TEXT:
        DB "-- no data; * Health/prior wear unverified; tracked attempts.",13,10,0
M_BANK_TEXT: DB "Data bank B",0
M_HELP_TEXT:
        DB "? VERSION(V) TIME; B0..3; D addr [end]; G addr; L BIN",13,10
        DB "M/!M addr bytes (1-8); force flash 1->0",13,10
        DB "B3:C/D/F protected; Q REC",13,10
        DB "M1-3 W APPS CLOCK MAINT; BATCH S T R EDU SRAM WORK",13,10,0
M_SYNTAX_TEXT: DB "REFUSED: syntax (use ?)",13,10,0
M_INPUT_TEXT: DB "Input canceled/rejected",13,10,0
M_CANCEL_TEXT: DB "Dump cancelled.",13,10,0
M_RANGE_TEXT: DB "REFUSED: range/entry",13,10,0
M_VERIFY_TEXT: DB "RAM verify failed; partial edit",13,10,0
M_BAD_F_TEXT: DB "BASE1/PR05 mismatch",13,10,0
M_MODULE_TEXT: DB "Services absent/invalid",13,10,0
M_END:
        ENDMOD
        END
