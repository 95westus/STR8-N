; SRAM 1.1 layout reader: primary only. WORK repairs interrupted primary.
        MODULE SRAM_LAYOUT
        XDEF AUX_END
        INCLUDE "store-data-eq.inc"
        INCLUDE "store-core-eq.inc"
        CODE
SELECT_LAYOUT:
        JSR HEADER_CRC
        BNE LAYOUT_BAD
        LDA BUF
        CMP #'S'
        BNE LAYOUT_BAD
        LDA BUF+1
        CMP #'S'
        BNE LAYOUT_BAD
        LDA BUF+3
        CMP #8
        BNE LAYOUT_BAD
        LDA BUF+4
        CMP #8
        BNE LAYOUT_BAD
        LDA BUF+2
        CMP #1
        BEQ SELECT_LEGACY
        CMP #2
        BNE LAYOUT_BAD
        LDA BUF+7
        ORA BUF+62
        BNE LAYOUT_BAD
        LDX #59
LAYOUT_RESERVED:
        LDA BUF,X
        BNE LAYOUT_BAD
        DEX
        CPX #11
        BNE LAYOUT_RESERVED
        LDA BUF+8
        ORA BUF+9
        ORA BUF+10
        ORA BUF+11
        BEQ LAYOUT_BAD
        LDA BUF+5
        AND #$3F
        BNE LAYOUT_BAD
        LDA BUF+6
        BEQ SELECT_SMALL
        CMP #1
        BNE LAYOUT_BAD
        LDA BUF+5
        BNE LAYOUT_BAD
        BRA SELECT_OK
SELECT_SMALL:
        LDA BUF+5
        BEQ LAYOUT_BAD
SELECT_OK:
        LDA BUF+5
        STA LIMIT
        LDA #0
        RTS
SELECT_LEGACY:
        LDX #59
LEGACY_COMPARE:
        LDA BUF,X
        CMP LAYOUT,X
        BNE LAYOUT_BAD
        DEX
        BPL LEGACY_COMPARE
        BRA SELECT_OK
LAYOUT_BAD:
        LDA #$41
        RTS
EXTENT_LIMIT:
        BCC EXTENT_NORMAL
        BNE LAYOUT_BAD
        LDX LIMIT
        BNE LAYOUT_BAD
        BRA EXTENT_OK
EXTENT_NORMAL:
        LDX LIMIT
        BEQ EXTENT_OK
        CMP LIMIT
        BCC EXTENT_OK
        BNE LAYOUT_BAD
EXTENT_OK:
        LDA #0
        RTS
FREE_PAGES:
        LDA LIMIT
        SEC
        SBC #8
        SEC
        SBC USED
        RTS
FORMAT_GUARD:
        STZ ADDR
        STZ ADDR+1
        JSR READ_BLOCK
        BNE GUARD_RETURN
        JSR CHECK_V2
        BNE GUARD_RETURN
        LDA #$40
        STA ADDR
        LDA #2
        STA ADDR+1
        JSR READ_BLOCK
        BNE GUARD_RETURN
CHECK_V2:
        LDA BUF+2
        CMP #2
        BNE GUARD_OK
        LDA BUF+63
        CMP #$A5
        BNE GUARD_OK
        LDA BUF
        CMP #'S'
        BNE GUARD_OK
        LDA BUF+1
        CMP #'S'
        BNE GUARD_OK
        LDA #$49
GUARD_RETURN:
        RTS
GUARD_OK:
        LDA #0
        RTS
AUX_END:
        ENDMOD
        END
