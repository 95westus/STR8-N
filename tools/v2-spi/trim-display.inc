; Read-only normal-trim correction. Uses formatter-local staging variables.
; OSCTRIM is sign/magnitude: bit 7 speeds up; clear bit 7 slows down.
TRIM_DISPLAY:
        LDA $66C0
        BNE TD_RETURN
        LDA $66C1
        AND #4
        BEQ TD_RETURN
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
