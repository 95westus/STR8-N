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
        BPL VX_SAVE
        LDA VX_REQUEST+1
        STA PBUF
        LDA VX_REQUEST+2
        STA PBUF+1
        CMP #$67
        BNE VX_BUFFER_APPLICATION
        LDA PBUF
        BNE VX_BAD_REQUEST
        BRA VX_BUFFER_CAPACITY
VX_BUFFER_APPLICATION:
        CMP #2
        BCC VX_BAD_REQUEST
        CMP #$65
        BCS VX_BAD_REQUEST
        LDA PBUF
        CLC
        ADC #VX_INFO_SIZE-1
        LDA PBUF+1
        ADC #0
        CMP #$65
        BCS VX_BAD_REQUEST
VX_BUFFER_CAPACITY:
        LDA (PBUF)
        CMP #VX_INFO_SIZE
        BCC VX_BAD_REQUEST
        LDA VX_REQUEST
        BEQ VX_REQUEST_OK
        CMP #$A0
        BEQ VX_REQUEST_OK
        CMP #$B0
        BNE VX_BAD_REQUEST
VX_REQUEST_OK:
        LDX #3
VX_RA_CHECK:
        LDA STR8V2_RAM_SIGNATURE,X
        CMP VX_RA_EXPECTED,X
        BNE VX_BAD_ABI
        DEX
        BPL VX_RA_CHECK
        STZ RPTR
        LDA #$F0
        STA RPTR+1
        STZ REND
        JSR VX_CRC_RANGE
        LDA RCRC
        CMP #F_CRC_LO
        BNE VX_BAD_ABI
        LDA RCRC+1
        CMP #F_CRC_HI
        BNE VX_BAD_ABI
        LDX #0
        LDA #$FF
VX_CLEAR_INFO:
        STA VX_FRAME,X
        INX
        CPX #VX_INFO_SIZE
        BNE VX_CLEAR_INFO
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
        BPL VX_F_GEN
        LDX #31
VX_F_ID:
        LDA VX_F_IDENTITY,X
        STA VX_FRAME+24,X
        LDA VX_BUILD_ID,X
        STA VX_FRAME+168,X
        DEX
        BPL VX_F_ID
        LDX #15
VX_F_RELEASE:
        LDA VX_F_RELEASE_TEXT,X
        STA VX_FRAME+120,X
        LDA VX_RELEASE_TEXT,X
        STA VX_FRAME+200,X
        DEX
        BPL VX_F_RELEASE
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
        BNE VX_OUTPUT
        LDA #0
        BRA VX_QUERY_EXIT
VX_BAD_REQUEST:
        LDA #$82
        BRA VX_QUERY_EXIT
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
        BNE VX_RESTORE
        LDX VX_REQUEST+1
        LDY VX_REQUEST+2
        LDA VX_REQUEST+3
        BEQ VX_QUERY_OK
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
        BNE VX_CRC_RANGE_BYTE
        INC RPTR+1
        LDA RPTR+1
        CMP REND
        BNE VX_CRC_RANGE_BYTE
        RTS
VX_CRC_BYTE:
        EOR RCRC+1
        STA RCRC+1
        LDX #8
VX_CRC_BIT:
        ASL RCRC
        ROL RCRC+1
        BCC VX_CRC_NEXT
        LDA RCRC
        EOR #$21
        STA RCRC
        LDA RCRC+1
        EOR #$10
        STA RCRC+1
VX_CRC_NEXT:
        DEX
        BNE VX_CRC_BIT
        RTS

VX_SLOT_INFO:
        STZ RPTR
        LDA SLOT
        STA RPTR+1
        LDY #0
        LDA (RPTR),Y
        CMP #'M'
        BNE VX_SLOT_DONE
        INY
        LDA (RPTR),Y
        CMP #'I'
        BNE VX_SLOT_DONE
        INY
        LDA (RPTR),Y
        CMP #1
        BNE VX_SLOT_DONE
        INY
        LDA (RPTR),Y
        CMP SLOT
        BNE VX_SLOT_DONE
        LDY #31
        LDA (RPTR),Y
        BNE VX_SLOT_DONE
        LDY #4
        LDA (RPTR),Y
        CMP #3
        BNE VX_SLOT_DONE
        INY
        LDA (RPTR),Y
        CMP #1
        BNE VX_SLOT_DONE
        INY
        LDA (RPTR),Y
        BNE VX_SLOT_DONE
        INY
        LDA (RPTR),Y
        BNE VX_SLOT_DONE
        LDY #12
        LDA (RPTR),Y
        INY
        ORA (RPTR),Y
        BEQ VX_SLOT_DONE
        LDY #13
        LDA (RPTR),Y
        CMP #$10
        BCS VX_SLOT_DONE
        CMP #$0F
        BNE VX_SLOT_LENGTH_OK
        DEY
        LDA (RPTR),Y
        CMP #$81
        BCS VX_SLOT_DONE
VX_SLOT_LENGTH_OK:
        LDY #15
        JSR VX_SLOT_ENTRY
        BCC VX_SLOT_DONE
        LDY #17
        JSR VX_SLOT_ENTRY
        BCC VX_SLOT_DONE
        JSR VX_CRC_INIT
        LDY #0
VX_SLOT_HEADER_CRC:
        LDA (RPTR),Y
        JSR VX_CRC_BYTE
        INY
        CPY #18
        BNE VX_SLOT_HEADER_CRC
        LDY #32
VX_SLOT_BODY_CRC:
        LDA (RPTR),Y
        JSR VX_CRC_BYTE
        INY
        BNE VX_SLOT_BODY_CRC
        INC RPTR+1
        LDA RPTR+1
        AND #15
        BNE VX_SLOT_BODY_CRC
        LDA SLOT
        STA RPTR+1
        LDY #18
        LDA (RPTR),Y
        CMP RCRC
        BNE VX_SLOT_DONE
        INY
        LDA (RPTR),Y
        CMP RCRC+1
        BNE VX_SLOT_DONE
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
        BNE VX_SLOT_GEN_COPY
        LDA #$C0
        STA RPTR
        LDA SLOT
        ORA #15
        STA RPTR+1
        LDY #0
VX_META_CHECK:
        LDA (RPTR),Y
        CMP VX_META_MAGIC,Y
        BNE VX_SLOT_DONE
        INY
        CPY #6
        BNE VX_META_CHECK
        LDA (RPTR),Y
        CMP SLOT
        BNE VX_SLOT_DONE
        INY
        LDA (RPTR),Y
        BNE VX_SLOT_DONE
        LDY #27
        LDA (RPTR),Y
        BNE VX_SLOT_DONE
        LDY #12
VX_META_TEXT:
        LDA (RPTR),Y
        BEQ VX_META_TEXT_NEXT
        CMP #32
        BCC VX_SLOT_DONE
        CMP #127
        BCS VX_SLOT_DONE
VX_META_TEXT_NEXT:
        INY
        CPY #28
        BNE VX_META_TEXT
        LDX ROFF
        TXA
        ASL A
        ASL A
        TAX
        LDY #8
VX_META_GEN:
        LDA (RPTR),Y
        CMP VX_FRAME+16,X
        BNE VX_SLOT_DONE
        INY
        INX
        CPY #12
        BNE VX_META_GEN
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
        BNE VX_META_ID
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
        BNE VX_META_RELEASE
VX_SLOT_DONE:
        RTS
VX_SLOT_ENTRY:
        LDA (RPTR),Y
        CMP SLOT
        BCC VX_ENTRY_BAD
        SEC
        SBC SLOT
        CMP #16
        BCS VX_ENTRY_BAD
        BNE VX_ENTRY_OK
        DEY
        LDA (RPTR),Y
        INY
        CMP #128
        BCC VX_ENTRY_BAD
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
        BNE VX_COMMAND_CAPS
        DEX
        BPL VX_COMMAND_VERSION
        LDA #0
        BRA VX_RENDER_BEGIN
VX_COMMAND_CAPS:
        LDX #4
VX_COMMAND_CAPS_BYTE:
        LDA STR8V2_LINE,X
        CMP VX_WORD_CAPS,X
        BNE VX_COMMAND_UNKNOWN
        DEX
        BPL VX_COMMAND_CAPS_BYTE
        LDA #1
VX_RENDER_BEGIN:
        STA VX_REQUEST+5
        LDA #VX_INFO_SIZE
        STA VX_FRAME
        LDA VX_REQUEST+4
        LDX #0
        LDY #$67
        JSR VX_QUERY_ENTRY
        BCC VX_RENDER_BAD
        LDX #15
VX_RENDER_SAVE:
        LDA $D0,X
        PHA
        DEX
        BPL VX_RENDER_SAVE
        LDA VX_REQUEST+5
        BNE VX_RENDER_CAPS
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
        BEQ VX_RENDER_UNAVAILABLE
        LDA VX_FRAME+9,X
        AND #2
        BEQ VX_RENDER_RELEASE_UNKNOWN
        LDA VX_RELEASE_OFF,X
        CLC
        ADC #<VX_FRAME
        TAX
        LDY #>VX_FRAME
        JSR VX_PRINT
        BRA VX_RENDER_GEN_TEXT
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
        BNE VX_RENDER_GEN
        LDX #<VX_ID_TEXT
        LDY #>VX_ID_TEXT
        JSR VX_PRINT
        LDX INDEX
        LDA VX_FRAME+9,X
        AND #2
        BEQ VX_RENDER_UNAVAILABLE
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
        BNE VX_RENDER_ID
        BRA VX_RENDER_NEXT
VX_RENDER_UNAVAILABLE:
        LDX #<VX_UNAVAILABLE
        LDY #>VX_UNAVAILABLE
        JSR VX_PRINT
VX_RENDER_NEXT:
        JSR STR8V2_RAM_NEWLINE
        INC INDEX
        LDA INDEX
        CMP #3
        BNE VX_RENDER_COMPONENT
        LDX #<VX_RUNNING
        LDY #>VX_RUNNING
        JSR VX_PRINT
        LDA VX_FRAME+8
        BEQ VX_RUNNING_UNKNOWN
        CMP #$A0
        BEQ VX_RUNNING_A
        LDA #'B'
        BRA VX_RUNNING_CHAR
VX_RUNNING_A:
        LDA #'A'
VX_RUNNING_CHAR:
        JSR STR8V2_RAM_PUTC
        BRA VX_RENDER_DONE
VX_RUNNING_UNKNOWN:
        LDX #<VX_UNAVAILABLE
        LDY #>VX_UNAVAILABLE
        JSR VX_PRINT
        BRA VX_RENDER_DONE
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
        BNE VX_RENDER_RESTORE
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
        BEQ VX_PRINT_DONE
        JSR STR8V2_RAM_PUTC
        INY
        BNE VX_PRINT_BYTE
        INC TEXT+1
        BRA VX_PRINT_BYTE
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
