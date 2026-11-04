OI_TARGET:
        LDA OI_HEADER+6
        JSR V2W_SELECT
        STZ V2_FLASH_PTR
        LDA OI_HEADER+7
        STA V2_FLASH_PTR+1
        RTS
OI_TARGET_CRC:
        JSR OI_TARGET
        STZ OI_PTR
        LDA OI_HEADER+7
        STA OI_PTR+1
        LDA #16
        STA OI_PAGES
        JSR OI_CRC_INIT
OI_TARGET_CRC_BYTE:
        LDA (OI_PTR)
        JSR OI_CRC_BYTE
        INC OI_PTR
        BNE OI_TARGET_CRC_BYTE
        INC OI_PTR+1
        DEC OI_PAGES
        BNE OI_TARGET_CRC_BYTE
        RTS
OI_COMPARE:
        JSR OI_TARGET
        STZ V2_BUF_PTR
        LDA #$68
        STA V2_BUF_PTR+1
        LDA #16
        STA OI_PAGES
OI_COMPARE_BYTE:
        LDA (V2_FLASH_PTR)
        CMP (V2_BUF_PTR)
        BNE OI_COMPARE_BAD
        INC V2_BUF_PTR
        INC V2_FLASH_PTR
        BNE OI_COMPARE_BYTE
        INC V2_BUF_PTR+1
        INC V2_FLASH_PTR+1
        DEC OI_PAGES
        BNE OI_COMPARE_BYTE
        SEC
        RTS
OI_COMPARE_BAD:
        CLC
        RTS

