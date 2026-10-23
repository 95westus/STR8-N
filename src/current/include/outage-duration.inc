; Yearless PF pair at OF_PTR. D_YEAR anchors the up event's assumed year.
; D_VALID is zero when no trustworthy calendar/capture year is available.
; Results are estimated days/hours/minutes; no seconds or lifetime claim.
D_CALC:
        LDA D_VALID
                        BNE D35_LONG_5
                        JMP D_BAD
D35_LONG_5:
        JSR OF_DECODE
                        BCS D35_LONG_7
                        JMP D_BAD
D35_LONG_7:
        LDA OF_MINUTE
        STA D_MIN
        LDA OF_HOUR
        STA D_HOUR
        LDA OF_DAY
        STA D_DAY
        LDA OF_MONTH
        STA D_MONTH
        CLC
        LDA OF_PTR
        ADC #4
        STA OF_PTR
                        BCC D_PTR_OK
        INC OF_PTR+1
D_PTR_OK:
        JSR OF_DECODE
                        BCS D35_LONG_24
                        JMP D_BAD
D35_LONG_24:
        LDA OF_MONTH
        CMP #2
                        BNE D_YEAR_START
        LDA OF_DAY
        CMP #29
                        BNE D_YEAR_START
        LDA D_YEAR
        AND #3
                        BEQ D35_LONG_33
                        JMP D_BAD
D35_LONG_33:
D_YEAR_START:
        LDA D_MONTH
        CMP OF_MONTH
                        BCC D_SOURCE_CHECK
                        BNE D_PREVIOUS_YEAR
        LDA D_DAY
        CMP OF_DAY
                        BCC D_SOURCE_CHECK
                        BEQ D_SOURCE_CHECK
D_PREVIOUS_YEAR:
        DEC D_YEAR
D_SOURCE_CHECK:
        LDA D_MONTH
        CMP #2
                        BNE D_COUNT
        LDA D_DAY
        CMP #29
                        BNE D_COUNT
        LDA D_YEAR
        AND #3
                        BEQ D35_LONG_54
                        JMP D_BAD
D35_LONG_54:
D_COUNT:
        STZ D_DAYS
        STZ D_DAYS+1
D_DAY_LOOP:
        LDA D_MONTH
        CMP OF_MONTH
                        BNE D_ADVANCE
        LDA D_DAY
        CMP OF_DAY
                        BEQ D_CLOCK
D_ADVANCE:
        INC D_DAYS
                        BNE D_LIMIT
        INC D_DAYS+1
D_LIMIT:
        LDA D_DAYS+1
                        BEQ D_NEXT_DAY
        LDA D_DAYS
        CMP #111
                        BCS D_BAD
D_NEXT_DAY:
        LDX D_MONTH
        DEX
        LDA OF_MONTH_DAYS,X
        CPX #1
                        BNE D_MONTH_LENGTH
        LDA D_YEAR
        AND #3
                        BEQ D_LEAP
        LDA #28
                        JMP D_MONTH_LENGTH
D_LEAP:
        LDA #29
D_MONTH_LENGTH:
        CMP D_DAY
                        BNE D_INCREMENT_DAY
        LDA #1
        STA D_DAY
        INC D_MONTH
        LDA D_MONTH
        CMP #13
                        BNE D_DAY_LOOP
        LDA #1
        STA D_MONTH
        INC D_YEAR
                        JMP D_DAY_LOOP
D_INCREMENT_DAY:
        INC D_DAY
                        JMP D_DAY_LOOP
D_CLOCK:
        SEC
        LDA OF_MINUTE
        SBC D_MIN
                        BCS D_MIN_READY
        ADC #60
        CLC
D_MIN_READY:
        STA D_MIN
        LDA OF_HOUR
        SBC D_HOUR
                        BCS D_HOUR_READY
        ADC #24
        PHA
        LDA D_DAYS
        ORA D_DAYS+1
                        BEQ D_NEGATIVE
        LDA D_DAYS
                        BNE D_DEC_DAY
        DEC D_DAYS+1
D_DEC_DAY:
        DEC D_DAYS
        PLA
D_HOUR_READY:
        STA D_HOUR
        SEC
        RTS
D_NEGATIVE:
        PLA
D_BAD:
        CLC
        RTS
D_PRINT:
        JSR NL
        LDX #<D_TEXT
        LDY #>D_TEXT
        LDA D_KIND
                        BEQ D_LABEL
        LDX #<D_ON_TEXT
        LDY #>D_ON_TEXT
D_LABEL:
        JSR PRINT
        JSR D_CALC
                        BCC D_UNKNOWN
D_VALUE:
        STZ D_HUNDREDS
D_DIV100:
        LDA D_DAYS+1
                        BNE D_SUB100
        LDA D_DAYS
        CMP #100
                        BCC D_DIGITS
D_SUB100:
        SEC
        LDA D_DAYS
        SBC #100
        STA D_DAYS
        LDA D_DAYS+1
        SBC #0
        STA D_DAYS+1
        INC D_HUNDREDS
                        JMP D_DIV100
D_DIGITS:
        LDA D_HUNDREDS
        CLC
        ADC #'0'
        JSR PUTC
        LDA D_DAYS
        JSR DECIMAL_2
        LDA #'d'
        JSR PUTC
        LDA #' '
        JSR PUTC
        LDA D_HOUR
        JSR DECIMAL_2
        LDA #':'
        JSR PUTC
        LDA D_MIN
        JSR DECIMAL_2
        LDX #<D_UNITS
        LDY #>D_UNITS
        JMP PRINT
D_UNKNOWN:
        LDX #<D_UNKNOWN_TEXT
        LDY #>D_UNKNOWN_TEXT
        JMP PRINT
D_TEXT DB "Outage: ~",0
D_ON_TEXT DB "On: ~",0
D_UNITS DB " (min)",0
D_UNKNOWN_TEXT DB "unknown",0
