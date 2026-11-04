; Read-only RevD probe/primary read. Executes inside the B2 status provider.
; Admit all PROGRAM ownership guards before reading ORB. That read captures
; the latch and acknowledges only disabled CB flags, as guarded PREP does.
; Never acknowledge an enabled/owned interrupt or clock SPI before admission.
MS_SRAM_READ:
        LDA ST_IER
        AND #$18
        BNE MS_SRAM_BAD
        LDA ST_PCR
        AND #$F0
        BNE MS_SRAM_BAD
        LDA ST_ACR
        AND #$1E
        BNE MS_SRAM_BAD
        LDA ST_DDR
        STA SI_DDR
        AND #$2F
        BNE MS_SRAM_BAD
        LDA ST_ORB
        TAY
        LDA ST_IFR
        AND #$18
        BNE MS_SRAM_BAD
        TYA
        STA SI_ORB
        AND #$FC
        ORA #$0C
        STA SI_PORT
        STA ST_ORB
        LDA SI_DDR
        AND #$DF
        ORA #$0F
        STA ST_DDR
        LDA #5
        JSR MS_SPI_COMMAND
        LDA #$FF
        JSR MS_SPI_BYTE
        PHA
        JSR MS_SPI_DESELECT
        PLA
        BEQ MS_SRAM_MODE
        CMP #$40
        BEQ MS_SRAM_MODE
        CMP #$80
        BNE MS_SRAM_RESTORE_BAD
MS_SRAM_MODE:
        STZ SI_INDEX
MS_SRAM_NEXT:
        LDA #3
        JSR MS_SPI_COMMAND
        LDA #0
        JSR MS_SPI_BYTE
        LDA #0
        JSR MS_SPI_BYTE
        LDA SI_INDEX
        JSR MS_SPI_BYTE
        LDA #$FF
        JSR MS_SPI_BYTE
        LDX SI_INDEX
        STA ST_RECORD,X
        JSR MS_SPI_DESELECT
        INC SI_INDEX
        LDA SI_INDEX
        CMP #64
        BCC MS_SRAM_NEXT
        SEC
        BRA MS_SRAM_RESTORE
MS_SRAM_RESTORE_BAD:
        CLC
MS_SRAM_RESTORE:
        LDA SI_DDR
        STA ST_DDR
        LDA SI_ORB
        STA ST_ORB
        RTS
MS_SRAM_BAD:
        CLC
        RTS
MS_SPI_COMMAND:
        PHA
        LDA SI_PORT
        AND #$FB
        STA SI_PORT
        STA ST_ORB
        PLA
        JMP MS_SPI_BYTE
MS_SPI_DESELECT:
        LDA SI_PORT
        ORA #$0C
        STA SI_PORT
        STA ST_ORB
        RTS
MS_SPI_BYTE:
        STA SI_TX
        LDX #8
MS_SPI_BIT:
        LDA #2
        TRB SI_PORT
        ASL SI_TX
        BCC MS_SPI_ZERO
        TSB SI_PORT
MS_SPI_ZERO:
        LDA SI_PORT
        STA ST_ORB
        INC A
        STA ST_ORB
        LDA ST_ORB
        ASL A
        ASL A
        ASL A
        ROL SI_RX
        LDA SI_PORT
        STA ST_ORB
        DEX
        BNE MS_SPI_BIT
        LDA SI_RX
        RTS
