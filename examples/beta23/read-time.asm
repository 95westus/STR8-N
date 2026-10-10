; Read UTC without SET, ACK, TRIM or EEPROM writes. Entry: G 2000.
; Binary copy at 3000: year LE16, month, day, weekday, hour, minute, second.
        MODULE READ_TIME
        XDEF START
        XDEF APP_END
TIME_COPY EQU $3000
TIME_FLAGS EQU $3008
STATUS EQU $3030
        CODE
START:  SEI
        CLD
        JSR EX_CHECK_RA
        BCC EX_NO_ABI
        LDA #1
        JSR EX_CHECK_SV
        BCC FAILED
        LDX #3
CHECK_RG:
        LDA $6500,X
        CMP EXPECTED_RG,X
        BNE ABSENT
        DEX
        BPL CHECK_RG
        JSR $6504
        BCC FAILED
        CMP #0
        BNE FAILED
        STA STATUS
        LDX #7
COPY_TIME:
        LDA $66C2,X
        STA TIME_COPY,X
        DEX
        BPL COPY_TIME
        LDA $66C1
        STA TIME_FLAGS
        LDX #<UTC_TEXT
        LDY #>UTC_TEXT
        JSR EX_PRINT
        LDA TIME_COPY
        SEC
        SBC #$D0            ; Valid RTC year 2000-2099 -> two decimal digits.
        JSR DECIMAL_2
        LDA #'-'
        JSR PUTC
        LDA TIME_COPY+2
        JSR DECIMAL_2
        LDA #'-'
        JSR PUTC
        LDA TIME_COPY+3
        JSR DECIMAL_2
        LDA #' '
        JSR PUTC
        LDA TIME_COPY+5
        JSR DECIMAL_2
        LDA #':'
        JSR PUTC
        LDA TIME_COPY+6
        JSR DECIMAL_2
        LDA #':'
        JSR PUTC
        LDA TIME_COPY+7
        JSR DECIMAL_2
        JSR NL
        JMP HOLD
ABSENT: LDA #$80
FAILED: STA STATUS
        LDX #<ERROR_TEXT
        LDY #>ERROR_TEXT
        JSR EX_PRINT
        LDA STATUS
        JSR HEX
        JSR NL
        JMP HOLD
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
EXPECTED_RG DB "RG",1,4
UTC_TEXT DB "UTC 20",0
ERROR_TEXT DB "TIME error: ",0
        INCLUDE "example-abi.inc"
APP_END:
        ENDMOD
        END
