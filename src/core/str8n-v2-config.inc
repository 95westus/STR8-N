; F now owns timeout/default booting; C controls its saved default target.
V2_COMMAND_C:
        LDA V2_LINE+1
        BEQ PC_SHOW
        CMP #' '
        BNE PC_BAD
        LDA V2_LINE+3
        BNE PC_BAD
        LDA V2_LINE+2
        STA JE_REQUEST
        JSR V2_CONFIRM
        BCC PC_CANCEL
        JSR BOOT_API_CFG
        BCC PC_FAILED
        JMP V2_FLASH_COMPLETE
PC_SHOW:
        JSR BOOT_API_READ
        BCC PC_FAILED
        LDA JE_FRAME+7
        JSR V2_PUTC
        JSR V2_NEWLINE
        JMP V2_PROMPT
PC_BAD: JMP V2_BAD_RANGE
PC_FAILED: JMP V2_FLASH_FAILED
PC_CANCEL: JMP V2_CANCELLED
V2_CONFIG_READ: JMP BOOT_API_READ
V2_CONFIG_SUM:
        STZ V2_CFG_SUM
        STZ V2_CFG_SUM2
        LDX #0
PC_SUM:
        LDA V2_CONFIG,X
        CLC
        ADC V2_CFG_SUM
        STA V2_CFG_SUM
        CLC
        ADC V2_CFG_SUM2
        STA V2_CFG_SUM2
        INX
        CPX #14
        BNE PC_SUM
        RTS
