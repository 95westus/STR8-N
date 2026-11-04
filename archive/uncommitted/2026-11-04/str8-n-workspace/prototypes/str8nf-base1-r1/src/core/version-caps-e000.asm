; VX1 read-only discovery/information provider. No flash or device mutator.
        MODULE VERSION_CAPS
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "version-caps-public.inc"
PBUF EQU $D0
RPTR EQU $D2
RCRC EQU $D4
REND EQU $D6
SLOT EQU $D7
ROFF EQU $D8
TEMP EQU $D9
TEXT EQU $DA
INDEX EQU $DC
        CODE
VX_HEADER:
        DB "VX",1,64
        JMP VX_QUERY
        JMP VX_COMMAND
        DB 0,0,0,1,1,VX_INFO_SIZE
        DW $1000
        DB "B15V"
        DS 9,$FF
        DB 0
        DS 32,$FF
VX_QUERY:
        STA VX_REQUEST
        STX VX_REQUEST+1
        STY VX_REQUEST+2
        LDX #15
VX_SAVE:
        LDA $D0,X
        PHA
        DEX
        BMI P_LONG_1
        JMP VX_SAVE
P_LONG_1:
        LDA VX_REQUEST+1
        STA PBUF
        LDA VX_REQUEST+2
        STA PBUF+1
        CMP #$67
        BEQ P_LONG_2
        JMP VX_BUFFER_APPLICATION
P_LONG_2:
        LDA PBUF
        BEQ P_LONG_3
        JMP VX_BAD_REQUEST
P_LONG_3:
        JMP VX_BUFFER_CAPACITY
VX_BUFFER_APPLICATION:
        CMP #2
        BCS P_LONG_4
        JMP VX_BAD_REQUEST
P_LONG_4:
        CMP #$65
        BCC P_LONG_5
        JMP VX_BAD_REQUEST
P_LONG_5:
        LDA PBUF
        CLC
        ADC #VX_INFO_SIZE-1
        LDA PBUF+1
        ADC #0
        CMP #$65
        BCC P_LONG_6
        JMP VX_BAD_REQUEST
P_LONG_6:
VX_BUFFER_CAPACITY:
        LDA (PBUF)
        CMP #VX_INFO_SIZE
        BCS P_LONG_7
        JMP VX_BAD_REQUEST
P_LONG_7:
        LDA VX_REQUEST
        BNE P_LONG_8
        JMP VX_REQUEST_OK
P_LONG_8:
        CMP #$A0
        BNE P_LONG_9
        JMP VX_REQUEST_OK
P_LONG_9:
        CMP #$B0
        BEQ P_LONG_10
        JMP VX_BAD_REQUEST
P_LONG_10:
VX_REQUEST_OK:
        LDX #3
VX_RA_CHECK:
        LDA STR8V2_RAM_SIGNATURE,X
        CMP VX_RA_EXPECTED,X
        BEQ P_LONG_11
        JMP VX_BAD_ABI
P_LONG_11:
        DEX
        BMI P_LONG_12
        JMP VX_RA_CHECK
P_LONG_12:
        STZ RPTR
        LDA #$F0
        STA RPTR+1
        STZ REND
        JSR VX_CRC_RANGE
        LDA RCRC
        CMP #F_CRC_LO
        BEQ P_LONG_13
        JMP VX_BAD_ABI
P_LONG_13:
        LDA RCRC+1
        CMP #F_CRC_HI
        BEQ P_LONG_14
        JMP VX_BAD_ABI
P_LONG_14:
        LDX #0
        LDA #$FF
VX_CLEAR_INFO:
        STA VX_FRAME,X
        INX
        CPX #VX_INFO_SIZE
        BEQ P_LONG_15
        JMP VX_CLEAR_INFO
P_LONG_15:
        LDA #'V'
        STA VX_FRAME
        LDA #'I'
        STA VX_FRAME+1
        LDA #1
        STA VX_FRAME+2
        STA VX_FRAME+7
        LDA #VX_INFO_SIZE
        STA VX_FRAME+3
        LDA VX_REQUEST
        STA VX_FRAME+8
        JSR STR8V2_RAM_CAPS_QUERY
        STA VX_FRAME+216
        STX VX_FRAME+4
        STY VX_FRAME+217
        JSR STR8V2_RAM_BOARD_QUERY
        STA VX_FRAME+218
        STX VX_FRAME+6
        STY VX_FRAME+219
        LDA #1
        STA VX_FRAME+5
        LDA #3
        STA VX_FRAME+9
        LDA #0
        STA VX_FRAME+10
        STA VX_FRAME+11
        LDX #3
VX_F_GEN:
        LDA VX_F_GENERATION,X
        STA VX_FRAME+12,X
        DEX
        BMI P_LONG_16
        JMP VX_F_GEN
P_LONG_16:
        LDX #31
VX_F_ID:
        LDA VX_F_IDENTITY,X
        STA VX_FRAME+24,X
        LDA VX_BUILD_ID,X
        STA VX_FRAME+168,X
        DEX
        BMI P_LONG_17
        JMP VX_F_ID
P_LONG_17:
        LDX #15
VX_F_RELEASE:
        LDA VX_F_RELEASE_TEXT,X
        STA VX_FRAME+120,X
        LDA VX_RELEASE_TEXT,X
        STA VX_FRAME+200,X
        DEX
        BMI P_LONG_18
        JMP VX_F_RELEASE
P_LONG_18:
        LDA #$A0
        STA SLOT
        STZ ROFF
        JSR VX_SLOT_INFO
        LDA #$B0
        STA SLOT
        LDA #1
        STA ROFF
        JSR VX_SLOT_INFO
        LDY #0
VX_OUTPUT:
        LDA VX_FRAME,Y
        STA (PBUF),Y
        INY
        CPY #VX_INFO_SIZE
        BEQ P_LONG_19
        JMP VX_OUTPUT
P_LONG_19:
        LDA #0
        JMP VX_QUERY_EXIT
VX_BAD_REQUEST:
        LDA #$82
        JMP VX_QUERY_EXIT
VX_BAD_ABI:
        LDA #$81
VX_QUERY_EXIT:
        STA VX_REQUEST+3
        LDX #0
VX_RESTORE:
        PLA
        STA $D0,X
        INX
        CPX #16
        BEQ P_LONG_20
        JMP VX_RESTORE
P_LONG_20:
        LDX VX_REQUEST+1
        LDY VX_REQUEST+2
        LDA VX_REQUEST+3
        BNE P_LONG_21
        JMP VX_QUERY_OK
P_LONG_21:
        CLC
        RTS
VX_QUERY_OK:
        SEC
        RTS

; CRC16/CCITT over [RPTR, end page), end page 0 means 10000.
VX_CRC_INIT:
        LDA #$FF
        STA RCRC
        STA RCRC+1
        RTS
VX_CRC_RANGE:
        JSR VX_CRC_INIT
VX_CRC_RANGE_BYTE:
        LDA (RPTR)
        JSR VX_CRC_BYTE
        INC RPTR
        BEQ P_LONG_22
        JMP VX_CRC_RANGE_BYTE
P_LONG_22:
        INC RPTR+1
        LDA RPTR+1
        CMP REND
        BEQ P_LONG_23
        JMP VX_CRC_RANGE_BYTE
P_LONG_23:
        RTS
VX_CRC_BYTE:
        EOR RCRC+1
        STA RCRC+1
        LDX #8
VX_CRC_BIT:
        ASL RCRC
        ROL RCRC+1
        BCS P_LONG_24
        JMP VX_CRC_NEXT
P_LONG_24:
        LDA RCRC
        EOR #$21
        STA RCRC
        LDA RCRC+1
        EOR #$10
        STA RCRC+1
VX_CRC_NEXT:
        DEX
        BEQ P_LONG_25
        JMP VX_CRC_BIT
P_LONG_25:
        RTS

VX_SLOT_INFO:
        STZ RPTR
        LDA SLOT
        STA RPTR+1
        LDY #0
        LDA (RPTR),Y
        CMP #'M'
        BEQ P_LONG_26
        JMP VX_SLOT_DONE
P_LONG_26:
        INY
        LDA (RPTR),Y
        CMP #'I'
        BEQ P_LONG_27
        JMP VX_SLOT_DONE
P_LONG_27:
        INY
        LDA (RPTR),Y
        CMP #1
        BEQ P_LONG_28
        JMP VX_SLOT_DONE
P_LONG_28:
        INY
        LDA (RPTR),Y
        CMP SLOT
        BEQ P_LONG_29
        JMP VX_SLOT_DONE
P_LONG_29:
        LDY #31
        LDA (RPTR),Y
        BEQ P_LONG_30
        JMP VX_SLOT_DONE
P_LONG_30:
        LDY #4
        LDA (RPTR),Y
        CMP #3
        BEQ P_LONG_31
        JMP VX_SLOT_DONE
P_LONG_31:
        INY
        LDA (RPTR),Y
        CMP #1
        BEQ P_LONG_32
        JMP VX_SLOT_DONE
P_LONG_32:
        INY
        LDA (RPTR),Y
        BEQ P_LONG_33
        JMP VX_SLOT_DONE
P_LONG_33:
        INY
        LDA (RPTR),Y
        BEQ P_LONG_34
        JMP VX_SLOT_DONE
P_LONG_34:
        LDY #12
        LDA (RPTR),Y
        INY
        ORA (RPTR),Y
        BNE P_LONG_35
        JMP VX_SLOT_DONE
P_LONG_35:
        LDY #13
        LDA (RPTR),Y
        CMP #$10
        BCC P_LONG_36
        JMP VX_SLOT_DONE
P_LONG_36:
        CMP #$0F
        BEQ P_LONG_37
        JMP VX_SLOT_LENGTH_OK
P_LONG_37:
        DEY
        LDA (RPTR),Y
        CMP #$81
        BCC P_LONG_38
        JMP VX_SLOT_DONE
P_LONG_38:
VX_SLOT_LENGTH_OK:
        LDY #15
        JSR VX_SLOT_ENTRY
        BCS P_LONG_39
        JMP VX_SLOT_DONE
P_LONG_39:
        LDY #17
        JSR VX_SLOT_ENTRY
        BCS P_LONG_40
        JMP VX_SLOT_DONE
P_LONG_40:
        JSR VX_CRC_INIT
        LDY #0
VX_SLOT_HEADER_CRC:
        LDA (RPTR),Y
        JSR VX_CRC_BYTE
        INY
        CPY #18
        BEQ P_LONG_41
        JMP VX_SLOT_HEADER_CRC
P_LONG_41:
        LDY #32
VX_SLOT_BODY_CRC:
        LDA (RPTR),Y
        JSR VX_CRC_BYTE
        INY
        BEQ P_LONG_42
        JMP VX_SLOT_BODY_CRC
P_LONG_42:
        INC RPTR+1
        LDA RPTR+1
        AND #15
        BEQ P_LONG_43
        JMP VX_SLOT_BODY_CRC
P_LONG_43:
        LDA SLOT
        STA RPTR+1
        LDY #18
        LDA (RPTR),Y
        CMP RCRC
        BEQ P_LONG_44
        JMP VX_SLOT_DONE
P_LONG_44:
        INY
        LDA (RPTR),Y
        CMP RCRC+1
        BEQ P_LONG_45
        JMP VX_SLOT_DONE
P_LONG_45:
        LDX ROFF
        LDA #1
        STA VX_FRAME+10,X
        TXA
        ASL A
        ASL A
        TAX
        LDY #8
VX_SLOT_GEN_COPY:
        LDA (RPTR),Y
        STA VX_FRAME+16,X
        INX
        INY
        CPY #12
        BEQ P_LONG_46
        JMP VX_SLOT_GEN_COPY
P_LONG_46:
        LDA #$C0
        STA RPTR
        LDA SLOT
        ORA #15
        STA RPTR+1
        LDY #0
VX_META_CHECK:
        LDA (RPTR),Y
        CMP VX_META_MAGIC,Y
        BEQ P_LONG_47
        JMP VX_SLOT_DONE
P_LONG_47:
        INY
        CPY #6
        BEQ P_LONG_48
        JMP VX_META_CHECK
P_LONG_48:
        LDA (RPTR),Y
        CMP SLOT
        BEQ P_LONG_49
        JMP VX_SLOT_DONE
P_LONG_49:
        INY
        LDA (RPTR),Y
        BEQ P_LONG_50
        JMP VX_SLOT_DONE
P_LONG_50:
        LDY #27
        LDA (RPTR),Y
        BEQ P_LONG_51
        JMP VX_SLOT_DONE
P_LONG_51:
        LDY #12
VX_META_TEXT:
        LDA (RPTR),Y
        BNE P_LONG_52
        JMP VX_META_TEXT_NEXT
P_LONG_52:
        CMP #32
        BCS P_LONG_53
        JMP VX_SLOT_DONE
P_LONG_53:
        CMP #127
        BCC P_LONG_54
        JMP VX_SLOT_DONE
P_LONG_54:
VX_META_TEXT_NEXT:
        INY
        CPY #28
        BEQ P_LONG_55
        JMP VX_META_TEXT
P_LONG_55:
        LDX ROFF
        TXA
        ASL A
        ASL A
        TAX
        LDY #8
VX_META_GEN:
        LDA (RPTR),Y
        CMP VX_FRAME+16,X
        BEQ P_LONG_56
        JMP VX_SLOT_DONE
P_LONG_56:
        INY
        INX
        CPY #12
        BEQ P_LONG_57
        JMP VX_META_GEN
P_LONG_57:
        LDX ROFF
        LDA #3
        STA VX_FRAME+10,X
        TXA
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        TAX
        LDY #28
VX_META_ID:
        LDA (RPTR),Y
        STA VX_FRAME+56,X
        INX
        INY
        CPY #60
        BEQ P_LONG_58
        JMP VX_META_ID
P_LONG_58:
        LDA ROFF
        ASL A
        ASL A
        ASL A
        ASL A
        TAX
        LDY #12
VX_META_RELEASE:
        LDA (RPTR),Y
        STA VX_FRAME+136,X
        INX
        INY
        CPY #28
        BEQ P_LONG_59
        JMP VX_META_RELEASE
P_LONG_59:
VX_SLOT_DONE:
        RTS
VX_SLOT_ENTRY:
        LDA (RPTR),Y
        CMP SLOT
        BCS P_LONG_60
        JMP VX_ENTRY_BAD
P_LONG_60:
        SEC
        SBC SLOT
        CMP #16
        BCC P_LONG_61
        JMP VX_ENTRY_BAD
P_LONG_61:
        BEQ P_LONG_62
        JMP VX_ENTRY_OK
P_LONG_62:
        DEY
        LDA (RPTR),Y
        INY
        CMP #128
        BCS P_LONG_63
        JMP VX_ENTRY_BAD
P_LONG_63:
VX_ENTRY_OK:
        SEC
        RTS
VX_ENTRY_BAD:
        CLC
        RTS

VX_COMMAND:
        STA VX_REQUEST+4
        LDX #7
VX_COMMAND_VERSION:
        LDA STR8V2_LINE,X
        CMP VX_WORD_VERSION,X
        BEQ P_LONG_64
        JMP VX_COMMAND_CAPS
P_LONG_64:
        DEX
        BMI P_LONG_65
        JMP VX_COMMAND_VERSION
P_LONG_65:
        LDA #0
        JMP VX_RENDER_BEGIN
VX_COMMAND_CAPS:
        LDX #4
VX_COMMAND_CAPS_BYTE:
        LDA STR8V2_LINE,X
        CMP VX_WORD_CAPS,X
        BEQ P_LONG_66
        JMP VX_COMMAND_UNKNOWN
P_LONG_66:
        DEX
        BMI P_LONG_67
        JMP VX_COMMAND_CAPS_BYTE
P_LONG_67:
        LDA #1
VX_RENDER_BEGIN:
        STA VX_REQUEST+5
        LDA #VX_INFO_SIZE
        STA VX_FRAME
        LDA VX_REQUEST+4
        LDX #0
        LDY #$67
        JSR VX_QUERY_ENTRY
        BCS P_LONG_68
        JMP VX_RENDER_BAD
P_LONG_68:
        LDX #15
VX_RENDER_SAVE:
        LDA $D0,X
        PHA
        DEX
        BMI P_LONG_69
        JMP VX_RENDER_SAVE
P_LONG_69:
        LDA VX_REQUEST+5
        BEQ P_LONG_70
        JMP VX_RENDER_CAPS
P_LONG_70:
        LDX #<VX_TITLE
        LDY #>VX_TITLE
        JSR VX_PRINT
        LDA #0
        STA INDEX
VX_RENDER_COMPONENT:
        LDX INDEX
        LDA VX_NAME_LO,X
        PHA
        LDA VX_NAME_HI,X
        TAY
        PLA
        TAX
        JSR VX_PRINT
        LDX INDEX
        LDA VX_FRAME+9,X
        AND #1
        BNE P_LONG_71
        JMP VX_RENDER_UNAVAILABLE
P_LONG_71:
        LDA VX_FRAME+9,X
        AND #2
        BNE P_LONG_72
        JMP VX_RENDER_RELEASE_UNKNOWN
P_LONG_72:
        LDA VX_RELEASE_OFF,X
        CLC
        ADC #<VX_FRAME
        TAX
        LDY #>VX_FRAME
        JSR VX_PRINT
        JMP VX_RENDER_GEN_TEXT
VX_RENDER_RELEASE_UNKNOWN:
        LDX #<VX_UNAVAILABLE
        LDY #>VX_UNAVAILABLE
        JSR VX_PRINT
VX_RENDER_GEN_TEXT:
        LDX #<VX_GEN_TEXT
        LDY #>VX_GEN_TEXT
        JSR VX_PRINT
        LDA INDEX
        ASL A
        ASL A
        CLC
        ADC #15
        STA TEMP
        LDX #4
        STX VX_REQUEST+6
VX_RENDER_GEN:
        LDY TEMP
        LDA VX_FRAME,Y
        JSR STR8V2_RAM_HEX_OUT
        DEC TEMP
        DEC VX_REQUEST+6
        BEQ P_LONG_73
        JMP VX_RENDER_GEN
P_LONG_73:
        LDX #<VX_ID_TEXT
        LDY #>VX_ID_TEXT
        JSR VX_PRINT
        LDX INDEX
        LDA VX_FRAME+9,X
        AND #2
        BNE P_LONG_74
        JMP VX_RENDER_UNAVAILABLE
P_LONG_74:
        LDA VX_ID_OFF,X
        STA TEMP
        LDA #32
        STA VX_REQUEST+6
VX_RENDER_ID:
        LDY TEMP
        LDA VX_FRAME,Y
        JSR STR8V2_RAM_HEX_OUT
        INC TEMP
        DEC VX_REQUEST+6
        BEQ P_LONG_75
        JMP VX_RENDER_ID
P_LONG_75:
        JMP VX_RENDER_NEXT
VX_RENDER_UNAVAILABLE:
        LDX #<VX_UNAVAILABLE
        LDY #>VX_UNAVAILABLE
        JSR VX_PRINT
VX_RENDER_NEXT:
        JSR STR8V2_RAM_NEWLINE
        INC INDEX
        LDA INDEX
        CMP #3
        BEQ P_LONG_76
        JMP VX_RENDER_COMPONENT
P_LONG_76:
        LDX #<VX_RUNNING
        LDY #>VX_RUNNING
        JSR VX_PRINT
        LDA VX_FRAME+8
        BNE P_LONG_77
        JMP VX_RUNNING_UNKNOWN
P_LONG_77:
        CMP #$A0
        BNE P_LONG_78
        JMP VX_RUNNING_A
P_LONG_78:
        LDA #'B'
        JMP VX_RUNNING_CHAR
VX_RUNNING_A:
        LDA #'A'
VX_RUNNING_CHAR:
        JSR STR8V2_RAM_PUTC
        JMP VX_RENDER_DONE
VX_RUNNING_UNKNOWN:
        LDX #<VX_UNAVAILABLE
        LDY #>VX_UNAVAILABLE
        JSR VX_PRINT
        JMP VX_RENDER_DONE
VX_RENDER_CAPS:
        LDX #<VX_CAP_TEXT
        LDY #>VX_CAP_TEXT
        JSR VX_PRINT
        LDA VX_FRAME+216
        JSR STR8V2_RAM_HEX_OUT
        LDA #'/'
        JSR STR8V2_RAM_PUTC
        LDA VX_FRAME+4
        JSR STR8V2_RAM_HEX_OUT
        LDX #<VX_CPU_TEXT
        LDY #>VX_CPU_TEXT
        JSR VX_PRINT
        LDA VX_FRAME+6
        JSR STR8V2_RAM_HEX_OUT
VX_RENDER_DONE:
        JSR STR8V2_RAM_NEWLINE
        LDX #0
VX_RENDER_RESTORE:
        PLA
        STA $D0,X
        INX
        CPX #16
        BEQ P_LONG_79
        JMP VX_RENDER_RESTORE
P_LONG_79:
        SEC
        RTS
VX_RENDER_BAD:
        LDX #<VX_ERROR
        LDY #>VX_ERROR
        JSR VX_PRINT
        SEC
        RTS
VX_COMMAND_UNKNOWN:
        CLC
        RTS
VX_PRINT:
        STX TEXT
        STY TEXT+1
        LDY #0
VX_PRINT_BYTE:
        LDA (TEXT),Y
        BNE P_LONG_80
        JMP VX_PRINT_DONE
P_LONG_80:
        JSR STR8V2_RAM_PUTC
        INY
        BEQ P_LONG_81
        JMP VX_PRINT_BYTE
P_LONG_81:
        INC TEXT+1
        JMP VX_PRINT_BYTE
VX_PRINT_DONE:
        RTS
VX_META_MAGIC: DB "MC",1,1,1,64
VX_RA_EXPECTED: DB "RA",1,13
VX_WORD_VERSION: DB "VERSION",0
VX_WORD_CAPS: DB "CAPS",0
VX_TITLE: DB 13,10,"STR8-N VERSION / VX1",13,10,0
VX_F_NAME: DB "F: ",0
VX_A_NAME: DB "MON A: ",0
VX_B_NAME: DB "MON B: ",0
VX_NAME_LO: DB <VX_F_NAME,<VX_A_NAME,<VX_B_NAME
VX_NAME_HI: DB >VX_F_NAME,>VX_A_NAME,>VX_B_NAME
VX_RELEASE_OFF: DB 120,136,152
VX_ID_OFF: DB 24,56,88
VX_GEN_TEXT: DB " gen ",0
VX_ID_TEXT: DB " build ",0
VX_RUNNING: DB "Running MON: ",0
VX_UNAVAILABLE: DB "unavailable",0
VX_CAP_TEXT: DB 13,10,"VX1 INFO=01/224; legacy CAPS=",0
VX_CPU_TEXT: DB "; CPU=",0
VX_ERROR: DB "VERSION/CAPS incompatible",13,10,0
        INCLUDE "version-caps-identities.inc"
VX_CODE_END:
        DS VX_HEADER+$0FC0-VX_CODE_END,$FF
VX_FOOTER:
        DB "XC",1,1,1,64,0,0
        DS 4,0
VX_RELEASE_TEXT: DB "b15-vx1",0,0,0,0,0,0,0,0,0
VX_BUILD_ID: DS 32,0
        DS 2,$FF
VX_SECTOR_CRC: DS 2,0
VX_END:
        ENDS
        END
