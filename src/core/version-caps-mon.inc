; Replacement of AP_TRY only. The legacy AP_CHECK/S/R/T/B29 gates stay closed.
AP_TRY:
        LDX #7
VX_MATCH_VERSION:
        LDA V2_LINE,X
        CMP VX_VERSION_WORD,X
        BNE VX_TRY_CAPS
        DEX
        BPL VX_MATCH_VERSION
        BRA VX_MON_TRY
VX_TRY_CAPS:
        LDX #4
VX_MATCH_CAPS:
        LDA V2_LINE,X
        CMP VX_CAPS_WORD,X
        BNE AP_UNHANDLED
        DEX
        BPL VX_MATCH_CAPS
VX_MON_TRY:
        JSR VX_DISCOVER
        BCC VX_MON_ABSENT
        LDA #V2_IMAGE_PAGE
        JMP VX_COMMAND_ENTRY
VX_MON_ABSENT:
        LDX #0
VX_MON_BAD_TEXT:
        LDA VX_UNAVAILABLE_TEXT,X
        BEQ VX_MON_HANDLED
        JSR STR8V2_RAM_PUTC
        INX
        BRA VX_MON_BAD_TEXT
VX_MON_HANDLED:
        SEC
        RTS
AP_UNHANDLED:
        CLC
        RTS
; Public candidate DISCOVER at MON facade offset AE. Does not publish RAM.
VX_DISCOVER:
        LDX #3
VX_SIGNATURE_CHECK:
        LDA VX_BASE,X
        CMP VX_EXPECTED_HEADER,X
        BNE VX_DISCOVER_BAD
        DEX
        BPL VX_SIGNATURE_CHECK
        LDA VX_BASE+16
        BNE VX_DISCOVER_BAD
        LDA VX_BASE+17
        CMP #$10
        BNE VX_DISCOVER_BAD
        LDA VX_BASE+31
        BNE VX_DISCOVER_BAD
        LDA VX_BASE+13
        CMP #1
        BNE VX_DISCOVER_BAD
        LDA VX_BASE+14
        CMP #1
        BNE VX_DISCOVER_BAD
        LDA VX_BASE+15
        CMP #VX_INFO_SIZE
        BNE VX_DISCOVER_BAD
        LDX #4
VX_ENTRY_CHECK:
        LDA VX_BASE,X
        CMP #$4C
        BNE VX_DISCOVER_BAD
        LDA VX_BASE+2,X
        CMP #$E0
        BCC VX_DISCOVER_BAD
        CMP #$F0
        BCS VX_DISCOVER_BAD
        CMP #$E0
        BNE VX_ENTRY_LAST_PAGE
        LDA VX_BASE+1,X
        CMP #$40
        BCC VX_DISCOVER_BAD
        BRA VX_ENTRY_IN_RANGE
VX_ENTRY_LAST_PAGE:
        CMP #$EF
        BNE VX_ENTRY_IN_RANGE
        LDA VX_BASE+1,X
        CMP #$C0
        BCS VX_DISCOVER_BAD
VX_ENTRY_IN_RANGE:
        INX
        INX
        INX
        CPX #10
        BNE VX_ENTRY_CHECK
        JSR AP_CRC_INIT
        STZ V2_PTR
        LDA #$E0
        STA V2_PTR+1
        LDY #0
VX_MON_CRC:
        LDA (V2_PTR),Y
        JSR AP_CRC_BYTE
        INY
        BNE VX_MON_CRC
        INC V2_PTR+1
        LDA V2_PTR+1
        CMP #$F0
        BNE VX_MON_CRC
        LDA J_CRC
        ORA J_CRC+1
        BNE VX_DISCOVER_BAD
        LDX #0
        LDY #$E0
        LDA #1
        SEC
        RTS
VX_DISCOVER_BAD:
        LDA #$80
        CLC
        RTS
VX_EXPECTED_HEADER: DB "VX",1,64
VX_VERSION_WORD: DB "VERSION",0
VX_CAPS_WORD: DB "CAPS",0
VX_UNAVAILABLE_TEXT: DB "VX1 unavailable",13,10,0
