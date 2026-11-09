; STR8-N UTIL RTC sampler. Copyright (c) 2026 95west.us/wlp1963; MIT.
; Read-only transport adapted from the STR8-N RTC phase observer.
; MON G 2000, 65C02 or 65C816 E=1. ! ready, r samples, q returns via HOLD.
        MODULE RTC_SAMPLE
        XDEF START
        XDEF SERVICE_END
VORA EQU $7FCF
VDDR EQU $7FC3
RTC_BUS_BUSY EQU 1
RTC_NACK EQU 2
RTC_TIMEOUT EQU 3
        CODE
START:
        PHP
        SEI
        CLD
OBSERVE:
        LDA #'!'
        JSR $7E6D
        JSR $7E70
        CMP #'r'
        BNE DONE
        STZ STATUS
        JSR INIT
        BCC SAMPLE_ERROR
        JSR SNAP
        BCS SAMPLE_READY
SAMPLE_ERROR:
        STA STATUS
SAMPLE_READY:
        JSR RESTORE
        LDA #'@'
        JSR $7E6D
        LDA STATUS
        STA SUM
        JSR $7E6D
        LDX #0
EMIT:
        LDA RAW,X
        EOR SUM
        STA SUM
        LDA RAW,X
        PHX
        JSR $7E6D
        PLX
        INX
        CPX #17
        BCC EMIT
        LDA SUM
        JSR $7E6D
        BRA OBSERVE
DONE:
        PLP
        JMP $7E67

SNAP:
        STZ REGADDR
        LDA #9
        STA COUNT
        JSR READ_REGS
        BCC SNAP_END
        LDX #8
COPY_RAW:
        LDA READBUF,X
        STA RAW,X
        DEX
        BPL COPY_RAW
        LDA #$18
        STA REGADDR
        LDA #8
        STA COUNT
        JSR READ_REGS
        BCC SNAP_END
        LDX #7
COPY_PF:
        LDA READBUF,X
        STA RAW+9,X
        DEX
        BPL COPY_PF
        ; Exclude a calendar snapshot taken across a seconds rollover.
        STZ REGADDR
        LDA #1
        STA COUNT
        JSR READ_REGS
        BCC SNAP_END
        LDA READBUF
        CMP RAW
        BEQ SNAP_OK
        LDA #4
        CLC
        RTS
SNAP_OK:
        SEC
SNAP_END:
        RTS

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
        BNE P_LONG_37
        JMP INIT_OK
P_LONG_37:
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
        BCS P_LONG_38
        JMP TRANS_END
P_LONG_38:
        JSR START_BUS
        BCS P_LONG_39
        JMP TRANS_END
P_LONG_39:
        LDA DEVICE
        ORA #1
        JSR WRITE_BYTE
        BCS P_LONG_40
        JMP TRANS_END
P_LONG_40:
        STZ INDEX
READ_NEXT
        LDY #0
        LDA INDEX
        INC A
        CMP COUNT
        BEQ P_LONG_41
        JMP READ_MORE
P_LONG_41:
        INY
READ_MORE JSR READ_BYTE
        BCS P_LONG_42
        JMP TRANS_END
P_LONG_42:
        LDX INDEX
        STA READBUF,X
        INC INDEX
        LDA INDEX
        CMP COUNT
        BEQ P_LONG_43
        JMP READ_NEXT
P_LONG_43:
        JMP TRANS_OK
TRANS_OK LDA #0
TRANS_END STA ERROR
        JSR STOP_BUS
        BCC P_LONG_44
        JMP STOP_OK
P_LONG_44:
        LDA ERROR
        BEQ P_LONG_45
        JMP STOP_OK
P_LONG_45:
        LDA #RTC_TIMEOUT
        STA ERROR
STOP_OK LDA ERROR
        BNE P_LONG_46
        JMP TRANS_GOOD
P_LONG_46:
        CLC
        RTS
TRANS_GOOD SEC
        RTS
ADDRESS JSR START_BUS
        BCS P_LONG_47
        JMP ADDRESS_END
P_LONG_47:
        LDA DEVICE
        JSR WRITE_BYTE
        BCS P_LONG_48
        JMP ADDRESS_END
P_LONG_48:
        LDA REGADDR
        JSR WRITE_BYTE
ADDRESS_END RTS
START_BUS JSR SDA_RELEASE
        JSR SCL_RELEASE
        BCS P_LONG_49
        JMP START_END
P_LONG_49:
        JSR SDA_LOW
        JSR SCL_LOW
        SEC
START_END RTS
STOP_BUS JSR SDA_LOW
        JSR SCL_RELEASE
        BCS P_LONG_50
        JMP START_END
P_LONG_50:
        JSR SDA_RELEASE
        SEC
        RTS
WRITE_BYTE STA BYTE
        LDX #8
WRITE_BIT ASL BYTE
        BCS P_LONG_51
        JMP WRITE_ZERO
P_LONG_51:
        JSR SDA_RELEASE
        JMP WRITE_PULSE
WRITE_ZERO JSR SDA_LOW
WRITE_PULSE JSR SCL_RELEASE
        BCS P_LONG_52
        JMP BYTE_END
P_LONG_52:
        JSR SCL_LOW
        DEX
        BEQ P_LONG_53
        JMP WRITE_BIT
P_LONG_53:
        JSR SDA_RELEASE
        JSR SCL_RELEASE
        BCS P_LONG_54
        JMP BYTE_END
P_LONG_54:
        LDA VORA
        AND #$80
        STA ACKBIT
        JSR SCL_LOW
        LDA ACKBIT
        BNE P_LONG_55
        JMP BYTE_GOOD
P_LONG_55:
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
        BCS P_LONG_56
        JMP BYTE_END
P_LONG_56:
        LDA VORA
        ASL A
        ROL BYTE
        JSR SCL_LOW
        DEX
        BEQ P_LONG_57
        JMP READ_BIT
P_LONG_57:
        CPY #0
        BEQ P_LONG_58
        JMP SEND_NACK
P_LONG_58:
        JSR SDA_LOW
        JMP READ_PULSE
SEND_NACK JSR SDA_RELEASE
READ_PULSE JSR SCL_RELEASE
        BCS P_LONG_59
        JMP BYTE_END
P_LONG_59:
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
        BEQ P_LONG_60
        JMP CLOCK_HIGH
P_LONG_60:
        DEY
        BEQ P_LONG_61
        JMP CLOCK_WAIT
P_LONG_61:
        PLY
        LDA #RTC_TIMEOUT
        CLC
        RTS
CLOCK_HIGH PLY
        NOP
        NOP
        SEC
        RTS

STATUS DB 0
SUM DB 0
RAW DS 17
DEVICE DB $DE
SAVEORA DB 0
SAVEDDR DB 0
REGADDR DB 0
COUNT DB 0
INDEX DB 0
ERROR DB 0
BYTE DB 0
ACKBIT DB 0
READBUF DS 9
SERVICE_END:
        ENDMOD
        END
