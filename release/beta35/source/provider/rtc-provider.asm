; Optional MCP79411 service. Original implementation using Microchip DS20002266J
; and WDC EDU Rev D wiring (VIA1 PA0=SCL, PA7=SDA). No SRAM/EEPROM access.
; Only SET/ACK write RTC data. Reads write the I2C register address pointer.
; Resident flash extension; private RAM state and exclusive VIA1 ownership.
        MODULE RTC_SERVICE
        XDEF START
        XDEF SERVICE_END
        INCLUDE "rtc-api.inc"
        INCLUDE "i2c-api.inc"
        CODE
START   DB "RC",3,7
        JMP DO_READ
        JMP DO_STATUS
        JMP DO_SET
        JMP DO_ACK
        JMP PUBLIC_I2C
        JMP SPI_PUBLIC
        JMP SRAM_PUBLIC
VORA    EQU $7FCF
VDDR    EQU $7FC3
DO_READ LDA #0
                        JMP ENTER
DO_STATUS LDA #1
                        JMP ENTER
DO_SET  LDA #2
                        JMP ENTER
DO_ACK  LDA #3
ENTER   PHP
        SEI
        CLD
        LDX BUSY
                        BEQ FREE
        PLP
        LDA #RTC_IN_USE
        CLC
        RTS
FREE    STA OP
        INC BUSY
        STZ RTC_RESULT
        LDA #RTC_F_CONTINUITY_UNKNOWN
        STA RTC_FLAGS
        LDX #7
ZEROTIME STZ RTC_TIME,X
        DEX
                        BPL ZEROTIME
        LDA RTC_KEY
        STA KEY0
        LDA RTC_KEY+1
        STA KEY1
        STZ RTC_KEY
        STZ RTC_KEY+1
        LDA OP
        CMP #2
                        BCC AUTH_OK
                        BEQ AUTH_SET
        LDA KEY0
        CMP #$50
                        BNE DENIED
        LDA KEY1
        CMP #$41
                        BNE DENIED
                        BRA AUTH_OK
AUTH_SET LDA KEY0
        CMP #$53
                        BNE DENIED
        LDA KEY1
        CMP #$54
                        BEQ AUTH_OK
DENIED  LDA #RTC_DENIED
        JMP RETURN
AUTH_OK JSR INIT
                        BCS INITIALIZED
        JMP FINISH
INITIALIZED
        JSR SNAPSHOT
                        BCS SNAP_OK
        JMP FINISH
SNAP_OK JSR DECODE
        LDA OP
                        BNE NOT_READ
        JMP READ_DONE
NOT_READ
        CMP #1
                        BNE NOT_STATUS
        JMP SUCCESS
NOT_STATUS
        CMP #2
                        BEQ SET_CLOCK
        ; ACK uses the observed weekday bits, preserving backup enable.
        LDA RTC_RAW+3
        AND #$0F
        STA WRITEBUF
        LDA #3
        STA REGADDR
        LDA #1
        STA COUNT
        JSR WRITE_REGS
                        BCS PV_LONG_97
                        JMP FINISH
PV_LONG_97:
                        BRA REFRESH
SET_CLOCK
        LDA RTC_RAW+7
        AND #$30
                        BEQ SET_NO_ALARM
        LDA #RTC_ALARM_ON
                        JMP FINISH
SET_NO_ALARM
        JSR ENCODE_REQUEST
                        BCS SET_VALID
        LDA #RTC_BAD_TIME
                        JMP FINISH
SET_VALID
        ; Stop oscillator before writing calendar. An error after this point
        ; may leave a stopped/partially changed clock; caller must re-read.
        LDA RTC_RAW
        AND #$7F
        STA WRITEBUF
        STZ REGADDR
        LDA #1
        STA COUNT
        JSR WRITE_REGS
                        BCC FINISH
        LDX #$FF
STOP_WAIT
        LDA #3
        STA REGADDR
        LDA #1
        STA COUNT
        PHX
        JSR READ_REGS
        PLX
                        BCC FINISH
        LDA READBUF
        AND #$20
                        BEQ STOPPED
        DEX
                        BNE STOP_WAIT
        LDA #RTC_TIMEOUT
                        JMP FINISH
STOPPED
        LDX #6
COPY_SET LDA SETBUF,X
        STA WRITEBUF,X
        DEX
                        BPL COPY_SET
        STZ REGADDR
        LDA #7
        STA COUNT
        JSR WRITE_REGS
                        BCC FINISH
REFRESH JSR SNAPSHOT
                        BCC FINISH
        JSR DECODE
                        JMP SUCCESS
READ_DONE
        LDA RTC_FLAGS
        AND #7
        CMP #7
                        BEQ SUCCESS
        LDA #RTC_BAD_TIME
                        JMP FINISH
SUCCESS LDA #0
FINISH  STA RTC_RESULT
        JSR RESTORE
        LDA RTC_RESULT
RETURN  STA RTC_RESULT
        STZ BUSY
        PLP
        LDA RTC_RESULT
                        BEQ RET_OK
        CLC
        RTS
RET_OK  SEC
        RTS

; Read calendar/control, then re-read seconds. Retry boundedly on rollover.
SNAPSHOT LDA #3
        STA RETRIES
SNAP_TRY STZ REGADDR
        LDA #9
        STA COUNT
        JSR READ_REGS
                        BCC SNAP_RETURN
        LDX #8
COPY_RAW LDA READBUF,X
        STA RTC_RAW,X
        DEX
                        BPL COPY_RAW
        STZ REGADDR
        LDA #1
        STA COUNT
        JSR READ_REGS
                        BCC SNAP_RETURN
        LDA READBUF
        CMP RTC_RAW
                        BEQ SNAP_COHERENT
        DEC RETRIES
                        BNE SNAP_TRY
        LDA #RTC_UNSTABLE
        CLC
        RTS
SNAP_COHERENT
        LDA #$18
        STA REGADDR
        LDA #8
        STA COUNT
        JSR READ_REGS
                        BCC SNAP_RETURN
        LDX #7
COPY_OUTAGE LDA READBUF,X
        STA RTC_OUTAGE,X
        DEX
                        BPL COPY_OUTAGE
        LDA RTC_RAW+3
        AND #$10
                        BEQ SNAP_GOOD
        ; Capture current latched event before an explicit write clears it.
        ; Retain the last capture after acknowledgment, until a newer event.
        LDX #7
CAPTURE_LOOP LDA RTC_OUTAGE,X
        STA RTC_CAPTURE,X
        DEX
                        BPL CAPTURE_LOOP
        LDA #1
        STA RTC_EVIDENCE
SNAP_GOOD LDA #0
        SEC
SNAP_RETURN RTS

DECODE  LDA #RTC_F_CONTINUITY_UNKNOWN
        STA RTC_FLAGS
        LDA RTC_RAW
                        BPL NOT_START
        INC RTC_FLAGS
NOT_START LDA RTC_RAW+3
        AND #$20
                        BEQ NOT_RUN
        LDA RTC_FLAGS
        ORA #RTC_F_RUNNING
        STA RTC_FLAGS
NOT_RUN LDA RTC_RAW+3
        AND #$10
                        BEQ NOT_FAIL
        LDA RTC_FLAGS
        ORA #RTC_F_POWERFAIL
        STA RTC_FLAGS
NOT_FAIL LDA RTC_RAW+3
        AND #8
                        BEQ NOT_BACKUP
        LDA RTC_FLAGS
        ORA #RTC_F_BACKUP_ENABLED
        STA RTC_FLAGS
NOT_BACKUP
        LDA RTC_RAW+6
        JSR UNBCD
                        BCS YEAR_BCD_OK
        RTS
YEAR_BCD_OK
        CLC
        ADC #$D0
        STA RTC_TIME
        LDA #7
        ADC #0
        STA RTC_TIME+1
        LDA RTC_RAW+5
        AND #$1F
        JSR UNBCD
                        BCS MONTH_BCD_OK
        RTS
MONTH_BCD_OK
        STA RTC_TIME+2
        LDA RTC_RAW+4
        AND #$3F
        JSR UNBCD
                        BCC DEC_FAIL
        STA RTC_TIME+3
        LDA RTC_RAW+3
        AND #7
        STA RTC_TIME+4
        LDA RTC_RAW+2
        AND #$40
                        BEQ H24
        LDA RTC_RAW+2
        AND #$1F
        JSR UNBCD
                        BCC DEC_FAIL
        CMP #1
                        BCC DEC_FAIL
        CMP #13
                        BCS DEC_FAIL
        CMP #12
                        BNE H12_NOT_NOON
        LDA #0
H12_NOT_NOON STA TEMP
        LDA RTC_RAW+2
        AND #$20
                        BEQ H12_AM
        LDA TEMP
        CLC
        ADC #12
                        JMP HOUR_STORE
H12_AM LDA TEMP
                        JMP HOUR_STORE
H24     LDA RTC_RAW+2
        AND #$3F
        JSR UNBCD
                        BCC DEC_FAIL
HOUR_STORE STA RTC_TIME+5
        LDA RTC_RAW+1
        AND #$7F
        JSR UNBCD
                        BCC DEC_FAIL
        STA RTC_TIME+6
        LDA RTC_RAW
        AND #$7F
        JSR UNBCD
                        BCC DEC_FAIL
        STA RTC_TIME+7
        ; RTC_TIME is 8 bytes (year occupies two); request follows same layout.
        JSR VALIDATE
                        BCC DEC_FAIL
        LDA RTC_FLAGS
        ORA #RTC_F_CALENDAR
        STA RTC_FLAGS
DEC_FAIL RTS

; Validate RTC_TIME as binary calendar in 2000-2099, weekday 1=Mon..7=Sun.
VALIDATE LDA RTC_TIME+1
        CMP #7
                        BEQ YEAR_07
        CMP #8
                        BNE VALID_FAIL
        LDA RTC_TIME
        CMP #$34
                        BCS VALID_FAIL
                        BRA YEAR_HIGH
YEAR_07 LDA RTC_TIME
        CMP #$D0
                        BCC VALID_FAIL
YEAR_HIGH
        LDA RTC_TIME+2
                        BEQ VALID_FAIL
        CMP #13
                        BCS VALID_FAIL
        TAX
        LDA MONTH_DAYS-1,X
        STA MAXDAY
        CPX #2
                        BNE MONTH_READY
        LDA RTC_TIME
        AND #3
                        BNE MONTH_READY
        INC MAXDAY
MONTH_READY
        LDA RTC_TIME+3
                        BEQ VALID_FAIL
        CMP MAXDAY
                        BCC DAY_OK
                        BNE VALID_FAIL
DAY_OK  LDA RTC_TIME+4
                        BEQ VALID_FAIL
        CMP #8
                        BCS VALID_FAIL
        LDA RTC_TIME+5
        CMP #24
                        BCS VALID_FAIL
        LDA RTC_TIME+6
        CMP #60
                        BCS VALID_FAIL
        LDA RTC_TIME+7
        CMP #60
                        BCS VALID_FAIL
        SEC
        RTS
VALID_FAIL CLC
        RTS
MONTH_DAYS DB 31,28,31,30,31,30,31,31,30,31,30,31

ENCODE_REQUEST
        LDX #7
COPY_REQUEST LDA RTC_REQUEST,X
        STA RTC_TIME,X
        DEX
                        BPL COPY_REQUEST
        JSR VALIDATE
                        BCC ENCODE_DONE
        LDA RTC_TIME+7
        JSR TOBCD
        ORA #$80
        STA SETBUF
        LDA RTC_TIME+6
        JSR TOBCD
        STA SETBUF+1
        LDA RTC_TIME+5
        JSR TOBCD
        STA SETBUF+2
        LDA RTC_TIME+4
        ORA #8
        STA SETBUF+3
        LDA RTC_TIME+3
        JSR TOBCD
        STA SETBUF+4
        LDA RTC_TIME+2
        JSR TOBCD
        STA SETBUF+5
        LDA RTC_TIME
        SEC
        SBC #$D0
        JSR TOBCD
        STA SETBUF+6
        SEC
ENCODE_DONE RTS
UNBCD   STA TEMP
        AND #$0F
        CMP #10
                        BCS BCD_FAIL
        STA ONES
        LDA TEMP
        LSR A
        LSR A
        LSR A
        LSR A
        CMP #10
                        BCS BCD_FAIL
        ASL A
        STA TEMP
        ASL A
        ASL A
        CLC
        ADC TEMP
        ADC ONES
        SEC
        RTS
BCD_FAIL CLC
        RTS
TOBCD   LDX #0
TENS    CMP #10
                        BCC PACKBCD
        SEC
        SBC #10
        INX
                        BRA TENS
PACKBCD STA ONES
        TXA
        ASL A
        ASL A
        ASL A
        ASL A
        ORA ONES
        RTS

; VIA no-handshake ORA reads cannot recover hidden latches of input pins.
; Save/restore observed levels and DDRA; never drive SCL/SDA high.
INIT    LDA VORA
        STA SAVEORA
        LDA VDDR
        STA SAVEDDR
        AND #$7E
        STA VDDR
        LDA SAVEORA
        AND #$7E
        STA VORA
        NOP
        NOP
        LDA VORA
        AND #$81
        CMP #$81
                        BEQ INIT_OK
        LDA #RTC_BUS_BUSY
        CLC
        RTS
INIT_OK LDA #0
        SEC
        RTS
RESTORE LDA SAVEORA
        STA VORA
        LDA SAVEDDR
        STA VDDR
        RTS

        INCLUDE "i2c-transport.inc"

START_BUS JSR SDA_RELEASE
        JSR SCL_RELEASE
                        BCC START_END
        JSR SDA_LOW
        JSR SCL_LOW
        SEC
START_END RTS
STOP_BUS JSR SDA_LOW
        JSR SCL_RELEASE
                        BCC START_END
        JSR SDA_RELEASE
        SEC
        RTS
WRITE_BYTE STA BYTE
        LDX #8
WRITE_BIT ASL BYTE
                        BCC WRITE_ZERO
        JSR SDA_RELEASE
                        BRA WRITE_PULSE
WRITE_ZERO JSR SDA_LOW
WRITE_PULSE JSR SCL_RELEASE
                        BCC BYTE_END
        JSR SCL_LOW
        DEX
                        BNE WRITE_BIT
        JSR SDA_RELEASE
        JSR SCL_RELEASE
                        BCC BYTE_END
        LDA VORA
        AND #$80
        STA ACKBIT
        JSR SCL_LOW
        LDA ACKBIT
                        BEQ BYTE_GOOD
        LDA #RTC_NACK
        CLC
BYTE_END RTS
BYTE_GOOD LDA #0
        SEC
        RTS
READ_BYTE STZ BYTE
        LDX #8
        JSR SDA_RELEASE
READ_BIT JSR SCL_RELEASE
                        BCC BYTE_END
        LDA VORA
        ASL A
        ROL BYTE
        JSR SCL_LOW
        DEX
                        BNE READ_BIT
        CPY #0
                        BNE SEND_NACK
        JSR SDA_LOW
                        BRA READ_PULSE
SEND_NACK JSR SDA_RELEASE
READ_PULSE JSR SCL_RELEASE
                        BCC BYTE_END
        JSR SCL_LOW
        JSR SDA_RELEASE
        LDA BYTE
        SEC
        RTS
SDA_RELEASE LDA VDDR
        AND #$7F
        STA VDDR
        NOP
        NOP
        RTS
SDA_LOW LDA VDDR
        ORA #$80
        STA VDDR
        NOP
        NOP
        RTS
SCL_LOW LDA VDDR
        ORA #1
        STA VDDR
        NOP
        NOP
        RTS
SCL_RELEASE
        LDA VDDR
        AND #$FE
        STA VDDR
        PHY
        LDY #$FF
CLOCK_WAIT LDA VORA
        AND #1
                        BNE CLOCK_HIGH
        DEY
                        BNE CLOCK_WAIT
        PLY
        LDA #RTC_TIMEOUT
        CLC
        RTS
CLOCK_HIGH PLY
        NOP
        NOP
        SEC
        RTS

BUSY EQU $6669
OP EQU $666A
KEY0 EQU $666B
KEY1 EQU $666C
SAVEORA EQU $666D
SAVEDDR EQU $666E
REGADDR EQU $666F
COUNT EQU $6670
INDEX EQU $6671
RETRIES EQU $6672
ERROR EQU $6673
BYTE EQU $6674
ACKBIT EQU $6675
TEMP EQU $6676
ONES EQU $6677
MAXDAY EQU $6678
READBUF EQU $6679
WRITEBUF EQU $6682
SETBUF EQU $668B
I_ADDRESS EQU $6692
I_FLAGS EQU $6693
I_TX_LEFT EQU $6694
I_RX_LEFT EQU $6695
I_ERROR EQU $6696
I_PTR_LO EQU $6697
I_REG_PACKET EQU $6698

        INCLUDE "eeprom-transfer.inc"SP_R EQU $6650
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

        INCLUDE "spi-links.inc"
SPI_PUBLIC:
        LDA #0
                        BRA SPI_ENTER
SRAM_PUBLIC:
        LDA #1
SPI_ENTER:
        PHA
        LDA BUSY
        ORA $7D22
                        BNE SPI_IN_USE
        INC BUSY
        PLA
        STA SP_KIND
        STA SP_OP
        STZ $6659
        STZ $665A
        STZ $665B
        LDA $6664
        AND #4
                        BNE SPI_CALL
        JSR SPI_VALIDATE
                        BCC SPI_REFUSED
        LDA $6664
        ORA #4
        STA $6664
SPI_CALL:
        INC $7D22
        JMP SPI_HANDLE
SPI_REFUSED:
        STZ BUSY
        RTS
SPI_IN_USE:
        PLA
        LDA #8
        RTS
SP_NEXT_RX:
        LDX #4
SP_NEXT_TX:
        INC SP_LO+1,X
                        BNE SP_NEXT_DONE
        INC SP_LO+2,X
SP_NEXT_DONE:
        RTS

SERVICE_END
        ENDMOD
        END
