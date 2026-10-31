; B2:AC00-AFFF, foreground read-only status. RAM bank-call gate is7BE8-7BFB.
        MODULE STATUS_CORE
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "status-interface.inc"
        INCLUDE "status-bindings.inc"
        INCLUDE "status-text.inc"
        CODE
        DB "ST",1,4,"PR05"
        JMP SC_MAIN
        JMP SC_PRINT
        JMP SC_DECIMAL
        JMP SC_TWO
        JMP SC_READ32
        JMP SC_CRC_INIT
        JMP SC_CRC_BYTE
        JMP SC_ABSOLUTE
        JMP SC_HOURS
        DB 31,28,31,30,31,30,31,31,30,31,30,31
SC_MAIN:
        LDA ST_SELECTED
        PHA
        JSR STR8V2_RAM_BOARD_QUERY
        CPX #2
        BNE SC_CPU816
        SAY ST_CPU02
        BRA SC_CPU_DONE
SC_CPU816:
        SAY ST_CPU816
SC_CPU_DONE:
        JSR STR8V2_RAM_NEWLINE
        JSR SC_SLOTS
        JSR STR8V2_RAM_NEWLINE
        JSR SD_SCAN
        SAY ST_BOARD
        LDA ST_BN_LEN
        BEQ SC_UNNAMED
        LDY #0
SC_BOARD_NEXT:
        LDA ST_BN_TEXT,Y
        JSR STR8V2_RAM_PUTC
        INY
        CPY ST_BN_LEN
        BCC SC_BOARD_NEXT
        BRA SC_BOARD_DONE
SC_UNNAMED:
        SAY ST_UNKNOWN
SC_BOARD_DONE:
        JSR STR8V2_RAM_NEWLINE
        JSR STR8V2_RAM_NEWLINE
        SAY ST_RAM
        LDA ST_EDU
        BEQ SC_EDU_OFF
        SAY ST_EDU_ON
        JSR SC_SRAM
        BCC SC_NO_SRAM
        SAY ST_PROGRAM
        STZ ST_NUM
        SEC
        LDA ST_RECORD+5
        SBC #8
        STA ST_NUM+1
        LDA ST_RECORD+6
        SBC #0
        STA ST_NUM+2
        JSR SC_DECIMAL
        SAY ST_BYTES_TEXT
        SAY ST_WORKSPACE
        LDA #$E0
        STA ST_NUM
        LDA #$FF
        SEC
        SBC ST_RECORD+5
        STA ST_NUM+1
        LDA #1
        SBC ST_RECORD+6
        STA ST_NUM+2
        JSR SC_DECIMAL
        SAY ST_BYTES_TEXT
        BRA SC_DEVICES_DONE
SC_EDU_OFF:
        SAY ST_EDU_OFF_TEXT
SC_NO_SRAM:
        SAY ST_SRAM_NONE
SC_DEVICES_DONE:
        JSR STR8V2_RAM_NEWLINE
        JSR SD_SCAN
        JSR SD_TIME
        LDA ST_WEAR_VECTOR
        STA ST_CALL_LO
        LDA ST_WEAR_VECTOR+1
        STA ST_CALL_HI
        LDA #3
        LDX #2
        JSR ST_CALL
        PHP
        SAY ST_FLASH
        PLP
        BCC SC_WEAR_NONE
        LDA #'B'
        JSR STR8V2_RAM_PUTC
        LDA $6A16
        LSR A
        LSR A
        LSR A
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA $6A16
        AND #7
        CLC
        ADC #'8'
        CMP #':'
        BCC SC_SECTOR
        CLC
        ADC #7
SC_SECTOR:
        JSR STR8V2_RAM_PUTC
        LDX #2
SC_MAX_COPY:
        LDA $6A13,X
        STA ST_NUM,X
        DEX
        BPL SC_MAX_COPY
        SAY ST_MAXIMUM
        JSR SC_DECIMAL
        LDA #'*'
        JSR STR8V2_RAM_PUTC
        JSR STR8V2_RAM_NEWLINE
        BRA SC_BATTERY
SC_WEAR_NONE:
        SAY ST_NONE
SC_BATTERY:
        JSR SD_BATTERY
        SAY ST_CAVEAT
        PLA
        STA ST_SELECTED
        RTS
SC_SLOTS:
        LDA #$A0
        STA SI_SLOT
SC_SLOT:
        SAY ST_MONITOR
        LDA #'A'
        LDX SI_SLOT
        CPX #$A0
        BEQ SC_SLOT_LETTER
        INC A
SC_SLOT_LETTER:
        JSR STR8V2_RAM_PUTC
        ; F's slot validator requires BOOT_DEST and does not copy generation.
        ; Snapshot this header before switching to B3 for its full CRC check.
        LDA SI_SLOT
        STA ST_ADDR+1
        STA $7D31
        STZ ST_ADDR
        JSR SC_READ32
        STZ ST_PTR
        LDA SI_SLOT
        STA ST_PTR+1
        LDA #<ST_F_SLOT_CHECK
        STA ST_CALL_LO
        LDA #>ST_F_SLOT_CHECK
        STA ST_CALL_HI
        LDA #3
        LDX #2
        JSR ST_CALL
        BCC SC_SLOT_INVALID
        SAY ST_GENERATION
        LDA #3
        STA SI_INDEX
SC_GEN_BYTE:
        LDX SI_INDEX
        LDA ST_RECORD+8,X
        JSR STR8V2_RAM_HEX_OUT
        DEC SI_INDEX
        BPL SC_GEN_BYTE
        SAY ST_VALID
        BIT ST_FLAGS
        BPL SC_SLOT_DONE
        LDA #'A'
        LDX SI_SLOT
        CPX #$A0
        BEQ SC_DEFAULT_TEST
        INC A
SC_DEFAULT_TEST:
        CMP ST_FRAME+7
        BNE SC_SLOT_DONE
        SAY ST_DEFAULT
        BRA SC_SLOT_DONE
SC_SLOT_INVALID:
        SAY ST_INVALID
SC_SLOT_DONE:
        JSR STR8V2_RAM_NEWLINE
        LDA SI_SLOT
        CMP #$B0
        BEQ SC_SLOTS_END
        LDA #$B0
        STA SI_SLOT
        BRA SC_SLOT
SC_SLOTS_END:
        RTS
SC_PRINT:
        STX ST_PTR
        STY ST_PTR+1
        LDY #0
SC_PRINT_NEXT:
        LDA (ST_PTR),Y
        BEQ SC_PRINT_END
        JSR STR8V2_RAM_PUTC
        INY
        BRA SC_PRINT_NEXT
SC_PRINT_END:
        RTS
SC_TWO:
        STZ SI_DIGIT
SC_TWO_TENS:
        CMP #10
        BCC SC_TWO_UNITS
        SEC
        SBC #10
        INC SI_DIGIT
        BRA SC_TWO_TENS
SC_TWO_UNITS:
        PHA
        LDA SI_DIGIT
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        PLA
        ORA #'0'
        JMP STR8V2_RAM_PUTC
SC_DECIMAL:
        STZ SI_STARTED
        STZ SI_INDEX
SC_POWER:
        STZ SI_DIGIT
SC_SUB_TEST:
        LDX SI_INDEX
        LDA ST_NUM+2
        CMP SC_POWERS+2,X
        BNE SC_SUB_DECIDE
        LDA ST_NUM+1
        CMP SC_POWERS+1,X
        BNE SC_SUB_DECIDE
        LDA ST_NUM
        CMP SC_POWERS,X
SC_SUB_DECIDE:
        BCC SC_DIGIT
        SEC
        LDA ST_NUM
        SBC SC_POWERS,X
        STA ST_NUM
        LDA ST_NUM+1
        SBC SC_POWERS+1,X
        STA ST_NUM+1
        LDA ST_NUM+2
        SBC SC_POWERS+2,X
        STA ST_NUM+2
        INC SI_DIGIT
        BRA SC_SUB_TEST
SC_DIGIT:
        LDA SI_DIGIT
        ORA SI_STARTED
        BNE SC_EMIT_DIGIT
        LDA SI_INDEX
        CMP #15
        BNE SC_NEXT_POWER
SC_EMIT_DIGIT:
        INC SI_STARTED
        LDA SI_DIGIT
        ORA #'0'
        JSR STR8V2_RAM_PUTC
SC_NEXT_POWER:
        INC SI_INDEX
        INC SI_INDEX
        INC SI_INDEX
        LDA SI_INDEX
        CMP #18
        BCC SC_POWER
        RTS
SC_POWERS: DB $A0,$86,1,$10,$27,0,$E8,3,0,100,0,0,10,0,0,1,0,0
SC_READ32:
        LDA #3
        STA ST_SELECTED
        LDA #16
        STA ST_COUNT
        JSR ST_F_READ
        LDX #15
SC_READ_FIRST:
        LDA ST_BYTES,X
        STA ST_RECORD,X
        DEX
        BPL SC_READ_FIRST
        LDA ST_ADDR
        CLC
        ADC #16
        STA ST_ADDR
        JSR ST_F_READ
        LDX #15
SC_READ_SECOND:
        LDA ST_BYTES,X
        STA ST_RECORD+16,X
        DEX
        BPL SC_READ_SECOND
        LDA ST_ADDR
        SEC
        SBC #16
        STA ST_ADDR
        RTS
SC_CRC_INIT:
        LDA #$FF
        STA SI_CRC
        STA SI_CRC+1
        RTS
SC_CRC_BYTE:
        PHX
        EOR SI_CRC+1
        STA SI_CRC+1
        LDX #8
SC_CRC_BIT:
        ASL SI_CRC
        ROL SI_CRC+1
        BCC SC_CRC_NEXT
        LDA SI_CRC
        EOR #$21
        STA SI_CRC
        LDA SI_CRC+1
        EOR #$10
        STA SI_CRC+1
SC_CRC_NEXT:
        DEX
        BNE SC_CRC_BIT
        PLX
        RTS
SC_ABSOLUTE:
        LDA ST_WORD+1
        BPL SC_ABS_DONE
        LDA #0
        SEC
        SBC ST_WORD
        STA ST_WORD
        LDA #0
        SBC ST_WORD+1
        STA ST_WORD+1
SC_ABS_DONE:
        RTS
SC_HOURS:
        STZ ST_TEMP
SC_DIVIDE:
        LDA ST_WORD+1
        BNE SC_SUB60
        LDA ST_WORD
        CMP #60
        BCC SC_HOURS_DONE
SC_SUB60:
        SEC
        LDA ST_WORD
        SBC #60
        STA ST_WORD
        LDA ST_WORD+1
        SBC #0
        STA ST_WORD+1
        INC ST_TEMP
        BRA SC_DIVIDE
SC_HOURS_DONE:
        RTS
        INCLUDE "status-sram.inc"
SC_END:
        ENDMOD
        END
