; WB2 RAM workbench. Store programs fresh SR01 bytes only; never erases.
; ROM monitor bridge contract: validate immutable 4800-63FF first, A=data bank,
; X/Y=40-byte NUL-terminated command. C=handled, A=resulting bank. D/DBR/PBR=0,
; E=1, SEI/CLD. WB2 adds the command result at 655F; g7 supplies the bridge.
        MODULE WORKBENCH
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "workbench-layout.inc"
        INCLUDE "workbench-foundation.inc"
        INCLUDE "program-layout.inc"
        INCLUDE "monitor-ui.inc"
SP_BASE EQU $6B00
SP_API_ENTRY EQU SP_BASE+8
SP_READ_ENTRY EQU SP_BASE+11
SP_GUARD_ENTRY EQU SP_BASE+14
WP_MODE EQU $6563
W_EXPLICIT EQU $6564
        CODE
W_BEGIN:
        DB "MW",WB_FORMAT,WB_PAGES,"PR05"
        JMP W_DISPATCH
        JMP W_SHELL
        JMP W_INIT
        DB "WG","WB_GENERATION_BYTES"
W_SHELL:
        LDA #3
W_ENTER_SHELL:
        SEI
        CLD
        LDX #$FF
        TXS
        PHA
        JSR W_INIT
        PLA
        STA W_BANK
        JSR STR8V2_RAM_RX_RESET
        LDX #<W_TITLE
        LDY #>W_TITLE
        JSR W_PUTS
        LDX #<W_SHELL_TEXT
        LDY #>W_SHELL_TEXT
        JSR W_PUTS
        BRA W_PROMPT
W_INIT:
        LDX #0
W_CLEAR:
        STZ $6400,X
        STZ $6500,X
        STZ $6600,X
        INX
        BNE W_CLEAR
        LDA #3
        STA W_BANK
        LDA MU_EDU
        AND #1
        STA W_EDU
        RTS
W_PROMPT:
        LDX #<W_PROMPT_TEXT
        LDY #>W_PROMPT_TEXT
        JSR W_PUTS
        JSR W_READ_LINE
        BCC W_INPUT_BAD
        LDA W_BANK
        LDX #<W_LINE
        LDY #>W_LINE
        JSR W_DISPATCH
        BCS W_PROMPT
W_INPUT_BAD:
        JSR STR8V2_RAM_RX_RESET
        LDX #<W_SYNTAX_TEXT
        LDY #>W_SYNTAX_TEXT
        JSR W_PUTS
        BRA W_PROMPT
W_DISPATCH:
        STZ W_RESULT
        CMP #4
        BCS W_UNHANDLED
        STA W_BANK
        STX W_PTR
        STY W_PTR+1
        LDY #0
W_COMMAND_COPY:
        LDA (W_PTR),Y
        STA W_LINE,Y
        BEQ W_COMMAND_START
        INY
        CPY #40
        BCC W_COMMAND_COPY
        ; A full 40 characters is permitted only with its terminator at +40.
        LDA (W_PTR),Y
        BNE W_UNHANDLED
        STA W_LINE,Y
W_COMMAND_START:
        STZ W_BAD
        JSR W_ALIASES
        LDX #0
        JSR W_SKIP
        BEQ W_HANDLED
        CMP #'?'
        BEQ W_HELP
        CMP #'B'
        BEQ W_BANK_NAME
        CMP #'T'
        BEQ W_TABLE_OR_TIME
        CMP #'V'
        BEQ W_VERSION_NAME
        CMP #'R'
        BEQ W_RESTORE_SHORT
        CMP #'Q'
        BEQ W_QUIT
        CMP #'S'
        BNE W_DEVICE_NAMES
        LDA W_LINE+1,X
        BEQ WS_STORE
        CMP #' '
        BEQ WS_STORE
        BRA W_DEVICE_NAMES
W_TABLE_OR_TIME:
        LDA W_LINE+1,X
        CMP #'I'
        BEQ W_TIME_NAME
        JMP W_TABLE_CMD
W_RESTORE_SHORT:
        LDA W_LINE+1,X
        BEQ W_RESTORE_CMD
        CMP #' '
        BEQ W_RESTORE_CMD
        JMP W_UNHANDLED
W_DEVICE_NAMES:
        LDX #<WC_WORD
        LDY #>WC_WORD
        JSR W_MATCH
        BCS WC_COMMAND
        LDX #<WC_MAINT_WORD
        LDY #>WC_MAINT_WORD
        JSR W_MATCH
        BCS WC_MAINT
        LDX #<WC_FLASH_WORD
        LDY #>WC_FLASH_WORD
        JSR W_MATCH
        BCS WC_FLASH
        LDX #<WC_BOOT_WORD
        LDY #>WC_BOOT_WORD
        JSR W_MATCH
        BCS WC_FLASH
        LDX #<WS_AREA_WORD
        LDY #>WS_AREA_WORD
        JSR W_MATCH
        BCS WS_AREA
        LDX #<WS_HELP_WORD
        LDY #>WS_HELP_WORD
        JSR W_MATCH
        BCS W_HELP_ARGS
        LDX #<W_EDU_WORD
        LDY #>W_EDU_WORD
        JSR W_MATCH
        BCS W_EDU_CMD
        LDX #<W_SRAM_WORD
        LDY #>W_SRAM_WORD
        JSR W_MATCH
        BCS W_SRAM_CMD
        LDX #<W_WORK_WORD
        LDY #>W_WORK_WORD
        JSR W_MATCH
        BCS W_WORK_CMD
W_UNHANDLED:
        LDA #WB_SYNTAX
        STA W_RESULT
        LDA W_BANK
        CLC
        RTS
W_HANDLED:
        LDA W_BANK
        SEC
        RTS
W_HELP:
        INX
W_HELP_ARGS:
        JSR W_END_ARGS
        BCC W_UNHANDLED
        LDX #<W_HELP_TEXT
        LDY #>W_HELP_TEXT
        JSR W_PUTS
        BRA W_HANDLED
W_BANK_NAME:
        LDA W_LINE+1,X
        CMP #'A'
        BNE W_BANK_CMD
        LDX #<WB_WORD
        LDY #>WB_WORD
        JSR W_MATCH
        BCS WB_BATCH
        JMP W_UNHANDLED
W_BANK_CMD:
        INX
        JSR W_SKIP
        BEQ W_BANK_SHOW
        SEC
        SBC #'0'
        CMP #4
        BCS W_UNHANDLED
        STA W_TMP
        INX
        JSR W_END_ARGS
        BCC W_UNHANDLED
        LDA W_TMP
        STA W_BANK
W_BANK_SHOW:
        LDX #<W_BANK_TEXT
        LDY #>W_BANK_TEXT
        JSR W_PUTS
        LDA W_BANK
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        JSR STR8V2_RAM_NEWLINE
        BRA W_HANDLED
W_QUIT:
        INX
        JSR W_END_ARGS
        BCC W_UNHANDLED
        SEI
        CLD
        JSR STR8V2_RAM_RX_RESET
        LDX #$FF
        TXS
        LDA #MU_BYPASS
        JSR W_UI_CHECK
        BCC W_QUIT_LEGACY
        LDA W_BANK
        STA MU_BANK
        JMP (W_UI_TARGET)
W_QUIT_LEGACY:
        LDA W_UI_VALID
        BEQ W_QUIT_RECOVERY
        JMP STR8V2_RAM_HOLD
W_QUIT_RECOVERY:
        JMP WB_F_RECOVERY

; Normalize only complete long command words, leaving arguments untouched.
; The matching token supplies its own first letter; in-place copy always
; moves left. BATCH validation uses the same normalization as execution.
W_ALIASES:
        LDX #<W_STORE_WORD
        LDY #>W_STORE_WORD
        JSR W_MATCH
        BCS W_ALIAS_COPY
        LDX #<W_TABLE_WORD
        LDY #>W_TABLE_WORD
        JSR W_MATCH
        BCS W_ALIAS_COPY
        LDX #<W_RESTORE_WORD
        LDY #>W_RESTORE_WORD
        JSR W_MATCH
        BCC W_ALIAS_RETURN
W_ALIAS_COPY:
        LDY #0
        LDA (W_PTR),Y
        STA W_LINE
        INY
W_ALIAS_ARGUMENTS:
        LDA W_LINE,X
        STA W_LINE,Y
        BEQ W_ALIAS_RETURN
        INX
        INY
        BRA W_ALIAS_ARGUMENTS
W_ALIAS_RETURN:
        RTS

; Word matching restarts at the beginning; on success X points at arguments.
W_MATCH:
        STX W_PTR
        STY W_PTR+1
        LDX #0
        JSR W_SKIP
        LDY #0
W_MATCH_BYTE:
        LDA (W_PTR),Y
        BEQ W_MATCH_END
        CMP W_LINE,X
        BNE W_MATCH_BAD
        INX
        INY
        BRA W_MATCH_BYTE
W_MATCH_END:
        LDA W_LINE,X
        BEQ W_MATCH_OK
        CMP #' '
        BNE W_MATCH_BAD
W_MATCH_OK:
        SEC
        RTS
W_MATCH_BAD:
        CLC
        RTS
W_SKIP:
        LDA W_LINE,X
        CMP #' '
        BNE W_SKIP_END
        INX
        BRA W_SKIP
W_SKIP_END:
        CMP #0
        RTS
W_END_ARGS:
        JSR W_SKIP
        BNE W_MATCH_BAD
        SEC
        RTS
W_HEX_WORD:
        JSR W_SKIP
        STZ W_VALUE
        STZ W_VALUE+1
        STZ W_TMP2
W_HEX_LOOP:
        LDA W_LINE,X
        BEQ W_HEX_DONE
        CMP #' '
        BEQ W_HEX_DONE
        CMP #'0'
        BCC W_MATCH_BAD
        CMP #'9'+1
        BCC W_HEX_DIGIT
        CMP #'A'
        BCC W_MATCH_BAD
        CMP #'F'+1
        BCS W_MATCH_BAD
        SEC
        SBC #7
W_HEX_DIGIT:
        SEC
        SBC #'0'
        PHA
        INC W_TMP2
        LDA W_TMP2
        CMP #5
        BCS W_HEX_TOO_LONG
        ASL W_VALUE
        ROL W_VALUE+1
        ASL W_VALUE
        ROL W_VALUE+1
        ASL W_VALUE
        ROL W_VALUE+1
        ASL W_VALUE
        ROL W_VALUE+1
        PLA
        ORA W_VALUE
        STA W_VALUE
        INX
        BRA W_HEX_LOOP
W_HEX_TOO_LONG:
        PLA
        CLC
        RTS
W_HEX_DONE:
        LDA W_TMP2
        BEQ W_MATCH_BAD
        SEC
        RTS

; Optional single-digit bank. Otherwise use the selected data bank.
W_RECORD_BANK:
        STZ W_EXPLICIT
        INX
        JSR W_SKIP
        CMP #'0'
        BCC W_RECORD_BANK_DONE
        CMP #'4'
        BCS W_RECORD_BANK_DONE
        LDY W_LINE+1,X
        CPY #' '
        BEQ W_RECORD_BANK_SET
        CPY #0
        BNE W_RECORD_BANK_DONE
W_RECORD_BANK_SET:
        INC W_EXPLICIT
        AND #3
        STA W_BANK
        INX
W_RECORD_BANK_DONE:
        RTS
W_TABLE_CMD:
        JSR W_PROGRAM_ARGUMENT
        BCS WP_TABLE_CMD
        JSR W_RECORD_BANK
        JSR W_END_ARGS
        BCC W_UNHANDLED
        LDX #<W_TABLE_TEXT
        LDY #>W_TABLE_TEXT
        JSR W_PUTS
        STZ W_ADDR
        LDA #$80
        STA W_ADDR+1
        STZ W_CACHE_VALID
W_TABLE_NEXT:
        JSR W_FIND_RECORD
        BCC W_TABLE_END
        JSR W_SHOW_RECORD
        JSR W_SKIP_RECORD
        BRA W_TABLE_NEXT
W_TABLE_END:
        LDA W_BAD
        BNE W_CANCELED
        LDA W_EXPLICIT
        BNE W_TABLE_FINISH
        LDA W_EDU
        BNE WP_TABLE
W_TABLE_FINISH:
        LDX #<W_TABLE_END_TEXT
        LDY #>W_TABLE_END_TEXT
        JSR W_PUTS
        JMP W_HANDLED
; R [bank] name|address [L]. Names are unique within the selected bank.
; Whole destination must be 0200-47FF: the RAM workbench owns 4800-66FF.
W_RESTORE_CMD:
        JSR W_NATIVE_RESTORE
        STZ WP_MODE
        JSR W_PROGRAM_ARGUMENT
        BCC W_RESTORE_FLASH
        LDA #1
        STA WP_MODE
        BRA W_RESTORE_NAME_ARGS
W_RESTORE_FLASH:
        JSR W_RECORD_BANK
        LDA W_EXPLICIT
        BNE W_RESTORE_NAME_ARGS
        LDA #2
        STA WP_MODE
W_RESTORE_NAME_ARGS:
        JSR W_SKIP
        BEQ W_UNHANDLED
        STX W_IX
        STZ W_NAME_LEN
        STZ W_ONLY
W_NAME_COPY:
        LDA W_LINE,X
        BEQ W_NAME_END
        CMP #' '
        BEQ W_NAME_END
        LDY W_NAME_LEN
        CPY #16
        BCS W_UNHANDLED
        STA W_NAME,Y
        INC W_NAME_LEN
        INX
        BRA W_NAME_COPY
W_NAME_END:
        LDY W_NAME_LEN
        LDA #0
W_NAME_PAD:
        CPY #16
        BCS W_NAME_PAD_DONE
        STA W_NAME,Y
        INY
        BRA W_NAME_PAD
W_NAME_PAD_DONE:
        JSR W_SKIP
        BEQ W_RESTORE_ARGS
        CMP #'L'
        BNE W_UNHANDLED
        INX
        JSR W_END_ARGS
        BCC W_UNHANDLED
        INC W_ONLY
W_RESTORE_ARGS:
        LDA WP_MODE
        CMP #1
        BEQ WP_RESTORE
        ; All-hex names are addresses, as in the legacy numeric form.
        LDX W_IX
        JSR W_HEX_WORD
        BCC W_RESTORE_NAME
        LDA W_VALUE+1
        CMP #$80
        BCC W_RANGE
        LDA W_VALUE
        STA W_ADDR
        LDA W_VALUE+1
        STA W_ADDR+1
        STZ W_CACHE_VALID
        JSR W_VALIDATE_RECORD
        BCC W_NOT_FOUND
        LDA W_HEADER+3
        CMP #$3F
        BNE W_NOT_FOUND
        BRA W_RESTORE_SELECTED
W_RESTORE_NAME:
        STZ W_ADDR
        LDA #$80
        STA W_ADDR+1
        STZ W_FOUND
        STZ W_CACHE_VALID
W_RESTORE_SEARCH:
        JSR W_FIND_RECORD
        BCC W_RESTORE_SEARCH_END
        LDA W_HEADER+3
        CMP #$3F
        BNE W_RESTORE_SEARCH_NEXT
        LDY #0
W_RESTORE_COMPARE:
        CPY W_NAME_LEN
        BEQ W_RESTORE_NAME_END
        LDA W_HEADER+8,Y
        JSR W_UPPER
        CMP W_NAME,Y
        BNE W_RESTORE_SEARCH_NEXT
        INY
        BRA W_RESTORE_COMPARE
W_RESTORE_NAME_END:
        CPY #16
        BEQ W_RESTORE_MATCH
        LDA W_HEADER+8,Y
        BNE W_RESTORE_SEARCH_NEXT
W_RESTORE_MATCH:
        INC W_FOUND
        LDA W_FOUND
        CMP #2
        BCS W_DUPLICATE
        LDA W_ADDR
        STA W_RECORD
        LDA W_ADDR+1
        STA W_RECORD+1
W_RESTORE_SEARCH_NEXT:
        JSR W_SKIP_RECORD
        BRA W_RESTORE_SEARCH
W_RESTORE_SEARCH_END:
        LDA W_BAD
        BNE W_CANCELED
        LDA WP_MODE
        CMP #2
        BNE W_RESTORE_POST_PROGRAM
        LDA W_EDU
        BEQ W_RESTORE_POST_PROGRAM
        JSR WP_LOOKUP
        BCC W_RESTORE_PROGRAM_MISS
        LDA W_FOUND
        BNE W_DUPLICATE
        JMP WP_RESTORE
W_RESTORE_PROGRAM_MISS:
        CMP #$42
        BNE WP_ERROR
W_RESTORE_POST_PROGRAM:
        LDA W_FOUND
        BEQ W_NOT_FOUND
        LDA W_RECORD
        STA W_ADDR
        LDA W_RECORD+1
        STA W_ADDR+1
        JSR W_VALIDATE_RECORD
        BCC W_NOT_FOUND
W_RESTORE_SELECTED:
        LDA W_HEADER+4
        STA W_DEST
        LDA W_HEADER+5
        STA W_DEST+1
        CMP #2
        BCC W_RANGE
        CMP W_RAM_FLOOR
        BCC W_RANGE
        CLC
        LDA W_DEST
        ADC W_HEADER+6
        STA W_VALUE
        LDA W_DEST+1
        ADC W_HEADER+7
        BCS W_RANGE
        CMP #>WB_ORIGIN
        BCC W_RESTORE_PREFLIGHT_OK
        BNE W_RANGE
        LDA W_VALUE
        BNE W_RANGE
W_RESTORE_PREFLIGHT_OK:
        LDA W_HEADER+6
        STA W_LEFT
        LDA W_HEADER+7
        STA W_LEFT+1
        CLC
        LDA W_ADDR
        ADC #24
        STA W_ADDR
        BCC W_RESTORE_COPY
        INC W_ADDR+1
W_RESTORE_COPY:
        JSR W_CANCEL
        BCS W_PARTIAL
        JSR W_FLASH_BYTE
        PHA
        LDA W_DEST
        STA W_COPY
        LDA W_DEST+1
        STA W_COPY+1
        PLA
        STA (W_COPY)
        CMP (W_COPY)
        BNE W_PARTIAL
        INC W_DEST
        BNE W_RESTORE_INC_SOURCE
        INC W_DEST+1
W_RESTORE_INC_SOURCE:
        INC W_ADDR
        BNE W_RESTORE_DEC
        INC W_ADDR+1
W_RESTORE_DEC:
        LDA W_LEFT
        BNE W_RESTORE_DEC_LOW
        DEC W_LEFT+1
W_RESTORE_DEC_LOW:
        DEC W_LEFT
        LDA W_LEFT
        ORA W_LEFT+1
        BNE W_RESTORE_COPY
        LDX #<W_LOADED_TEXT
        LDY #>W_LOADED_TEXT
        JSR W_PUTS
        LDA W_ONLY
        BNE W_RESTORE_DONE
        LDA W_HEADER+4
        STA W_F_VECTOR
        LDA W_HEADER+5
        STA W_F_VECTOR+1
        LDA W_BANK
        STA W_F_SELECTED
        JMP WB_F_EXECUTE
W_RESTORE_DONE:
        JMP W_HANDLED
W_RANGE:
        LDX #<W_RANGE_TEXT
        LDY #>W_RANGE_TEXT
        BRA W_RECORD_ERROR
W_NOT_FOUND:
        LDX #<W_NOT_FOUND_TEXT
        LDY #>W_NOT_FOUND_TEXT
        BRA W_RECORD_ERROR
W_DUPLICATE:
        LDX #<W_DUPLICATE_TEXT
        LDY #>W_DUPLICATE_TEXT
        BRA W_RECORD_ERROR
W_PARTIAL:
        LDA #WB_PARTIAL
        STA W_RESULT
        LDX #<W_PARTIAL_TEXT
        LDY #>W_PARTIAL_TEXT
        BRA W_MESSAGE
W_CANCELED:
        LDA #WB_CANCELED
        STA W_RESULT
        LDX #<W_CANCELED_TEXT
        LDY #>W_CANCELED_TEXT
        BRA W_MESSAGE
W_RECORD_ERROR:
        LDA #WB_REFUSED
        STA W_RESULT
W_MESSAGE:
        JSR W_PUTS
        JMP W_HANDLED

; Bytewise cached scanner; complete and pending SR/01 records are structural
; records, not payload-checksummed images. Scan to E000 like the legacy arena.
W_FIND_RECORD:
        JSR W_CANCEL
        BCS W_FIND_END
        LDA W_ADDR+1
        CMP #$E0
        BCS W_FIND_END
        JSR W_FLASH_BYTE
        CMP #'S'
        BNE W_FIND_ADVANCE
        JSR W_VALIDATE_RECORD
        BCS W_FIND_OK
W_FIND_ADVANCE:
        INC W_ADDR
        BNE W_FIND_RECORD
        INC W_ADDR+1
        BRA W_FIND_RECORD
W_FIND_OK:
        SEC
        RTS
W_FIND_END:
        CLC
        RTS
W_VALIDATE_RECORD:
        LDA W_ADDR+1
        CMP #$80
        BCC W_RECORD_BAD
        CMP #$DF
        BCC W_HEADER_READ
        BNE W_RECORD_BAD
        LDA W_ADDR
        CMP #$E9
        BCS W_RECORD_BAD
W_HEADER_READ:
        LDA W_ADDR
        PHA
        LDA W_ADDR+1
        PHA
        LDY #0
W_HEADER_BYTE:
        JSR W_FLASH_BYTE
        STA W_HEADER,Y
        INC W_ADDR
        BNE W_HEADER_INC
        INC W_ADDR+1
W_HEADER_INC:
        INY
        CPY #24
        BCC W_HEADER_BYTE
        PLA
        STA W_ADDR+1
        PLA
        STA W_ADDR
W_CHECK_HEADER:
        LDA W_HEADER
        CMP #'S'
        BNE W_RECORD_BAD
        LDA W_HEADER+1
        CMP #'R'
        BNE W_RECORD_BAD
        LDA W_HEADER+2
        CMP #1
        BNE W_RECORD_BAD
        LDA W_HEADER+3
        CMP #$3F
        BEQ W_HEADER_STATE_OK
        CMP #$FF
        BNE W_RECORD_BAD
W_HEADER_STATE_OK:
        LDA W_HEADER+6
        ORA W_HEADER+7
        BEQ W_RECORD_BAD
        CLC
        LDA W_ADDR
        ADC #24
        STA W_END
        LDA W_ADDR+1
        ADC #0
        STA W_END+1
        CLC
        LDA W_END
        ADC W_HEADER+6
        STA W_END
        LDA W_END+1
        ADC W_HEADER+7
        BCS W_RECORD_BAD
        STA W_END+1
        CMP #$E0
        BCC W_HEADER_NAME
        BNE W_RECORD_BAD
        LDA W_END
        BNE W_RECORD_BAD
W_HEADER_NAME:
        LDY #0
        STZ W_TMP
W_HEADER_NAME_BYTE:
        LDA W_HEADER+8,Y
        BEQ W_HEADER_ZERO
        LDX W_TMP
        BNE W_RECORD_BAD
        CMP #$21
        BCC W_RECORD_BAD
        CMP #$7F
        BCS W_RECORD_BAD
        BRA W_HEADER_NAME_NEXT
W_HEADER_ZERO:
        INC W_TMP
W_HEADER_NAME_NEXT:
        INY
        CPY #16
        BCC W_HEADER_NAME_BYTE
        SEC
        RTS
W_RECORD_BAD:
        CLC
        RTS
W_SKIP_RECORD:
        LDA W_END
        STA W_ADDR
        LDA W_END+1
        STA W_ADDR+1
        RTS
W_SHOW_RECORD:
        JSR W_SHOW_LOCATION
        BRA W_SHOW_FIELDS
W_SHOW_LOCATION:
        LDA #'B'
        JSR STR8V2_RAM_PUTC
        LDA W_BANK
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA W_ADDR+1
        JSR STR8V2_RAM_HEX_OUT
        LDA W_ADDR
        JSR STR8V2_RAM_HEX_OUT
        RTS
W_SHOW_FIELDS:
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA #'+'
        LDX W_HEADER+3
        CPX #$3F
        BEQ W_SHOW_STATE
        LDA #'?'
W_SHOW_STATE:
        JSR STR8V2_RAM_PUTC
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA W_HEADER+5
        JSR STR8V2_RAM_HEX_OUT
        LDA W_HEADER+4
        JSR STR8V2_RAM_HEX_OUT
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA W_HEADER+7
        JSR STR8V2_RAM_HEX_OUT
        LDA W_HEADER+6
        JSR STR8V2_RAM_HEX_OUT
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDY #0
W_SHOW_NAME:
        LDA W_HEADER+8,Y
        BEQ W_SHOW_DONE
        JSR STR8V2_RAM_PUTC
        INY
        CPY #16
        BCC W_SHOW_NAME
W_SHOW_DONE:
        JMP STR8V2_RAM_NEWLINE
W_FLASH_BYTE:
        PHX
        PHY
        LDA W_ADDR
        AND #$F0
        CMP W_CACHE_ADDR
        BNE W_CACHE_FILL
        LDA W_ADDR+1
        CMP W_CACHE_ADDR+1
        BNE W_CACHE_FILL
        LDA W_CACHE_VALID
        BNE W_CACHE_HIT
W_CACHE_FILL:
        LDA W_ADDR
        AND #$F0
        STA W_CACHE_ADDR
        STA W_F_ADDR
        LDA W_ADDR+1
        STA W_CACHE_ADDR+1
        STA W_F_ADDR+1
        LDA W_F_SELECTED
        PHA
        LDA W_BANK
        STA W_F_SELECTED
        LDA #16
        STA W_F_COUNT
        JSR WB_F_READ
        LDX #15
W_CACHE_COPY:
        LDA W_F_BYTES,X
        STA W_CACHE,X
        DEX
        BPL W_CACHE_COPY
        PLA
        STA W_F_SELECTED
        LDA #1
        STA W_CACHE_VALID
W_CACHE_HIT:
        LDA W_ADDR
        AND #15
        TAX
        LDA W_CACHE,X
        PLY
        PLX
        RTS

        INCLUDE "workbench-store.inc"
        INCLUDE "workbench-sram.inc"
        INCLUDE "workbench-program.inc"
        INCLUDE "workbench-batch.inc"
        INCLUDE "workbench-clock.inc"
        INCLUDE "workbench-native.inc"
        INCLUDE "workbench-monitor-ui.inc"

W_CANCEL:
        PHX
        PHY
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS W_CANCEL_FOUND
        ; Frozen F latches Ctrl-C only; ESC stays in its ordinary RX queue.
        ; Inspect without consuming other typeahead. An explicit cancel may
        ; discard queued input, exactly as the foundation Ctrl-C path does.
        LDY W_RX_COUNT
        BEQ W_CANCEL_CLEAR
        LDX $FD
W_CANCEL_SCAN:
        TXA
        AND #63
        TAX
        LDA $7D40,X
        CMP #27
        BEQ W_CANCEL_FOUND
        INX
        DEY
        BNE W_CANCEL_SCAN
W_CANCEL_CLEAR:
        CLC
        BRA W_NOT_CANCELED
W_CANCEL_FOUND:
        JSR STR8V2_RAM_RX_RESET
        LDA #1
        STA W_BAD
        SEC
W_NOT_CANCELED:
        PLY
        PLX
        RTS
W_PUTS:
        STX W_PTR
        STY W_PTR+1
        LDY #0
W_PUTS_BYTE:
        LDA (W_PTR),Y
        BEQ W_PUTS_END
        JSR STR8V2_RAM_PUTC
        INY
        BNE W_PUTS_BYTE
        INC W_PTR+1
        BRA W_PUTS_BYTE
W_PUTS_END:
        RTS
W_UPPER:
        CMP #'a'
        BCC W_UPPER_END
        CMP #'z'+1
        BCS W_UPPER_END
        AND #$DF
W_UPPER_END:
        RTS
W_READ_LINE:
        STZ W_LEN
        LDA W_RX_BAD
        STA W_BAD
        ORA W_RX_COUNT
        BNE W_KEEP_OWNER
        STZ W_DC_OWNER
W_KEEP_OWNER:
        STZ W_RX_BAD
W_READ_BYTE:
        JSR STR8V2_RAM_GETC
        STA W_CHAR
        LDA W_RX_BAD
        BEQ W_READ_CHAR
        LDA #1
        STA W_BAD
        STZ W_RX_BAD
W_READ_CHAR:
        LDA W_CHAR
        CMP #10
        BNE W_READ_NOT_LF
        LDA W_DC_LAST
        AND W_SKIP_LF
        BNE W_READ_BYTE
        BRA W_LINE_END
W_READ_NOT_LF:
        LDA W_DC_LAST
        TRB W_SKIP_LF
        LDA W_CHAR
        CMP #13
        BNE W_READ_NOT_CR
        LDA W_DC_LAST
        TSB W_SKIP_LF
        BRA W_LINE_END
W_READ_NOT_CR:
        CMP #3
        BEQ W_LINE_CANCEL
        CMP #27
        BEQ W_LINE_CANCEL
        LDA W_BAD
        BNE W_READ_BYTE
        LDA W_CHAR
        CMP #8
        BEQ W_BACKSPACE
        CMP #127
        BEQ W_BACKSPACE
        CMP #9
        BNE W_READ_PRINTABLE
        LDA #' '
W_READ_PRINTABLE:
        CMP #32
        BCC W_BAD_CHAR
        CMP #127
        BCS W_BAD_CHAR
        JSR W_UPPER
        LDX W_LEN
        CPX #40
        BCS W_BAD_CHAR
        STA W_LINE,X
        INC W_LEN
        JSR STR8V2_RAM_PUTC
        BRA W_READ_BYTE
W_BAD_CHAR:
        LDA #1
        STA W_BAD
        BRA W_READ_BYTE
W_BACKSPACE:
        LDA W_LEN
        BEQ W_READ_BYTE
        DEC W_LEN
        LDA #8
        JSR STR8V2_RAM_PUTC
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA #8
        JSR STR8V2_RAM_PUTC
        BRA W_READ_BYTE
W_LINE_CANCEL:
        LDA #1
        STA W_BAD
        STZ W_LEN
W_LINE_END:
        LDX W_LEN
        STZ W_LINE,X
        JSR STR8V2_RAM_NEWLINE
        LDA W_BAD
        BNE W_LINE_BAD
        SEC
        RTS
W_LINE_BAD:
        CLC
        RTS
W_CRC_START:
        LDA #$FF
        STA W_CRC
        STA W_CRC+1
        RTS
W_CRC_BYTE:
        PHX
        EOR W_CRC+1
        STA W_CRC+1
        LDX #8
W_CRC_BIT:
        ASL W_CRC
        ROL W_CRC+1
        BCC W_CRC_NEXT
        LDA W_CRC
        EOR #$21
        STA W_CRC
        LDA W_CRC+1
        EOR #$10
        STA W_CRC+1
W_CRC_NEXT:
        DEX
        BNE W_CRC_BIT
        PLX
        RTS
W_TITLE: DB 13,10
W_VERSION_TEXT: DB "STR8-N WORKBENCH WB2 gWB_GENERATION_TEXT / BASE1 PR05",13,10
        DB 0
W_SHELL_TEXT:
        DB "RAM 0200-47FF; tools 4800-66FF",13,10
        DB "EDU selection retained; ? help; Q monitor",13,10,0
W_PROMPT_TEXT: DB "WORKBENCH> ",0
W_SYNTAX_TEXT: DB "REFUSED: syntax/command/input",13,10,0
W_STORE_WORD: DB "STORE",0
W_TABLE_WORD: DB "TABLE",0
W_RESTORE_WORD: DB "RESTORE",0
W_HELP_TEXT: DB "B0..3; TABLE [bank|P]; RESTORE [bank|P] name|addr [L]",13,10
        DB "AREA [bank first last]; STORE bank|P addr|AUTO first last [name]",13,10
        DB "EDU ON|OFF; SRAM [PREP|READ half addr]; WORK; Q",13,10
        DB "VERSION/V; TIME; R CLOCK|FLASH|MAINT; BOOT; Q monitor",13,10
        DB "BATCH cmd;cmd (34 bytes): B TABLE ? HELP EDU SRAM WORK",13,10,0
W_BANK_TEXT: DB "Data bank B",0
W_TABLE_TEXT: DB "SR01 +complete ?pending: addr load size name (hex)",13,10,0
W_TABLE_END_TEXT: DB "End; SR01 has no payload CRC.",13,10,0
W_LOADED_TEXT: DB "Loaded; RAM verified.",13,10,0
W_RANGE_TEXT: DB "REFUSED: record bounds or reserved destination RAM",13,10,0
W_NOT_FOUND_TEXT: DB "No complete SR01 record at that address/name",13,10,0
W_DUPLICATE_TEXT: DB "REFUSED: ambiguous name; select bank/P/address",13,10,0
W_PARTIAL_TEXT: DB "Stopped: destination RAM may be partially loaded",13,10,0
W_CANCELED_TEXT: DB "Canceled; no restore started",13,10,0
W_CODE_END:
        ENDMOD
        END
