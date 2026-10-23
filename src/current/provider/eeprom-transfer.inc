; Private B3-only transport for the managed journal. Raw public EEPROM denied.
; Buffers/sizes are fixed to monitor scratch; pages never cross an 8-byte boundary.
EE_TRANSFER:
        PHP
        SEI
        CLD
        LDA BUSY
                        BEQ EE_LONG_7
                        JMP EE_IN_USE
EE_LONG_7:
        INC BUSY
        LDA $6BE3
                        BNE EE_LONG_10
                        JMP EE_BAD
EE_LONG_10:
        CMP #33
                        BCC EE_LONG_12
                        JMP EE_BAD
EE_LONG_12:
        LDA $6BE4
                        BNE EE_VALIDATE_WRITE
        LDA $6BE2
        CMP #$FF
                        BNE EE_VALIDATE_READ
        LDA $6BE3
        CMP #1
                        BEQ EE_LONG_20
                        JMP EE_BAD
EE_LONG_20:
                        JMP EE_READ_READY
EE_VALIDATE_READ:
        CMP #$F2
                        BNE EE_ORDINARY_READ
        LDA $6BE3
        CMP #6
                        BEQ EE_LONG_27
                        JMP EE_BAD
EE_LONG_27:
                        JMP EE_READ_READY
EE_ORDINARY_READ:
        CMP #$80
                        BCC EE_LONG_31
                        JMP EE_BAD
EE_LONG_31:
        CLC
        ADC $6BE3
        CMP #$81
                        BCC EE_LONG_35
                        JMP EE_BAD
EE_LONG_35:
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
                        JMP EE_READY
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
                        JMP EE_DONE
EE_IN_USE:
        PLP
        LDA #8
        CLC
        RTS

 ; Private confirmed fine-trim update. Clear CRSTRIM, then write OSCTRIM.
; Preserve other controls; refuse active alarm/SQW; never alter calendar/PF/EEPROM.
TRIM_CONTROL:
        PHP
        SEI
        CLD
        LDA BUSY
                        BNE EE_IN_USE
        INC BUSY
        LDA $6BE6
        CMP #$80             ; Reject signed zero; canonical zero is $00.
                        BEQ EE_BAD
        STA $6BF9
        LDA #$6F
        STA I_ADDRESS
        JSR INIT
                        BCC EE_RESTORE
        JSR TRIM_READ
                        BCC EE_RESTORE
        LDA $6BA0
        AND #$70
                        BNE TRIM_DENIED
        LDA $6BA0
        AND #$FB
        STA $6BF8
        CMP $6BA0
                        BEQ TRIM_WRITE_VALUE
        ; Disable coarse before installing any new nonzero correction.
        LDA #7
        STA $6BC0
        LDA $6BF8
        STA $6BC1
        JSR TRIM_WRITE
                        BCC EE_RESTORE
        JSR TRIM_READ
                        BCC EE_RESTORE
        LDA $6BA0
        CMP $6BF8
                        BNE TRIM_VERIFY_FAILED
TRIM_WRITE_VALUE:
        LDA $6BA1
        CMP $6BF9
                        BEQ TRIM_VERIFY
        LDA #8
        STA $6BC0
        LDA $6BF9
        STA $6BC1
        JSR TRIM_WRITE
                        BCS EE_LONG_152
                        JMP EE_RESTORE
EE_LONG_152:
        JSR TRIM_READ
                        BCS EE_LONG_154
                        JMP EE_RESTORE
EE_LONG_154:
TRIM_VERIFY:
        LDA $6BA0
        CMP $6BF8
                        BNE TRIM_VERIFY_FAILED
        LDA $6BA1
        CMP $6BF9
                        BNE TRIM_VERIFY_FAILED
        LDA #0
                        JMP EE_RESTORE
TRIM_DENIED:
        LDA #6
                        JMP EE_RESTORE
TRIM_VERIFY_FAILED:
        LDA #7
                        JMP EE_RESTORE
TRIM_WRITE:
        LDA #$C0
        STA IO_LOAD+1
        LDA #$6B
        STA IO_LOAD+2
        LDA #2
        STA I_TX_LEFT
        STZ I_RX_LEFT
        STZ I_FLAGS
        JMP TRANSFER
TRIM_READ:
        LDA #$C0
        STA IO_LOAD+1
        LDA #$A0
        STA IO_STORE+1
        LDA #$6B
        STA IO_LOAD+2
        STA IO_STORE+2
        LDA #7
        STA $6BC0
        LDA #1
        STA I_TX_LEFT
        LDA #2
        STA I_RX_LEFT
        LDA #1
        STA I_FLAGS
        JMP TRANSFER
