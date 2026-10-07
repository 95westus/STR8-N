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
OF_PTR EQU $E2
OF_MINUTE EQU $7D11
OF_HOUR EQU $7D12
OF_DAY EQU $7D13
OF_MONTH EQU $7D14
OF_TEMP EQU $7D15
OF_UNITS EQU $7D16
OF_RAW_HOUR EQU $7D17
OF_MAX_DAY EQU $7D18
        INCLUDE "journal-eq.inc"
        CODE
START   DB "BT",1,2
        JMP INSTALL
        JMP BANNER
INSTALL:
        STZ J_DESC
        STZ J_LOCK
        LDA #<START+7
        STA BANNER_PTR
        LDA #>START+7
        STA BANNER_PTR+1
        LDX #3
J_HEADER_CHECK:
        LDA $9000,X
        CMP J_MAGIC,X
        BNE J_INSTALL_DONE
        DEX
        BPL J_HEADER_CHECK
        ; Verify complete sector 9 before publishing its executable entry.
        LDA #$FF
        STA $7D23
        STA $7D24
        STZ TEXT
        LDA #$90
        STA TEXT+1
        LDY #0
J_CRC_BYTE:
        LDA (TEXT),Y
        EOR $7D24
        STA $7D24
        LDX #8
J_CRC_BIT:
        ASL $7D23
        ROL $7D24
        BCC J_CRC_NEXT
        LDA $7D23
        EOR #$21
        STA $7D23
        LDA $7D24
        EOR #$10
        STA $7D24
J_CRC_NEXT:
        DEX
        BNE J_CRC_BIT
        INY
        BNE J_CRC_BYTE
        INC TEXT+1
        LDA TEXT+1
        CMP #$A0
        BNE J_CRC_BYTE
        LDA $7D23
        ORA $7D24
        BNE J_INSTALL_DONE
        LDX #7
J_PUBLISH:
        LDA J_DISCOVERY,X
        STA J_DESC,X
        DEX
        BPL J_PUBLISH
J_INSTALL_DONE:
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
        JSR PRINT
        JMP SHOW_EVENT
INVALID:
        LDX #<INVALID_TEXT
        LDY #>INVALID_TEXT
        JSR PRINT
        JMP SHOW_EVENT
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
SHOW_EVENT:
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
        BEQ EVENT_DONE
        LDX #<POWERFAIL_TEXT
        LDY #>POWERFAIL_TEXT
        JSR PRINT
        JSR NL
        LDX #<DOWN_TEXT
        LDY #>DOWN_TEXT
        JSR PRINT
        LDA #<RTC_OUTAGE
        STA OF_PTR
        LDA #>RTC_OUTAGE
        STA OF_PTR+1
        JSR OF_FORMAT
        JSR NL
        LDX #<UP_TEXT
        LDY #>UP_TEXT
        JSR PRINT
        LDA #<RTC_OUTAGE+4
        STA OF_PTR
        LDA #>RTC_OUTAGE+4
        STA OF_PTR+1
        JSR OF_FORMAT
EVENT_DONE:
        LDA $7D26
        BEQ J_BOOT_DONE
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
        BEQ J_BOOT_DONE
        STZ J_OUTCOME
        LDA J_DESC
        CMP #'P'
        BNE J_BOOT_FAILED
        LDX #J_SAVE_ACK_OP
        JSR $9004
        ; Report verified progress, including a durable save with failed ACK.
        LDA J_OUTCOME
        AND #1
        BEQ J_BOOT_FAILED
        LDA J_OUTCOME
        AND #2
        BEQ J_BOOT_UNVERIFIED
        JSR NL
        LDX #<J_SAVED_TEXT
        LDY #>J_SAVED_TEXT
        JMP PRINT
J_BOOT_UNVERIFIED:
        JSR NL
        LDX #<J_UNVERIFIED_TEXT
        LDY #>J_UNVERIFIED_TEXT
        JMP PRINT
J_BOOT_FAILED:
        JSR NL
        LDX #<J_FAILED_TEXT
        LDY #>J_FAILED_TEXT
        JMP PRINT
J_BOOT_DONE:
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
POWERFAIL_TEXT DB " [power-fail]",0
DOWN_TEXT DB "Power down: ",0
UP_TEXT DB "Power up:   ",0
J_MAGIC DB "PJ",2,1
J_DISCOVERY DB "PJ",1,1,4,$90,0,$6B
J_SAVED_TEXT DB "RTCC: PF logged, ACK",0
J_FAILED_TEXT DB "RTCC: PF logging failed.",0
J_UNVERIFIED_TEXT DB "RTCC: PF logged, unverified ACK",0
        INCLUDE "outage-format.inc"
BANNER_END:
        ENDMOD
        END
