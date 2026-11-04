; Reserved native names are independent of selected owner bank/PROGRAM mount.
W_NATIVE_RESTORE:
        LDX #<WC_WORD
        LDY #>WC_WORD
        JSR W_R_MATCH
        BCS WC_COMMAND
        LDX #<WC_FLASH_WORD
        LDY #>WC_FLASH_WORD
        JSR W_R_MATCH
        BCS WC_FLASH
        LDX #<WC_MAINT_WORD
        LDY #>WC_MAINT_WORD
        JSR W_R_MATCH
        BCS WC_MAINT_APP
        LDX #<W_SRAM_WORD
        LDY #>W_SRAM_WORD
        JSR W_R_MATCH
        BCS WN_SRAM
        LDX #<W_WORK_WORD
        LDY #>W_WORK_WORD
        JSR W_R_MATCH
        BCS WN_WORK
        LDX #<W_EDU_WORD
        LDY #>W_EDU_WORD
        JSR W_R_MATCH
        BCS WN_EDU
        LDX #0
        RTS
; A reserved name never falls through to stored-program lookup or E dispatch.
; Print syntax errors locally; preserve the result byte so BATCH stops.
WN_SRAM:
        LDA #3
        BRA WN_STORAGE
WN_WORK:
        LDA #4
WN_STORAGE:
        PHA
        JSR W_END_ARGS
        PLA
        BCC WN_QUERY_RETURN
        JMP W_NATIVE
WN_EDU:
        JSR W_EDU_CMD
WN_QUERY_RETURN:
        BCS WN_QUERY_OK
        LDA #WB_SYNTAX
        STA W_RESULT
        LDX #<W_SYNTAX_TEXT
        LDY #>W_SYNTAX_TEXT
        JSR W_PUTS
WN_QUERY_OK:
        SEC
        RTS
; Match after R, accepting its normal spaces, and reuse the command names.
W_R_MATCH:
        STX W_PTR
        STY W_PTR+1
        LDX #1
        JSR W_SKIP
        LDY #0
        JMP W_MATCH_BYTE
W_NATIVE_CLOCK:
        LDA #0
        BRA W_NATIVE
W_NATIVE_BOARD:
        LDA #1
        BRA W_NATIVE
W_NATIVE_MAINT:
        LDA #2
W_NATIVE:
        STA $6639
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE WN_NO_BATCH
        JSR WB_SAVE
        LDA BQ_PROVIDER
        STA BQ_PARENT
        CLC
        LDA $6639
        ADC #2
        STA BQ_PROVIDER
WN_NO_BATCH:
        LDA W_BANK
        STA MU_BANK
        LDA #3
        JSR WB_F_SELECT
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE WN_COPY_START
        LDX #3
WN_BATCH_CAP:
        LDA $8C0B,X
        CMP WN_BATCH_ID,X
        BNE WN_REFUSED
        DEX
        BPL WN_BATCH_CAP
WN_COPY_START:
        LDX #0
WN_COPY:
        LDA $8C00,X
        STA $7000,X
        LDA $8D00,X
        STA $7100,X
        LDA $8E00,X
        STA $7200,X
        LDA $8F00,X
        STA $7300,X
        INX
        BNE WN_COPY
        JSR W_CRC_START
        STZ W_PTR
        LDA #$70
        STA W_PTR+1
        LDX #4
        LDY #0
WN_CRC:
        LDA (W_PTR),Y
        JSR W_CRC_BYTE
        INY
        BNE WN_CRC
        INC W_PTR+1
        DEX
        BNE WN_CRC
        LDA W_CRC
        ORA W_CRC+1
        BNE WN_REFUSED
        LDX #7
WN_ID:
        LDA $7000,X
        CMP WN_MAGIC,X
        BNE WN_REFUSED
        DEX
        BPL WN_ID
WN_ENTER:
        LDA $6639
        JMP $7008
WN_REFUSED:
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE WN_ERROR
        LDA BQ_PARENT
        STA BQ_PROVIDER
WN_ERROR:
        LDA #WB_REFUSED
        STA W_RESULT
        LDX #<WN_BAD_TEXT
        LDY #>WN_BAD_TEXT
        JMP W_MESSAGE
WN_BATCH_ID: DB "NB",1,2
WN_MAGIC: DB "NL",1,5,"PR05"
WN_BAD_TEXT: DB "REFUSED: native loader",13,10,0
