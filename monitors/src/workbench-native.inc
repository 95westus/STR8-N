; Reserved native names are independent of selected owner bank/PROGRAM mount.
W_NATIVE_RESTORE:
        LDX #<WN_R_CLOCK
        LDY #>WN_R_CLOCK
        JSR W_MATCH
        BCS WC_COMMAND
        LDX #<WN_R_FLASH
        LDY #>WN_R_FLASH
        JSR W_MATCH
        BCS WC_FLASH
        LDX #<WN_R_MAINT
        LDY #>WN_R_MAINT
        JSR W_MATCH
        BCS WC_FLASH
        LDX #0
        RTS
W_NATIVE_CLOCK:
        LDA #0
        BRA W_NATIVE
W_NATIVE_BOARD:
        LDA #1
W_NATIVE:
        STA $6639
        LDA W_BATCH_ACTIVE
        BNE WN_REFUSED
        LDA W_BANK
        STA MU_BANK
        LDA #3
        JSR WB_F_SELECT
        LDX #0
WN_COPY:
        LDA $8C00,X
        STA $7000,X
        LDA $8D00,X
        STA $7100,X
        LDA $8E00,X
        STA $7200,X
        LDA $8F00,X
        STA $7300,X
        INX
        BNE WN_COPY
        JSR W_CRC_START
        STZ W_PTR
        LDA #$70
        STA W_PTR+1
        LDX #4
        LDY #0
WN_CRC:
        LDA (W_PTR),Y
        JSR W_CRC_BYTE
        INY
        BNE WN_CRC
        INC W_PTR+1
        DEX
        BNE WN_CRC
        LDA W_CRC
        ORA W_CRC+1
        BNE WN_REFUSED
        LDX #7
WN_ID:
        LDA $7000,X
        CMP WN_MAGIC,X
        BNE WN_REFUSED
        DEX
        BPL WN_ID
        LDX #<WN_RAM_TEXT
        LDY #>WN_RAM_TEXT
        JSR W_PUTS
        LDA $6639
        JMP $7008
WN_REFUSED:
        LDA #WB_REFUSED
        STA W_RESULT
        LDX #<WN_BAD_TEXT
        LDY #>WN_BAD_TEXT
        JMP W_MESSAGE
WN_R_CLOCK: DB "R CLOCK",0
WN_R_FLASH: DB "R FLASH",0
WN_R_MAINT: DB "R MAINT",0
WN_MAGIC: DB "NL",1,2,"PR05"
WN_RAM_TEXT: DB "Native overlay: RAM 2000-73FF; FLASH buffer through77FF; Q MON.",13,10,0
WN_BAD_TEXT: DB "REFUSED: native loader/active BATCH",13,10,0
