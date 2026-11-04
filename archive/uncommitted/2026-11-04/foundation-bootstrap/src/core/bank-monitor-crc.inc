OI_PRINT:
        STX OI_PTR
        STY OI_PTR+1
        LDY #0
OI_PRINT_BYTE:
        LDA (OI_PTR),Y
        BEQ OI_PRINT_DONE
        JSR V2W_PUTC
        BCC OI_PRINT_BAD
        INY
        BNE OI_PRINT_BYTE
        INC OI_PTR+1
        BRA OI_PRINT_BYTE
OI_PRINT_DONE:
        SEC
        RTS
OI_PRINT_BAD:
        CLC
        RTS

; Local RAM CRC is essential when arbitrary target flash overlays hide F.
; CRC16/CCITT-FALSE matches F exactly: polynomial1021, initFFFF, Y preserved.
OI_CRC_INIT:
        LDA #$FF
        STA OI_CRC
        STA OI_CRC+1
        RTS
OI_CRC_BYTE:
        EOR OI_CRC+1
        STA OI_CRC+1
        LDX #8
OI_CRC_BIT:
        ASL OI_CRC
        ROL OI_CRC+1
        BCC OI_CRC_NEXT
        LDA OI_CRC
        EOR #$21
        STA OI_CRC
        LDA OI_CRC+1
        EOR #$10
        STA OI_CRC+1
OI_CRC_NEXT:
        DEX
        BNE OI_CRC_BIT
        RTS

