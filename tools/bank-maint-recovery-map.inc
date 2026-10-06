; Sector status remains E/U; legends describe reservations and recognized
; complete SR records beginning at a sector boundary, including continuations.
MAP_STATUS EQU $6128
MAP_OWNER_END EQU $6130
MAP_OWNER_LABEL EQU $6132

MAP_LEGENDS:            STZ MAP_OWNER_END
                        STZ MAP_OWNER_END+1
                        LDA #$80
                        STA MAPSEC
MAP_LEGEND_NEXT:        LDA MAPBANK
                        CMP #$03
                        BNE MAP_LEGEND_USED
                        LDA MAPSEC
                        CMP #$A0
                        BCS MAP_LEGEND_SHOW
MAP_LEGEND_USED:        LDA MAPSEC
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        TAX
                        LDA MAP_STATUS,X
                        CMP #'U'
                        BNE MAP_LEGEND_ADVANCE
MAP_LEGEND_SHOW:        JSR NL
                        LDA MAPBANK
                        JSR SPACE_NAME
                        LDA #':'
                        JSR PUTC
                        LDA MAPSEC
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        CMP #$0A
                        BCC MAP_LEGEND_DIGIT
                        ADC #$06
MAP_LEGEND_DIGIT:       CLC
                        ADC #'0'
                        JSR PUTC
                        LDA #' '
                        JSR PUTC
                        LDA MAPBANK
                        CMP #$03
                        BNE MAP_LEGEND_RECORD
                        LDA MAPSEC
                        CMP #$A0
                        BCC MAP_LEGEND_RECORD
                        SEC
                        SBC #$A0
                        LSR A
                        LSR A
                        LSR A
                        TAX
                        LDA MAP_RESERVED+1,X
                        TAY
                        LDA MAP_RESERVED,X
                        TAX
                        JSR PRINT
                        BRA MAP_LEGEND_ADVANCE
MAP_LEGEND_RECORD:      LDA MAPSEC
                        CMP MAP_OWNER_END+1
                        BCC MAP_LEGEND_CONTINUED
                        BNE MAP_LEGEND_HEADER
                        LDA MAP_OWNER_END
                        BNE MAP_LEGEND_CONTINUED
MAP_LEGEND_HEADER:      STZ SRC
                        LDA MAPSEC
                        STA SRC+1
                        JSR MAP_RECORD_HEADER
                        BCC MAP_LEGEND_UNKNOWN
                        LDX #<MAP_RECORD_TEXT
                        LDY #>MAP_RECORD_TEXT
                        JSR PRINT
                        JSR MAP_RECORD_LABEL
                        BRA MAP_LEGEND_ADVANCE
MAP_LEGEND_CONTINUED:   LDX #<MAP_RECORD_TEXT
                        LDY #>MAP_RECORD_TEXT
                        JSR PRINT
                        JSR MAP_RECORD_LABEL
                        LDX #<MAP_CONTINUED_TEXT
                        LDY #>MAP_CONTINUED_TEXT
                        JSR PRINT
                        BRA MAP_LEGEND_ADVANCE
MAP_LEGEND_UNKNOWN:     LDX #<MAP_UNKNOWN_TEXT
                        LDY #>MAP_UNKNOWN_TEXT
                        LDA MAPSEC
                        CMP #$F0
                        BNE MAP_LEGEND_PRINT
                        LDA $FFFD
                        BPL MAP_LEGEND_PRINT
                        CMP #$FF
                        BNE MAP_LEGEND_BOOT
                        LDA $FFFC
                        CMP #$FF
                        BEQ MAP_LEGEND_PRINT
MAP_LEGEND_BOOT:        LDX #<MAP_BOOT_TEXT
                        LDY #>MAP_BOOT_TEXT
MAP_LEGEND_PRINT:       JSR PRINT
MAP_LEGEND_ADVANCE:     LDA MAPSEC
                        CLC
                        ADC #$10
                        STA MAPSEC
                        BNE MAP_LEGEND_NEXT
                        JSR NL
                        RTS

MAP_RECORD_HEADER:     LDY #$00
                        LDA (SRC),Y
                        CMP #'S'
                        BNE MAP_HEADER_BAD
                        INY
                        LDA (SRC),Y
                        CMP #'R'
                        BNE MAP_HEADER_BAD
                        INY
                        LDA (SRC),Y
                        CMP #$01
                        BNE MAP_HEADER_BAD
                        INY
                        LDA (SRC),Y
                        CMP #$3F
                        BNE MAP_HEADER_BAD
                        LDY #$06
                        LDA (SRC),Y
                        STA CNT
                        INY
                        LDA (SRC),Y
                        STA CNT+1
                        ORA CNT
                        BEQ MAP_HEADER_BAD
                        LDA CNT
                        CLC
                        ADC #$18
                        STA CNT
                        LDA CNT+1
                        ADC SRC+1
                        BCS MAP_HEADER_BAD
                        STA CNT+1
                        CMP #$E0
                        BCC MAP_HEADER_LIMIT
                        BNE MAP_HEADER_BAD
                        LDA CNT
                        BNE MAP_HEADER_BAD
MAP_HEADER_LIMIT:      LDA MAPBANK
                        CMP #$03
                        BNE MAP_HEADER_LABEL
                        LDA CNT+1
                        CMP #$A0
                        BCC MAP_HEADER_LABEL
                        BNE MAP_HEADER_BAD
                        LDA CNT
                        BNE MAP_HEADER_BAD
MAP_HEADER_LABEL:      LDY #$08
MAP_HEADER_CHAR:       LDA (SRC),Y
                        BEQ MAP_HEADER_PAD
                        CMP #$21
                        BCC MAP_HEADER_BAD
                        CMP #$7F
                        BCS MAP_HEADER_BAD
                        INY
                        CPY #$18
                        BNE MAP_HEADER_CHAR
                        BRA MAP_HEADER_VALID
MAP_HEADER_PAD:        LDA (SRC),Y
                        BNE MAP_HEADER_BAD
                        INY
                        CPY #$18
                        BNE MAP_HEADER_PAD
MAP_HEADER_VALID:      LDA CNT
                        STA MAP_OWNER_END
                        LDA CNT+1
                        STA MAP_OWNER_END+1
                        LDA #$08
                        STA MAP_OWNER_LABEL
                        LDA SRC+1
                        STA MAP_OWNER_LABEL+1
                        SEC
                        RTS
MAP_HEADER_BAD:        CLC
                        RTS
MAP_RECORD_LABEL:      LDA MAP_OWNER_LABEL
                        STA SRC
                        LDA MAP_OWNER_LABEL+1
                        STA SRC+1
                        LDY #$00
MAP_RECORD_CHAR:       LDA (SRC),Y
                        BEQ MAP_RECORD_DONE
                        JSR PUTC
                        INY
                        CPY #$10
                        BNE MAP_RECORD_CHAR
MAP_RECORD_DONE:       RTS

MAP_RESERVED:          DW MAP_SLOT_A,MAP_SLOT_B,MAP_JOURNAL,MAP_JOURNAL,MAP_EXTENSION,MAP_RECOVERY
; The ACCESS column carries protection; avoid duplicating it in CONTENTS.
MAP_SLOT_A:            DB "Monitor slot A",0
MAP_SLOT_B:            DB "Monitor slot B",0
MAP_JOURNAL:           DB "Config/wear journal [reserved]",0
MAP_EXTENSION:         DB "S/R/T and preserved bytes",0
MAP_RECOVERY:          DB "Fixed boot/recovery and vectors",0
MAP_UNKNOWN_TEXT:      DB "Used; owner untagged",0
MAP_BOOT_TEXT:         DB "Boot image; see RESET vector",0
MAP_RECORD_TEXT:       DB "SR ",0
MAP_CONTINUED_TEXT:    DB " (continued)",0
