; RAM-only UTC baseline client. G2000 READ; G2003 explicit SET from $2400.
; The monitor protects service RAM; staging happens inside the application.
        MODULE RTC_SYNC_CLIENT
        XDEF START
        XDEF CLIENT_END
        CODE
START   JMP READ_TIME
        JMP SET_TIME
READ_TIME
        JSR $6504
        BRA COMPLETE
SET_TIME
        LDX #7
COPY_REQUEST
        LDA $2400,X
        STA $66E0,X
        DEX
        BPL COPY_REQUEST
        LDA #'S'
        STA $66E9
        LDA #'T'
        STA $66EA
        JSR $650A
COMPLETE
        ; Receipt of this marker bounds the completed RTC operation before HOLD.
        LDA #'@'
        JSR $7E6D
        JMP $7E67
CLIENT_END
        ENDMOD
        END
