SELECT_LAYOUT:
        LDA BUF+62
        BNE LAYOUT_BAD
        JSR HEADER_CRC
                        BEQ BM_LONG_8
                        JMP LAYOUT_BAD
BM_LONG_8:
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
                        JMP SELECT_OK
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
                        JMP SELECT_OK
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
