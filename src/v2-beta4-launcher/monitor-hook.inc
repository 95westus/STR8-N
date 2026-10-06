; Candidate-only hook. Checked E000-E7FF extension, including its command table.
; Fixed F is unchanged; these private CRC helpers are pinned by its exact hash.
AP_TRY:                LDA V2_LINE
                       BEQ AP_UNHANDLED
                       JSR AP_CHECK
                       BCC AP_UNHANDLED
                       JMP $E008
AP_UNHANDLED:          CLC
                       RTS

AP_CHECK:              LDA $E000
                       CMP #'N'
                       BNE AP_BAD
                       LDA $E001
                       CMP #'A'
                       BNE AP_BAD
                       LDA $E002
                       CMP #$01
                       BNE AP_BAD
                       LDA $E003
                       CMP #$3F
                       BNE AP_BAD
                       JSR AP_CRC_INIT
                       STZ V2_PTR
                       LDA #$E0
                       STA V2_PTR+1
                       LDY #$00
AP_CHECK_LOOP:         LDA (V2_PTR),Y
                       JSR AP_CRC_BYTE
                       INY
                       BNE AP_CHECK_LOOP
                       INC V2_PTR+1
                       LDA V2_PTR+1
                       CMP #$E8
                       BNE AP_CHECK_LOOP
                       LDA J_CRC
                       ORA J_CRC+1
                       BNE AP_BAD
                       SEC
                       RTS
AP_BAD:                CLC
                       RTS

V2_SR_DISPATCH:        JSR AP_CHECK
                       BCC V2_SR_MISSING
                       JMP $E00B
V2_MAP_REQUEST:        JSR AP_CHECK
                       BCC V2_SR_MISSING
                       JMP $E00E
V2_SR_MISSING:         LDX #V2_SR_MISSING_TEXT
                       JMP V2_MESSAGE
