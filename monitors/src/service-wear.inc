; Read newest boot-selected snapshot; no journal service/writer is installed.
S_WEAR:
        JSR SB_F_BOOT_READ
        BCC SW_UNAVAILABLE
        LDA S_F_J_BEST+1
        CMP #$C0
        BCC SW_UNAVAILABLE
        CMP #$E0
        BCS SW_UNAVAILABLE
        STA S_PTR+1
        STA S_JOURNAL_PAGE
        STZ S_PTR
        LDY #0
SW_COPY:
        LDA (S_PTR),Y
        STA S_FRAME,Y
        INY
        BNE SW_COPY
        LDX #3
SW_MAGIC:
        LDA S_FRAME,X
        CMP SW_SNBT,X
        BNE SW_UNAVAILABLE
        DEX
        BPL SW_MAGIC
        LDA S_FRAME+4
        CMP #1
        BNE SW_UNAVAILABLE
        LDA S_FRAME+$FF
        BNE SW_UNAVAILABLE
        LDA S_FRAME+$FE
        CMP #$FF
        BNE SW_UNAVAILABLE
        JSR S_CRC_INIT
        LDY #0
SW_CRC:
        LDA S_FRAME,Y
        JSR S_CRC_BYTE
        INY
        CPY #$FC
        BCC SW_CRC
        LDA S_CRC
        CMP S_FRAME+$FC
        BNE SW_UNAVAILABLE
        LDA S_CRC+1
        CMP S_FRAME+$FD
        BNE SW_UNAVAILABLE
        LDX #<SW_TITLE
        LDY #>SW_TITLE
        JSR S_PUTS
        LDA S_JOURNAL_PAGE
        JSR STR8V2_RAM_HEX_OUT
        LDA #0
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        LDX #<SW_COLUMNS
        LDY #>SW_COLUMNS
        JSR S_PUTS
        STZ S_ROW_BANK
        LDA #$40
        STA S_COUNT_INDEX
SW_BANK:
        LDA #'B'
        JSR STR8V2_RAM_PUTC
        LDA S_ROW_BANK
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        LDA #' '
        JSR STR8V2_RAM_PUTC
        STZ S_ROW_PAGE
SW_COUNT:
        LDX S_COUNT_INDEX
        LDA S_FRAME+2,X
        JSR STR8V2_RAM_HEX_OUT
        LDX S_COUNT_INDEX
        LDA S_FRAME+1,X
        JSR STR8V2_RAM_HEX_OUT
        LDX S_COUNT_INDEX
        LDA S_FRAME,X
        JSR STR8V2_RAM_HEX_OUT
        LDA #' '
        JSR STR8V2_RAM_PUTC
        CLC
        LDA S_COUNT_INDEX
        ADC #3
        STA S_COUNT_INDEX
        INC S_ROW_PAGE
        LDA S_ROW_PAGE
        CMP #8
        BCC SW_COUNT
        JSR STR8V2_RAM_NEWLINE
        INC S_ROW_BANK
        LDA S_ROW_BANK
        CMP #4
        BCC SW_BANK
        LDX #<SW_FOOTER
        LDY #>SW_FOOTER
        JMP S_MESSAGE
SW_UNAVAILABLE:
        LDX #<SW_UNAVAILABLE_TEXT
        LDY #>SW_UNAVAILABLE_TEXT
        JMP S_MESSAGE
SW_SNBT: DB "SNBT"
SW_TITLE: DB "Tracked erase attempts (hex), snapshot B3:",0
SW_COLUMNS: DB "      8      9      A      B      C      D      E      F",13,10,0
SW_FOOTER: DB "* Prior physical wear unverified; these are tracked attempts.",13,10,0
SW_UNAVAILABLE_TEXT: DB "W: no valid committed boot/wear snapshot",13,10,0
