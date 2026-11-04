; 34-byte queue; utility menu commands are consumed only at command prompts.
; Confirmations stay live console input. Raw G/L/reset and unregistered apps
; are not batch operations. Provider0=MON,1=WB,2=CLOCK,3=FLASH,4=registered app.
WB_BATCH:
        JSR W_SKIP
        BNE WB_NEW
        LDA BQ_MAGIC
        CMP #BQ_ON
        BEQ WB_RUN
        JMP WB_BAD
WB_NEW:
        LDA BQ_MAGIC
        CMP #BQ_ON
        BEQ WB_BAD
        LDY #0
WB_CAPTURE:
        LDA W_LINE,X
        BEQ WB_CAPTURE_END
        CPY #34
        BCS WB_BAD
        STA BQ_QUEUE,Y
        INX
        INY
        BRA WB_CAPTURE
WB_CAPTURE_END:
        CPY #0
        BEQ WB_BAD
        STY BQ_SIZE
        LDA #0
        STA BQ_QUEUE,Y
        LDX #0
        LDY #0
WB_SEPARATOR_CHECK:
        LDA BQ_QUEUE,X
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
        CPX BQ_SIZE
        BCC WB_SEPARATOR_CHECK
        CPY #0
        BEQ WB_BAD
        STZ BQ_POS
        STZ BQ_ERROR
        LDA W_SHELL_ACTIVE
        STA BQ_PROVIDER
        JSR WB_SAVE
        LDA #BQ_ON
        STA BQ_MAGIC
WB_RUN:
        JSR WB_RESTORE
        LDA BQ_ERROR
        BNE WB_STOP
        JSR W_CANCEL
        BCS WB_CANCEL
        LDA BQ_POS
        CMP BQ_SIZE
        BCS WB_DONE
        JSR WB_SEGMENT
        JSR WB_EXECUTE
        BCC WB_EXEC_SYNTAX
        LDA W_RESULT
        STA BQ_ERROR
        BNE WB_STOP
        JSR WB_SAVE
        BRA WB_RUN
WB_EXEC_SYNTAX:
        LDA #WB_SYNTAX
        STA BQ_ERROR
        BRA WB_STOP
WB_CANCEL:
        LDA #WB_CANCELED
        STA BQ_ERROR
WB_STOP:
        STZ BQ_MAGIC
        LDX #<WB_STOP_TEXT
        LDY #>WB_STOP_TEXT
        JSR W_PUTS
        LDA BQ_ERROR
        STA W_RESULT
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        BRA WB_FINISH
WB_DONE:
        STZ BQ_MAGIC
        LDX #<WB_DONE_TEXT
        LDY #>WB_DONE_TEXT
        JSR W_PUTS
WB_FINISH:
        LDA BQ_PROVIDER
        BEQ WB_RETURN
        LDX #$FF
        TXS
        JMP W_PROMPT
WB_RETURN:
        JMP W_HANDLED
WB_BAD:
        STZ BQ_MAGIC
        LDA #WB_SYNTAX
        STA W_RESULT
        LDX #<WB_BAD_TEXT
        LDY #>WB_BAD_TEXT
        JMP W_MESSAGE
WB_SAVE:
        LDA W_BANK
        STA BQ_BANK
        LDA W_RAM_FLOOR
        STA BQ_FLOOR
        LDA W_EDU
        STA MU_EDU
        LDX #6
WB_SAVE_AREA:
        LDA W_AREA_ON,X
        STA BQ_AREA,X
        DEX
        BPL WB_SAVE_AREA
        RTS
WB_RESTORE:
        LDA BQ_PROVIDER
        STA W_SHELL_ACTIVE
        LDA BQ_BANK
        STA W_BANK
        LDA BQ_FLOOR
        STA W_RAM_FLOOR
        LDA MU_EDU
        STA W_EDU
        LDX #6
WB_RESTORE_AREA:
        LDA BQ_AREA,X
        STA W_AREA_ON,X
        DEX
        BPL WB_RESTORE_AREA
        RTS
WB_SEGMENT:
        LDX BQ_POS
        LDY #0
WB_SEGMENT_BYTE:
        CPX BQ_SIZE
        BCS WB_SEGMENT_END
        LDA BQ_QUEUE,X
        INX
        CMP #';'
        BEQ WB_SEGMENT_END
        STA W_LINE,Y
        INY
        BRA WB_SEGMENT_BYTE
WB_SEGMENT_END:
        STX BQ_POS
        LDA #0
        STA W_LINE,Y
        LDX #<W_LINE
        LDY #>W_LINE
        JSR W_PUTS
        JMP STR8V2_RAM_NEWLINE
WB_EXECUTE:
        LDX #<WB_WORD
        LDY #>WB_WORD
        JSR W_MATCH
        BCS WB_DENY
        LDX #<WB_Q_WORD
        LDY #>WB_Q_WORD
        JSR W_MATCH
        BCC WB_DISPATCH
        JSR W_END_ARGS
        BCC WB_DENY
        LDA BQ_PROVIDER
        BEQ WB_DENY
        STZ BQ_PROVIDER
        STZ W_RESULT
        SEC
        RTS
WB_DISPATCH:
        LDX #0
        JSR W_SKIP
        CMP #'D'
        BEQ WB_MON
        CMP #'M'
        BNE WB_MODULE
        INX
        JSR W_SKIP
        CMP #'0'
        BCC WB_MODULE
        CMP #'F'+1
        BCS WB_MODULE
WB_MON:
        LDY #40
WB_MON_COPY:
        LDA W_LINE,Y
        STA MU_LINE,Y
        DEY
        BPL WB_MON_COPY
        LDA #MU_COMMAND
        JSR W_UI_CHECK
        BCC WB_DENY
        LDA W_BANK
        JSR W_UI_JUMP
        STA W_RESULT
        LDA MU_BANK
        STA W_BANK
        SEC
        RTS
WB_MODULE:
        LDA W_BANK
        LDX #<W_LINE
        LDY #>W_LINE
        JSR W_DISPATCH
        BCS WB_EXECUTED
        LDX #3
WB_SERVICE_CAP:
        LDA $E00B,X
        CMP WB_SERVICE_ID,X
        BNE WB_DENY
        DEX
        BPL WB_SERVICE_CAP
        STZ W_RESULT
        LDA BQ_FLOOR
        STA $69FF
        LDA W_BANK
        LDX #<W_LINE
        LDY #>W_LINE
        JSR $E008
        STA W_BANK
WB_EXECUTED:
        RTS
WB_DENY:
        CLC
        RTS
WB_SERVICE_ID: DB "SB",1,1
WB_WORD: DB "BATCH",0
WB_Q_WORD: DB "Q",0
WB_DONE_TEXT: DB "BATCH done",13,10,0
WB_STOP_TEXT: DB "BATCH stopped; result $",0
WB_BAD_TEXT: DB "BATCH refused: empty/long/nested",13,10,0
