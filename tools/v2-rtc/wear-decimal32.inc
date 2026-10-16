; Print the intact 24-bit maximum as unsigned decimal, using only the
; helper's existing borrowed staging region. At most eight digits.
WEAR_DECIMAL:
        LDX #2
WEAR_DEC_COPY:
        LDA WEAR_MAX,X
        STA WEAR_QUOTIENT,X
        DEX
        BPL WEAR_DEC_COPY
        STZ WEAR_DIGIT_COUNT
WEAR_DEC_DIVIDE:
        LDA #0
        LDX #24
WEAR_DEC_BIT:
        ASL WEAR_QUOTIENT
        ROL WEAR_QUOTIENT+1
        ROL WEAR_QUOTIENT+2
        ROL A
        CMP #10
        BCC WEAR_DEC_NEXT
        SBC #10
        INC WEAR_QUOTIENT
WEAR_DEC_NEXT:
        DEX
        BNE WEAR_DEC_BIT
        CLC
        ADC #'0'
        LDX WEAR_DIGIT_COUNT
        STA WEAR_DIGITS,X
        INC WEAR_DIGIT_COUNT
        LDA WEAR_QUOTIENT
        ORA WEAR_QUOTIENT+1
        ORA WEAR_QUOTIENT+2
        BNE WEAR_DEC_DIVIDE
        LDX WEAR_DIGIT_COUNT
WEAR_DEC_PRINT:
        DEX
        LDA WEAR_DIGITS,X
        JSR $7E6D
        CPX #0
        BNE WEAR_DEC_PRINT
        RTS
WEAR_QUOTIENT DS 3
WEAR_DIGIT_COUNT DB 0
WEAR_DIGITS DS 8
