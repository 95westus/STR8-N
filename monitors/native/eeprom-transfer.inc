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
                        BEQ EE_LONG_14
                        JMP EE_VALIDATE_WRITE
EE_LONG_14:
        LDA $6BE2
        CMP #$FF
                        BEQ EE_LONG_17
                        JMP EE_VALIDATE_READ
EE_LONG_17:
        LDA $6BE3
        CMP #1
                        BEQ EE_LONG_20
                        JMP EE_BAD
EE_LONG_20:
                        JMP EE_READ_READY
EE_VALIDATE_READ:
        CMP #$F2
                        BEQ EE_LONG_24
                        JMP EE_ORDINARY_READ
EE_LONG_24:
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
                        BEQ EE_LONG_41
                        JMP EE_BAD
EE_LONG_41:
        STA IO_STORE+2
        LDA $6BE0
        CLC
        ADC $6BE3
                        BCC EE_LONG_46
                        JMP EE_BAD
EE_LONG_46:
        CMP #$C1
                        BCC EE_LONG_48
                        JMP EE_BAD
EE_LONG_48:
        LDA #1
        STA I_TX_LEFT
        STA I_FLAGS
        LDA $6BE3
        STA I_RX_LEFT
                        JMP EE_READY
EE_VALIDATE_WRITE:
        LDA $6BE2
        CMP #$80
                        BCC EE_LONG_58
                        JMP EE_BAD
EE_LONG_58:
        AND #7
        CLC
        ADC $6BE3
        CMP #9
                        BCC EE_LONG_63
                        JMP EE_BAD
EE_LONG_63:
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
                        BCS EE_LONG_79
                        JMP EE_RESTORE
EE_LONG_79:
        JSR TRANSFER
EE_RESTORE:
        STA $6BE5
        JSR RESTORE
        LDA $6BE5
EE_DONE:
        STZ BUSY
        PLP
        CMP #0
                        BNE EE_LONG_89
                        JMP EE_GOOD
EE_LONG_89:
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
                        BEQ EE_LONG_111
                        JMP EE_IN_USE
EE_LONG_111:
        INC BUSY
        LDA $6BE6
        CMP #$80             ; Reject signed zero; canonical zero is $00.
                        BNE EE_LONG_115
                        JMP EE_BAD
EE_LONG_115:
        STA $6BF9
        LDA #$6F
        STA I_ADDRESS
        JSR INIT
                        BCS EE_LONG_120
                        JMP EE_RESTORE
EE_LONG_120:
        JSR TRIM_READ
                        BCS EE_LONG_122
                        JMP EE_RESTORE
EE_LONG_122:
        LDA $6BA0
        AND #$70
                        BEQ EE_LONG_125
                        JMP TRIM_DENIED
EE_LONG_125:
        LDA $6BA0
        AND #$FB
        STA $6BF8
        CMP $6BA0
                        BNE EE_LONG_130
                        JMP TRIM_WRITE_VALUE
EE_LONG_130:
        ; Disable coarse before installing any new nonzero correction.
        LDA #7
        STA $6BC0
        LDA $6BF8
        STA $6BC1
        JSR TRIM_WRITE
                        BCS EE_LONG_137
                        JMP EE_RESTORE
EE_LONG_137:
        JSR TRIM_READ
                        BCS EE_LONG_139
                        JMP EE_RESTORE
EE_LONG_139:
        LDA $6BA0
        CMP $6BF8
                        BEQ EE_LONG_142
                        JMP TRIM_VERIFY_FAILED
EE_LONG_142:
TRIM_WRITE_VALUE:
        LDA $6BA1
        CMP $6BF9
                        BNE EE_LONG_146
                        JMP TRIM_VERIFY
EE_LONG_146:
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
                        BEQ EE_LONG_158
                        JMP TRIM_VERIFY_FAILED
EE_LONG_158:
        LDA $6BA1
        CMP $6BF9
                        BEQ EE_LONG_161
                        JMP TRIM_VERIFY_FAILED
EE_LONG_161:
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
