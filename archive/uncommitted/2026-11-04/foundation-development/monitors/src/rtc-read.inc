; Explicit MCP79411 read, WDC EDU Rev D: VIA1 PA0=SCL, PA7=SDA.
; No automatic probe. No RTC data writes, EEPROM/SRAM access or flag clearing.
; I2C address-pointer writes are necessary for a register read.
; Writes only DDRA and the non-handshaking ORA alias; no IFR/IER/PCR access.
; Both bus pins must already be released inputs and high. Reject otherwise.
; Registers00..08 (calendar/control/trim), then seconds again; three total
; tries shared by rollover and invalid-calendar reads. Never display an
; invalid frame or replace a persistent calendar fault with cached data.
; See docs/MON_AB_RTCC_ADAPTER.md for pin-latch and qualification limits.
MR_SAMPLE:
        STZ MR_VALID
        LDA MR_VACR
        AND #1
        BNE MR_BUSY
        LDA MR_VDDR
        STA MR_DDR
        AND #$81
        BNE MR_BUSY
        LDA MR_VORA
        STA MR_ORA
        AND #$81
        CMP #$81
        BNE MR_BUSY
        LDA MR_ORA
        AND #$7E
        STA MR_VORA
        LDA #3
        STA MR_TRIES
MR_SNAPSHOT:
        LDA #9
        STA MR_COUNT
        JSR MR_READ
        BCC MR_FINISH
        LDX #6
MR_COPY:
        LDA MR_BUFFER,X
        STA MR_RAW,X
        DEX
        BPL MR_COPY
        LDA #1
        STA MR_COUNT
        JSR MR_READ
        BCC MR_FINISH
        LDA MR_BUFFER
        CMP MR_RAW
        BEQ MR_COHERENT
        DEC MR_TRIES
        BNE MR_SNAPSHOT
        LDA #7
        BRA MR_FINISH
MR_COHERENT:
        JSR MR_DECODE
        BCC MR_BAD_TIME
        INC MR_VALID
        LDA #0
        BRA MR_FINISH
MR_BAD_TIME:
        DEC MR_TRIES
        BNE MR_SNAPSHOT
        LDA #4
MR_FINISH:
        STA MR_ERROR
        ; Release inputs before restoring high input samples to the latch.
        LDA MR_DDR
        STA MR_VDDR
        LDA MR_ORA
        STA MR_VORA
        LDA MR_ERROR
        RTS
MR_BUSY:
        LDA #1
        RTS

MR_READ:
        JSR MR_START
        BCC MR_TRANS_END
        LDA #$DE
        JSR MR_WRITE_BYTE
        BCC MR_TRANS_END
        LDA #0
        JSR MR_WRITE_BYTE
        BCC MR_TRANS_END
        JSR MR_START
        BCC MR_TRANS_END
        LDA #$DF
        JSR MR_WRITE_BYTE
        BCC MR_TRANS_END
        STZ MR_INDEX
MR_READ_NEXT:
        LDY #0
        LDA MR_INDEX
        INC A
        CMP MR_COUNT
        BNE MR_READ_MORE
        INY
MR_READ_MORE:
        JSR MR_READ_BYTE
        BCC MR_TRANS_END
        LDX MR_INDEX
        STA MR_BUFFER,X
        INC MR_INDEX
        LDA MR_INDEX
        CMP MR_COUNT
        BNE MR_READ_NEXT
        LDA #0
MR_TRANS_END:
        STA MR_ERROR
        JSR MR_STOP
        BCS MR_STOPPED
        LDA MR_ERROR
        BNE MR_STOPPED
        LDA #3
        STA MR_ERROR
MR_STOPPED:
        LDA MR_ERROR
        BEQ MR_TRANS_OK
        CLC
        RTS
MR_TRANS_OK:
        SEC
        RTS
MR_START:
        JSR MR_SDA_RELEASE
        JSR MR_SCL_RELEASE
        BCC MR_BUS_RETURN
        JSR MR_SDA_LOW
        JSR MR_SCL_LOW
        SEC
MR_BUS_RETURN:
        RTS
MR_STOP:
        JSR MR_SDA_LOW
        JSR MR_SCL_RELEASE
        BCC MR_BUS_RETURN
        JSR MR_SDA_RELEASE
        SEC
        RTS
MR_WRITE_BYTE:
        STA MR_BYTE
        LDX #8
MR_WRITE_BIT:
        ASL MR_BYTE
        BCC MR_WRITE_ZERO
        JSR MR_SDA_RELEASE
        BRA MR_WRITE_PULSE
MR_WRITE_ZERO:
        JSR MR_SDA_LOW
MR_WRITE_PULSE:
        JSR MR_SCL_RELEASE
        BCC MR_BUS_RETURN
        JSR MR_SCL_LOW
        DEX
        BNE MR_WRITE_BIT
        JSR MR_SDA_RELEASE
        JSR MR_SCL_RELEASE
        BCC MR_BUS_RETURN
        LDA MR_VORA
        AND #$80
        STA MR_ACK
        JSR MR_SCL_LOW
        LDA MR_ACK
        BEQ MR_BYTE_OK
        LDA #2
        CLC
        RTS
MR_BYTE_OK:
        LDA #0
        SEC
        RTS
MR_READ_BYTE:
        STZ MR_BYTE
        LDX #8
        JSR MR_SDA_RELEASE
MR_READ_BIT:
        JSR MR_SCL_RELEASE
        BCC MR_BUS_RETURN
        LDA MR_VORA
        ASL A
        ROL MR_BYTE
        JSR MR_SCL_LOW
        DEX
        BNE MR_READ_BIT
        CPY #0
        BNE MR_NACK
        JSR MR_SDA_LOW
        BRA MR_READ_PULSE
MR_NACK:
        JSR MR_SDA_RELEASE
MR_READ_PULSE:
        JSR MR_SCL_RELEASE
        BCC MR_BUS_RETURN
        JSR MR_SCL_LOW
        JSR MR_SDA_RELEASE
        LDA MR_BYTE
        SEC
        RTS
MR_SDA_RELEASE:
        LDA MR_VDDR
        AND #$7F
        STA MR_VDDR
        NOP
        NOP
        RTS
MR_SDA_LOW:
        LDA MR_VDDR
        ORA #$80
        STA MR_VDDR
        NOP
        NOP
        RTS
MR_SCL_LOW:
        LDA MR_VDDR
        ORA #1
        STA MR_VDDR
        NOP
        NOP
        RTS
MR_SCL_RELEASE:
        LDA MR_VDDR
        AND #$FE
        STA MR_VDDR
        PHY
        LDY #$FF
MR_CLOCK_WAIT:
        LDA MR_VORA
        AND #1
        BNE MR_CLOCK_HIGH
        DEY
        BNE MR_CLOCK_WAIT
        PLY
        LDA #3
        CLC
        RTS
MR_CLOCK_HIGH:
        PLY
        NOP
        NOP
        SEC
        RTS

; Decode to sec,min,hour,weekday,date,month,year (2000..2099).
MR_DECODE:
        LDA MR_RAW
        BPL MR_INVALID
        LDA MR_RAW+3
        AND #$20
        BEQ MR_INVALID
        LDX #0
MR_DECODE_NEXT:
        LDA MR_RAW,X
        AND MR_MASK,X
        CPX #2
        BNE MR_CONVERT
        BIT MR_RAW+2
        BVC MR_CONVERT
        AND #$1F
MR_CONVERT:
        JSR MR_UNBCD
        BCC MR_INVALID
        CPX #2
        BNE MR_RANGE_CHECK
        BIT MR_RAW+2
        BVC MR_RANGE_CHECK
        CMP #1
        BCC MR_INVALID
        CMP #13
        BCS MR_INVALID
        CMP #12
        BNE MR_NOT_NOON
        LDA #0
MR_NOT_NOON:
        PHA
        LDA MR_RAW+2
        AND #$20
        BEQ MR_AM
        PLA
        CLC
        ADC #12
        BRA MR_RANGE_CHECK
MR_AM:
        PLA
MR_RANGE_CHECK:
        CMP MR_MIN,X
        BCC MR_INVALID
        CMP MR_LIMIT,X
        BCS MR_INVALID
        STA MR_TIME,X
        INX
        CPX #7
        BNE MR_DECODE_NEXT
        LDX MR_TIME+5
        LDA MR_MONTH_DAYS-1,X
        STA MR_MAXDAY
        CPX #2
        BNE MR_DAY_CHECK
        LDA MR_TIME+6
        AND #3
        BNE MR_DAY_CHECK
        INC MR_MAXDAY
MR_DAY_CHECK:
        LDA MR_TIME+4
        CMP MR_MAXDAY
        BCC MR_VALID_TIME
        BNE MR_INVALID
MR_VALID_TIME:
        SEC
        RTS
MR_INVALID:
        CLC
        RTS
MR_UNBCD:
        STA MR_TEMP
        AND #15
        CMP #10
        BCS MR_INVALID
        STA MR_ONES
        LDA MR_TEMP
        LSR A
        LSR A
        LSR A
        LSR A
        CMP #10
        BCS MR_INVALID
        ASL A
        STA MR_TEMP
        ASL A
        ASL A
        CLC
        ADC MR_TEMP
        ADC MR_ONES
        SEC
        RTS

MR_DISPLAY:
        LDX #<MR_TITLE
        LDY #>MR_TITLE
        JSR M_PUTS
        LDA MR_VALID
        BNE MR_SHOW_TIME
        LDX #<MR_NONE
        LDY #>MR_NONE
        JMP M_PUTS
MR_SHOW_TIME:
        LDA #'2'
        JSR STR8V2_RAM_PUTC
        LDA #'0'
        JSR STR8V2_RAM_PUTC
        STZ MR_INDEX
MR_SHOW_FIELD:
        LDX MR_INDEX
        LDY MR_ORDER,X
        LDA MR_TIME,Y
        JSR MR_TWO_DIGITS
        LDX MR_INDEX
        LDA MR_SEPARATOR,X
        BEQ MR_SHOW_FLAGS
        JSR STR8V2_RAM_PUTC
        INC MR_INDEX
        BRA MR_SHOW_FIELD
MR_SHOW_FLAGS:
        LDX #<MR_FLAGS_TEXT
        LDY #>MR_FLAGS_TEXT
        JSR M_PUTS
        LDA MR_RAW+3
        AND #$38
        JSR STR8V2_RAM_HEX_OUT
        LDX #<MR_TRIM_TEXT
        LDY #>MR_TRIM_TEXT
        JSR M_PUTS
        LDA MR_TRIM
        JSR STR8V2_RAM_HEX_OUT
        LDX #<MR_CONTROL_TEXT
        LDY #>MR_CONTROL_TEXT
        JSR M_PUTS
        LDA MR_CONTROL
        JSR STR8V2_RAM_HEX_OUT
        JMP STR8V2_RAM_NEWLINE
MR_TWO_DIGITS:
        STZ MR_ONES
MR_TENS:
        CMP #10
        BCC MR_UNITS
        SEC
        SBC #10
        INC MR_ONES
        BRA MR_TENS
MR_UNITS:
        STA MR_TEMP
        LDA MR_ONES
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        LDA MR_TEMP
        ORA #'0'
        JMP STR8V2_RAM_PUTC
MR_MASK: DB $7F,$7F,$3F,7,$3F,$1F,$FF
MR_MIN: DB 0,0,0,1,1,1,0
MR_LIMIT: DB 60,60,24,8,32,13,100
MR_MONTH_DAYS: DB 31,28,31,30,31,30,31,31,30,31,30,31
MR_ORDER: DB 6,5,4,2,1,0
MR_SEPARATOR: DB "-- ::",0
MR_TITLE: DB "RTCC: ",0
MR_NONE: DB "--",13,10,0
MR_FLAGS_TEXT: DB " flags $",0
MR_TRIM_TEXT: DB " trim $",0
MR_CONTROL_TEXT: DB " ctrl $",0
