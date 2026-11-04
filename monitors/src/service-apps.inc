; AP/02: aligned owner XIP image,32-byte header, PR05 and CRC-sealed payload.
; Retained AP/01 images/private providers are not admitted by this scanner.
AP_END EQU $68E6
AP_ENTRY EQU $68E8
AP_FOUND EQU $68EA
AP_MODE EQU $68EB
AP_BANK EQU $68EC
AP_PAGE EQU $68ED
AP_SAVED_BANK EQU $68EE
AP_SAVED_ENTRY EQU $68EF
AP_PAYCRC EQU $68F1
AP_NAME EQU $6828
AP_LABEL EQU $6834
AP_SAVED_END EQU $69D0
AP_LIST:
        STZ AP_MODE
        LDX #<AP_NATIVE_TEXT
        LDY #>AP_NATIVE_TEXT
        JSR S_PUTS
        BRA AP_SCAN_START
AP_LAUNCH:
        JSR S_SKIP
        BEQ S_UNHANDLED
        LDY #0
AP_TOKEN:
        LDA S_LINE,X
        BEQ AP_TOKEN_END
        CMP #' '
        BEQ AP_TOKEN_END
        CPY #11
        BCS S_UNHANDLED
        STA AP_NAME,Y
        INX
        INY
        BRA AP_TOKEN
AP_TOKEN_END:
        JSR S_END_ARGS
        BCC S_UNHANDLED
        LDA #0
AP_TOKEN_PAD:
        CPY #12
        BCS AP_TOKEN_READY
        STA AP_NAME,Y
        INY
        BRA AP_TOKEN_PAD
AP_TOKEN_READY:
        LDA #1
        STA AP_MODE
AP_SCAN_START:
        STZ AP_FOUND
        STZ AP_BANK
        LDA #$80
        STA AP_PAGE
AP_SCAN:
        LDA AP_BANK
        STA S_READ_BANK
        STZ S_ADDR
        LDA AP_PAGE
        STA S_ADDR+1
        JSR S_READ64
        JSR AP_VALIDATE
        BCC AP_NEXT
        LDA AP_MODE
        BNE AP_MATCH_NAME
        LDX #<AP_LABEL
        LDY #>AP_LABEL
        JSR S_PUTS
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA #'B'
        JSR STR8V2_RAM_PUTC
        LDA AP_BANK
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA AP_PAGE
        JSR STR8V2_RAM_HEX_OUT
        LDA #0
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        BRA AP_NEXT
AP_MATCH_NAME:
        LDY #11
AP_COMPARE:
        LDA AP_NAME,Y
        CMP AP_LABEL,Y
        BNE AP_NEXT
        DEY
        BPL AP_COMPARE
        LDA AP_END
        STA AP_SAVED_END
        LDA AP_END+1
        STA AP_SAVED_END+1
        INC AP_FOUND
        LDA AP_BANK
        STA AP_SAVED_BANK
        LDA AP_ENTRY
        STA AP_SAVED_ENTRY
        LDA AP_ENTRY+1
        STA AP_SAVED_ENTRY+1
AP_NEXT:
        CLC
        LDA AP_PAGE
        ADC #$10
        STA AP_PAGE
        BCS AP_BANK_NEXT
        LDA AP_BANK
        CMP #3
        BNE AP_SCAN
        LDA AP_PAGE
        CMP #$A0
        BCC AP_SCAN
AP_BANK_NEXT:
        INC AP_BANK
        LDA #$80
        STA AP_PAGE
        LDA AP_BANK
        CMP #4
        BCC AP_SCAN
        LDA AP_MODE
        BEQ AP_DONE
        LDA AP_FOUND
        CMP #1
        BNE AP_NO_UNIQUE
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE AP_RUN
        CLC
        LDA AP_SAVED_ENTRY
        ADC #5
        TAX
        LDA AP_SAVED_ENTRY+1
        ADC #0
        BCS AP_NO_UNIQUE
        CPX AP_SAVED_END
        SBC AP_SAVED_END+1
        BCS AP_NO_UNIQUE
        LDA AP_SAVED_BANK
        STA S_READ_BANK
        LDA AP_SAVED_ENTRY
        STA S_ADDR
        LDA AP_SAVED_ENTRY+1
        STA S_ADDR+1
        JSR S_READ64
        LDX #5
AP_BATCH_ID:
        LDA S_BUFFER,X
        CMP AP_BT,X
        BNE AP_NO_UNIQUE
        DEX
        BPL AP_BATCH_ID
AP_RUN:
        LDA AP_SAVED_ENTRY
        STA $FE
        LDA AP_SAVED_ENTRY+1
        STA $FF
        LDA AP_SAVED_BANK
        STA S_F_SELECTED
        JMP SB_F_EXECUTE
AP_NO_UNIQUE:
        LDA #WB_REFUSED
        STA WB_RESULT
        LDX #<AP_MISSING_TEXT
        LDY #>AP_MISSING_TEXT
        JMP S_MESSAGE
AP_DONE:
        JMP S_HANDLED
AP_VALIDATE:
        LDX #7
AP_HEADER_MAGIC:
        LDA S_BUFFER,X
        CMP AP_MAGIC,X
        BNE AP_BAD
        DEX
        BPL AP_HEADER_MAGIC
        LDA S_BUFFER+12
        ORA S_BUFFER+13
        BNE AP_BAD
        LDA S_BUFFER+14
        CMP #1
        BNE AP_BAD
        JSR STR8V2_RAM_BOARD_QUERY
        CPX #2
        BEQ AP_CPU_MATCH
        CPX #$16
        BNE AP_BAD
AP_CPU_MATCH:
        TXA
        CMP S_BUFFER+15
        BNE AP_BAD
        LDA S_BUFFER+27
        BNE AP_BAD
        JSR S_CRC_INIT
        LDY #0
AP_HEADER_CRC:
        LDA S_BUFFER,Y
        JSR S_CRC_BYTE
        INY
        CPY #28
        BCC AP_HEADER_CRC
        LDA S_CRC
        CMP S_BUFFER+28
        BNE AP_BAD
        LDA S_CRC+1
        CMP S_BUFFER+29
        BNE AP_BAD
        LDA S_BUFFER+8
        LDX S_BUFFER+9
        BNE AP_LENGTH
        CMP #33
        BCC AP_BAD
AP_LENGTH:
        STA AP_END
        TXA
        CLC
        ADC AP_PAGE
        BCS AP_BAD
        STA AP_END+1
        CMP #$FF
        BCC AP_BANK_LIMIT
        BNE AP_BAD
        LDA AP_END
        CMP #$E1
        BCS AP_BAD
AP_BANK_LIMIT:
        LDA AP_BANK
        CMP #3
        BNE AP_ENTRY_CHECK
        LDA AP_END+1
        CMP #$A0
        BCC AP_ENTRY_CHECK
        BNE AP_BAD
        LDA AP_END
        BNE AP_BAD
AP_ENTRY_CHECK:
        LDA S_BUFFER+10
        STA AP_ENTRY
        SEC
        SBC #32
        LDA S_BUFFER+11
        STA AP_ENTRY+1
        SBC AP_PAGE
        BCC AP_BAD
        LDA AP_ENTRY
        CMP AP_END
        LDA AP_ENTRY+1
        SBC AP_END+1
        BCS AP_BAD
        STZ S_BYTE
        LDY #0
AP_NAME_CHECK:
        LDA S_BUFFER+16,Y
        STA AP_LABEL,Y
        BEQ AP_NAME_ZERO
        LDX S_BYTE
        BNE AP_BAD
        CMP #$21
        BCC AP_BAD
        CMP #'-'
        BEQ AP_NAME_NEXT
        CMP #'_'
        BEQ AP_NAME_NEXT
        CMP #'0'
        BCC AP_BAD
        CMP #'9'+1
        BCC AP_NAME_NEXT
        CMP #'A'
        BCC AP_BAD
        CMP #'Z'+1
        BCS AP_BAD
        BRA AP_NAME_NEXT
AP_NAME_ZERO:
        INC S_BYTE
AP_NAME_NEXT:
        INY
        CPY #12
        BCC AP_NAME_CHECK
        LDA AP_LABEL
        BEQ AP_BAD
        LDA S_BUFFER+30
        STA AP_PAYCRC
        LDA S_BUFFER+31
        STA AP_PAYCRC+1
        LDA #32
        STA S_ADDR
        LDA AP_PAGE
        STA S_ADDR+1
        JSR S_CRC_INIT
AP_PAYLOAD_BLOCK:
        JSR S_READ64
        LDY #0
AP_PAYLOAD_BYTE:
        LDA S_BUFFER,Y
        JSR S_CRC_BYTE
        INC S_ADDR
        BNE AP_ADDRESS_NEXT
        INC S_ADDR+1
AP_ADDRESS_NEXT:
        LDA S_ADDR
        CMP AP_END
        BNE AP_MORE
        LDA S_ADDR+1
        CMP AP_END+1
        BEQ AP_PAYLOAD_END
AP_MORE:
        INY
        CPY #64
        BCC AP_PAYLOAD_BYTE
        BRA AP_PAYLOAD_BLOCK
AP_PAYLOAD_END:
        LDA S_CRC
        CMP AP_PAYCRC
        BNE AP_BAD
        LDA S_CRC+1
        CMP AP_PAYCRC+1
        BNE AP_BAD
        SEC
        RTS
AP_BAD:
        CLC
        RTS
AP_BT: DB $80,4,"BT",1,1
AP_MAGIC: DB "AP",2,32,"PR05"
AP_NATIVE_TEXT: DB "CLOCK B2:B000; FLASH B2:E000; MAINT B1:8000",13,10
        DB "R tool; EDU SRAM WORK; T; R/APP name",13,10,0
AP_MISSING_TEXT: DB "REFUSED: app missing/invalid/duplicate",13,10,0
