; Optional MCP79411 service. Original implementation using Microchip DS20002266J
; and WDC EDU Rev D wiring (VIA1 PA0=SCL, PA7=SDA). No SRAM/EEPROM access.
; Only SET/ACK write RTC data. Reads write the I2C register address pointer.
; Application must reserve $3000-$3FFF and provide exclusive VIA1 ownership.
        MODULE RTC_SERVICE
        XDEF START
        XDEF SERVICE_END
        INCLUDE "rtc-api.inc"
        CODE
START   DB "RC",1,4
        JMP DO_READ
        JMP DO_STATUS
        JMP DO_SET
        JMP DO_ACK
VORA    EQU $7FCF
VDDR    EQU $7FC3
DO_READ LDA #0
        BRA ENTER
DO_STATUS LDA #1
        BRA ENTER
DO_SET  LDA #2
        BRA ENTER
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
        BCC FINISH
        BRA REFRESH
SET_CLOCK
        LDA RTC_RAW+7
        AND #$30
        BEQ SET_NO_ALARM
        LDA #RTC_ALARM_ON
        BRA FINISH
SET_NO_ALARM
        JSR ENCODE_REQUEST
        BCS SET_VALID
        LDA #RTC_BAD_TIME
        BRA FINISH
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
        BRA FINISH
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
        BRA SUCCESS
READ_DONE
        LDA RTC_FLAGS
        AND #7
        CMP #7
        BEQ SUCCESS
        LDA #RTC_BAD_TIME
        BRA FINISH
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
        BRA HOUR_STORE
H12_AM LDA TEMP
        BRA HOUR_STORE
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

READ_REGS
        JSR ADDRESS
        BCC TRANS_END
        JSR START_BUS
        BCC TRANS_END
        LDA #$DF
        JSR WRITE_BYTE
        BCC TRANS_END
        STZ INDEX
READ_NEXT
        LDY #0
        LDA INDEX
        INC A
        CMP COUNT
        BNE READ_MORE
        INY
READ_MORE JSR READ_BYTE
        BCC TRANS_END
        LDX INDEX
        STA READBUF,X
        INC INDEX
        LDA INDEX
        CMP COUNT
        BNE READ_NEXT
        BRA TRANS_OK
WRITE_REGS
        JSR ADDRESS
        BCC TRANS_END
        STZ INDEX
WRITE_NEXT LDX INDEX
        LDA WRITEBUF,X
        JSR WRITE_BYTE
        BCC TRANS_END
        INC INDEX
        LDA INDEX
        CMP COUNT
        BNE WRITE_NEXT
TRANS_OK LDA #0
TRANS_END STA ERROR
        JSR STOP_BUS
        BCS STOP_OK
        LDA ERROR
        BNE STOP_OK
        LDA #RTC_TIMEOUT
        STA ERROR
STOP_OK LDA ERROR
        BEQ TRANS_GOOD
        CLC
        RTS
TRANS_GOOD SEC
        RTS
ADDRESS JSR START_BUS
        BCC ADDRESS_END
        LDA #$DE
        JSR WRITE_BYTE
        BCC ADDRESS_END
        LDA REGADDR
        JSR WRITE_BYTE
ADDRESS_END RTS
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

BUSY DB 0
OP DB 0
KEY0 DB 0
KEY1 DB 0
SAVEORA DB 0
SAVEDDR DB 0
REGADDR DB 0
COUNT DB 0
INDEX DB 0
RETRIES DB 0
ERROR DB 0
BYTE DB 0
ACKBIT DB 0
TEMP DB 0
ONES DB 0
MAXDAY DB 0
READBUF DS 9
WRITEBUF DS 9
SETBUF DS 7
SERVICE_END
        ENDMOD
        END
