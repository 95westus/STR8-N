; Fixed 2512 b14 MON removal/restore kit. No caller-supplied flash address.
; X accepts only the backed-up image or an already blank MON sector.
; T restores only the two embedded original MON images, commit byte last.
; JE reserves wear before each erase. All busy execution stays in RAM.
MA_PAGE EQU $7C70
MA_PAGES EQU $7C71
MA_MODE EQU $7C72
MA_CHECKED EQU $7C73
MA_START:
        SEI
        CLD
        LDA #3
        JSR V2W_SELECT
        LDA #1
        STA DC_BINARY
        JSR V2W_RX_RESET
        STZ V2_NMI_HOLD
        JSR J_CRC_INIT
        LDA #<MA_START
        STA V2_PTR
        LDA #>MA_START
        STA V2_PTR+1
MA_SELF:
        LDA (V2_PTR)
        JSR J_CRC_BYTE
        INC V2_PTR
        BNE MA_SELF_CHECK
        INC V2_PTR+1
MA_SELF_CHECK:
        LDA V2_PTR
        CMP #<MA_SUM
        BNE MA_SELF
        LDA V2_PTR+1
        CMP #>MA_SUM
        BNE MA_SELF
        LDA J_CRC
        CMP MA_SUM
        BNE MA_BAD
        LDA J_CRC+1
        CMP MA_SUM+1
        BNE MA_BAD
        JSR J_CRC_INIT
        STZ V2_PTR
        LDA #$F0
        STA V2_PTR+1
MA_F_CRC:
        LDA (V2_PTR)
        JSR J_CRC_BYTE
        INC V2_PTR
        BNE MA_F_CRC
        INC V2_PTR+1
        BNE MA_F_CRC
        LDA J_CRC
        CMP #F_SUM_LO
        BNE MA_BAD
        LDA J_CRC+1
        CMP #F_SUM_HI
        BNE MA_BAD
        LDX #<MA_MENU
        LDY #>MA_MENU
        JSR BOOT_PRINT
MA_COMMAND:
        JSR V2W_GETC
        CMP #'Q'
        BEQ MA_QUIT
        CMP #'X'
        BEQ MA_DESTROY
        CMP #'T'
        BEQ MA_RESTORE
        JMP MA_BAD
MA_DESTROY:
        STZ MA_MODE
        ; Verify BOTH exact preimages before the first journal mutation.
        LDA #$A0
        STA MA_PAGE
        JSR MA_ACCEPT
        BCC MA_BAD
        LDA #$B0
        STA MA_PAGE
        JSR MA_ACCEPT
        BCC MA_BAD
        BRA MA_BEGIN
MA_RESTORE:
        LDA #1
        STA MA_MODE
MA_BEGIN:
        LDA #$A0
        STA MA_PAGE
MA_SLOT:
        JSR MA_TARGET
        LDA MA_MODE
        BEQ MA_X_BLANK
        JSR MA_COMPARE
        BCS MA_NEXT
        BRA MA_ERASE
MA_X_BLANK:
        JSR MA_BLANK
        BCS MA_NEXT
MA_ERASE:
        LDA MA_PAGE
        CMP #$A0
        BEQ MA_COUNT_A
        CMP #$B0
        BNE MA_BAD
        LDA #27
        BRA MA_COUNT
MA_COUNT_A:
        LDA #26
MA_COUNT:
        STA J_COUNTINDEX
        LDA #2
        JSR JE_ENTER
        BCC MA_BAD
        JSR MA_TARGET
        LDA #1
        STA V2_NMI_HOLD
        STZ V2_FLASH_ERROR
        JSR V2W_ERASE_RAW+2
        BCC MA_BAD
        JSR MA_BLANK
        BCC MA_BAD
        LDA MA_MODE
        BEQ MA_NEXT
        JSR MA_TARGET
MA_PROGRAM:
        ; Commit stays FF until all other bytes have been read back.
        LDA V2_FLASH_PTR+1
        CMP MA_PAGE
        BNE MA_PROGRAM_DATA
        LDA V2_FLASH_PTR
        CMP #31
        BEQ MA_PROGRAM_NEXT
MA_PROGRAM_DATA:
        LDA (V2_BUF_PTR)
        CMP #$FF
        BEQ MA_PROGRAM_NEXT
        STA V2_FLASH_DATA
        JSR V2W_BYTE+2
        BCC MA_BAD
MA_PROGRAM_NEXT:
        INC V2_BUF_PTR
        BNE MA_PROGRAM_PTR
        INC V2_BUF_PTR+1
MA_PROGRAM_PTR:
        INC V2_FLASH_PTR
        BNE MA_PROGRAM
        INC V2_FLASH_PTR+1
        DEC MA_PAGES
        BNE MA_PROGRAM
        JSR MA_COMPARE_UNCOMMITTED
        BCC MA_BAD
        JSR MA_TARGET
        LDA #31
        STA V2_FLASH_PTR
        STZ V2_FLASH_DATA
        JSR V2W_BYTE+2
        BCC MA_BAD
        JSR MA_COMPARE
        BCC MA_BAD
MA_NEXT:
        STZ V2_NMI_HOLD
        LDA MA_PAGE
        CMP #$A0
        BNE MA_DONE
        LDA #$B0
        STA MA_PAGE
        JMP MA_SLOT
MA_DONE:
        LDX #<MA_OK
        LDY #>MA_OK
        JSR BOOT_PRINT
MA_QUIT:
        STZ V2_NMI_HOLD
        STZ DC_BINARY
        JSR V2W_RX_RESET
        JMP $F004
MA_BAD:
        LDA #3
        JSR V2W_SELECT
        STZ V2_NMI_HOLD
        STZ DC_BINARY
        LDX #<MA_ERROR
        LDY #>MA_ERROR
        JSR BOOT_PRINT
        JMP BOOT_RECOVERY
MA_ACCEPT:
        JSR MA_COMPARE
        BCS MA_ACCEPT_OK
        JSR MA_BLANK
        RTS
MA_ACCEPT_OK:
        SEC
        RTS
MA_TARGET:
        LDA #3
        JSR V2W_SELECT
        STZ V2_FLASH_PTR
        LDA MA_PAGE
        STA V2_FLASH_PTR+1
        CMP #$A0
        BEQ MA_SOURCE_A
        LDA #<MA_IMAGE_B
        STA V2_BUF_PTR
        LDA #>MA_IMAGE_B
        BRA MA_SOURCE_HIGH
MA_SOURCE_A:
        LDA #<MA_IMAGE_A
        STA V2_BUF_PTR
        LDA #>MA_IMAGE_A
MA_SOURCE_HIGH:
        STA V2_BUF_PTR+1
        LDA #16
        STA MA_PAGES
        RTS
MA_BLANK:
        JSR MA_TARGET
MA_BLANK_BYTE:
        LDA (V2_FLASH_PTR)
        CMP #$FF
        BNE MA_COMPARE_BAD
        INC V2_FLASH_PTR
        BNE MA_BLANK_BYTE
        INC V2_FLASH_PTR+1
        DEC MA_PAGES
        BNE MA_BLANK_BYTE
        SEC
        RTS
MA_COMPARE_UNCOMMITTED:
        LDA #1
        BRA MA_COMPARE_ENTRY
MA_COMPARE:
        LDA #0
MA_COMPARE_ENTRY:
        STA MA_CHECKED
        JSR MA_TARGET
MA_COMPARE_BYTE:
        LDA MA_CHECKED
        BEQ MA_COMPARE_DATA
        LDA V2_FLASH_PTR+1
        CMP MA_PAGE
        BNE MA_COMPARE_DATA
        LDA V2_FLASH_PTR
        CMP #31
        BNE MA_COMPARE_DATA
        LDA (V2_FLASH_PTR)
        CMP #$FF
        BNE MA_COMPARE_BAD
        BRA MA_COMPARE_NEXT
MA_COMPARE_DATA:
        LDA (V2_FLASH_PTR)
        CMP (V2_BUF_PTR)
        BNE MA_COMPARE_BAD
MA_COMPARE_NEXT:
        INC V2_BUF_PTR
        BNE MA_COMPARE_PTR
        INC V2_BUF_PTR+1
MA_COMPARE_PTR:
        INC V2_FLASH_PTR
        BNE MA_COMPARE_BYTE
        INC V2_FLASH_PTR+1
        DEC MA_PAGES
        BNE MA_COMPARE_BYTE
        SEC
        RTS
MA_COMPARE_BAD:
        CLC
        RTS
MA_MENU: DB "MON KIT X=eraseAB T=restoreAB Q=boot> ",0
MA_OK: DB 13,10,"MON KIT DONE",13,10,0
MA_ERROR: DB 13,10,"MON KIT REFUSED/FAILED",13,10,0
