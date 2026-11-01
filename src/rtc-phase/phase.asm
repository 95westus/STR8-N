        MODULE RTC_PHASE
        XDEF START
        XDEF SERVICE_END
VORA EQU $7FCF
VDDR EQU $7FC3
RTC_BUS_BUSY EQU 1
RTC_NACK EQU 2
RTC_TIMEOUT EQU 3
        CODE
START JMP CALIBRATE
        JMP PAUSE_CLOCK
        JMP OBSERVE
CALIBRATE:
        PHP
        SEI
        CLD
        STZ STATUS
        JSR HANDSHAKE
        BCS P_LONG_1
        JMP REFUSE
P_LONG_1:
        JSR CHECK_COUNT
        BCS P_LONG_2
        JMP COMPLETE
P_LONG_2:
        JSR DELAY
        JMP COMPLETE
OBSERVE:
        PHP
        SEI
        CLD
OBSERVE_AGAIN:
        STZ STATUS
        JSR HANDSHAKE
        BCS P_LONG_3
        JMP OBSERVE_END
P_LONG_3:
        JSR INIT
        BCS P_LONG_4
        JMP OBSERVE_ERROR
P_LONG_4:
        JSR SNAP
        BCC P_LONG_5
        JMP OBSERVE_READY
P_LONG_5:
OBSERVE_ERROR:
        STA STATUS
OBSERVE_READY:
        JSR RESTORE
        JSR SEND_PACKET
        JMP OBSERVE_AGAIN
OBSERVE_END:
        PLP
        JMP $7E67
PAUSE_CLOCK:
        PHP
        SEI
        CLD
        STZ STATUS
        JSR HANDSHAKE
        BCS P_LONG_6
        JMP REFUSE
P_LONG_6:
        LDA KEY
        CMP #$50
        BEQ P_LONG_7
        JMP REFUSE
P_LONG_7:
        LDA KEY+1
        CMP #$48
        BEQ P_LONG_8
        JMP REFUSE
P_LONG_8:
        STZ KEY
        STZ KEY+1
        JSR CHECK_COUNT
        BCS P_LONG_9
        JMP COMPLETE
P_LONG_9:
        JSR INIT
        BCS P_LONG_10
        JMP IO_ERROR
P_LONG_10:
        JSR SNAP
        BCS P_LONG_11
        JMP IO_ERROR
P_LONG_11:
        LDA RAW
        BMI P_LONG_12
        JMP REFUSE_RESTORE
P_LONG_12:
        STA SECONDS
        STA RESUME_SECONDS
        LDA ADJUST
        BNE P_LONG_13
        JMP ADJUST_DONE
P_LONG_13:
        CMP #1
        BEQ P_LONG_14
        JMP REFUSE_RESTORE
P_LONG_14:
        LDA SECONDS
        AND #$7F
        CMP #$59
        BCC P_LONG_15
        JMP REFUSE_RESTORE
P_LONG_15:
        SED
        CLC
        ADC #1
        CLD
        ORA #$80
        STA RESUME_SECONDS
ADJUST_DONE:
        LDA RAW+3
        AND #$30
        CMP #$20
        BEQ P_LONG_16
        JMP REFUSE_RESTORE
P_LONG_16:
        LDA RAW+7
        CMP EXPECTED
        BEQ P_LONG_17
        JMP REFUSE_RESTORE
P_LONG_17:
        AND #$30
        BEQ P_LONG_18
        JMP REFUSE_RESTORE
P_LONG_18:
        LDA RAW+8
        CMP EXPECTED+1
        BEQ P_LONG_19
        JMP REFUSE_RESTORE
P_LONG_19:
        LDA SECONDS
        AND #$7F
        STA SECONDS
        JSR WRITE_SECONDS
        BCS P_LONG_20
        JMP RESUME_ERROR
P_LONG_20:
        LDA #$FF
        STA POLLS
STOP_WAIT:
        LDA #3
        STA REGADDR
        LDA #1
        STA COUNT
        JSR READ_REGS
        BCS P_LONG_21
        JMP RESUME_ERROR
P_LONG_21:
        LDA READBUF
        AND #$20
        BNE P_LONG_22
        JMP STOPPED
P_LONG_22:
        DEC POLLS
        BEQ P_LONG_23
        JMP STOP_WAIT
P_LONG_23:
        JMP RESUME_ERROR
STOPPED:
        JSR DELAY
        JSR RESUME
        BCS P_LONG_24
        JMP RESUME_ERROR
P_LONG_24:
        JSR SNAP
        BCS P_LONG_25
        JMP IO_ERROR
P_LONG_25:
        JMP RESTORE_DONE
RESUME_ERROR:
        ; Autonomous finite restart attempts even after an I2C error.
        JSR RESUME
        JSR RESUME
        LDA #$E2
        JMP IO_ERROR
RESUME:
        LDA RESUME_SECONDS
        STA SECONDS
        JMP WRITE_SECONDS
REFUSE_RESTORE:
        LDA #$E1
        JMP IO_ERROR
REFUSE:
        LDA #$E1
        STA STATUS
        JMP COMPLETE
IO_ERROR:
        STA STATUS
RESTORE_DONE:
        JSR RESTORE
COMPLETE:
        JSR SEND_PACKET
        PLP
        JMP $7E67
SEND_PACKET:
        LDA #'@'
        JSR $7E6D
        LDA STATUS
        JSR $7E6D
        LDX #0
EMIT:
        LDA RAW,X
        PHX
        JSR $7E6D
        PLX
        INX
        CPX #17
        BEQ P_LONG_26
        JMP EMIT
P_LONG_26:
        RTS
HANDSHAKE:
        LDA #'!'
        JSR $7E6D
        JSR $7E70
        CMP #'r'
        BNE P_LONG_27
        JMP HAND_OK
P_LONG_27:
        CLC
        RTS
HAND_OK:
        SEC
        RTS
CHECK_COUNT:
        LDA TICKS+1
        CMP #$40
        BCC P_LONG_28
        JMP BAD_COUNT
P_LONG_28:
        ORA TICKS
        BNE P_LONG_29
        JMP BAD_COUNT
P_LONG_29:
        SEC
        RTS
BAD_COUNT:
        LDA #$E1
        STA STATUS
        CLC
        RTS
DELAY:
        LDA TICKS
        STA LEFT
        LDA TICKS+1
        STA LEFT+1
DELAY_OUTER:
        LDY #0
DELAY_INNER:
        DEY
        BEQ P_LONG_30
        JMP DELAY_INNER
P_LONG_30:
        LDA LEFT
        BEQ P_LONG_31
        JMP DELAY_LOW
P_LONG_31:
        DEC LEFT+1
DELAY_LOW:
        DEC LEFT
        LDA LEFT
        ORA LEFT+1
        BEQ P_LONG_32
        JMP DELAY_OUTER
P_LONG_32:
        RTS
SNAP:
        STZ REGADDR
        LDA #9
        STA COUNT
        JSR READ_REGS
        BCS P_LONG_33
        JMP SNAP_END
P_LONG_33:
        LDX #8
COPY_RAW:
        LDA READBUF,X
        STA RAW,X
        DEX
        BMI P_LONG_34
        JMP COPY_RAW
P_LONG_34:
        LDA #$18
        STA REGADDR
        LDA #8
        STA COUNT
        JSR READ_REGS
        BCS P_LONG_35
        JMP SNAP_END
P_LONG_35:
        LDX #7
COPY_PF:
        LDA READBUF,X
        STA RAW+9,X
        DEX
        BMI P_LONG_36
        JMP COPY_PF
P_LONG_36:
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

WRITE_SECONDS:
        STZ REGADDR
        JSR ADDRESS
        BCS P_LONG_62
        JMP TRANS_END
P_LONG_62:
        LDA SECONDS
        JSR WRITE_BYTE
        BCS P_LONG_63
        JMP TRANS_END
P_LONG_63:
        JMP TRANS_OK

ADJUST DB 0
RESUME_SECONDS DB 0
KEY DS 2
TICKS DS 2
EXPECTED DS 2
LEFT DS 2
STATUS DB 0
RAW DS 17
SECONDS DB 0
POLLS DB 0
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
SERVICE_END
        ENDMOD
        END
