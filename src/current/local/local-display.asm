        MODULE LOCAL_DISPLAY
        XDEF START
        XDEF APP_END
        CODE
START:  DB "LT",1,1
        JMP LOCAL_ENTRY
LOCAL_ENTRY:
        STA KIND
        CMP #3
        BNE LOCAL_TIME
        JSR $7E7F
        JSR BN_READ
        LDA BN_LENGTH
        BEQ BN_LOCAL_DONE
        JSR $7E7F
        JMP BN_SHOW
LOCAL_TIME:
        LDA $7D27
        CMP #2
        BEQ BN_LOCAL_DONE
        LDA KIND
        CMP #1
        BNE LOCAL_BOOT_DISPLAY
        JSR TRIM_DISPLAY
LOCAL_BOOT_DISPLAY:
        JSR TZ_SHOW_LOCAL
        LDA KIND
        BNE BN_LOCAL_DONE
        JMP $7E7F
BN_LOCAL_DONE:
        RTS
PRINT:  JMP TZ_PRINT
KIND DB 0
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
                        BEQ LT_LONG_125
                        JMP TZ_SCAN
LT_LONG_125:
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
                        BNE LT_LONG_249
                        JMP TZ_RENDER
LT_LONG_249:
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
        LDA KIND
        CMP #2
        BEQ TZ_DATE_ONLY
        LDA KIND
                        BNE TZ_DETAIL_PREFIX
        LDX #<TZ_BOOT_TEXT
        LDY #>TZ_BOOT_TEXT
                        BRA TZ_PREFIX_READY
TZ_DETAIL_PREFIX:
        LDX #<TZ_LOCAL_TEXT
        LDY #>TZ_LOCAL_TEXT
TZ_PREFIX_READY:
        JSR TZ_PRINT
TZ_DATE_ONLY:
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

TZ_BOOT_TEXT DB "RTCC: ",0

; BN,1,0; sequence LE32; length 0..8; eight zero-padded printable bytes;
; reserved FF through byte 27; CRC16 LE at 28; FF at 30; commit 0 at 31.
; Shared append-only EI/TZ tail. Uncommitted and malformed slots stay occupied.
BN_READ:
        STZ BN_LENGTH
        STZ BN_FREE+1
        LDX #3
BN_RESET:
        STZ BN_SEQ,X
        DEX
                        BPL BN_RESET
        LDA $7FEC
        PHA
        AND #$11
        ORA #$EE
        STA $7FEC
        STZ TZ_PTR
        LDA #$9C
        STA TZ_PTR+1
BN_SLOT:
        LDY #0
BN_BLANK:
        LDA (TZ_PTR),Y
        CMP #$FF
                        BNE BN_CHECK
        INY
        CPY #32
                        BNE BN_BLANK
        LDA BN_FREE+1
                        BEQ LT_LONG_496
                        JMP BN_NEXT
LT_LONG_496:
        LDA TZ_PTR
        STA BN_FREE
        LDA TZ_PTR+1
        STA BN_FREE+1
                        JMP BN_NEXT
BN_CHECK:
        LDY #31
        LDA (TZ_PTR),Y
                        BEQ LT_LONG_505
                        JMP BN_NEXT
LT_LONG_505:
        LDY #3
BN_HEADER:
        LDA (TZ_PTR),Y
        CMP BN_MAGIC,Y
                        BNE BN_NEXT
        DEY
                        BPL BN_HEADER
        JSR TZ_CRC
        LDY #28
        LDA (TZ_PTR),Y
        CMP TZ_SUM
                        BNE BN_NEXT
        INY
        LDA (TZ_PTR),Y
        CMP TZ_SUM+1
                        BNE BN_NEXT
        LDY #8
        LDA (TZ_PTR),Y
        CMP #9
                        BCS BN_NEXT
        STA BN_WORK
        TAX
BN_CHAR_CHECK:
        INY
        CPY #17
                        BEQ BN_NEWEST
        LDA (TZ_PTR),Y
        CPX #0
                        BEQ BN_PADDING
        CMP #$21
                        BCC BN_NEXT
        CMP #$7F
                        BCS BN_NEXT
        DEX
                        JMP BN_CHAR_CHECK
BN_PADDING:
        CMP #0
                        BNE BN_NEXT
                        JMP BN_CHAR_CHECK
BN_NEWEST:
        LDY #7
        LDX #3
BN_NEWER:
        LDA (TZ_PTR),Y
        CMP BN_SEQ,X
                        BCC BN_NEXT
                        BNE BN_KEEP
        DEY
        DEX
                        BPL BN_NEWER
BN_KEEP:
        LDY #7
        LDX #3
BN_COPY_SEQ:
        LDA (TZ_PTR),Y
        STA BN_SEQ,X
        DEY
        DEX
                        BPL BN_COPY_SEQ
        LDA BN_WORK
        STA BN_LENGTH
        LDY #9
        LDX #0
BN_COPY:
        LDA (TZ_PTR),Y
        STA BN_TEXT,X
        INY
        INX
        CPX #8
                        BNE BN_COPY
BN_NEXT:
        LDA TZ_PTR
        CLC
        ADC #32
        STA TZ_PTR
                        BCC BN_PAGE
        INC TZ_PTR+1
BN_PAGE:
        LDA TZ_PTR+1
        CMP #$A0
                        BEQ LT_LONG_586
                        JMP BN_SLOT
LT_LONG_586:
        PLA
        STA $7FEC
        RTS
BN_SHOW:
        JSR BN_READ
        LDA BN_LENGTH
                        BEQ BN_SHOW_DONE
        LDX #<BN_LABEL
        LDY #>BN_LABEL
        JSR PRINT
        LDX #0
BN_PRINT:
        LDA BN_TEXT,X
        JSR $7E6D
        INX
        CPX BN_LENGTH
                        BNE BN_PRINT
        JSR $7E7F
BN_SHOW_DONE:
        RTS
BN_MAGIC DB "BN",1,0
BN_LABEL DB "Board: ",0
BN_LENGTH DB 0
BN_WORK DB 0
BN_TEXT DS 8
BN_SEQ DS 4
BN_FREE DS 2

; Read-only normal-trim correction. Uses formatter-local staging variables.
; OSCTRIM is sign/magnitude: bit 7 speeds up; clear bit 7 slows down.
TRIM_DISPLAY:
        LDA $66C0
                        BEQ LT_LONG_619
                        JMP TD_RETURN
LT_LONG_619:
        LDA $66C1
        AND #4
                        BNE LT_LONG_622
                        JMP TD_RETURN
LT_LONG_622:
        LDA $66D3
        AND #$7F
        STA TD_MAG
        LDA KIND
        CMP #2
                        BEQ TD_DETAIL
        LDX #<TD_SUFFIX
        LDY #>TD_SUFFIX
        JSR PRINT
        JSR TD_STEPS
                        BRA TD_COARSE_BOOT
TD_DETAIL:
        JSR $7E7F
        LDX #<TD_TITLE
        LDY #>TD_TITLE
        JSR PRINT
        JSR TD_STEPS
        LDX #<TD_STEPS_TEXT
        LDY #>TD_STEPS_TEXT
        JSR PRINT
        LDA $66D2
        AND #4
                        BNE TD_COARSE_DETAIL
        ; Q16 factors: 101.72526 hundredths ppm and 87.890625
        ; thousandths seconds/day per normal step. Model checks every value.
        LDA #$AB
        STA TD_FACTOR
        LDA #$B9
        STA TD_FACTOR+1
        LDA #$65
        STA TD_FACTOR+2
        LDA #3
        STA TD_DOT
        JSR TD_MULTIPLY
        JSR TD_SIGN
        JSR TD_NUMBER
        LDX #<TD_PPM_TEXT
        LDY #>TD_PPM_TEXT
        JSR PRINT
        LDA #0
        STA TD_FACTOR
        LDA #$E4
        STA TD_FACTOR+1
        LDA #$57
        STA TD_FACTOR+2
        LDA #2
        STA TD_DOT
        JSR TD_MULTIPLY
        JSR TD_SIGN
        JSR TD_NUMBER
        LDX #<TD_DAY_TEXT
        LDY #>TD_DAY_TEXT
        JMP PRINT
TD_COARSE_DETAIL:
        LDX #<TD_COARSE_TEXT
        LDY #>TD_COARSE_TEXT
        JMP PRINT
TD_COARSE_BOOT:
        LDA $66D2
        AND #4
                        BEQ TD_RETURN
        LDX #<TD_COARSE_SHORT
        LDY #>TD_COARSE_SHORT
        JMP PRINT
TD_RETURN:
        RTS
TD_SIGN:
        LDA TD_MAG
                        BEQ TD_RETURN
        LDA $66D3
                        BMI TD_PLUS
        LDA #'-'
                        BRA TD_SIGN_OUT
TD_PLUS:
        LDA #'+'
TD_SIGN_OUT:
        JMP $7E6D
TD_STEPS:
        JSR TD_SIGN
        LDA TD_MAG
        STA TD_VALUE
        STZ TD_VALUE+1
        LDA #5
        STA TD_DOT
                        BRA TD_NUMBER
TD_MULTIPLY:
        STZ TD_VALUE
        STZ TD_VALUE+1
        STZ TD_VALUE+2
        STZ TD_VALUE+3
        LDX TD_MAG
                        BEQ TD_ROUND
TD_ADD:
        CLC
        LDA TD_VALUE
        ADC TD_FACTOR
        STA TD_VALUE
        LDA TD_VALUE+1
        ADC TD_FACTOR+1
        STA TD_VALUE+1
        LDA TD_VALUE+2
        ADC TD_FACTOR+2
        STA TD_VALUE+2
        LDA TD_VALUE+3
        ADC #0
        STA TD_VALUE+3
        DEX
                        BNE TD_ADD
TD_ROUND:
        LDA TD_VALUE+1
        CLC
        ADC #128
        LDA TD_VALUE+2
        ADC #0
        STA TD_VALUE
        LDA TD_VALUE+3
        ADC #0
        STA TD_VALUE+1
        RTS
TD_NUMBER:
        STZ TD_SEEN
        STZ TD_INDEX
TD_PLACE:
        LDX TD_INDEX
        CPX TD_DOT
                        BNE TD_DIGIT_BEGIN
        LDA #'.'
        JSR $7E6D
TD_DIGIT_BEGIN:
        STZ TD_DIGIT
TD_SUBTRACT:
        LDX TD_INDEX
        LDA TD_VALUE
        SEC
        SBC TD_POW_LO,X
        TAY
        LDA TD_VALUE+1
        SBC TD_POW_HI,X
                        BCC TD_DIGIT_DONE
        STA TD_VALUE+1
        STY TD_VALUE
        INC TD_DIGIT
                        BRA TD_SUBTRACT
TD_DIGIT_DONE:
        LDA TD_INDEX
        INC A
        CMP TD_DOT
                        BCS TD_OUTPUT
        LDA TD_SEEN
        ORA TD_DIGIT
                        BEQ TD_NEXT
TD_OUTPUT:
        INC TD_SEEN
        LDA TD_DIGIT
        ORA #'0'
        JSR $7E6D
TD_NEXT:
        INC TD_INDEX
        LDA TD_INDEX
        CMP #5
                        BNE TD_PLACE
        RTS
TD_POW_LO DB <10000,<1000,<100,<10,<1
TD_POW_HI DB >10000,>1000,>100,>10,>1
TD_SUFFIX DB "; trim ",0
TD_TITLE DB "RTCC: Trim ",0
TD_STEPS_TEXT DB " steps: ",0
TD_PPM_TEXT DB " ppm, ",0
TD_DAY_TEXT DB " s/day correction",0
TD_COARSE_TEXT DB "coarse ON; ppm/day unavailable",0
TD_COARSE_SHORT DB " coarse ON",0
TD_MAG DB 0
TD_FACTOR DS 3
TD_VALUE DS 4
TD_DOT DB 0
TD_SEEN DB 0
TD_INDEX DB 0
TD_DIGIT DB 0

APP_END:
        ENDMOD
