; Compact cache: eight 24-byte rows, wholly inside the existing state reservation.
; Name[12], bank, conflict flag, start[2], exclusive end[2], unused[6].
MAP_APP_OWNER EQU $613D
MAP_APP_SLOT EQU $613E
MAP_APP_OFFSET EQU $613F
MAP_APPS EQU $6140

MAP_APP_PREPARE:       LDX #$00
MAP_APP_CLEAR:         STZ MAP_APPS,X
                        INX
                        CPX #$C0
                        BNE MAP_APP_CLEAR
                        LDA #$03
                        JSR V2W_SELECT
                        LDA #$03
                        STA V2_SELECTED
                        LDX #$03
MAP_APP_EXT_HEADER:    LDA $E000,X
                        CMP MAP_APP_EXT_ID,X
                        BNE MAP_APP_PREP_DONE
                        DEX
                        BPL MAP_APP_EXT_HEADER
                        LDX #$07
MAP_APP_CAPABILITY:    LDA $E6E0,X
                        CMP MAP_APP_CAP_ID,X
                        BNE MAP_APP_PREP_DONE
                        DEX
                        BPL MAP_APP_CAPABILITY
                        LDX #$03
MAP_APP_TABLE_HEADER:  LDA $E6F0,X
                        CMP MAP_APP_TABLE_ID,X
                        BNE MAP_APP_PREP_DONE
                        DEX
                        BPL MAP_APP_TABLE_HEADER
                        LDA $E011
                        CMP #$4C
                        BNE MAP_APP_PREP_DONE
                        JSR MAP_CRC_INIT
                        STZ SRC
                        LDA #$E0
                        STA SRC+1
MAP_APP_EXT_CRC:       LDA (SRC)
                        JSR MAP_CRC_BYTE
                        INC SRC
                        BNE MAP_APP_EXT_CRC
                        INC SRC+1
                        LDA SRC+1
                        CMP #$E8
                        BNE MAP_APP_EXT_CRC
                        LDA J_CRC
                        ORA J_CRC+1
                        BNE MAP_APP_PREP_DONE
                        STZ MAP_APP_SLOT
                        STZ MAP_APP_OFFSET
MAP_APP_PROBE:         JSR CHECK_CANCEL
                        LDA MAP_APP_SLOT
                        JSR $E011
                        BCC MAP_APP_NEXT
                        LDA MAP_APP_OFFSET
                        CLC
                        ADC #$40
                        STA SRC
                        LDA #$61
                        STA SRC+1
                        LDY #$0F
MAP_APP_COPY:          LDA $7D90,Y
                        STA (SRC),Y
                        DEY
                        BPL MAP_APP_COPY
                        LDY #$0D
                        LDA #$00
                        STA (SRC),Y
                        LDA $7DC4
                        LDY #$10
                        STA (SRC),Y
                        INY
                        LDA $7DC5
                        STA (SRC),Y
MAP_APP_NEXT:          LDA MAP_APP_OFFSET
                        CLC
                        ADC #$18
                        STA MAP_APP_OFFSET
                        INC MAP_APP_SLOT
                        LDA MAP_APP_SLOT
                        CMP #$08
                        BNE MAP_APP_PROBE
                        JSR MAP_APP_CONFLICTS
MAP_APP_PREP_DONE:     RTS

; Shared sectors are ambiguous for a sector map. Suppress every conflicting
; descriptor, even if its exact byte extent does not overlap another image.
MAP_APP_CONFLICTS:     LDX #$00
MAP_APP_OUTER:         TXA
                        CLC
                        ADC #$18
                        TAY
MAP_APP_PAIR:          CPY #$C0
                        BEQ MAP_APP_OUTER_NEXT
                        LDA MAP_APPS,X
                        BEQ MAP_APP_PAIR_NEXT
                        LDA MAP_APPS,Y
                        BEQ MAP_APP_PAIR_NEXT
                        LDA MAP_APPS+12,X
                        CMP MAP_APPS+12,Y
                        BNE MAP_APP_PAIR_NEXT
                        LDA MAP_APPS+15,X
                        AND #$F0
                        STA BYTE
                        LDA MAP_APPS+17,Y
                        PHA
                        LDA MAP_APPS+16,Y
                        BNE MAP_APP_Y_END
                        PLA
                        DEC A
                        BRA MAP_APP_Y_LAST
MAP_APP_Y_END:         PLA
MAP_APP_Y_LAST:        AND #$F0
                        CMP BYTE
                        BCC MAP_APP_PAIR_NEXT
                        LDA MAP_APPS+15,Y
                        AND #$F0
                        STA BYTE
                        LDA MAP_APPS+17,X
                        PHA
                        LDA MAP_APPS+16,X
                        BNE MAP_APP_X_END
                        PLA
                        DEC A
                        BRA MAP_APP_X_LAST
MAP_APP_X_END:         PLA
MAP_APP_X_LAST:        AND #$F0
                        CMP BYTE
                        BCC MAP_APP_PAIR_NEXT
                        LDA #$01
                        STA MAP_APPS+13,X
                        STA MAP_APPS+13,Y
MAP_APP_PAIR_NEXT:     TYA
                        CLC
                        ADC #$18
                        TAY
                        BRA MAP_APP_PAIR
MAP_APP_OUTER_NEXT:    TXA
                        CLC
                        ADC #$18
                        TAX
                        CPX #$C0
                        BNE MAP_APP_OUTER
                        RTS

MAP_APP_LOOKUP:        LDX #$00
MAP_APP_FIND:          LDA MAP_APPS,X
                        BEQ MAP_APP_FIND_NEXT
                        LDA MAP_APPS+13,X
                        BNE MAP_APP_FIND_NEXT
                        LDA MAP_APPS+12,X
                        CMP MAPBANK
                        BNE MAP_APP_FIND_NEXT
                        LDA MAP_APPS+15,X
                        AND #$F0
                        CMP MAPSEC
                        BCC MAP_APP_CHECK_END
                        BNE MAP_APP_FIND_NEXT
MAP_APP_CHECK_END:     LDA MAP_APPS+17,X
                        PHA
                        LDA MAP_APPS+16,X
                        BNE MAP_APP_END_HIGH
                        PLA
                        DEC A
                        BRA MAP_APP_LAST_HIGH
MAP_APP_END_HIGH:      PLA
MAP_APP_LAST_HIGH:     AND #$F0
                        CMP MAPSEC
                        BCC MAP_APP_FIND_NEXT
                        STX MAP_APP_OWNER
                        LDA MAP_APPS+16,X
                        STA MAP_OWNER_END
                        LDA MAP_APPS+17,X
                        STA MAP_OWNER_END+1
                        TXA
                        CLC
                        ADC #$40
                        STA MAP_OWNER_LABEL
                        LDA #$61
                        STA MAP_OWNER_LABEL+1
                        LDA #'+'
                        STA MAP_KIND
                        LDA MAP_APPS+15,X
                        AND #$F0
                        CMP MAPSEC
                        BNE MAP_APP_FOUND
                        LDA #'P'
                        STA MAP_KIND
MAP_APP_FOUND:         SEC
                        RTS
MAP_APP_FIND_NEXT:     TXA
                        CLC
                        ADC #$18
                        TAX
                        CPX #$C0
                        BNE MAP_APP_FIND
                        CLC
                        RTS

MAP_APP_VECTORS:       LDX #$00
MAP_APP_VECTOR_NEXT:   LDA MAP_APPS,X
                        BEQ MAP_APP_VECTOR_SKIP
                        LDA MAP_APPS+13,X
                        BNE MAP_APP_VECTOR_SKIP
                        LDA MAP_APPS+12,X
                        CMP MAPBANK
                        BNE MAP_APP_VECTOR_SKIP
                        LDA #'V'
                        STA MAP_KIND
                        SEC
                        RTS
MAP_APP_VECTOR_SKIP:   TXA
                        CLC
                        ADC #$18
                        TAX
                        CPX #$C0
                        BNE MAP_APP_VECTOR_NEXT
                        CLC
                        RTS

; Show any bytes preceding a nonaligned app separately, preserving exact extent.
MAP_APP_PREFIX:        LDA MAP_START
                        BNE MAP_APP_PREFIX_SHOW
                        LDA MAP_START+1
                        CMP MAPSEC
                        BEQ MAP_APP_PREFIX_DONE
MAP_APP_PREFIX_SHOW:   LDA MAP_START+1
                        PHA
                        LDA MAP_START
                        PHA
                        LDA MAP_RANGE_END+1
                        PHA
                        LDA MAP_RANGE_END
                        PHA
                        SEC
                        LDA MAP_START
                        SBC #$01
                        STA MAP_RANGE_END
                        LDA MAP_START+1
                        SBC #$00
                        STA MAP_RANGE_END+1
                        STZ MAP_START
                        STZ SRC
                        LDA MAPSEC
                        STA MAP_START+1
                        STA SRC+1
MAP_APP_PREFIX_SCAN:   LDA (SRC)
                        CMP #$FF
                        BNE MAP_APP_PREFIX_USED
                        LDA SRC+1
                        CMP MAP_RANGE_END+1
                        BNE MAP_APP_PREFIX_ADV
                        LDA SRC
                        CMP MAP_RANGE_END
                        BEQ MAP_APP_PREFIX_ERASED
MAP_APP_PREFIX_ADV:    INC SRC
                        BNE MAP_APP_PREFIX_SCAN
                        INC SRC+1
                        BRA MAP_APP_PREFIX_SCAN
MAP_APP_PREFIX_ERASED: JSR MAP_RANGE_PREFIX
                        JSR MAP_DESC_ERASED
                        BRA MAP_APP_PREFIX_ACCESS
MAP_APP_PREFIX_USED:   JSR MAP_RANGE_PREFIX
                        JSR MAP_DESC_UNKNOWN
MAP_APP_PREFIX_ACCESS: JSR MAP_ACCESS
                        PLA
                        STA MAP_RANGE_END
                        PLA
                        STA MAP_RANGE_END+1
                        PLA
                        STA MAP_START
                        PLA
                        STA MAP_START+1
MAP_APP_PREFIX_DONE:   RTS

MAP_DESC_APP:          LDX #<MAP_APP_TEXT
                        LDY #>MAP_APP_TEXT
                        JSR PRINT
                        JMP MAP_RECORD_LABEL
MAP_DESC_APP_PAD:      LDX #<MAP_APP_PAD_TEXT
                        LDY #>MAP_APP_PAD_TEXT
                        JSR PRINT
                        JSR MAP_RECORD_LABEL
                        LDX #<MAP_APP_PAD_END
                        LDY #>MAP_APP_PAD_END
                        JMP PRINT
MAP_DESC_VECTORS:      LDX #<MAP_APP_VECTOR_TEXT
                        LDY #>MAP_APP_VECTOR_TEXT
                        JMP PRINT

MAP_APP_EXT_ID:        DB "NA",$01,$3F
MAP_APP_CAP_ID:        DB "MP",$01,$08,$11,$E0,$90,$7D
MAP_APP_TABLE_ID:      DB "AT",$01,$08
MAP_APP_TEXT:          DB "APP ",0
MAP_APP_PAD_TEXT:      DB "Erased; ",0
MAP_APP_PAD_END:       DB " sector padding",0
MAP_APP_VECTOR_TEXT:   DB "Application-bank vectors",0
