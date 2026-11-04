; Read-only flash service / fixed-range owner RAM restoration at $6800.
; Binary FTDI only. No flash mutator and no caller-controlled RAM addresses.
MS_BANK EQU $7C74
MS_PAGES EQU $7C75
MS_START:
        SEI
        CLD
        LDA #3
        JSR V2W_SELECT
        LDA #1
        STA DC_BINARY
        JSR V2W_RX_RESET
MS_MENU:
        LDX #<MS_PROMPT
        LDY #>MS_PROMPT
        JSR BOOT_PRINT
MS_COMMAND:
        JSR V2W_GETC
        CMP #'F'
        BEQ MS_FLASH
        CMP #'M'
        BEQ MS_RAM
        CMP #'Z'
        BEQ MS_ZP
        CMP #'W'
        BEQ MS_WRITE
        CMP #'Q'
        BEQ MS_QUIT
        CMP #'J'
        BEQ MS_BOOT
        BRA MS_BAD
MS_FLASH:
        JSR V2W_GETC
        CMP #4
        BCS MS_BAD
        STA MS_BANK
        STZ V2_PTR
        LDA #$80
        STA V2_PTR+1
        STA MS_PAGES
        LDA MS_BANK
        JSR V2W_SELECT
        BRA MS_SEND
MS_RAM:
        STZ V2_PTR
        LDA #2
        STA V2_PTR+1
        LDA #$63
        STA MS_PAGES
        BRA MS_SEND
MS_ZP:
        JSR J_CRC_INIT
        LDX #0
MS_ZP_BYTE:
        LDA $00,X
        PHA
        PHX
        JSR J_CRC_BYTE
        PLX
        PLA
        JSR V2W_PUTC
        BCC MS_LOCK
        INX
        CPX #$E0
        BNE MS_ZP_BYTE
        BRA MS_SUM
MS_SEND:
        ; J_CRC_BYTE lives in F; keep B3 visible except for the data fetch.
        LDA #3
        JSR V2W_SELECT
        JSR J_CRC_INIT
MS_SEND_BYTE:
        LDA V2_PTR+1
        BPL MS_RAM_FETCH
        LDA MS_BANK
        JSR V2W_SELECT
        LDA (V2_PTR)
        PHA
        LDA #3
        JSR V2W_SELECT
        PLA
        BRA MS_DATA
MS_RAM_FETCH:
        LDA (V2_PTR)
MS_DATA:
        PHA
        JSR J_CRC_BYTE
        PLA
        JSR V2W_PUTC
        BCC MS_LOCK
        INC V2_PTR
        BNE MS_SEND_BYTE
        INC V2_PTR+1
        DEC MS_PAGES
        BNE MS_SEND_BYTE
MS_SUM:
        LDA J_CRC
        JSR V2W_PUTC
        BCC MS_LOCK
        LDA J_CRC+1
        JSR V2W_PUTC
        BCC MS_LOCK
        JMP MS_MENU
MS_WRITE:
        ; Fixed 25344-byte restore. Trailer CRC is verified before success.
        JSR J_CRC_INIT
        STZ V2_PTR
        LDA #2
        STA V2_PTR+1
MS_WRITE_BYTE:
        JSR V2W_GETC
        STA (V2_PTR)
        JSR J_CRC_BYTE
        INC V2_PTR
        BNE MS_WRITE_BYTE
        INC V2_PTR+1
        LDA V2_PTR+1
        CMP #$65
        BNE MS_WRITE_BYTE
        JSR V2W_GETC
        CMP J_CRC
        BNE MS_LOCK
        JSR V2W_GETC
        CMP J_CRC+1
        BNE MS_LOCK
        LDA V2_RX_BAD
        BNE MS_LOCK
        JMP MS_MENU
MS_BOOT:
        STZ DC_BINARY
        JSR V2W_RX_RESET
        JMP $F004
MS_QUIT:
        STZ DC_BINARY
        LDA #3
        JSR BOOT_CON_SELECT
        JSR V2W_RX_RESET
        JMP BOOT_RECOVERY
MS_BAD:
        LDA #3
        JSR V2W_SELECT
        JMP MS_MENU
MS_LOCK:
        JMP MS_LOCK
MS_PROMPT: DB "RAM SERVICE> ",0
MS_END:
