; Reject erased/malformed names before emitting console bytes. Keep this
; helper after the resident service kernel in compact beta24 rebuilds.
AP_LIST_NAME_OK:       LDX #$03
AP_LIST_MAGIC_LOOP:    LDA AP_TABLE,X
                       CMP AP_LIST_MAGIC,X
                       BNE AP_LIST_BAD
                       DEX
                       BPL AP_LIST_MAGIC_LOOP
                       LDY #$00
                       LDA (V2_PTR),Y
                       BEQ AP_LIST_BAD
AP_LIST_CHECK_CHAR:    CMP #'A'
                       BCC AP_LIST_BAD
                       CMP #'Z'+1
                       BCS AP_LIST_BAD
                       INY
                       LDA (V2_PTR),Y
                       BEQ AP_LIST_CHECK_PAD
                       CPY #$0B
                       BCC AP_LIST_CHECK_CHAR
                       BRA AP_LIST_BAD
AP_LIST_CHECK_PAD:     INY
                       CPY #$0C
                       BEQ AP_LIST_GOOD
                       LDA (V2_PTR),Y
                       BEQ AP_LIST_CHECK_PAD
AP_LIST_BAD:           CLC
                       RTS
AP_LIST_GOOD:          SEC
                       RTS
AP_LIST_MAGIC:         DB "AT",$01,$08

; Full read-only descriptor/header/vector/image validation, rather than
; treating a committed flag alone as proof of an installed application.
AP_LIST_INSTALLED:     LDA #$08
                       SEC
                       SBC AP_ROWS
                       JMP AP_PROBE
