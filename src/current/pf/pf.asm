        MODULE PF_WORKER
        XDEF START
        XDEF APP_END
        INCLUDE "kernel-rtc-api.inc"
PRINT EQU $8AD1
PUTC EQU $7E6D
DECIMAL_2 EQU $8AB9
NL EQU $7E7F
OF_PTR EQU $00E2
OF_MINUTE EQU $7D11
OF_HOUR EQU $7D12
OF_DAY EQU $7D13
OF_MONTH EQU $7D14
OF_TEMP EQU $7D15
OF_UNITS EQU $7D16
OF_RAW_HOUR EQU $7D17
OF_MAX_DAY EQU $7D18
OF_DECODE EQU $8BDE
OF_FORMAT EQU $8BAB
OF_MONTH_DAYS EQU $8CA2
SHOW_EVENT EQU $8A31
UTC_TEXT EQU $8AE6
D_MIN EQU $6A00
D_HOUR EQU $6A01
D_DAY EQU $6A02
D_MONTH EQU $6A03
D_YEAR EQU $6A04
D_VALID EQU $6A05
D_DAYS EQU $6A06
D_DAYS_HI EQU $6A07
D_HUNDREDS EQU $6A08
D_KIND EQU $6A09
        CODE
START:  DB "PD",1,1
        CMP #1
        BNE D_BOOT_UP
        JSR NL
        LDX #<UTC_TEXT
        LDY #>UTC_TEXT
        JSR PRINT
        JSR $6E07
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
        JMP SHOW_EVENT
D_BOOT_UP:
        LDA #<RTC_OUTAGE+4
        STA OF_PTR
        LDA #>RTC_OUTAGE+4
        STA OF_PTR+1
        JSR OF_DECODE
        SEC
        LDA OF_PTR
        SBC #4
        STA OF_PTR
        BCS D_BOOT_PTR
        DEC OF_PTR+1
D_BOOT_PTR:
        LDA RTC_TIME
        STA D_YEAR
        LDA OF_MONTH
        CMP RTC_TIME+2
        BCC D_BOOT_YEAR
        BNE D_BOOT_PREV
        LDA OF_DAY
        CMP RTC_TIME+3
        BCC D_BOOT_YEAR
        BEQ D_BOOT_YEAR
D_BOOT_PREV:
        DEC D_YEAR
D_BOOT_YEAR:
        LDA RTC_FLAGS
        AND #7
        CMP #7
        LDA #0
        ROL A
        STA D_VALID
        STZ D_KIND
        JMP D_PRINT
        INCLUDE "outage-duration.inc"
APP_END:
        ENDMOD
        END
