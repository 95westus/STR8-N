OI_APPLY:
        JSR OI_TARGET
        LDA #1
        STA V2_NMI_HOLD
        STZ V2_FLASH_ERROR
        ; Skip the optional BRK $FC debugger tag. Arbitrary target banks need
        ; not contain interrupt vectors; only protected B3 journal calls use
        ; the normal tagged entries. IRQ is disabled throughout this tool.
        JSR V2W_ERASE_RAW+2
        BCC OI_FLASH_BAD
        JSR OI_TARGET
        LDA #16
        STA OI_PAGES
OI_ERASE_VERIFY:
        LDA (V2_FLASH_PTR)
        CMP #$FF
        BNE OI_FLASH_BAD
        INC V2_FLASH_PTR
        BNE OI_ERASE_VERIFY
        INC V2_FLASH_PTR+1
        DEC OI_PAGES
        BNE OI_ERASE_VERIFY
        JSR OI_TARGET
        STZ V2_BUF_PTR
        LDA #$68
        STA V2_BUF_PTR+1
        LDA #16
        STA OI_PAGES
OI_PROGRAM:
        LDA (V2_BUF_PTR)
        CMP #$FF
        BEQ OI_PROGRAM_NEXT
        STA V2_FLASH_DATA
        JSR V2W_BYTE+2
        BCC OI_FLASH_BAD
OI_PROGRAM_NEXT:
        INC V2_BUF_PTR
        INC V2_FLASH_PTR
        BNE OI_PROGRAM
        INC V2_BUF_PTR+1
        INC V2_FLASH_PTR+1
        DEC OI_PAGES
        BNE OI_PROGRAM
OI_PROGRAM_END:
        JSR OI_COMPARE
        BCC OI_FLASH_BAD
        JSR OI_TARGET_CRC
        LDA OI_CRC
        CMP OI_HEADER+12
        BNE OI_FLASH_BAD
        LDA OI_CRC+1
        CMP OI_HEADER+13
        BNE OI_FLASH_BAD
        LDX #<OI_OK_TEXT
        LDY #>OI_OK_TEXT
        JMP OI_FINISH
OI_IDENTICAL:
        LDX #<OI_SAME_TEXT
        LDY #>OI_SAME_TEXT
        JMP OI_FINISH
OI_PREIMAGE_BAD:
        LDX #<OI_PREIMAGE_TEXT
        LDY #>OI_PREIMAGE_TEXT
        JMP OI_FINISH
OI_JOURNAL_BAD:
        LDX #<OI_JOURNAL_TEXT
        LDY #>OI_JOURNAL_TEXT
        JMP OI_FINISH
OI_FLASH_BAD:
        LDX #<OI_FLASH_TEXT
        LDY #>OI_FLASH_TEXT
        JMP OI_FINISH
