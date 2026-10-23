X28_APPS:
        LDX #15
X28_APPS_SAVE_ZP:
        LDA $D0,X
        PHA
        DEX
        BPL X28_APPS_SAVE_ZP
        LDX #<X28_APPS_TEXT
        LDY #>X28_APPS_TEXT
        JSR WK_PRINT
        LDX #0
X28_APPS_RESTORE_ZP:
        PLA
        STA $D0,X
        INX
        CPX #16
        BNE X28_APPS_RESTORE_ZP
        LDA $7D2E
        STA V2_SELECTED
        PHP
        PHA
        LDA #<$E19C
        STA X28_CALL+1
        LDA #>$E19C
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_TAIL
X28_APPS_TEXT DB 13,10,"MAINT FLASH B2",13,10,"SRAM FLASH B2",13,10,"WORK FLASH B2; API 5003",13,10,"EDU FLASH B2",13,10,0
B29_LINE_1:
        JSR BFX_VALID
        BCC B29_OLD_1
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        LDA #1
        JMP $7C9F
B29_OLD_1: JMP MM_READLINE

B29_LINE_2:
        JSR BFX_VALID
        BCC B29_OLD_2
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        LDA #2
        JMP $7C9F
B29_OLD_2: JMP SM_C_READLINE

B29_LINE_3:
        JSR BFX_VALID
        BCC B29_OLD_3
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        LDA #3
        JMP $7C9F
B29_OLD_3: JMP WK_LINE_READ

B29_LINE_4:
        JSR BFX_VALID
        BCC B29_OLD_4
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        NOP
        LDA #4
        JMP $7C9F
B29_OLD_4: JMP ED_READ_LINE
B29_ERROR_HOOK:
        PHP
        PHA
        JSR BFX_VALID
        BCC B29_ERROR_DONE
        NOP
        NOP
        LDA $7EE4
        BEQ B29_ERROR_DONE
        LDA $7EE7
        CMP #2
        BEQ B29_ERROR_DONE
        LDA #1
        STA $7EE7
B29_ERROR_DONE:
        PLA
        PLP
        RTS
B29_CANCEL_HOOK:
        PHP
        PHA
        JSR BFX_VALID
        BCC B29_CANCEL_DONE
        NOP
        NOP
        LDA $7EE4
        BEQ B29_CANCEL_DONE
        LDA #2
        STA $7EE7
B29_CANCEL_DONE:
        PLA
        PLP
        RTS
B29_APP_CHECK:
        LDA $7EE4
        BEQ B29_APP_ACCEPT
        JSR BFX_VALID
        BCC B29_APP_ACCEPT
        NOP
        NOP
        LDY #0
        LDA ($FE),Y
        CMP #$80
        BNE B29_APP_REFUSE
        INY
        LDA ($FE),Y
        CMP #4
        BNE B29_APP_REFUSE
        LDY #5
B29_APP_MAGIC:
        LDA ($FE),Y
        CMP B29_APP_ID-2,Y
        BNE B29_APP_REFUSE
        DEY
        CPY #1
        BNE B29_APP_MAGIC
B29_APP_ACCEPT:
        SEC
        RTS
B29_APP_REFUSE:
        JSR B29_ERROR_HOOK
        CLC
        RTS
B29_APP_ID DB "BT",1,1
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
                        JMP B29_STOP
B29_ESC:
        JSR $7E79
        LDX #<B29_CANCEL_TEXT
        LDY #>B29_CANCEL_TEXT
                        JMP B29_STOP
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
                        BEQ B29_LONG_99
                        JMP B29_TYPED_RETURN
B29_LONG_99:
        JSR B30_ALIAS
        LDA $7C00
        CMP #'?'
                        BNE B29_TRY_BATCH
        LDA $7C01
                        BNE B29_TYPED_RETURN
        JSR B29_FULL_HELP
        STZ $7C00
                        JMP B29_TYPED_RETURN
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
                        JMP B29_NEXT
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
                        BEQ B29_LONG_260
                        JMP B29_READY
B29_LONG_260:
        LDA $7C00
        CMP #'?'
                        BNE B29_MON_NOT_HELP
        LDA $7C01
                        BEQ BFX_HELP_END
                        JMP B29_SEGMENT_BAD
BFX_HELP_END:
        JSR B29_FULL_HELP
        STZ $7C00
                        JMP B29_READY
B29_MON_NOT_HELP:
        JSR B30_ALIAS
        LDA $7C00
        CMP #'A'
        BNE B33_NOT_APP
        JSR B33_BATCH_APPS
        BCS B33_NOT_APP
        JMP B29_SEGMENT_BAD
B33_NOT_APP:
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
                        JMP B29_SEGMENT_BAD
B29_MON_RUN:
        JSR BFX_CLOCK_RUN
        BCC BFX_NATIVE_RUN
        JMP B29_READY
BFX_NATIVE_RUN:
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
                        JMP B29_NATIVE_MATCH
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
                        JMP B29_NATIVE_MATCH
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
        BRA B29_PRINT
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

B29_FULL_HELP_TEXT:
        DB $54,$49,$4D,$45,$0D,$0A,$42,$30,$2D,$33,$20,$44,$20,$61,$64,$64
        DB $72,$20,$5B,$65,$6E,$64,$5D,$20,$4D,$2F,$46,$20,$61,$64,$64,$72
        DB $20,$62,$79,$74,$65,$73,$20,$47,$20,$61,$64,$64,$72,$20,$4C,$0D
        DB $0A,$4D,$20,$5B,$31,$20,$67,$72,$69,$64,$7C,$32,$20,$72,$61,$6E
        DB $67,$65,$73,$7C,$33,$20,$77,$65,$61,$72,$5D,$0D,$0A,$49,$20,$73
        DB $74,$61,$72,$74,$20,$65,$6E,$64,$20,$57,$20,$55,$20,$41,$7C,$42
        DB $0D,$0A,$53,$20,$62,$61,$6E,$6B,$20,$66,$6C,$61,$73,$68,$20,$73
        DB $74,$61,$72,$74,$20,$65,$6E,$64,$20,$5B,$6E,$61,$6D,$65,$5D,$0D
        DB $0A,$52,$20,$5B,$62,$61,$6E,$6B,$5D,$20,$6E,$61,$6D,$65,$7C,$62
        DB $61,$6E,$6B,$20,$66,$6C,$61,$73,$68,$20,$5B,$4C,$5D,$0D,$0A,$54
        DB $20,$5B,$62,$61,$6E,$6B,$7C,$66,$69,$72,$73,$74,$2D,$6C,$61,$73
        DB $74,$5D,$0D,$0A,$4A,$30,$2D,$33,$20,$43,$20,$5B,$30,$7C,$31,$20
        DB $62,$61,$6E,$6B,$20,$61,$64,$64,$72,$7C,$56,$20,$64,$65,$6C,$61
        DB $79,$5D,$20,$50,$20,$5B,$41,$7C,$42,$5D,$0D,$0A,$4D,$41,$49,$4E
        DB $54,$20,$53,$52,$41,$4D,$20,$57,$4F,$52,$4B,$20,$45,$44,$55,$20
        DB $28,$52,$20,$6F,$70,$74,$69,$6F,$6E,$61,$6C,$29,$0D,$0A,$42,$41
        DB $54,$43,$48,$20,$63,$6D,$64,$3B,$63,$6D,$64,$20,$28,$33,$34,$20
        DB $74,$65,$78,$74,$20,$62,$79,$74,$65,$73,$29,$3B,$20,$45,$53,$43
        DB $20,$63,$61,$6E,$63,$65,$6C,$73,$0D,$0A,$00

B29_MON_DELTA EQU $0A
B29_READERS DW $AAF2,MM_READLINE,SM_C_READLINE,WK_LINE_READ,ED_READ_LINE,$25D1
B29_LINES DW $7C00,MM_BM_LINE,SM_C_LINE,WK_LINE,ED_LINE,$364B
B29_LENGTHS DW $7EEF,MM_LINELEN,SM_D_LINE_LENGTH,WK_LINE_N,ED_COUNT,$3633
B29_LIMITS DB 41,64,64,56,8,40
; Exact monitor aliases share the existing native-name table.
; Only called for provider zero. Do not intercept utility subcommands.
B30_ALIAS:
        LDX #0
B30_LEADING:
        LDA $7C00,X
        CMP #' '
        BNE B30_FIRST
        INX
        BRA B30_LEADING
B30_FIRST:
        STX B29_LIMIT
        LDY #0
B30_NAME:
        STY B29_LENGTH
        LDX B29_LIMIT
B30_MATCH:
        LDA B29_NATIVE_NAMES,Y
        BEQ B30_TAIL
        CMP #$FF
        BEQ B30_RETURN
        CMP $7C00,X
        BNE B30_NEXT
        INX
        INY
        BRA B30_MATCH
B30_TAIL:
        LDA $7C00,X
        BEQ B30_EXPAND
        CMP #' '
        BNE B30_NEXT
        INX
        BRA B30_TAIL
B30_NEXT:
        LDA B29_NATIVE_NAMES,Y
        CMP #$FF
        BEQ B30_RETURN
        INY
        CMP #0
        BNE B30_NEXT
        BRA B30_NAME
B30_EXPAND:
        LDY B29_LENGTH
        LDX #2
B30_COPY:
        LDA B29_NATIVE_NAMES,Y
        STA $7C00,X
        BEQ B30_PREFIX
        INX
        INY
        BRA B30_COPY
B30_PREFIX:
        STX B29_N
        LDA #'R'
        STA $7C00
        LDA #' '
        STA $7C01
B30_RETURN:
        RTS

B33_BATCH_APPS:
        LDX #0
B33_APPS_MATCH:
        LDA $7C00,X
        CMP B33_APPS_WORD,X
        BNE B33_APPS_BAD
        INX
        CPX #4
        BNE B33_APPS_MATCH
B33_APPS_TAIL:
        LDA $7C00,X
        BEQ B33_APPS_OK
        CMP #' '
        BNE B33_APPS_BAD
        INX
        BRA B33_APPS_TAIL
B33_APPS_OK: SEC
        RTS
B33_APPS_BAD: CLC
        RTS
B33_APPS_WORD DB "APPS"
; Batchfix-r1 capability ABI: BA means checked UX/3/42 provider + new gate.
; B9 is accepted only on legacy B monitors, retaining their existing contract.
BFX_VALID:
        LDA $7D30
        AND #$EF
        CMP #$A0
        BNE BFX_NO
        LDA $7EF4
        CMP #$BA
        BEQ BFX_GATE
        CMP #$B9
        BNE BFX_NO
        LDA $7D30
        CMP #$B0
        BNE BFX_NO
BFX_GATE:
        LDA $7C94
        CMP #$A9
        BNE BFX_NO
        LDA $7C9F
        CMP #$8D
        BNE BFX_NO
        SEC
        RTS
BFX_NO: CLC
        RTS
; Exact CLOCK launch admission; no arbitrary named programs or arguments.
BFX_CLOCK_RUN:
        LDX #1
BFX_CLOCK_SPACE:
        LDA $7C00,X
        CMP #' '
        BNE BFX_CLOCK_BANK
        INX
        BRA BFX_CLOCK_SPACE
BFX_CLOCK_BANK:
        CMP #'1'
        BNE BFX_CLOCK_NAME
        INX
        LDA $7C00,X
        CMP #' '
        BNE BFX_CLOCK_BAD
BFX_CLOCK_SPACE2:
        INX
        LDA $7C00,X
        CMP #' '
        BEQ BFX_CLOCK_SPACE2
BFX_CLOCK_NAME:
        LDY #0
BFX_CLOCK_MATCH:
        LDA $7C00,X
        CMP BFX_CLOCK_WORD,Y
        BNE BFX_CLOCK_BAD
        INX
        INY
        CPY #5
        BNE BFX_CLOCK_MATCH
BFX_CLOCK_TAIL:
        LDA $7C00,X
        BEQ BFX_CLOCK_OK
        CMP #' '
        BNE BFX_CLOCK_BAD
        INX
        BRA BFX_CLOCK_TAIL
BFX_CLOCK_OK: SEC
        RTS
BFX_CLOCK_BAD: CLC
        RTS
BFX_CLOCK_WORD DB "CLOCK"
