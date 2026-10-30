; Exact-F adapter. Only called after RA/descriptor/whole-F CRC admission.
M_CHECK_F:
        LDA STR8V2_ID_LOCATOR
        CMP #'F'
        BNE M_F_FAIL
        LDA STR8V2_ID_LOCATOR+1
        CMP #'I'
        BNE M_F_FAIL
        LDA STR8V2_ID_LOCATOR+2
        STA M_PTR
        LDA STR8V2_ID_LOCATOR+3
        STA M_PTR+1
        CMP #$F0
        BCC M_F_FAIL
        CMP #$FF
        BNE M_DESCRIPTOR
        LDA M_PTR
        CMP #$C1
        BCS M_F_FAIL
M_DESCRIPTOR:
        LDY #39
M_DESCRIPTOR_BYTE:
        LDA (M_PTR),Y
        CMP M_EXPECT_ID,Y
        BNE M_F_FAIL
        DEY
        BPL M_DESCRIPTOR_BYTE
        LDA #$F0
        LDX #16
        JSR M_CRC_PAGES
        LDA M_CRC
        CMP #MON_F_CRC_LO
        BNE M_F_FAIL
        LDA M_CRC+1
        CMP #MON_F_CRC_HI
        BNE M_F_FAIL
        SEC
        RTS
M_F_FAIL:
        CLC
        RTS
M_MODULE_CHECK:
        LDX #7
M_MODULE_ID_BYTE:
        LDA WB_ORIGIN,X
        CMP M_MODULE_ID,X
        BNE M_F_FAIL
        DEX
        BPL M_MODULE_ID_BYTE
        LDA #>WB_ORIGIN
        LDX #WB_PAGES
        JSR M_CRC_PAGES
        LDA M_CRC
        ORA M_CRC+1
        BNE M_F_FAIL
        SEC
        RTS
M_MODULE_ID: DB "MW",WB_FORMAT,WB_PAGES,"PR05"
M_SERVICE_CHECK:
        LDX #7
M_SERVICE_ID_BYTE:
        LDA MON_SERVICE_BASE,X
        CMP M_SERVICE_ID,X
        BNE M_F_FAIL
        DEX
        BPL M_SERVICE_ID_BYTE
        LDA #>MON_SERVICE_BASE
        LDX #SB_PAGES
        JSR M_CRC_PAGES
        LDA M_CRC
        ORA M_CRC+1
        BNE M_F_FAIL
        SEC
        RTS
M_SERVICE_ID: DB "MS",SB_FORMAT,SB_PAGES,"PR05"
M_CRC_PAGES:
        STZ M_PTR
        STA M_PTR+1
        JSR M_CRC_START
        LDY #0
M_PAGES_NEXT:
        LDA (M_PTR),Y
        JSR M_CRC_BYTE
        INY
        BNE M_PAGES_NEXT
        INC M_PTR+1
        DEX
        BNE M_PAGES_NEXT
        RTS
M_BIND:
        LDA #3
        STA F_RESIDENT
        STZ F_DC_BINARY
        LDA #MON_SLOT_PAGE
        BEQ M_BIND_NO_SLOT
        STA F_BOOT_ACTIVE
M_BIND_NO_SLOT:
        LDA #<MON_F_NO_SERVICE
        STA F_JE_HANDLER
        LDA #>MON_F_NO_SERVICE
        STA F_JE_HANDLER+1
        RTS
; UI/1 caller has already admitted the MI image and reset console/stack.
; Bind the monitor's private F gates, retain session/cache, omit the banner.
M_QUIET_ENTRY:
        JSR M_BIND
        JMP M_PROMPT
M_READ_BYTES:
        LDA F_SELECTED
        PHA
        LDA M_BANK
        STA F_SELECTED
        LDA M_ADDR
        STA F_ADDR
        LDA M_ADDR+1
        STA F_ADDR+1
        LDA M_ROW
        STA F_COUNT
        JSR MON_F_READ
        LDX #0
M_READ_COPY:
        LDA F_BYTES,X
        STA M_BUFFER,X
        INX
        CPX M_ROW
        BCC M_READ_COPY
        PLA
        STA F_SELECTED
        RTS
M_EXECUTE:
        LDA M_BANK
        STA F_SELECTED
        LDA M_VALUE
        STA F_VECTOR
        LDA M_VALUE+1
        STA F_VECTOR+1
        JMP MON_F_EXECUTE
M_RECOVERY:
        SEI
        CLD
        JSR STR8V2_RAM_RX_RESET
        LDX #$FF
        TXS
        JMP MON_F_RECOVERY

; Read the newest boot-selected journal page, then validate its complete body.
; No journal service is installed and no erase/program opcode is invoked.
M_READ_WEAR:
        JSR MON_F_BOOT_READ
        BCC M_WEAR_BAD
        STZ M_PTR
        LDA F_J_BEST+1
        STA M_PTR+1
        CMP #$C0
        BCC M_WEAR_BAD
        CMP #$E0
        BCS M_WEAR_BAD
        LDY #0
M_WEAR_COPY:
        LDA (M_PTR),Y
        STA F_FRAME,Y
        INY
        BNE M_WEAR_COPY
        LDA F_FRAME+$FF
        BNE M_WEAR_BAD
        LDA F_FRAME+$FE
        CMP #$FF
        BNE M_WEAR_BAD
        JSR M_CRC_START
        LDY #0
M_WEAR_CRC:
        LDA F_FRAME,Y
        JSR M_CRC_BYTE
        INY
        CPY #$FC
        BNE M_WEAR_CRC
        LDA M_CRC
        CMP F_FRAME+$FC
        BNE M_WEAR_BAD
        LDA M_CRC+1
        CMP F_FRAME+$FD
        BNE M_WEAR_BAD
        STZ M_MAX
        STZ M_MAX+1
        STZ M_MAX+2
        STZ M_MAX_ROW
        STZ M_INDEX
        LDY #$40
M_WEAR_MAX:
        LDA F_FRAME+2,Y
        CMP M_MAX+2
        BCC M_WEAR_NEXT
        BNE M_WEAR_SET
        LDA F_FRAME+1,Y
        CMP M_MAX+1
        BCC M_WEAR_NEXT
        BNE M_WEAR_SET
        LDA F_FRAME,Y
        CMP M_MAX
        BCC M_WEAR_NEXT
        BEQ M_WEAR_NEXT
M_WEAR_SET:
        LDA F_FRAME,Y
        STA M_MAX
        LDA F_FRAME+1,Y
        STA M_MAX+1
        LDA F_FRAME+2,Y
        STA M_MAX+2
        LDA M_INDEX
        STA M_MAX_ROW
M_WEAR_NEXT:
        INY
        INY
        INY
        INC M_INDEX
        LDA M_INDEX
        CMP #32
        BCC M_WEAR_MAX
        SEC
        RTS
M_WEAR_BAD:
        CLC
        RTS
M_CRC_START:
        LDA #$FF
        STA M_CRC
        STA M_CRC+1
        RTS
M_CRC_BYTE:
        PHX
        EOR M_CRC+1
        STA M_CRC+1
        LDX #8
M_CRC_BIT:
        ASL M_CRC
        ROL M_CRC+1
        BCC M_CRC_NEXT
        LDA M_CRC
        EOR #$21
        STA M_CRC
        LDA M_CRC+1
        EOR #$10
        STA M_CRC+1
M_CRC_NEXT:
        DEX
        BNE M_CRC_BIT
        PLX
        RTS
M_EXPECT_ID:
        DB "NFI1",64,2,1,0,1,0,0,0
        DB "STR8N-F",0,"0.3.0",0,0,0,"BASE1",0,0,0,"PR05"
