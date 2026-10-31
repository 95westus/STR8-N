W_PROGRAM_ARGUMENT:
        PHX
        INX
        JSR W_SKIP
        CMP #'P'
        BNE WP_ARG_NO
        INX
        LDA W_LINE,X
        BEQ WP_ARG_YES
        CMP #' '
        BNE WP_ARG_NO
WP_ARG_YES:
        PLA
        SEC
        RTS
WP_ARG_NO:
        PLX
        CLC
        RTS
WP_CHECK:
        PHX
        PHY
        LDX #7
WP_MAGIC_LOOP:
        LDA SP_BASE,X
        CMP WP_MAGIC,X
        BNE WP_CHECK_BAD
        DEX
        BPL WP_MAGIC_LOOP
        LDX #3
WP_CAP_LOOP:
        LDA SP_BASE+17,X
        CMP WP_CAP,X
        BNE WP_CHECK_BAD
        DEX
        BPL WP_CAP_LOOP
        JSR W_CRC_START
        STZ W_PTR
        LDA #>SP_BASE
        STA W_PTR+1
        LDX #13
        LDY #0
WP_CRC_LOOP:
        LDA (W_PTR),Y
        JSR W_CRC_BYTE
        INY
        BNE WP_CRC_LOOP
        INC W_PTR+1
        DEX
        BNE WP_CRC_LOOP
        LDA W_CRC
        ORA W_CRC+1
        BNE WP_CHECK_BAD
        SEC
        BRA WP_CHECK_END
WP_CHECK_BAD:
        CLC
WP_CHECK_END:
        PLY
        PLX
        RTS
WP_INIT_REQUEST:
        PHA
        LDY #31
        LDA #0
WP_REQ_CLEAR:
        STA REQUEST,Y
        DEY
        BPL WP_REQ_CLEAR
        PLA
        STA REQUEST
        LDY #15
WP_REQ_NAME:
        LDA W_NAME,Y
        STA REQUEST+8,Y
        DEY
        BPL WP_REQ_NAME
        RTS
WP_REQUEST:
        JSR WP_INIT_REQUEST
WP_CALL:
        JSR WP_CHECK
        BCC WP_CALL_BAD
        LDA #<REQUEST
        LDX #>REQUEST
        JMP SP_API_ENTRY
WP_CALL_BAD:
        LDA #$81
        CLC
        RTS
WP_LOOKUP:
        LDA #4
        JMP WP_REQUEST
WP_RESTORE:
        LDA #7
        LDX W_ONLY
        BEQ WP_RESTORE_OP
        LDA #6
WP_RESTORE_OP:
        JSR WP_INIT_REQUEST
        LDA #MU_BYPASS
        JSR W_UI_CHECK
        BCS WP_RETURN_READY
        LDA #<STR8V2_RAM_HOLD
        STA W_UI_TARGET
        LDA #>STR8V2_RAM_HOLD
        STA W_UI_TARGET+1
WP_RETURN_READY:
        LDA W_UI_TARGET
        STA REQUEST+26
        LDA W_UI_TARGET+1
        STA REQUEST+27
        LDA W_BANK
        STA REQUEST+28
        LDA W_RAM_FLOOR
        STA REQUEST+29
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE WP_LOAD
        JSR WB_SAVE
WP_LOAD:
        JSR WP_CALL
        BCC WP_ERROR
        LDX #<WP_LOADED_TEXT
        LDY #>WP_LOADED_TEXT
        JSR W_PUTS
        LDA W_ONLY
        BNE W_HANDLED
WP_RUN:
        LDA ENTRY
        STA W_F_VECTOR
        LDA ENTRY+1
        STA W_F_VECTOR+1
        LDA W_BANK
        STA W_F_SELECTED
        JMP WB_F_EXECUTE
WP_TABLE_CMD:
        JSR W_END_ARGS
        BCC W_UNHANDLED
WP_TABLE:
        LDA #0
        JSR WP_REQUEST
        BCC WP_ERROR
        LDX #<WP_TABLE_TEXT
        LDY #>WP_TABLE_TEXT
        JSR W_PUTS
        STZ W_IX
WP_TABLE_ROW:
        JSR W_CANCEL
        BCS W_CANCELED
        LDA W_IX
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA W_COPY
        LDA #>DIR
        STA W_COPY+1
        LDY #3
        LDA (W_COPY),Y
        CMP #$A5
        BNE WP_TABLE_NEXT
        LDY #7
WP_TABLE_FIELDS:
        LDA (W_COPY),Y
        STA W_HEADER,Y
        DEY
        CPY #3
        BNE WP_TABLE_FIELDS
        LDY #31
        LDX #23
WP_TABLE_NAME:
        LDA (W_COPY),Y
        STA W_HEADER,X
        DEX
        DEY
        CPY #15
        BNE WP_TABLE_NAME
        LDY #10
        LDA (W_COPY),Y
        STA W_STORE_NEXT
        INY
        LDA (W_COPY),Y
        STA W_STORE_NEXT+1
        LDY #15
        LDA (W_COPY),Y
        PHA
        LDA #'P'
        JSR STR8V2_RAM_PUTC
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA W_IX
        JSR STR8V2_RAM_HEX_OUT
        LDA #'/'
        JSR STR8V2_RAM_PUTC
        PLA
        JSR STR8V2_RAM_HEX_OUT
        LDA #$3F
        STA W_HEADER+3
        LDA #'#'
        JSR STR8V2_RAM_PUTC
        LDA W_STORE_NEXT+1
        JSR STR8V2_RAM_HEX_OUT
        LDA W_STORE_NEXT
        JSR STR8V2_RAM_HEX_OUT
        JSR W_SHOW_FIELDS
WP_TABLE_NEXT:
        INC W_IX
        LDA W_IX
        CMP #8
        BCC WP_TABLE_ROW
        JMP W_HANDLED
WP_STORE:
        LDA #1
        STA WP_MODE
        STZ W_STORE_FIRST
        STZ W_STORE_FIRST+1
        JSR W_SKIP
        CMP #'A'
        BNE WP_STORE_ADDRESS
        LDA W_LINE+1,X
        CMP #'U'
        BNE WP_STORE_ADDRESS
        LDY #0
WP_STORE_AUTO:
        LDA W_LINE,X
        CMP WS_AUTO_WORD,Y
        BNE W_UNHANDLED
        INX
        INY
        CPY #4
        BCC WP_STORE_AUTO
        LDA W_LINE,X
        CMP #' '
        BNE W_UNHANDLED
        JMP WS_FIRST_OK
WP_STORE_ADDRESS:
        JSR W_HEX_WORD
        BCC W_UNHANDLED
        LDA W_VALUE
        BNE W_RANGE
        LDA W_VALUE+1
        CMP #8
        BCC W_RANGE
        STA W_STORE_FIRST+1
        JMP WS_FIRST_OK
WP_STORE_READY:
        LDY #15
WP_STORE_NAME:
        LDA W_HEADER+8,Y
        STA W_NAME,Y
        DEY
        BPL WP_STORE_NAME
        LDA #5
        JSR WP_INIT_REQUEST
        LDA W_STORE_FIRST
        STA REQUEST+24
        LDA W_STORE_FIRST+1
        STA REQUEST+25
        LDY #1
WP_STORE_SOURCE:
        LDA W_HEADER+4,Y
        STA REQUEST+2,Y
        STA REQUEST+6,Y
        DEY
        BPL WP_STORE_SOURCE
        CLC
        LDA W_HEADER+4
        ADC W_HEADER+6
        STA REQUEST+4
        LDA W_HEADER+5
        ADC W_HEADER+7
        STA REQUEST+5
        LDA REQUEST+4
        BNE WP_STORE_END_LOW
        DEC REQUEST+5
WP_STORE_END_LOW:
        DEC REQUEST+4
        JSR WP_CALL
        BCC WP_ERROR
        STZ W_STORE_FIRST
        LDA FIRST_PAGE
        STA W_STORE_FIRST+1
        LDX #<WP_TARGET_TEXT
        LDY #>WP_TARGET_TEXT
        JSR W_PUTS
        LDA FIRST_PAGE
        JSR STR8V2_RAM_HEX_OUT
        LDA #0
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        JMP WS_CONFIRM_DIALOG
WP_STORE_COMMIT:
        LDA #1
        STA REQUEST
        STZ REQUEST+24
        LDA W_STORE_FIRST+1
        STA REQUEST+25
        JSR WP_CALL
        BCS WP_STORE_OK
        PHA
        LDA #WB_PARTIAL
        STA W_RESULT
        PLA
        JMP WP_REPORT
WP_STORE_OK:
        LDX #<WP_STORED_TEXT
        LDY #>WP_STORED_TEXT
        JMP W_MESSAGE
WP_CAP: DB "SW",1,1
WP_MAGIC: DB "SP",1,13,"PR05"
WP_TARGET_TEXT: DB "Target PROGRAM $",0
WP_TABLE_TEXT: DB "P:slot/kind#seq (01=data,02=delete)",13,10,0
WP_LOADED_TEXT: DB "Loaded PROGRAM; payload CRC verified",13,10,0
WP_STORED_TEXT: DB "Stored PROGRAM; CRC verified; commit last",13,10,0
