; Private SRAM/WORK command reader. Confirmations keep their live readers.
; Both line buffers use SW_LINE, outside the persistent6AD0-6AFF queue.
; Provider5=SRAM,6=WORK. Q restores the caller and resumes its next command.
SW_BATCH_LIMIT EQU $5B3E
B29_LINE_2:
        LDA #5
        LDX #39
        BRA SB_LINE
B29_LINE_3:
        LDA #6
        LDX #15
SB_LINE:
        STA SW_MODE
        STX SW_BATCH_LIMIT
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE SB_LIVE
        LDA BQ_PROVIDER
        CMP SW_MODE
        BNE SB_BAD
        LDA BQ_ERROR
        BNE SB_STOP
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS SB_CANCEL
        LDA BQ_SIZE
        BEQ SB_BAD
        CMP #35
        BCS SB_BAD
        LDX BQ_POS
        CPX BQ_SIZE
        BEQ SB_DONE
        BCS SB_BAD
        LDY #0
SB_COPY:
        CPX BQ_SIZE
        BCS SB_END
        LDA BQ_QUEUE,X
        INX
        CMP #';'
        BEQ SB_END
        CPY SW_BATCH_LIMIT
        BCS SB_BAD
        STA SW_LINE,Y
        JSR STR8V2_RAM_PUTC
        INY
        BRA SB_COPY
SB_END:
        STX BQ_POS
        LDA #0
        STA SW_LINE,Y
        STY SM_D_LINE_LENGTH
        STY WK_LINE_N
        JSR STR8V2_RAM_NEWLINE
        ; The control menu changes routes and unlock state; keep it live.
        LDA SW_LINE
        CMP #'!'
        BEQ SB_BAD
        SEC
        RTS
SB_CANCEL:
        LDA #3
        BRA SB_ERROR
SB_BAD:
        LDA #2
SB_ERROR:
        STA BQ_ERROR
SB_STOP:
        LDX #<SB_STOP_TEXT
        LDY #>SB_STOP_TEXT
        BRA SB_FINISH
SB_DONE:
        LDX #<SB_DONE_TEXT
        LDY #>SB_DONE_TEXT
SB_FINISH:
        STZ BQ_MAGIC
        JSR SW_PRINT
        ; Return to the actual manager prompt before reading live input.
        CLC
        RTS
SB_LIVE:
        LDA SW_MODE
        CMP #5
        BNE SB_WORK_LIVE
        JMP SM_C_READLINE
SB_WORK_LIVE:
        JMP WK_LINE_READ
B29_ERROR_HOOK:
        PHP
        PHA
        LDA #2
        BRA SB_HOOK
B29_CANCEL_HOOK:
        PHP
        PHA
        LDA #3
SB_HOOK:
        STA SW_ERROR
        PHX
        LDX BQ_MAGIC
        CPX #BQ_ON
        BNE SB_HOOK_END
        STA BQ_ERROR
SB_HOOK_END:
        PLX
        PLA
        PLP
        RTS
SB_DONE_TEXT: DB "BATCH done",13,10,0
SB_STOP_TEXT: DB "BATCH stopped",13,10,0
