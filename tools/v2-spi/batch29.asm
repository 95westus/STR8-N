; Foreground command-boundary batch executive, linked in sealed B2 utilities.
B29_ACTIVE EQU $7EE4
B29_POS EQU $7EE5
B29_SIZE EQU $7EE6
B29_ERROR EQU $7EE7
B29_PROVIDER EQU $7EE8
B29_PORT EQU $7EE9
B29_ORIG EQU $7EEA
B29_PTR EQU $DC
B29_N EQU $7EEC
B29_START EQU $7EED
B29_LIMIT EQU $7EEE
B29_LENGTH EQU $7EEF
B29_OP EQU $7EF0
B29_LENPTR EQU $DE
B29_QUEUE EQU $7BD4
B29_RAM_MON EQU $7C90
B29_RAM_CLOCK EQU $7C94
B29_RAM_ERROR EQU $7C98
B29_RAM_APP EQU $7C9E
B29_RAM_COMMON EQU $7C9F

; Bit 7 means a complete interactive line has just been read. Only the
; monitor accepts BATCH; ordinary utility input retains its existing parser.
B29_ENGINE:
        STA B29_OP
        AND #$7F
        STA B29_PROVIDER
        ASL A
        TAX
        LDA B29_READERS,X
        STA B29_ORIG
        LDA B29_READERS+1,X
        STA B29_ORIG+1
        LDA B29_PROVIDER
        BNE B29_NOT_MON
        LDA $7D30
        CLC
        ADC #B29_MON_DELTA
        STA B29_ORIG+1
B29_NOT_MON:
        LDA B29_OP
        BMI B29_TYPED
        LDA B29_ACTIVE
        BEQ B29_INTERACTIVE
        JSR $7E76
        BCS B29_ESC
        LDY $F9
        BEQ B29_POLL_DONE
        LDA $FD
        AND #63
        TAX
B29_POLL_ESC:
        LDA $7D40,X
        CMP #$1B
        BEQ B29_ESC
        INX
        TXA
        AND #63
        TAX
        DEY
        BNE B29_POLL_ESC
B29_POLL_DONE:
        LDA B29_ERROR
        BEQ B29_NO_ERROR
        CMP #2
        BEQ B29_ESC
        BRA B29_FAILED
B29_NO_ERROR:
        LDA B29_POS
        CMP B29_SIZE
        BCS B29_COMPLETED
        JMP B29_NEXT
B29_COMPLETED:
        LDX #<B29_DONE_TEXT
        LDY #>B29_DONE_TEXT
        BRA B29_STOP
B29_ESC:
        JSR $7E79
        LDX #<B29_CANCEL_TEXT
        LDY #>B29_CANCEL_TEXT
        BRA B29_STOP
B29_FAILED:
        LDX #<B29_FAIL_TEXT
        LDY #>B29_FAIL_TEXT
B29_STOP:
        STZ B29_ACTIVE
        STZ B29_ERROR
        JSR B29_PRINT
        LDX B29_PROVIDER
        LDA B29_PROMPT_LO,X
        LDY B29_PROMPT_HI,X
        TAX
        JSR B29_PRINT
B29_INTERACTIVE:
        CLC
        RTS
B29_TYPED:
        LDA B29_PROVIDER
        BNE B29_TYPED_RETURN
        LDA $7C00
        CMP #'?'
        BNE B29_TRY_BATCH
        LDA $7C01
        BNE B29_TYPED_RETURN
        JSR B29_FULL_HELP
        STZ $7C00
        BRA B29_TYPED_RETURN
B29_TRY_BATCH:
        LDX #5
B29_MATCH:
        LDA $7C00,X
        CMP B29_WORD,X
        BNE B29_TYPED_RETURN
        DEX
        BPL B29_MATCH
        LDX #6
        LDY #0
B29_CAPTURE:
        LDA $7C00,X
        BEQ B29_CAPTURED
        CPY #34
        BCS B29_SYNTAX
        STA B29_QUEUE,Y
        INX
        INY
        BRA B29_CAPTURE
B29_CAPTURED:
        STY B29_SIZE
        CPY #0
        BEQ B29_SYNTAX
        STZ B29_POS
        STZ B29_ERROR
        LDA #1
        STA B29_ACTIVE
        ; Validate all separators before executing the first command.
        LDX #0
        LDY #0
B29_VALIDATE:
        LDA B29_QUEUE,X
        CMP #';'
        BEQ B29_SEPARATOR
        CMP #' '
        BEQ B29_VALID_NEXT
        INY
        BRA B29_VALID_NEXT
B29_SEPARATOR:
        CPY #0
        BEQ B29_SYNTAX
        LDY #0
B29_VALID_NEXT:
        INX
        CPX B29_SIZE
        BNE B29_VALIDATE
        CPY #0
        BEQ B29_SYNTAX
        BRA B29_NEXT
B29_SYNTAX:
        STZ B29_ACTIVE
        STZ B29_ERROR
        STZ $7C00
        LDX #<B29_SYNTAX_TEXT
        LDY #>B29_SYNTAX_TEXT
        JSR B29_PRINT
        LDX #0
        LDY #0
        SEC
        RTS
B29_TYPED_RETURN:
        SEC
        RTS
B29_NEXT:
        LDX B29_POS
B29_SKIP_SPACE:
        LDA B29_QUEUE,X
        CMP #' '
        BNE B29_BEGIN
        INX
        BRA B29_SKIP_SPACE
B29_BEGIN:
        STX B29_START
        LDY #0
B29_COUNT:
        CPX B29_SIZE
        BEQ B29_COUNTED
        LDA B29_QUEUE,X
        CMP #';'
        BEQ B29_COUNTED
        INY
        INX
        BRA B29_COUNT
B29_COUNTED:
        CPX B29_SIZE
        BEQ B29_POSITION
        INX
B29_POSITION:
        STX B29_POS
        ; Strip trailing spaces and check the current interpreter's bound.
        TYA
        CLC
        ADC B29_START
        TAX
B29_TRIM:
        DEX
        LDA B29_QUEUE,X
        CMP #' '
        BNE B29_TRIMMED
        DEY
        BRA B29_TRIM
B29_TRIMMED:
        STY B29_N
        LDX B29_PROVIDER
        TYA
        CMP B29_LIMITS,X
        BCC B29_SEGMENT_FITS
        JMP B29_SEGMENT_BAD
B29_SEGMENT_FITS:
        TXA
        ASL A
        TAX
        LDA B29_LINES,X
        STA B29_PTR
        LDA B29_LINES+1,X
        STA B29_PTR+1
        LDA B29_LENGTHS,X
        STA B29_LENPTR
        LDA B29_LENGTHS+1,X
        STA B29_LENPTR+1
        LDA B29_PROVIDER
        BNE B29_COPY_SETUP
        LDA #'B'
        JSR $7E6D
B29_MON_SUFFIX:
        LDA $F3
        ORA #'0'
        JSR $7E6D
        LDA #'>'
        JSR $7E6D
        LDA #' '
        JSR $7E6D
B29_COPY_SETUP:
        LDX B29_START
        LDY #0
B29_COPY:
        LDA B29_QUEUE,X
        STA (B29_PTR),Y
        JSR $7E6D
        INX
        INY
        CPY B29_N
        BNE B29_COPY
        LDA #0
        STA (B29_PTR),Y
        LDA B29_N
        LDY #0
        STA (B29_LENPTR),Y
        JSR $7E7F
        ; Monitor batches deliberately exclude raw jumps/loaders/reset and
        ; unregistered RAM programs. Native launch commands are recognized.
        LDA B29_PROVIDER
        BNE B29_READY
        LDA $7C00
        CMP #'?'
        BNE B29_MON_NOT_HELP
        LDA $7C01
        BNE B29_SEGMENT_BAD
        JSR B29_FULL_HELP
        STZ $7C00
        BRA B29_READY
B29_MON_NOT_HELP:
        LDA $7C00
        CMP #'R'
        BEQ B29_MON_RUN
        LDX #0
B29_MON_ALLOWED:
        CMP B29_MON_KEYS,X
        BEQ B29_READY
        INX
        CPX #8
        BNE B29_MON_ALLOWED
        BRA B29_SEGMENT_BAD
B29_MON_RUN:
        LDX #1
B29_RUN_SPACE:
        LDA $7C00,X
        CMP #' '
        BNE B29_RUN_BANK
        INX
        BRA B29_RUN_SPACE
B29_RUN_BANK:
        CMP #'2'
        BNE B29_MON_NAME
        INX
B29_BANK_SPACE:
        LDA $7C00,X
        CMP #' '
        BNE B29_MON_NAME
        INX
        BRA B29_BANK_SPACE
B29_MON_NAME:
        STX B29_LIMIT
        LDY #0
B29_NATIVE_MATCH:
        LDA $7C00,X
        CMP B29_NATIVE_NAMES,Y
        BNE B29_NATIVE_SKIP
        INX
        INY
        LDA $7C00,X
        BEQ B29_NATIVE_END
        BRA B29_NATIVE_MATCH
B29_NATIVE_END:
        LDA B29_NATIVE_NAMES,Y
        BEQ B29_READY
B29_NATIVE_SKIP:
        LDA B29_NATIVE_NAMES,Y
        INY
        CMP #$FF
        BEQ B29_SEGMENT_BAD
        CMP #0
        BNE B29_NATIVE_SKIP
        LDX B29_LIMIT
        BRA B29_NATIVE_MATCH
B29_SEGMENT_BAD:
        STZ B29_ACTIVE
        STZ B29_ERROR
        LDX #<B29_UNSUPPORTED_TEXT
        LDY #>B29_UNSUPPORTED_TEXT
        JSR B29_PRINT
        LDA B29_PROVIDER
        BEQ B29_MON_EMPTY
        JMP B29_INTERACTIVE
B29_MON_EMPTY:
        STZ $7C00
B29_READY:
        STZ B29_ERROR
        LDX B29_N
        LDY #0
        SEC
        RTS
B29_PRINT:
        STX B29_PTR
        STY B29_PTR+1
        LDY #0
B29_PRINT_NEXT:
        LDA (B29_PTR),Y
        BEQ B29_PRINT_DONE
        JSR $7E6D
        INY
        BNE B29_PRINT_NEXT
        INC B29_PTR+1
        BRA B29_PRINT_NEXT
B29_PRINT_DONE:
        RTS
B29_FULL_HELP:
        LDX #<B29_FULL_HELP_TEXT
        LDY #>B29_FULL_HELP_TEXT
        JMP B29_PRINT
B29_WORD DB "BATCH "
B29_MON_KEYS DB "?BDTWAMV"
B29_NATIVE_NAMES DB "MAINT",0,"SRAM",0,"WORK",0,"EDU",0,$FF
B29_DONE_TEXT DB 13,10,"BATCH done",13,10,0
B29_FAIL_TEXT DB 13,10,"BATCH stopped: command failed",13,10,0
B29_CANCEL_TEXT DB 13,10,"BATCH canceled",13,10,0
B29_SYNTAX_TEXT DB "BATCH: empty/long command list",13,10,0
B29_UNSUPPORTED_TEXT DB "BATCH stopped: unsupported/long command",13,10,0
B29_PROMPT_LO DB <B29_P0,<B29_P1,<B29_P2,<B29_P3,<B29_P4,<B29_P5
B29_PROMPT_HI DB >B29_P0,>B29_P1,>B29_P2,>B29_P3,>B29_P4,>B29_P5
B29_P0 DB 0
B29_P1 DB "BM> ",0
B29_P2 DB "SRAM> ",0
B29_P3 DB "WORK> ",0
B29_P4 DB "EDU> ",0
B29_P5 DB "CLOCK> ",0
