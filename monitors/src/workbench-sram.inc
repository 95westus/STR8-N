; Explicit EDU Rev D / 23LCV1024 profile only. RDMR(05) and READ(03), never
; WRITE(02), WRMR(01), format, repair, resize or probe-by-writing.
W_EDU_CMD:
        JSR W_SKIP
        BEQ W_EDU_SHOW
        CMP #'O'
        BNE W_UNHANDLED
        INX
        LDA W_LINE,X
        CMP #'N'
        BEQ W_EDU_ON
        CMP #'F'
        BNE W_UNHANDLED
        INX
        LDA W_LINE,X
        CMP #'F'
        BNE W_UNHANDLED
        INX
        JSR W_END_ARGS
        BCC W_UNHANDLED
        STZ W_EDU
        STZ MU_EDU
        BRA W_EDU_SHOW
W_EDU_ON:
        INX
        JSR W_END_ARGS
        BCC W_UNHANDLED
        LDA #1
        STA W_EDU
        STA MU_EDU
W_EDU_SHOW:
        LDX #<W_EDU_OFF_TEXT
        LDY #>W_EDU_OFF_TEXT
        LDA W_EDU
        BEQ W_EDU_PRINT
        LDX #<W_EDU_ON_TEXT
        LDY #>W_EDU_ON_TEXT
W_EDU_PRINT:
        JSR W_PUTS
        JMP W_HANDLED
W_SRAM_CMD:
        JSR WP_CHECK
        BCC WP_BAD_PROVIDER
        JSR W_SKIP
        BEQ W_STORAGE_STATUS
        CMP #'R'
        BEQ WP_RAW_READ
        LDY #0
W_PREP_MATCH:
        LDA W_LINE,X
        CMP W_PREP_WORD,Y
        BNE W_UNHANDLED
        INX
        INY
        CPY #4
        BCC W_PREP_MATCH
        JSR W_END_ARGS
        BCC W_UNHANDLED
        LDA W_EDU
        BEQ W_EDU_REQUIRED
        JSR SP_GUARD_ENTRY
        BCC W_PIN_BUSY
        LDA W_IFR
        AND #$18
        BEQ W_PREP_DONE
        LDA W_ORB
        LDA W_IFR
        AND #$18
        BNE W_PIN_BUSY
W_PREP_DONE:
        LDX #<W_PREP_TEXT
        LDY #>W_PREP_TEXT
        JMP W_MESSAGE
W_WORK_CMD:
        JSR W_END_ARGS
        BCC W_UNHANDLED
W_STORAGE_STATUS:
        LDA #0
        JSR WP_REQUEST
        BCC WP_ERROR
        LDX #<WP_STATUS_TEXT
        LDY #>WP_STATUS_TEXT
        JSR W_PUTS
        LDA LIMIT
        JSR STR8V2_RAM_HEX_OUT
        LDX #<WP_STATUS_END
        LDY #>WP_STATUS_END
        JMP W_MESSAGE
WP_RAW_READ:
        LDY #0
WP_RAW_TOKEN:
        LDA W_LINE,X
        CMP WP_READ_WORD,Y
        BNE W_UNHANDLED
        INX
        INY
        CPY #4
        BCC WP_RAW_TOKEN
        JSR W_SKIP
        SEC
        SBC #'0'
        CMP #2
        BCS W_UNHANDLED
        STA W_A2
        INX
        LDA W_LINE,X
        CMP #' '
        BNE W_UNHANDLED
        JSR W_HEX_WORD
        BCC W_UNHANDLED
        JSR W_END_ARGS
        BCC W_UNHANDLED
        LDA W_VALUE
        STA W_A0
        LDA W_VALUE+1
        STA W_A1
        JSR SP_READ_ENTRY
        BCC WP_ERROR
        LDX #<WP_RAW_TEXT
        LDY #>WP_RAW_TEXT
        JSR W_PUTS
        LDY #0
WP_RAW_BYTES:
        LDA W_LAYOUT,Y
        JSR STR8V2_RAM_HEX_OUT
        LDA #' '
        JSR STR8V2_RAM_PUTC
        INY
        CPY #64
        BCC WP_RAW_BYTES
        JSR STR8V2_RAM_NEWLINE
        JMP W_HANDLED
W_EDU_REQUIRED:
        LDA #$80
        BRA WP_ERROR
W_PIN_BUSY:
        LDA #1
WP_ERROR:
        PHA
        LDA #WB_REFUSED
        STA W_RESULT
        PLA
WP_REPORT:
        PHA
        LDX #<WP_ERROR_TEXT
        LDY #>WP_ERROR_TEXT
        JSR W_PUTS
        PLA
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        JMP W_HANDLED
WP_BAD_PROVIDER:
        LDX #<WP_BAD_PROVIDER_TEXT
        LDY #>WP_BAD_PROVIDER_TEXT
        JMP W_RECORD_ERROR
W_EDU_WORD: DB "EDU",0
W_SRAM_WORD: DB "SRAM",0
W_WORK_WORD: DB "WORK",0
W_PREP_WORD: DB "PREP"
WP_READ_WORD: DB "READ"
W_EDU_OFF_TEXT: DB "EDU OFF (session; no bus access)",13,10,0
W_EDU_ON_TEXT: DB "EDU ON (Rev D; not presence proof)",13,10,0
W_PREP_TEXT: DB "Disabled CB flags acknowledged; no SPI clocks",13,10,0
WP_STATUS_TEXT: DB "SSRAM PROGRAM: 0800 to page ",0
WP_STATUS_END: DB " (00=10000). WORKSPACE untouched.",13,10,0
WP_ERROR_TEXT: DB "SSRAM error $",0
WP_BAD_PROVIDER_TEXT: DB "PROGRAM provider invalid; MAINT LOAD",13,10,0
WP_RAW_TEXT: DB "RAW64 ",0
