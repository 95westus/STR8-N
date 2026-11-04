EC_RAW_CRC:
        LDA EC_SRC
        STA EC_PTR
        LDA EC_SRC+1
        STA EC_PTR+1
EC_CRC_AT_PTR:
        LDA #$FF
        STA EC_CRC
        STA EC_CRC+1
EC_CRC_LOOP:
        LDA (EC_PTR)
        JSR EC_CRC_BYTE
        JSR EC_NEXT_PTR
        JSR EC_DEC_COUNT
        BEQ EC_CRC_LONG_1
        JMP EC_CRC_LOOP
EC_CRC_LONG_1:
        RTS
EC_CRC_BYTE:
        EOR EC_CRC+1
        STA EC_CRC+1
        LDX #8
EC_CRC_BIT:
        ASL EC_CRC
        ROL EC_CRC+1
        BCS EC_CRC_LONG_2
        JMP EC_CRC_NO_XOR
EC_CRC_LONG_2:
        LDA EC_CRC
        EOR #$21
        STA EC_CRC
        LDA EC_CRC+1
        EOR #$10
        STA EC_CRC+1
EC_CRC_NO_XOR:
        DEX
        BEQ EC_CRC_LONG_3
        JMP EC_CRC_BIT
EC_CRC_LONG_3:
        RTS

EC_NEXT_PTR:
        INC EC_PTR
        BEQ EC_CRC_LONG_4
        JMP EC_NEXT_DONE
EC_CRC_LONG_4:
        INC EC_PTR+1
EC_NEXT_DONE:
        RTS
EC_DEC_COUNT:
        LDA EC_COUNT
        BEQ EC_CRC_LONG_5
        JMP EC_DEC_LOW
EC_CRC_LONG_5:
        DEC EC_COUNT+1
EC_DEC_LOW:
        DEC EC_COUNT
        LDA EC_COUNT
        ORA EC_COUNT+1
        RTS
