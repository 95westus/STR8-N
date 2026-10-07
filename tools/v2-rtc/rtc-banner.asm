; Private optional banner extension. Entire backing sector is verified first.
; INIT publishes a monitor-owned pointer; PRINT makes one bounded RTC READ.
        MODULE RTC_BANNER
        XDEF START
        XDEF BANNER_END
        INCLUDE "kernel-rtc-api.inc"
TEXT EQU $E0
BANNER_PTR EQU $7D0F
PUTC EQU $7E6D
NL EQU $7E7F
        CODE
START   DB "BT",1,2
        JMP INSTALL
        JMP BANNER
INSTALL:
        LDA #<START+7
        STA BANNER_PTR
        LDA #>START+7
        STA BANNER_PTR+1
        RTS
BANNER:
        JSR NL
        JSR RTC_READ
        BCS SHOW_TIME
        CMP #4
        BNE UNAVAILABLE
        LDA RTC_FLAGS
        AND #3
        CMP #3
        BEQ INVALID
        LDX #<STOPPED_TEXT
        LDY #>STOPPED_TEXT
        JMP PRINT
INVALID:
        LDX #<INVALID_TEXT
        LDY #>INVALID_TEXT
        JMP PRINT
UNAVAILABLE:
        LDX #<UNAVAILABLE_TEXT
        LDY #>UNAVAILABLE_TEXT
        JMP PRINT
SHOW_TIME:
        LDX #<UTC_TEXT
        LDY #>UTC_TEXT
        JSR PRINT
        LDA #'2'
        JSR PUTC
        LDA #'0'
        JSR PUTC
        LDA RTC_TIME
        SEC
        SBC #$D0
        JSR DECIMAL_2
        LDA #'-'
        JSR PUTC
        LDA RTC_TIME+2
        JSR DECIMAL_2
        LDA #'-'
        JSR PUTC
        LDA RTC_TIME+3
        JSR DECIMAL_2
        LDA #' '
        JSR PUTC
        LDA RTC_TIME+5
        JSR DECIMAL_2
        LDA #':'
        JSR PUTC
        LDA RTC_TIME+6
        JSR DECIMAL_2
        LDA #':'
        JSR PUTC
        LDA RTC_TIME+7
        JSR DECIMAL_2
        RTS
DECIMAL_2:
        LDX #0
DECIMAL_TENS:
        CMP #10
        BCC DECIMAL_OUTPUT
        SBC #10
        INX
        BRA DECIMAL_TENS
DECIMAL_OUTPUT:
        PHA
        TXA
        ORA #'0'
        JSR PUTC
        PLA
        ORA #'0'
        JMP PUTC
PRINT:
        STX TEXT
        STY TEXT+1
        LDY #0
PRINT_LOOP:
        LDA (TEXT),Y
        BEQ PRINT_DONE
        JSR PUTC
        INY
        BNE PRINT_LOOP
        INC TEXT+1
        BRA PRINT_LOOP
PRINT_DONE:
        RTS
UTC_TEXT DB "UTC ",0
STOPPED_TEXT DB "RTC stopped - use R CLOCK",0
INVALID_TEXT DB "RTC time invalid - use R CLOCK",0
UNAVAILABLE_TEXT DB "RTC unavailable",0
BANNER_END:
        ENDMOD
        END
