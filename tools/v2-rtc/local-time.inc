; Read-only fixed-offset display. UTC snapshots and hardware remain unchanged.
; TZ records share the append-only identity tail; EI records are ignored.
TZ_PTR EQU $D6
TZ_READ:
        STZ TZ_OFFSET
        STZ TZ_OFFSET+1
        STZ TZ_FOUND
        STZ TZ_FREE+1
        LDX #3
TZ_ZERO_SEQ:
        STZ TZ_SEQ,X
        DEX
        BPL TZ_ZERO_SEQ
        LDA $7FEC
        PHA
        AND #$11
        ORA #$EE
        STA $7FEC
        STZ TZ_PTR
        LDA #$9C
        STA TZ_PTR+1
TZ_SCAN:
        LDY #0
TZ_BLANK:
        LDA (TZ_PTR),Y
        CMP #$FF
        BNE TZ_CHECK
        INY
        CPY #32
        BNE TZ_BLANK
        LDA TZ_FREE+1
        BNE TZ_NEXT
        LDA TZ_PTR
        STA TZ_FREE
        LDA TZ_PTR+1
        STA TZ_FREE+1
        BRA TZ_NEXT
TZ_CHECK:
        LDY #31
        LDA (TZ_PTR),Y
        BNE TZ_NEXT
        LDY #3
TZ_HEADER_CHECK:
        LDA (TZ_PTR),Y
        CMP TZ_MAGIC,Y
        BNE TZ_NEXT
        DEY
        BPL TZ_HEADER_CHECK
        JSR TZ_CRC
        LDY #28
        LDA (TZ_PTR),Y
        CMP TZ_SUM
        BNE TZ_NEXT
        INY
        LDA (TZ_PTR),Y
        CMP TZ_SUM+1
        BNE TZ_NEXT
        LDY #8
        LDA (TZ_PTR),Y
        STA TZ_WORK
        INY
        LDA (TZ_PTR),Y
        STA TZ_WORK+1
        JSR TZ_RANGE
        BCC TZ_NEXT
        LDY #7
        LDX #3
TZ_NEWER:
        LDA (TZ_PTR),Y
        CMP TZ_SEQ,X
        BCC TZ_NEXT
        BNE TZ_KEEP
        DEY
        DEX
        BPL TZ_NEWER
TZ_KEEP:
        LDY #7
        LDX #3
TZ_KEEP_SEQ:
        LDA (TZ_PTR),Y
        STA TZ_SEQ,X
        DEY
        DEX
        BPL TZ_KEEP_SEQ
        LDY #8
        LDA (TZ_PTR),Y
        STA TZ_OFFSET
        INY
        LDA (TZ_PTR),Y
        STA TZ_OFFSET+1
        INC TZ_FOUND
TZ_NEXT:
        LDA TZ_PTR
        CLC
        ADC #32
        STA TZ_PTR
        BCC TZ_SCAN_PAGE
        INC TZ_PTR+1
TZ_SCAN_PAGE:
        LDA TZ_PTR+1
        CMP #$A0
        BNE TZ_SCAN
        PLA
        STA $7FEC
        RTS
TZ_CRC:
        LDA #$FF
        STA TZ_SUM
        STA TZ_SUM+1
        LDY #0
TZ_CRC_BYTE:
        LDA (TZ_PTR),Y
        EOR TZ_SUM+1
        STA TZ_SUM+1
        LDX #8
TZ_CRC_BIT:
        ASL TZ_SUM
        ROL TZ_SUM+1
        BCC TZ_CRC_NEXT
        LDA TZ_SUM
        EOR #$21
        STA TZ_SUM
        LDA TZ_SUM+1
        EOR #$10
        STA TZ_SUM+1
TZ_CRC_NEXT:
        DEX
        BNE TZ_CRC_BIT
        INY
        CPY #28
        BNE TZ_CRC_BYTE
        RTS
TZ_ABS:
        LDA TZ_WORK+1
        BPL TZ_ABS_DONE
        LDA #0
        SEC
        SBC TZ_WORK
        STA TZ_WORK
        LDA #0
        SBC TZ_WORK+1
        STA TZ_WORK+1
TZ_ABS_DONE:
        RTS
; Signed minute range -12:00 through +14:00, no wrapping malformed values.
TZ_RANGE:
        LDA TZ_WORK+1
        BMI TZ_RANGE_NEG
        CMP #3
        BCC TZ_RANGE_OK
        BNE TZ_RANGE_BAD
        LDA TZ_WORK
        CMP #$49
        BCC TZ_RANGE_OK
        BRA TZ_RANGE_BAD
TZ_RANGE_NEG:
        CMP #$FD
        BCC TZ_RANGE_BAD
        BNE TZ_RANGE_OK
        LDA TZ_WORK
        CMP #$30
        BCC TZ_RANGE_BAD
TZ_RANGE_OK:
        SEC
        RTS
TZ_RANGE_BAD:
        CLC
        RTS
TZ_OFFSET_TEXT:
        LDA TZ_OFFSET
        STA TZ_WORK
        LDA TZ_OFFSET+1
        STA TZ_WORK+1
        LDA #'+'
        BIT TZ_OFFSET+1
        BPL TZ_SIGN_READY
        LDA #'-'
TZ_SIGN_READY:
        JSR $7E6D
        JSR TZ_ABS
        STZ TZ_HOURS
TZ_HOUR_LOOP:
        LDA TZ_WORK+1
        BNE TZ_HOUR_SUB
        LDA TZ_WORK
        CMP #60
        BCC TZ_HOUR_DONE
TZ_HOUR_SUB:
        LDA TZ_WORK
        SEC
        SBC #60
        STA TZ_WORK
        LDA TZ_WORK+1
        SBC #0
        STA TZ_WORK+1
        INC TZ_HOURS
        BRA TZ_HOUR_LOOP
TZ_HOUR_DONE:
        LDA TZ_HOURS
        JSR TZ_DECIMAL
        LDA #':'
        JSR $7E6D
        LDA TZ_WORK
        JMP TZ_DECIMAL
TZ_SHOW_LOCAL:
        LDA $66C0
        BNE TZ_RENDER_DONE
        LDA $66C1
        AND #4
        BEQ TZ_RENDER_DONE
        JSR TZ_READ
        LDX #7
TZ_COPY_DATE:
        LDA $66C2,X
        STA TZ_DATE,X
        DEX
        BPL TZ_COPY_DATE
        LDA TZ_OFFSET
        STA TZ_WORK
        LDA TZ_OFFSET+1
        STA TZ_WORK+1
        JSR TZ_ABS
TZ_MINUTE_LOOP:
        LDA TZ_WORK
        ORA TZ_WORK+1
        BEQ TZ_RENDER
        LDA TZ_OFFSET+1
        BMI TZ_BACKWARD
        JSR TZ_FORWARD
        BRA TZ_COUNT_MINUTE
TZ_BACKWARD:
        JSR TZ_REVERSE
TZ_COUNT_MINUTE:
        LDA TZ_WORK
        BNE TZ_COUNT_LOW
        DEC TZ_WORK+1
TZ_COUNT_LOW:
        DEC TZ_WORK
        BRA TZ_MINUTE_LOOP
TZ_RENDER_DONE:
        RTS
TZ_FORWARD:
        INC TZ_DATE+6
        LDA TZ_DATE+6
        CMP #60
        BNE TZ_DATE_DONE
        STZ TZ_DATE+6
        INC TZ_DATE+5
        LDA TZ_DATE+5
        CMP #24
        BNE TZ_DATE_DONE
        STZ TZ_DATE+5
        INC TZ_DATE+4
        LDA TZ_DATE+4
        CMP #8
        BNE TZ_F_DAY
        LDA #1
        STA TZ_DATE+4
TZ_F_DAY:
        JSR TZ_MONTH_DAYS
        INC TZ_DATE+3
        CMP TZ_DATE+3
        BCS TZ_DATE_DONE
        LDA #1
        STA TZ_DATE+3
        INC TZ_DATE+2
        LDA TZ_DATE+2
        CMP #13
        BNE TZ_DATE_DONE
        LDA #1
        STA TZ_DATE+2
        INC TZ_DATE
        BNE TZ_DATE_DONE
        INC TZ_DATE+1
TZ_DATE_DONE:
        RTS
TZ_REVERSE:
        DEC TZ_DATE+6
        BPL TZ_DATE_DONE
        LDA #59
        STA TZ_DATE+6
        DEC TZ_DATE+5
        BPL TZ_DATE_DONE
        LDA #23
        STA TZ_DATE+5
        DEC TZ_DATE+4
        BNE TZ_R_DAY
        LDA #7
        STA TZ_DATE+4
TZ_R_DAY:
        DEC TZ_DATE+3
        BNE TZ_DATE_DONE
        DEC TZ_DATE+2
        BNE TZ_R_MONTH
        LDA #12
        STA TZ_DATE+2
        LDA TZ_DATE
        BNE TZ_R_YEAR_LOW
        DEC TZ_DATE+1
TZ_R_YEAR_LOW:
        DEC TZ_DATE
TZ_R_MONTH:
        JSR TZ_MONTH_DAYS
        STA TZ_DATE+3
        RTS
TZ_MONTH_DAYS:
        LDX TZ_DATE+2
        LDA TZ_MONTHS-1,X
        CPX #2
        BNE TZ_DAYS_DONE
        LDX TZ_DATE
        CPX #$34             ; 2100 is not a leap year.
        BEQ TZ_DAYS_DONE
        TXA
        AND #3
        BNE TZ_FEB_NORMAL
        LDA #29
        RTS
TZ_FEB_NORMAL:
        LDA #28
TZ_DAYS_DONE:
        RTS
TZ_RENDER:
        JSR $7E7F
        LDX #<TZ_LOCAL_TEXT
        LDY #>TZ_LOCAL_TEXT
        JSR TZ_PRINT
        LDA TZ_DATE+4
        DEC A
        ASL A
        ASL A
        TAY
        LDX #4
TZ_WEEKDAY_CHAR:
        LDA TZ_WEEKDAYS,Y
        JSR $7E6D
        INY
        DEX
        BNE TZ_WEEKDAY_CHAR
        LDA TZ_DATE
        CMP #$CF             ; 1999 / 2000..2099 / 2100
        BNE TZ_YEAR_20
        LDA #'1'
        JSR $7E6D
        LDA #'9'
        JSR $7E6D
        LDA #99
        BRA TZ_YEAR_LAST
TZ_YEAR_20:
        LDA #'2'
        JSR $7E6D
        LDA #'0'
        LDX TZ_DATE
        CPX #$34
        BNE TZ_YEAR_PREFIX
        INC A
TZ_YEAR_PREFIX:
        JSR $7E6D
        LDA TZ_DATE
        SEC
        SBC #$D0
        CMP #100
        BNE TZ_YEAR_LAST
        LDA #0
TZ_YEAR_LAST:
        JSR TZ_DECIMAL
        LDA #'-'
        JSR $7E6D
        LDA TZ_DATE+2
        JSR TZ_DECIMAL
        LDA #'-'
        JSR $7E6D
        LDA TZ_DATE+3
        JSR TZ_DECIMAL
        LDA #' '
        JSR $7E6D
        LDA TZ_DATE+5
        JSR TZ_DECIMAL
        LDA #':'
        JSR $7E6D
        LDA TZ_DATE+6
        JSR TZ_DECIMAL
        LDA #':'
        JSR $7E6D
        LDA TZ_DATE+7
        JSR TZ_DECIMAL
        LDA #' '
        JSR $7E6D
        LDA #'('
        JSR $7E6D
        JSR TZ_OFFSET_TEXT
        LDA #')'
        JMP $7E6D
TZ_DECIMAL:
        LDX #0
TZ_TENS:
        CMP #10
        BCC TZ_DIGITS
        SBC #10
        INX
        BRA TZ_TENS
TZ_DIGITS:
        PHA
        TXA
        ORA #'0'
        JSR $7E6D
        PLA
        ORA #'0'
        JMP $7E6D
TZ_PRINT:
        STX TZ_PTR
        STY TZ_PTR+1
        LDY #0
TZ_PRINT_NEXT:
        LDA (TZ_PTR),Y
        BEQ TZ_PRINT_DONE
        JSR $7E6D
        INY
        BNE TZ_PRINT_NEXT
TZ_PRINT_DONE:
        RTS
TZ_MAGIC DB "TZ",1,0
TZ_LOCAL_TEXT DB "RTCC: Local ",0
TZ_WEEKDAYS DB "Mon Tue Wed Thu Fri Sat Sun "
TZ_MONTHS DB 31,28,31,30,31,30,31,31,30,31,30,31
TZ_OFFSET DS 2
TZ_WORK DS 2
TZ_FREE DS 2
TZ_SEQ DS 4
TZ_SUM DS 2
TZ_FOUND DB 0
TZ_HOURS DB 0
TZ_DATE DS 8
