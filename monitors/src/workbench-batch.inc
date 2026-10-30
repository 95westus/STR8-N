; WB2's first BATCH increment: bounded returning module commands only.
; Queue text never becomes console input. No loaders, jumps, Q, nested BATCH,
; Store/confirmation, PREP or application handoff in this initial allowlist.
WB_BATCH:
        LDA W_BATCH_ACTIVE
        BNE WB_BAD
        JSR W_SKIP
        LDY #0
WB_CAPTURE:
        LDA W_LINE,X
        BEQ WB_CAPTURE_END
        CPY #34
        BCS WB_BAD
        STA W_BATCH_QUEUE,Y
        INX
        INY
        BRA WB_CAPTURE
WB_CAPTURE_END:
        CPY #0
        BEQ WB_BAD
        STY W_BATCH_SIZE
        LDA #0
        STA W_BATCH_QUEUE,Y
        ; Reject every empty segment before executing the first command.
        LDX #0
        LDY #0
WB_SEPARATOR_CHECK:
        LDA W_BATCH_QUEUE,X
        CMP #';'
        BEQ WB_SEPARATOR
        CMP #' '
        BEQ WB_SEPARATOR_NEXT
        INY
        BRA WB_SEPARATOR_NEXT
WB_SEPARATOR:
        CPY #0
        BEQ WB_BAD
        LDY #0
WB_SEPARATOR_NEXT:
        INX
        CPX W_BATCH_SIZE
        BCC WB_SEPARATOR_CHECK
        CPY #0
        BEQ WB_BAD
        ; Check the complete command allowlist before any bank/policy change.
        STZ W_BATCH_POS
WB_VALIDATE:
        JSR WB_SEGMENT
        JSR WB_ALLOWED
        BCC WB_BAD
        LDA W_BATCH_POS
        CMP W_BATCH_SIZE
        BCC WB_VALIDATE
        STZ W_BATCH_POS
        LDA #1
        STA W_BATCH_ACTIVE
WB_RUN:
        JSR W_CANCEL
        BCS WB_CANCEL
        JSR WB_SEGMENT
        LDA W_BANK
        LDX #<W_LINE
        LDY #>W_LINE
        JSR W_DISPATCH
        BCC WB_STOP
        LDA W_RESULT
        BNE WB_STOP
        LDA W_BATCH_POS
        CMP W_BATCH_SIZE
        BCC WB_RUN
        STZ W_BATCH_ACTIVE
        LDX #<WB_DONE_TEXT
        LDY #>WB_DONE_TEXT
        JMP W_MESSAGE
WB_CANCEL:
        LDA #WB_CANCELED
        STA W_RESULT
WB_STOP:
        STZ W_BATCH_ACTIVE
        LDX #<WB_STOP_TEXT
        LDY #>WB_STOP_TEXT
        JSR W_PUTS
        LDA W_RESULT
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        JMP W_HANDLED
WB_BAD:
        STZ W_BATCH_ACTIVE
        LDA #WB_SYNTAX
        STA W_RESULT
        LDX #<WB_BAD_TEXT
        LDY #>WB_BAD_TEXT
        JMP W_MESSAGE

; Copy one bounded segment from the separate queue into the command buffer.
; POS is the next queue character, or SIZE once the last segment is copied.
WB_SEGMENT:
        LDX W_BATCH_POS
        LDY #0
WB_SEGMENT_BYTE:
        CPX W_BATCH_SIZE
        BCS WB_SEGMENT_END
        LDA W_BATCH_QUEUE,X
        INX
        CMP #';'
        BEQ WB_SEGMENT_END
        STA W_LINE,Y
        INY
        BRA WB_SEGMENT_BYTE
WB_SEGMENT_END:
        STX W_BATCH_POS
        LDA #0
        STA W_LINE,Y
        RTS

; Module commands with bounded return and no subprompt/handoff. Full command
; argument validation remains in the ordinary dispatcher, which sets RESULT.
WB_ALLOWED:
        JSR W_ALIASES
        LDX #<W_VERSION_WORD
        LDY #>W_VERSION_WORD
        JSR W_MATCH
        BCS WB_EXACT_ARGS
        LDX #<WC_TIME_WORD
        LDY #>WC_TIME_WORD
        JSR W_MATCH
        BCS WB_EXACT_ARGS
        LDX #0
        JSR W_SKIP
        CMP #'?'
        BEQ WB_EXACT
        CMP #'V'
        BEQ WB_EXACT
        CMP #'B'
        BEQ WB_SHORT
        CMP #'T'
        BEQ WB_SHORT
        LDX #<WS_HELP_WORD
        LDY #>WS_HELP_WORD
        JSR W_MATCH
        BCS WB_EXACT_ARGS
        LDX #<W_EDU_WORD
        LDY #>W_EDU_WORD
        JSR W_MATCH
        BCS WB_ALLOW
        LDX #<W_SRAM_WORD
        LDY #>W_SRAM_WORD
        JSR W_MATCH
        BCS WB_EXACT_ARGS
        LDX #<W_WORK_WORD
        LDY #>W_WORK_WORD
        JSR W_MATCH
        BCS WB_EXACT_ARGS
        CLC
        RTS
WB_SHORT:
        LDA W_LINE+1,X
        BEQ WB_ALLOW
        CMP #' '
        BEQ WB_ALLOW
        CMP #'0'
        BCC WB_DENY
        CMP #'4'
        BCC WB_ALLOW
WB_DENY:
        CLC
        RTS
WB_EXACT:
        INX
WB_EXACT_ARGS:
        JMP W_END_ARGS
WB_ALLOW:
        SEC
        RTS

WB_WORD: DB "BATCH",0
WB_DONE_TEXT: DB "BATCH done",13,10,0
WB_STOP_TEXT: DB "BATCH stopped; result $",0
WB_BAD_TEXT: DB "BATCH refused: empty/long list or unsupported command",13,10,0
