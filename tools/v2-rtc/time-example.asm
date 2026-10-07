; Read-only clock example. Load time-example.s19, then G 2000.
; Foreground 65C02 or 816 E=1, D/DBR/PBR=0. Never SET or ACK.
        MODULE TIME_EXAMPLE
        XDEF START
        XDEF APP_END
        INCLUDE "kernel-rtc-api.inc"
TEXT EQU $D0
PUTC EQU $7E6D
NL EQU $7E7F
HOLD EQU $7E67
        CODE
START:  CLD
        JSR DISCOVER
        BCC UNAVAILABLE
        JSR RTC_READ
        BCC UNAVAILABLE
        LDX #7
COPY_TIME:
        LDA RTC_TIME,X
        STA MY_TIME,X
        DEX
        BPL COPY_TIME
        LDX #<UTC_TEXT
        LDY #>UTC_TEXT
        JSR PRINT
        LDA MY_TIME
        SEC
        SBC #$D0             ; Supported years 2000-2099 -> 00-99.
        JSR DECIMAL_2
        LDA #'-'
        JSR PUTC
        LDA MY_TIME+2
        JSR DECIMAL_2
        LDA #'-'
        JSR PUTC
        LDA MY_TIME+3
        JSR DECIMAL_2
        LDA #' '
        JSR PUTC
        LDA MY_TIME+5
        JSR DECIMAL_2
        LDA #':'
        JSR PUTC
        LDA MY_TIME+6
        JSR DECIMAL_2
        LDA #':'
        JSR PUTC
        LDA MY_TIME+7
        JSR DECIMAL_2
        JSR NL
        JMP HOLD
UNAVAILABLE:
        PHA
        LDX #<ERROR_TEXT
        LDY #>ERROR_TEXT
        JSR PRINT
        PLA
        PHA
        LSR A
        LSR A
        LSR A
        LSR A
        JSR NIBBLE
        PLA
        AND #15
        JSR NIBBLE
        JSR NL
        JMP HOLD
NIBBLE: CMP #10
        BCC DIGIT
        ADC #6
DIGIT:  ADC #'0'
        JMP PUTC
DISCOVER:
        LDX #7
CHECK_SV:
        LDA RTC_DISCOVERY,X
        CPX #3              ; Only require clock flag; I2C is independent.
        BNE CHECK_BYTE
        AND #1
CHECK_BYTE:
        CMP SV_EXPECTED,X
        BNE NO_SERVICE
        DEX
        BPL CHECK_SV
        LDX #3
CHECK_RG:
        LDA RTC_SIGNATURE,X
        CMP RG_EXPECTED,X
        BNE NO_SERVICE
        DEX
        BPL CHECK_RG
        SEC
        RTS
NO_SERVICE:
        LDA #$80
        CLC
        RTS
DECIMAL_2:
        LDX #0
TENS:   CMP #10
        BCC DIGITS
        SBC #10
        INX
        BRA TENS
DIGITS: PHA
        TXA
        ORA #'0'
        JSR PUTC
        PLA
        ORA #'0'
        JMP PUTC
PRINT:  STX TEXT
        STY TEXT+1
        LDY #0
PRINT_NEXT:
        LDA (TEXT),Y
        BEQ PRINT_DONE
        JSR PUTC
        INY
        BRA PRINT_NEXT
PRINT_DONE:
        RTS
SV_EXPECTED DB "SV",1,1,0,$65,$FF,$64
RG_EXPECTED DB "RG",1,4
UTC_TEXT DB "UTC 20",0
ERROR_TEXT DB "UTC unavailable; error ",0
MY_TIME DS 8               ; Copy before HOLD: boot formatter may replace results.
APP_END:
        ENDMOD
        END
