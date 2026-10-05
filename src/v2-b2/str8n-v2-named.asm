; Named commands share the manager lifetime and service directory.
                        MODULE V2_NAMED
                        XDEF NAMED_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
                        INCLUDE "named-host-symbols.inc"
                        CODE
NAMED_REGISTER_ENTRY:   JMP NAMED_REGISTER
NAMED_DISPATCH_ENTRY:   JMP NAMED_DISPATCH
NAMED_LEGACY_ENTRY:     JMP NAMED_LEGACY_CONFLICT
NAMED_BAD:              LDA #$01
                        BRA NAMED_FAIL
NAMED_DUP:              LDA #$02
                        BRA NAMED_FAIL
NAMED_FULL:             LDA #$03
NAMED_FAIL:             CLC
                        RTS
NAMED_REGISTER:         CPY #$00
                        BNE NAMED_BAD
                        STA V2_BUF_PTR
                        STX V2_BUF_PTR+1
                        LDA MG_READY
                        CMP #$01
                        BNE NAMED_BAD
                        CPX #$02
                        BCC NAMED_BAD
                        CPX #$79
                        BCC NAMED_DESC_RAM
                        CPX #$80
                        BCC NAMED_BAD
                        CPX #$FF
                        BNE NAMED_DESC_OK
                        LDA V2_BUF_PTR
                        CMP #$FD
                        BCS NAMED_BAD
                        BRA NAMED_DESC_OK
NAMED_DESC_RAM:         CPX #$78
                        BNE NAMED_DESC_OK
                        LDA V2_BUF_PTR
                        CMP #$FD
                        BCS NAMED_BAD
NAMED_DESC_OK:          LDY #$02
                        LDA (V2_BUF_PTR),Y
                        STA V2_FLASH_PTR
                        INY
                        LDA (V2_BUF_PTR),Y
                        STA V2_FLASH_PTR+1
                        TAX
                        JSR NAMED_PIN
                        BCC NAMED_BAD
                        LDY #$00
                        LDA (V2_BUF_PTR),Y
                        STA V2_ADDR
                        INY
                        LDA (V2_BUF_PTR),Y
                        STA V2_ADDR+1
                        TAX
                        JSR NAMED_PIN
                        BCC NAMED_BAD
                        LDY #$00
NAMED_VALIDATE:         LDA (V2_ADDR),Y
                        BEQ NAMED_NAME_END
                        CMP #'A'
                        BCC NAMED_BAD
                        CMP #'Z'+1
                        BCS NAMED_BAD
                        INY
                        CPY #$10
                        BCS NAMED_BAD
                        BRA NAMED_VALIDATE
NAMED_NAME_END:         CPY #$00
                        BEQ NAMED_BAD
                        STY V2_LAST
                        TYA
                        CLC
                        ADC V2_ADDR
                        PHA
                        LDA V2_ADDR+1
                        ADC #$00
                        TAX
                        PLA
                        BCS NAMED_BAD
                        JSR NAMED_PIN
                        BCC NAMED_BAD
                        LDA V2_LAST
                        CMP #$01
                        BNE NAMED_COMPACT_CHECK
                        LDY #$00
                        LDA (V2_ADDR),Y
                        LDX #$09
NAMED_CORE_CHECK:      CMP NAMED_CORE_KEYS,X
                        BEQ NAMED_BAD
                        DEX
                        BPL NAMED_CORE_CHECK
                        LDX #$00
NAMED_LETTER_CHECK:     CPX MG_COUNT
                        BEQ NAMED_SCAN_START
                        CMP MG_TABLE,X
                        BEQ NAMED_DUP
                        INX
                        INX
                        INX
                        BRA NAMED_LETTER_CHECK
; Preserve compact address forms such as DABCD and MFFFF.
NAMED_COMPACT_CHECK:    CMP #$06
                        BCS NAMED_SCAN_START
                        LDY #$00
                        LDA (V2_ADDR),Y
                        CMP #'D'
                        BEQ NAMED_COMPACT_HEX
                        CMP #'M'
                        BEQ NAMED_COMPACT_HEX
                        CMP #'F'
                        BEQ NAMED_COMPACT_HEX
                        CMP #'G'
                        BEQ NAMED_COMPACT_HEX
                        CMP #'I'
                        BNE NAMED_SCAN_START
NAMED_COMPACT_HEX:      INY
                        LDA (V2_ADDR),Y
                        BEQ NAMED_BAD
                        CMP #'A'
                        BCC NAMED_SCAN_START
                        CMP #'F'+1
                        BCC NAMED_COMPACT_HEX
NAMED_SCAN_START:       LDA MG_NAMED_COUNT
                        CMP #$21
                        BCS NAMED_BAD
                        AND #$03
                        BNE NAMED_BAD
                        LDX #$00
NAMED_SCAN:             CPX MG_NAMED_COUNT
                        BEQ NAMED_INSERT
                        LDA MG_NAMED_TABLE,X
                        STA V2_PTR
                        LDA MG_NAMED_TABLE+1,X
                        STA V2_PTR+1
                        LDY #$00
NAMED_COMPARE:          LDA (V2_ADDR),Y
                        CMP (V2_PTR),Y
                        BNE NAMED_NEXT
                        CMP #$00
                        BEQ NAMED_DUP
                        INY
                        CPY #$10
                        BNE NAMED_COMPARE
NAMED_NEXT:             INX
                        INX
                        INX
                        INX
                        BRA NAMED_SCAN
NAMED_INSERT:           CPX #$20
                        BCS NAMED_FULL
                        LDA V2_ADDR
                        STA MG_NAMED_TABLE,X
                        LDA V2_ADDR+1
                        STA MG_NAMED_TABLE+1,X
                        LDA V2_FLASH_PTR
                        STA MG_NAMED_TABLE+2,X
                        LDA V2_FLASH_PTR+1
                        STA MG_NAMED_TABLE+3,X
                        TXA
                        CLC
                        ADC #$04
                        STA MG_NAMED_COUNT
                        LDA #$00
                        SEC
                        RTS
; Same pinned target/name windows as legacy commands: overlay/module RAM,
; resident B..E ROM. The caller must keep name bytes immutable until reset.
NAMED_PIN:              CPX #$B0
                        BCC NAMED_PIN_RAM
                        CPX #$F0
                        BCC NAMED_PIN_OK
                        BRA NAMED_PIN_BAD
NAMED_PIN_RAM:          CPX #$58
                        BCC NAMED_PIN_BAD
                        CPX #$60
                        BCC NAMED_PIN_OK
                        CPX #$71
                        BCC NAMED_PIN_BAD
                        CPX #$79
                        BCS NAMED_PIN_BAD
NAMED_PIN_OK:           SEC
                        RTS
NAMED_PIN_BAD:          CLC
                        RTS
NAMED_DISPATCH:         LDA MG_NAMED_COUNT
                        CMP #$21
                        BCS NAMED_UNHANDLED
                        AND #$03
                        BNE NAMED_UNHANDLED
                        LDX #$00
NAMED_DISPATCH_NEXT:    CPX MG_NAMED_COUNT
                        BEQ NAMED_UNHANDLED
                        LDA MG_NAMED_TABLE,X
                        STA V2_PTR
                        LDA MG_NAMED_TABLE+1,X
                        STA V2_PTR+1
                        LDY #$00
NAMED_MATCH:            LDA (V2_PTR),Y
                        BEQ NAMED_BOUNDARY
                        CMP V2_LINE,Y
                        BNE NAMED_DISPATCH_SKIP
                        INY
                        CPY #$10
                        BNE NAMED_MATCH
NAMED_DISPATCH_SKIP:    INX
                        INX
                        INX
                        INX
                        BRA NAMED_DISPATCH_NEXT
NAMED_BOUNDARY:         LDA V2_LINE,Y
                        BEQ NAMED_FOUND
                        CMP #' '
                        BNE NAMED_DISPATCH_SKIP
NAMED_FOUND:            LDA MG_NAMED_TABLE+2,X
                        STA MG_CALL
                        LDA MG_NAMED_TABLE+3,X
                        STA MG_CALL+1
                        TYA
                        TAX
NAMED_ARG_SPACES:       LDA V2_LINE,X
                        CMP #' '
                        BNE NAMED_CALL
                        INX
                        BRA NAMED_ARG_SPACES
NAMED_CALL:             JMP (MG_CALL)
NAMED_UNHANDLED:        LDA #$00
                        RTS
; Preserve A (legacy key) and the legacy target scratch pointer.
NAMED_LEGACY_CONFLICT:  STA V2_LAST
                        LDX #$00
NAMED_LEGACY_NEXT:      CPX MG_NAMED_COUNT
                        BEQ NAMED_LEGACY_OK
                        CPX #$20
                        BCS NAMED_LEGACY_OK
                        LDA MG_NAMED_TABLE,X
                        STA V2_PTR
                        LDA MG_NAMED_TABLE+1,X
                        STA V2_PTR+1
                        LDY #$00
                        LDA (V2_PTR),Y
                        CMP V2_LAST
                        BNE NAMED_LEGACY_SKIP
                        INY
                        LDA (V2_PTR),Y
                        BEQ NAMED_LEGACY_DUP
NAMED_LEGACY_SKIP:      INX
                        INX
                        INX
                        INX
                        BRA NAMED_LEGACY_NEXT
NAMED_LEGACY_OK:        LDA V2_LAST
                        CLC
                        RTS
NAMED_LEGACY_DUP:       LDA V2_LAST
                        SEC
                        RTS
NAMED_END:
                        ENDMOD
                        END
