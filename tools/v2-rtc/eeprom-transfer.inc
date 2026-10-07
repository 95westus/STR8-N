; Private B3-only transport for the managed journal. Raw public EEPROM denied.
; Buffers/sizes are fixed to monitor scratch; pages never cross an 8-byte boundary.
EE_TRANSFER:
        PHP
        SEI
        CLD
        LDA BUSY
        BNE EE_IN_USE
        INC BUSY
        LDA $6BE3
        BEQ EE_BAD
        CMP #33
        BCS EE_BAD
        LDA $6BE4
        BNE EE_VALIDATE_WRITE
        LDA $6BE2
        CMP #$FF
        BNE EE_VALIDATE_READ
        LDA $6BE3
        CMP #1
        BNE EE_BAD
        BRA EE_READ_READY
EE_VALIDATE_READ:
        CMP #$80
        BCS EE_BAD
        CLC
        ADC $6BE3
        CMP #$81
        BCS EE_BAD
EE_READ_READY:
        LDA $6BE0
        STA IO_STORE+1
        LDA $6BE1
        CMP #$6B
        BNE EE_BAD
        STA IO_STORE+2
        LDA $6BE0
        CLC
        ADC $6BE3
        BCS EE_BAD
        CMP #$C1
        BCS EE_BAD
        LDA #1
        STA I_TX_LEFT
        STA I_FLAGS
        LDA $6BE3
        STA I_RX_LEFT
        BRA EE_READY
EE_VALIDATE_WRITE:
        LDA $6BE2
        CMP #$80
        BCS EE_BAD
        AND #7
        CLC
        ADC $6BE3
        CMP #9
        BCS EE_BAD
        LDA $6BE3
        INC A
        STA I_TX_LEFT
        STZ I_RX_LEFT
        STZ I_FLAGS
EE_READY:
        LDA $6BE2
        STA $6BC0
        LDA #$C0
        STA IO_LOAD+1
        LDA #$6B
        STA IO_LOAD+2
        LDA #$57
        STA I_ADDRESS
        JSR INIT
        BCC EE_RESTORE
        JSR TRANSFER
EE_RESTORE:
        STA $6BE5
        JSR RESTORE
        LDA $6BE5
EE_DONE:
        STZ BUSY
        PLP
        CMP #0
        BEQ EE_GOOD
        CLC
        RTS
EE_GOOD:
        SEC
        RTS
EE_BAD:
        LDA #9
        BRA EE_DONE
EE_IN_USE:
        PLP
        LDA #8
        CLC
        RTS
