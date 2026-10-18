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
TIME_MODE EQU $7D25
MON_LINE EQU $7C00
        INCLUDE "journal-eq.inc"
        INCLUDE "kernel-private.inc"
        CODE
START   DB "BT",5,3
        JMP INSTALL
        JMP BANNER
        JMP TRY_TIME
INSTALL:
        STZ TIME_MODE
        STZ J_LOCK
        LDA #<START+7
        STA BANNER_PTR
        LDA #>START+7
        STA BANNER_PTR+1
SPI_VALIDATE:
        LDA #3
        STA $7D07
        STZ J_DESC
        LDX #3
J_HEADER_CHECK:
        LDA $9000,X
        CMP J_MAGIC,X
                        BNE SPI_BAD_FORMAT
        DEX
                        BPL J_HEADER_CHECK
        ; Verify complete sector 9 before publishing its executable entry.
        JSR KERNEL_CRC_INIT
        STZ TEXT
        LDA #$90
        STA TEXT+1
        LDY #0
J_CRC_BYTE:
        LDA (TEXT),Y
        JSR KERNEL_CRC_BYTE
        INY
                        BNE J_CRC_BYTE
        INC TEXT+1
        LDA TEXT+1
        CMP #$9C
                        BNE J_CRC_BYTE
        LDA $7D38
        ORA $7D39
                        BNE SPI_BAD_CRC
        LDX #7
J_PUBLISH:
        LDA J_DISCOVERY,X
        STA J_DESC,X
        DEX
                        BPL J_PUBLISH
        LDA $7D07
        ORA #$0C
        STA $7D07
        LDA #0
        SEC
        RTS
SPI_BAD_FORMAT:
        LDA #$80
        CLC
        RTS
SPI_BAD_CRC:
        LDA #$81
        CLC
        RTS
TRY_TIME:
        LDX #4
TIME_MATCH:
        LDA MON_LINE,X
        CMP TIME_COMMAND,X
                        BNE TIME_UNHANDLED
        DEX
                        BPL TIME_MATCH
        INC TIME_MODE
        JSR BANNER
        STZ TIME_MODE
        SEC
        RTS
TIME_UNHANDLED:
        CLC
        RTS
BANNER:
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
        LDA TIME_MODE
        BEQ SHOW_EVENT
        LDA #1
        BRA D_LOAD
D_LOAD_DURATION:
        JSR OF_FORMAT
        LDA #0
D_LOAD:
        PHA
        LDA $F3
        PHA
        LDA #2
        STA $F3
        STZ $E2
        STZ $E6
        LDA #$FB
        STA $E3
        LDA #$67
        STA $E7
        JSR KERNEL_CRC_INIT
D_READ_LOOP:
        LDA #16
        STA $EA
        JSR $7830
        LDY #0
D_COPY_LOOP:
        LDA $7C80,Y
        STA ($E6),Y
        JSR KERNEL_CRC_BYTE
        INY
        CPY #16
        BNE D_COPY_LOOP
        LDA $E2
        CLC
        ADC #16
        STA $E2
        STA $E6
        BCC D_READ_LOOP
        INC $E3
        INC $E7
        LDA $E7
        CMP #$6A
        BNE D_READ_LOOP
        LDA $7D38
        ORA $7D39
        BNE D_ASSET_BAD
        LDX #3
D_HEADER:
        LDA $6700,X
        CMP D_MAGIC,X
        BNE D_ASSET_BAD
        DEX
        BPL D_HEADER
        PLA
        STA $F3
        PLA
        JMP $6704
D_ASSET_BAD:
        PLA
        STA $F3
        PLA
        BRA UNAVAILABLE
D_MAGIC DB "PD",1,1
SHOW_EVENT:
        LDA TIME_MODE
                        BEQ BN_LONG_160
                        JMP J_BOOT_DONE
BN_LONG_160:
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
        JSR D_LOAD_DURATION
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
UTC_TEXT DB "RTCC: UTC ",0
TIME_COMMAND DB "TIME",0
STOPPED_TEXT DB "RTCC: stopped",0
INVALID_TEXT DB "RTCC: invalid",0
UNAVAILABLE_TEXT DB "RTCC: Time unavailable",0
POWERFAIL_TEXT DB " [power-fail]",0
DOWN_TEXT DB "Power down: ",0
UP_TEXT DB "Power up:   ",0
J_MAGIC DB "PJ",6,1
J_DISCOVERY DB "PJ",1,1,4,$90,0,$6B
J_SAVED_TEXT DB "RTCC: PF logged, ACK",0
J_FAILED_TEXT DB "RTCC: PF logging failed.",0
J_UNVERIFIED_TEXT DB "RTCC: PF logged, unverified ACK",0
        INCLUDE "outage-format.inc"
SHOW_EUI:
        JSR NL
        LDA J_DESC
        CMP #'P'
                        BNE EUI_UNAVAILABLE
        LDX #J_BIND_PRINT_OP
        JMP $9004
EUI_UNAVAILABLE:
        LDX #<EUI_UNAVAILABLE_TEXT
        LDY #>EUI_UNAVAILABLE_TEXT
        JMP PRINT
EUI_UNAVAILABLE_TEXT DB "RTCC: EUI unavailable",0
SP_R EQU $6650
SP_GBUSY EQU $6660
SP_BUSY EQU $6669
SP_OP EQU $666A
SP_ODDR EQU $666B
SP_OORB EQU $666C
SP_PORT EQU $666D
SP_TX EQU $666E
SP_RX EQU $666F
SP_LEFT EQU $6670
SP_MASK EQU $6671
SP_OLDMODE EQU $6672
SP_ERR EQU $6673
SP_A0 EQU $6674
SP_A1 EQU $6675
SP_A2 EQU $6676
SP_COUNT EQU $6677
SP_CHANGED EQU $6678
SP_READY EQU $6679
SP_T0 EQU $667A
SP_KIND EQU $667B
SP_SAVED_PCR EQU $667C
SP_LO EQU $66B0
SP_HI EQU $66B4
SP_DDR EQU $7FC2
SP_ORB EQU $7FC0
SP_IFR EQU $7FCD
SP_PCR EQU $7FCC
SP_MANAGED EQU $66AE
SP_BACKUP EQU $6B80

        DS $3F5-(*-START)
SP_READ_MODE:
        LDA #5
        JSR SP_COMMAND
        LDA #0
        JSR SP_BYTE
        PHA
        JSR SP_DESELECT
        PLA
        RTS
SP_WRITE_MODE:
        PHA
        LDA #1
        JSR SP_COMMAND
        PLA
        JSR SP_BYTE
        BRA SP_DESELECT
SP_COMMAND:
        PHA
        JSR SP_SELECT
        PLA
        BRA SP_BYTE
SP_INIT:
        ; Port B handshakes/pending IRQs cannot be preserved by SP_ORB accesses.
        LDA SP_IFR
        AND #$18
                        BNE SP_PIN_BUSY
        LDA SP_PCR
        AND #$C0
        CMP #$80
                        BEQ SP_PIN_BUSY
        LDA $7FCB
        AND #2
                        BNE SP_PIN_BUSY
        LDA SP_DDR
        STA SP_ODDR
        LDA SP_ORB
        STA SP_OORB
        EOR #$FF
        AND SP_ODDR
        AND #$0C
                        BNE SP_PIN_BUSY
        LDA SP_OORB
        AND #$FC
        ORA #$0C
        STA SP_PORT
        STA SP_ORB
        LDA SP_ODDR
        AND #$DF
        ORA #$0F
        STA SP_DDR
        INC SP_READY
        SEC
        RTS
SP_PIN_BUSY:
        LDA #1
        CLC
        RTS
SP_SELECT:
        LDA SP_MASK
        EOR #$FF
        AND SP_PORT
        STA SP_PORT
        STA SP_ORB
        RTS
SP_DESELECT:
        LDA SP_PORT
        ORA #$0C
        STA SP_PORT
        STA SP_ORB
        RTS
SP_RESTORE:
        JSR SP_DESELECT
        LDA SP_ODDR
        STA SP_DDR
        LDA SP_OORB
        STA SP_ORB
        RTS
SP_BYTE:
        STA SP_TX
        LDX #8
SP_BIT_LOOP:
        LDA #2
        TRB SP_PORT
        ASL SP_TX
                        BCC SP_BIT_ZERO
        TSB SP_PORT
SP_BIT_ZERO:
        LDA SP_PORT
        STA SP_ORB
        INC A
        STA SP_ORB
        LDA SP_ORB
        ASL A
        ASL A
        ASL A
        ROL SP_RX
        LDA SP_PORT
        STA SP_ORB
        DEX
                        BNE SP_BIT_LOOP
        LDA SP_RX
        RTS
SPI_PREP:
        STZ SP_CHANGED
        STZ SP_READY
        STZ SP_ERR
        RTS
SPI_REPAIR_MODE:
        LDA SP_OLDMODE
        JSR SP_WRITE_MODE
        JSR SP_READ_MODE
        CMP SP_OLDMODE
                        BEQ SPI_MODE_OK
        LDA #7
        STA SP_ERR
SPI_MODE_OK:
        RTS
SPI_FINISH_PHASE:
        LDA SP_KIND
                        BNE SPI_PHASE_DONE
        LDA SP_ERR
                        BNE SPI_PHASE_DONE
        LDA #3
        STA SP_R+11
SPI_PHASE_DONE:
        RTS

BANNER_END:
        ENDMOD
        END
