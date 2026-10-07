; Shared, yearless outage decoder/formatter. OF_PTR points to MIN,HOUR,DATE,MTH.
; Caller provides PRINT, DECIMAL_2, PUTC and eight OF_* scratch bytes.
OF_FORMAT:
        JSR OF_DECODE
        BCC OF_BAD_FIELDS
        LDA OF_MONTH
        JSR DECIMAL_2
        LDA #'-'
        JSR PUTC
        LDA OF_DAY
        JSR DECIMAL_2
        LDA #' '
        JSR PUTC
        LDA OF_HOUR
        JSR DECIMAL_2
        LDA #':'
        JSR PUTC
        LDA OF_MINUTE
        JMP DECIMAL_2
OF_BAD_FIELDS:
        LDX #<OF_BAD_TEXT
        LDY #>OF_BAD_TEXT
        JMP PRINT
OF_DECODE:
        LDY #0
        LDA (OF_PTR),Y
        AND #$7F
        JSR OF_BCD
        BCC OF_INVALID
        CMP #60
        BCS OF_INVALID
        STA OF_MINUTE
        LDY #1
        LDA (OF_PTR),Y
        STA OF_RAW_HOUR
        AND #$40
        BEQ OF_HOUR_24
        LDA OF_RAW_HOUR
        AND #$1F
        JSR OF_BCD
        BCC OF_INVALID
        CMP #1
        BCC OF_INVALID
        CMP #13
        BCS OF_INVALID
        CMP #12
        BNE OF_AM_PM
        LDA #0
OF_AM_PM:
        STA OF_HOUR
        LDA OF_RAW_HOUR
        AND #$20
        BEQ OF_DATE
        LDA OF_HOUR
        CLC
        ADC #12
        STA OF_HOUR
        BRA OF_DATE
OF_HOUR_24:
        LDA OF_RAW_HOUR
        AND #$3F
        JSR OF_BCD
        BCC OF_INVALID
        CMP #24
        BCS OF_INVALID
        STA OF_HOUR
OF_DATE:
        LDY #3
        LDA (OF_PTR),Y
        AND #$1F
        JSR OF_BCD
        BCC OF_INVALID
        CMP #1
        BCC OF_INVALID
        CMP #13
        BCS OF_INVALID
        STA OF_MONTH
        TAX
        DEX
        LDA OF_MONTH_DAYS,X
        STA OF_MAX_DAY
        LDY #2
        LDA (OF_PTR),Y
        AND #$3F
        JSR OF_BCD
        BCC OF_INVALID
        CMP #1
        BCC OF_INVALID
        CMP OF_MAX_DAY
        BEQ OF_DAY_OK
        BCS OF_INVALID
OF_DAY_OK:
        STA OF_DAY
        SEC
        RTS
OF_INVALID:
        CLC
        RTS
OF_BCD:
        STA OF_TEMP
        AND #$0F
        CMP #10
        BCS OF_INVALID
        STA OF_UNITS
        LDA OF_TEMP
        LSR A
        LSR A
        LSR A
        LSR A
        CMP #10
        BCS OF_INVALID
        STA OF_TEMP
        ASL A
        ASL A
        CLC
        ADC OF_TEMP
        ASL A
        CLC
        ADC OF_UNITS
        SEC
        RTS
OF_MONTH_DAYS DB 31,29,31,30,31,30,31,31,30,31,30,31
OF_BAD_TEXT DB "invalid fields",0
