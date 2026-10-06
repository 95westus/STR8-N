; Three RAM-only map views. M defaults to ranges; T returns to maintenance.
MAP_VIEW EQU $6134
MAP_ONCE EQU $6135
MAP_META EQU $6136
MAP_RANGE_END EQU $6138
MAP_KIND EQU $613A
MAP_START EQU $613B
MAP_TABLE_RETURN EQU $613D

BM_MAP:                JSR SPACES
                        BEQ MAP_DEFAULT
                        JSR NUMBER
                        BCC BM_BAD
                        LDA NUM+1
                        BNE BM_BAD
                        LDA NUM
                        BEQ BM_BAD
                        CMP #$04
                        BCS BM_BAD
                        BRA MAP_ARGUMENT
MAP_DEFAULT:           LDA #$02
MAP_ARGUMENT:          STA MAP_VIEW
                        JSR ENDLINE
                        BCC BM_BAD
BM_MAP_START:          JSR $F0B2
                        STZ MAP_META
                        BCC MAP_NO_META
                        INC MAP_META
MAP_NO_META:           JSR MAP_APP_PREPARE
                        LDA MAP_VIEW
                        CMP #$01
                        BEQ MAP_GRID_TITLE
                        CMP #$03
                        BEQ MAP_DETAIL_TITLE
                        LDX #<MAP_RANGES_TEXT
                        LDY #>MAP_RANGES_TEXT
                        BRA MAP_TITLE
MAP_GRID_TITLE:        LDX #<MAP_GRID_TEXT
                        LDY #>MAP_GRID_TEXT
                        BRA MAP_TITLE
MAP_DETAIL_TITLE:      LDX #<MAP_DETAIL_TEXT
                        LDY #>MAP_DETAIL_TEXT
MAP_TITLE:             JSR PRINT
                        STZ MAPBANK
MAP_BANK:              JSR CHECK_CANCEL
                        LDA MAPBANK
                        JSR V2W_SELECT
                        LDA #$80
                        STA MAPSEC
MAP_SECTOR:            STZ SRC
                        LDA MAPSEC
                        STA SRC+1
                        LDX #$10
                        LDY #$00
MAP_SCAN:              LDA (SRC),Y
                        CMP #$FF
                        BNE MAP_USED
                        INY
                        BNE MAP_SCAN
                        INC SRC+1
                        DEX
                        BNE MAP_SCAN
                        LDA #'E'
                        BRA MAP_CHAR
MAP_USED:              LDA #'U'
MAP_CHAR:              PHA
                        LDA MAPSEC
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        TAY
                        PLA
                        STA MAP_STATUS,Y
                        LDA MAPSEC
                        CLC
                        ADC #$10
                        STA MAPSEC
                        BNE MAP_SECTOR
                        STZ MAP_OWNER_END
                        STZ MAP_OWNER_END+1
                        LDA #$FF
                        STA MAP_APP_OWNER
                        LDA #$80
                        STA MAPSEC
                        LDA MAP_VIEW
                        CMP #$01
                        BNE MAP_ROWS
                        LDA MAPBANK
                        JSR SPACE_NAME
                        LDA #' '
                        JSR PUTC
MAP_GRID_SECTOR:       JSR MAP_IDENTIFY
                        LDA MAP_KIND
                        JSR PUTC
                        LDA MAPBANK
                        CMP #$03
                        BNE MAP_GRID_INACTIVE
                        LDA MAPSEC
                        CMP BOOT_ACTIVE
                        BNE MAP_GRID_INACTIVE
                        LDA #'*'
                        BRA MAP_GRID_MARK
MAP_GRID_INACTIVE:     LDA #' '
MAP_GRID_MARK:         JSR PUTC
                        LDA #' '
                        JSR PUTC
                        LDA MAPSEC
                        CLC
                        ADC #$10
                        STA MAPSEC
                        BNE MAP_GRID_SECTOR
                        BRA MAP_BANK_END
MAP_ROWS:              JSR MAP_IDENTIFY
                        LDA MAP_VIEW
                        CMP #$02
                        BNE MAP_DETAIL_ROW
                        LDA MAP_KIND
                        CMP #'+'
                        BEQ MAP_ROW_ADVANCE
                        LDA MAPBANK
                        CMP #$03
                        BNE MAP_RANGE_ROW
                        LDA MAPSEC
                        CMP #$D0
                        BEQ MAP_ROW_ADVANCE
MAP_RANGE_ROW:         STZ MAP_START
                        LDA MAPSEC
                        STA MAP_START+1
                        LDA #$FF
                        STA MAP_RANGE_END
                        LDA MAPSEC
                        ORA #$0F
                        STA MAP_RANGE_END+1
                        LDA MAP_KIND
                        CMP #'S'
                        BNE MAP_RANGE_RESERVED
                        SEC
                        LDA MAP_OWNER_END
                        SBC #$01
                        STA MAP_RANGE_END
                        LDA MAP_OWNER_END+1
                        SBC #$00
                        STA MAP_RANGE_END+1
                        BRA MAP_RANGE_PRINT
MAP_RANGE_RESERVED:    LDA MAP_KIND
                        CMP #'P'
                        BNE MAP_RANGE_OTHER
                        LDX MAP_APP_OWNER
                        LDA MAP_APPS+14,X
                        STA MAP_START
                        LDA MAP_APPS+15,X
                        STA MAP_START+1
                        SEC
                        LDA MAP_OWNER_END
                        SBC #$01
                        STA MAP_RANGE_END
                        LDA MAP_OWNER_END+1
                        SBC #$00
                        STA MAP_RANGE_END+1
                        JSR MAP_APP_PREFIX
                        BRA MAP_RANGE_PRINT
MAP_RANGE_OTHER:       LDA MAPBANK
                        CMP #$03
                        BNE MAP_RANGE_PRINT
                        LDA MAPSEC
                        CMP #$C0
                        BNE MAP_RANGE_PRINT
                        LDA #$DF
                        STA MAP_RANGE_END+1
MAP_RANGE_PRINT:       JSR MAP_RANGE_PREFIX
                        JSR MAP_DESCRIPTION
                        JSR MAP_ACCESS
                        LDA MAP_KIND
                        CMP #'S'
                        BEQ MAP_RANGE_TAIL
                        CMP #'P'
                        BNE MAP_ROW_ADVANCE
MAP_RANGE_TAIL:
                        JSR MAP_RECORD_TAIL
                        BRA MAP_ROW_ADVANCE
MAP_DETAIL_ROW:        LDA MAPBANK
                        JSR SPACE_NAME
                        LDA #':'
                        JSR PUTC
                        LDA MAPSEC
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        JSR MAP_NIBBLE
                        JSR MAP_SPACE
                        LDA MAPSEC
                        JSR HEX
                        LDA #$00
                        JSR HEX
                        LDA #'-'
                        JSR PUTC
                        LDA MAPSEC
                        ORA #$0F
                        JSR HEX
                        LDA #$FF
                        JSR HEX
                        JSR MAP_SPACE
                        LDA MAPSEC
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        TAX
                        LDA MAP_STATUS,X
                        JSR PUTC
                        JSR MAP_SPACE
                        LDA MAP_META
                        BEQ MAP_WEAR_UNKNOWN
                        LDA MAPBANK
                        ASL A
                        ASL A
                        ASL A
                        STX BYTE
                        ORA BYTE
                        STA BYTE
                        ASL A
                        CLC
                        ADC BYTE
                        TAX
                        LDA $671A,X
                        JSR HEX
                        LDA $6719,X
                        JSR HEX
                        LDA $6718,X
                        JSR HEX
                        BRA MAP_WEAR_DONE
MAP_WEAR_UNKNOWN:     LDX #<MAP_UNKNOWN_COUNT
                        LDY #>MAP_UNKNOWN_COUNT
                        JSR PRINT
MAP_WEAR_DONE:         JSR MAP_SPACE
                        JSR MAP_DESCRIPTION
                        JSR MAP_ACCESS
MAP_ROW_ADVANCE:       LDA MAPSEC
                        CLC
                        ADC #$10
                        STA MAPSEC
                        BNE MAP_ROWS
MAP_BANK_END:          JSR NL
                        INC MAPBANK
                        LDA MAPBANK
                        CMP #$04
                        BNE MAP_BANK
                        LDA MAP_VIEW
                        CMP #$01
                        BEQ MAP_GRID_LEGEND
                        CMP #$03
                        BNE MAP_ACCESS_NOTE
                        LDX #<MAP_DETAIL_LEGEND_TEXT
                        LDY #>MAP_DETAIL_LEGEND_TEXT
                        JSR PRINT
                        BRA MAP_ACCESS_NOTE
MAP_GRID_LEGEND:
                        LDX #<MAP_LEGEND_TEXT
                        LDY #>MAP_LEGEND_TEXT
                        JSR PRINT
MAP_ACCESS_NOTE:        LDX #<MAP_ACCESS_NOTE_TEXT
                        LDY #>MAP_ACCESS_NOTE_TEXT
                        JSR PRINT
                        LDA MAP_ONCE
                        BEQ MAP_TO_MENU
                        STZ MAP_ONCE
                        LDA RESIDENT
                        JSR V2W_SELECT
                        JMP $F007
MAP_TO_MENU:           JMP BM_MENU

MAP_IDENTIFY:          LDA MAPSEC
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        TAX
                        LDA #'.'
                        LDY MAP_STATUS,X
                        CPY #'E'
                        BEQ MAP_STORE_KIND
                        LDA #'U'
MAP_STORE_KIND:        STA MAP_KIND
                        LDA MAPBANK
                        CMP #$03
                        BNE MAP_IDENTIFY_RECORD
                        LDA MAPSEC
                        CMP #$A0
                        BCC MAP_IDENTIFY_RECORD
                        SEC
                        SBC #$A0
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        TAX
                        LDA MAP_CODES,X
                        CPX #$03
                        BNE MAP_STORE_RESERVED
                        LDY MAP_STATUS+5
                        CPY #'E'
                        BNE MAP_STORE_RESERVED
                        LDA #'j'
MAP_STORE_RESERVED:    STA MAP_KIND
                        RTS
MAP_IDENTIFY_RECORD:   LDA MAP_APP_OWNER
                        CMP #$FF
                        BEQ MAP_IDENTIFY_SR
                        STZ MAP_OWNER_END
                        STZ MAP_OWNER_END+1
                        LDA #$FF
                        STA MAP_APP_OWNER
MAP_IDENTIFY_SR:       LDA MAPSEC
                        CMP MAP_OWNER_END+1
                        BCC MAP_IDENTIFY_CONT
                        BNE MAP_IDENTIFY_HEADER
                        LDA MAP_OWNER_END
                        BNE MAP_IDENTIFY_CONT
MAP_IDENTIFY_HEADER:   STZ SRC
                        LDA MAPSEC
                        STA SRC+1
                        JSR MAP_RECORD_HEADER
                        BCC MAP_IDENTIFY_APP
                        LDA #'S'
                        STA MAP_KIND
                        RTS
MAP_IDENTIFY_CONT:     LDA #'+'
                        STA MAP_KIND
                        RTS
MAP_IDENTIFY_APP:      JSR MAP_APP_LOOKUP
                        BCS MAP_IDENTIFY_DONE
MAP_IDENTIFY_BOOT:     LDA MAPSEC
                        CMP #$F0
                        BNE MAP_IDENTIFY_DONE
                        JSR MAP_APP_VECTORS
                        BCS MAP_IDENTIFY_DONE
                        LDA $FFFD
                        CMP #$80
                        BCC MAP_IDENTIFY_DONE
                        CMP #$FF
                        BNE MAP_IDENTIFY_IS_BOOT
                        LDA $FFFC
                        CMP #$FF
                        BEQ MAP_IDENTIFY_DONE
MAP_IDENTIFY_IS_BOOT:  LDA #'K'
                        STA MAP_KIND
MAP_IDENTIFY_DONE:     RTS

MAP_DESCRIPTION:      LDA MAP_KIND
                        CMP #'P'
                        BEQ MAP_DESC_APP
                        CMP #'V'
                        BEQ MAP_DESC_VECTORS
                        CMP #'S'
                        BEQ MAP_DESC_RECORD
                        CMP #'+'
                        BEQ MAP_DESC_CONT
                        CMP #'.'
                        BEQ MAP_DESC_ERASED
                        CMP #'K'
                        BEQ MAP_DESC_BOOT
                        LDA MAPBANK
                        CMP #$03
                        BNE MAP_DESC_UNKNOWN
                        LDA MAPSEC
                        CMP #$A0
                        BCC MAP_DESC_UNKNOWN
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
                        LDA MAPSEC
                        CMP #$C0
                        BCS MAP_DESC_DONE
                        STZ V2_PTR
                        STA V2_PTR+1
                        STA BOOT_DEST
                        JSR BOOT_SLOT_CHECK
                        BCC MAP_DESC_INVALID
                        LDX #<MAP_VALID_TEXT
                        LDY #>MAP_VALID_TEXT
                        JSR PRINT
                        LDY #$0B
MAP_DESC_GENERATION:   LDA (V2_PTR),Y
                        JSR HEX
                        DEY
                        CPY #$07
                        BNE MAP_DESC_GENERATION
                        LDA MAPSEC
                        CMP BOOT_ACTIVE
                        BNE MAP_DESC_DONE
                        LDX #<MAP_ACTIVE_TEXT
                        LDY #>MAP_ACTIVE_TEXT
                        JMP PRINT
MAP_DESC_INVALID:      LDX #<MAP_INVALID_TEXT
                        LDY #>MAP_INVALID_TEXT
                        JMP PRINT
MAP_DESC_RECORD:      LDX #<MAP_RECORD_TEXT
                        LDY #>MAP_RECORD_TEXT
                        JSR PRINT
                        JMP MAP_RECORD_LABEL
MAP_DESC_CONT:        LDA MAP_APP_OWNER
                        CMP #$FF
                        BEQ MAP_DESC_SR_CONT
                        JSR MAP_DESC_APP
                        BRA MAP_DESC_CONT_TEXT
MAP_DESC_SR_CONT:     JSR MAP_DESC_RECORD
MAP_DESC_CONT_TEXT:
                        LDX #<MAP_CONTINUED_TEXT
                        LDY #>MAP_CONTINUED_TEXT
                        JMP PRINT
MAP_DESC_ERASED:      LDX #<MAP_ERASED_TEXT
                        LDY #>MAP_ERASED_TEXT
                        JMP PRINT
MAP_DESC_BOOT:        LDX #<MAP_BOOT_TEXT
                        LDY #>MAP_BOOT_TEXT
                        JMP PRINT
MAP_DESC_UNKNOWN:     LDX #<MAP_UNKNOWN_TEXT
                        LDY #>MAP_UNKNOWN_TEXT
                        JMP PRINT
MAP_DESC_DONE:        RTS
MAP_ACCESS:           LDX #<MAP_WRITABLE_TEXT
                        LDY #>MAP_WRITABLE_TEXT
                        LDA MAPBANK
                        CMP #$03
                        BNE MAP_ACCESS_PRINT
                        LDA MAPSEC
                        CMP #$A0
                        BCC MAP_ACCESS_PRINT
                        LDX #<MAP_PROTECTED_TEXT
                        LDY #>MAP_PROTECTED_TEXT
MAP_ACCESS_PRINT:     JSR PRINT
                        JMP NL
MAP_RANGE_PREFIX:     LDA MAPBANK
                        JSR SPACE_NAME
                        JSR MAP_SPACE
                        LDA MAP_START+1
                        JSR HEX
                        LDA MAP_START
                        JSR HEX
                        LDA #'-'
                        JSR PUTC
                        LDA MAP_RANGE_END+1
                        JSR HEX
                        LDA MAP_RANGE_END
                        JSR HEX
MAP_SPACE:            LDA #' '
                        JMP PUTC
MAP_NIBBLE:           CMP #$0A
                        BCC MAP_DIGIT
                        ADC #$06
MAP_DIGIT:            CLC
                        ADC #'0'
                        JMP PUTC
MAP_RECORD_TAIL:      LDA MAP_OWNER_END
                        STA SRC
                        STA MAP_START
                        LDA MAP_OWNER_END+1
                        STA SRC+1
                        STA MAP_START+1
                        AND #$0F
                        ORA SRC
                        BEQ MAP_TAIL_DONE
                        LDA SRC+1
                        ORA #$0F
                        STA MAP_RANGE_END+1
                        LDA #$FF
                        STA MAP_RANGE_END
MAP_TAIL_SCAN:        LDA (SRC)
                        CMP #$FF
                        BNE MAP_TAIL_DONE
                        INC SRC
                        BNE MAP_TAIL_SCAN
                        INC SRC+1
                        LDA SRC+1
                        AND #$0F
                        BNE MAP_TAIL_SCAN
                        JSR MAP_RANGE_PREFIX
                        LDA MAP_KIND
                        CMP #'P'
                        BNE MAP_TAIL_SR
                        JSR MAP_DESC_APP_PAD
                        BRA MAP_TAIL_ACCESS
MAP_TAIL_SR:
                        JSR MAP_DESC_ERASED
MAP_TAIL_ACCESS:
                        JSR MAP_ACCESS
MAP_TAIL_DONE:        RTS

; The monitor prompt supports a one-shot RAM return for utility table calls.
BM_TABLE:             LDX INDEX
                        LDY #$01
                        LDA #'T'
                        STA V2_LINE
BM_TABLE_COPY:        LDA BM_LINE,X
                        STA V2_LINE,Y
                        BEQ BM_TABLE_GO
                        INX
                        INY
                        CPY #$28
                        BNE BM_TABLE_COPY
                        JMP BM_BAD
BM_TABLE_GO:          LDA #<BM_TABLE_DONE
                        STA $7DFA
                        LDA #>BM_TABLE_DONE
                        STA $7DFB
                        LDA #$54
                        STA $7DF9
                        LDA RESIDENT
                        JSR V2W_SELECT
                        JMP $E80E
BM_TABLE_DONE:        JMP BM_MENU

MAP_CODES:            DB "ABJJXR"
MAP_GRID_TEXT:        DB "   8  9  A  B  C  D  E  F",$0D,$0A,0
MAP_RANGES_TEXT:      DB "BANK RANGE CONTENTS ACCESS",$0D,$0A,0
MAP_DETAIL_TEXT:      DB "SECTOR RANGE E/U ERASE-ATTEMPTS CONTENTS ACCESS",$0D,$0A,0
MAP_LEGEND_TEXT:      DB "S record; + continued; U untagged; . erased; K boot-vector",$0D,$0A
                       DB "P application; V application-bank vectors",$0D,$0A
                       DB "A/B monitors; J/j journal used/erased; X extension; R recovery",$0D,$0A
                       DB "* active.",$0D,$0A,0
MAP_DETAIL_LEGEND_TEXT: DB "E = all FF; U = programmed. ERASE-ATTEMPTS are hexadecimal.",$0D,$0A,0
MAP_ACCESS_NOTE_TEXT:   DB "Erased does not mean available. B3:A-F protected.",$0D,$0A,0
MAP_ERASED_TEXT:      DB "Erased",0
MAP_VALID_TEXT:       DB " VALID gen ",0
MAP_INVALID_TEXT:     DB " INVALID",0
MAP_ACTIVE_TEXT:      DB " active",0
MAP_WRITABLE_TEXT:    DB " writable",0
MAP_PROTECTED_TEXT:   DB " protected",0
MAP_UNKNOWN_COUNT:    DB "??????",0
