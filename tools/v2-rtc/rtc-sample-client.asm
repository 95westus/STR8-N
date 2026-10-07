; UTC/drift client with an application-owned result snapshot.
; HOLD may trigger a monitor RTC read; host timing belongs to this call only.
        MODULE RTC_SAMPLE_CLIENT
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
        LDX #$3F
COPY_RESULT
        LDA $66C0,X
        STA $2440,X
        DEX
        BPL COPY_RESULT
        LDA #'@'
        JSR $7E6D
        JMP $7E67
CLIENT_END
        ENDMOD
        END
