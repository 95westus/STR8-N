; Named console operations. Every path returns to the manager, not the prompt.
SR_CLI_SAVE:            JSR RTS_COMMAND_BEGIN
                        LDX #$01
                        JSR V2_HEX_WORD
                        BCC RTS_BAD_SAVE_A
                        LDA V2_VALUE
                        STA SR_REQUEST+3
                        LDA V2_VALUE+1
                        STA SR_REQUEST+4
                        JSR V2_HEX_WORD
                        BCC RTS_BAD_SAVE_A
                        LDA V2_VALUE
                        STA SR_REQUEST+5
                        LDA V2_VALUE+1
                        STA SR_REQUEST+6
                        JSR RTS_PARSE_NAME
                        BCC RTS_BAD_SAVE_A
                        JSR RTS_PARSE_FILTER
                        BCC RTS_BAD_SAVE_A
                        LDA SR_REQUEST+4
                        CMP #$02
                        BCC RTS_BAD_SAVE_A
                        CMP #$58
                        BCS RTS_BAD_SAVE_A
                        LDA SR_REQUEST+6
                        CMP #$58
                        BCS RTS_BAD_SAVE_A
                        LDA SR_REQUEST+5
                        SEC
                        SBC SR_REQUEST+3
                        STA RTS_NEED
                        LDA SR_REQUEST+6
                        SBC SR_REQUEST+4
                        BCC RTS_BAD_SAVE_A
                        STA RTS_NEED+1
                        LDA RTS_NEED
                        CLC
                        ADC #SR_HEADER_SIZE+1
                        STA RTS_NEED
                        BCC RTS_SAVE_FIND
                        INC RTS_NEED+1
RTS_SAVE_FIND:          JSR RTS_FIND
                        BCS RTS_SAVE_DUPLICATE
                        CMP #$06
                        BNE RTS_SAVE_ERROR
                        JSR RTS_ALLOCATE
                        BCC RTS_SAVE_ERROR
                        LDA #<SR_REQUEST
                        LDX #>SR_REQUEST
                        JSR SR_API_SAVE
                        JMP RTS_RESULT
RTS_BAD_SAVE_A:         JMP SR_CLI_BAD
RTS_SAVE_DUPLICATE:     LDA #$02
RTS_SAVE_ERROR:         JMP SR_CLI_ERROR

SR_CLI_RESTORE:         JSR RTS_COMMAND_BEGIN
                        LDX #$01
                        JSR RTS_PARSE_NAME
                        BCC SR_CLI_BAD
                        JSR RTS_PARSE_FILTER
                        BCC SR_CLI_BAD
                        JSR RTS_FIND
                        BCC SR_CLI_ERROR
                        LDA #<SR_REQUEST
                        LDX #>SR_REQUEST
                        JSR SR_API_RESTORE
RTS_RESULT:             BCC SR_CLI_ERROR
                        LDX #<RTS_DONE_TEXT
                        LDY #>RTS_DONE_TEXT
                        BRA RTS_MESSAGE
SR_CLI_BAD:             LDX #<RTS_BAD_TEXT
                        LDY #>RTS_BAD_TEXT
                        BRA RTS_MESSAGE
SR_CLI_ERROR:           CMP #$08
                        BEQ RTS_CANCELLED
                        PHA
                        LDX #<RTS_ERROR_TEXT
                        LDY #>RTS_ERROR_TEXT
                        JSR RTS_PRINT
                        PLA
                        JSR V2_HEX_OUT
                        BRA RTS_COMMAND_DONE
RTS_CANCELLED:          STZ V2_CANCEL_REQUEST
                        LDX #<RTS_CANCEL_TEXT
                        LDY #>RTS_CANCEL_TEXT
RTS_MESSAGE:            JSR RTS_PRINT
RTS_COMMAND_DONE:       LDA RTS_OLD_BANK
                        STA V2_SELECTED
                        LDA #$01
                        RTS
RTS_COMMAND_BEGIN:      LDA V2_SELECTED
                        STA RTS_OLD_BANK
                        LDA #$FF
                        STA RTS_FILTER
                        RTS
RTS_PRINT:              STX V2_ADDR
                        STY V2_ADDR+1
                        LDY #$00
RTS_PRINT_BYTE:         LDA (V2_ADDR),Y
                        BEQ RTS_PRINT_DONE
                        JSR V2_PUTC
                        INY
                        BRA RTS_PRINT_BYTE
RTS_PRINT_DONE:         RTS

RTS_PARSE_NAME:         JSR V2_SKIP_SPACES
                        LDY #$0F
                        LDA #$00
RTS_NAME_CLEAR:         STA SR_REQUEST+7,Y
                        DEY
                        BPL RTS_NAME_CLEAR
                        LDY #$00
RTS_NAME_BYTE:          LDA V2_LINE,X
                        BEQ RTS_NAME_END
                        CMP #' '
                        BEQ RTS_NAME_END
                        CPY #$10
                        BCS RTS_PARSE_FAIL
                        STA SR_REQUEST+7,Y
                        INY
                        INX
                        BRA RTS_NAME_BYTE
RTS_NAME_END:           CPY #$01
                        BCC RTS_PARSE_FAIL
                        SEC
                        RTS
RTS_PARSE_FILTER:       JSR V2_SKIP_SPACES
                        BEQ RTS_PARSE_OK
                        CMP #'B'
                        BNE RTS_PARSE_FAIL
                        INX
                        LDA V2_LINE,X
                        SEC
                        SBC #'0'
                        CMP #$04
                        BCS RTS_PARSE_FAIL
                        STA RTS_FILTER
                        INX
                        JSR V2_SKIP_SPACES
                        BNE RTS_PARSE_FAIL
RTS_PARSE_OK:           SEC
                        RTS
RTS_PARSE_FAIL:         CLC
                        RTS

; Scanner uses configured masks; excluded sectors are never read.
RTS_SCAN_BEGIN:         STZ RTS_BANK
                        STZ SR_RECORD
                        LDA #$80
                        STA SR_RECORD+1
RTS_SCAN_READY:         LDA RTS_BANK
                        CMP #$04
                        BCS RTS_SCAN_FINISHED
                        CMP RTS_FILTER
                        BEQ RTS_SCAN_POLICY
                        LDY RTS_FILTER
                        CPY #$FF
                        BNE RTS_SCAN_NEXT_BANK
RTS_SCAN_POLICY:        LDX RTS_BANK
                        LDA RTS_POLICY,X
                        AND #$3F
                        BEQ RTS_SCAN_NEXT_BANK
                        STX V2_SELECTED
                        LDA SR_RECORD+1
                        CMP #$E0
                        BCS RTS_SCAN_NEXT_BANK
                        JSR RTS_CURRENT_ALLOWED
                        BCS RTS_SCAN_POLL
                        LDA SR_RECORD+1
                        AND #$F0
                        CLC
                        ADC #$10
                        STA SR_RECORD+1
                        STZ SR_RECORD
                        STZ RTS_RUN
                        STZ RTS_RUN+1
                        BRA RTS_SCAN_READY
RTS_SCAN_NEXT_BANK:     INC RTS_BANK
                        STZ SR_RECORD
                        STZ RTS_RUN
                        STZ RTS_RUN+1
                        LDA #$80
                        STA SR_RECORD+1
                        BRA RTS_SCAN_READY
RTS_SCAN_POLL:          LDA SR_RECORD
                        BNE RTS_SCAN_OK
                        JSR V2_CHECK_CANCEL
                        BCS RTS_SCAN_CANCEL
RTS_SCAN_OK:            SEC
                        RTS
RTS_SCAN_CANCEL:        LDA #$08
                        CLC
                        RTS
RTS_SCAN_FINISHED:      LDA #$06
                        CLC
                        RTS
RTS_SCAN_ADVANCE:       INC SR_RECORD
                        BNE RTS_SCAN_READY
                        INC SR_RECORD+1
                        BRA RTS_SCAN_READY
RTS_SCAN_SKIP:          LDA SR_LIMIT
                        STA SR_RECORD
                        LDA SR_LIMIT+1
                        STA SR_RECORD+1
                        BRA RTS_SCAN_READY
RTS_CURRENT_ALLOWED:   LDA SR_RECORD+1
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        TAY
                        LDX RTS_BANK
                        LDA RTS_POLICY,X
                        AND RTS_SECTOR_BITS,Y
                        BEQ RTS_NOT_ALLOWED
                        SEC
                        RTS
RTS_NOT_ALLOWED:        CLC
                        RTS
; SR_VALIDATE bounds records below E000. All touched sectors must be permitted.
RTS_EXTENT_ALLOWED:     LDA SR_RECORD+1
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        TAY
                        LDA SR_LIMIT+1
                        LDX SR_LIMIT
                        BNE RTS_EXTENT_LAST
                        DEC A
RTS_EXTENT_LAST:        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        STA RTS_LAST_SECTOR
RTS_EXTENT_LOOP:        LDX RTS_BANK
                        LDA RTS_POLICY,X
                        AND RTS_SECTOR_BITS,Y
                        BEQ RTS_NOT_ALLOWED
                        CPY RTS_LAST_SECTOR
                        BEQ RTS_SCAN_OK
                        INY
                        BRA RTS_EXTENT_LOOP
RTS_RECORD_AT_CURSOR:   LDA SR_RECORD
                        STA SR_CURSOR
                        LDA SR_RECORD+1
                        STA SR_CURSOR+1
                        JSR SR_READ
                        CMP #'S'
                        BNE RTS_NOT_ALLOWED
                        JSR SR_HEADER_FITS
                        BCC RTS_NOT_ALLOWED
                        LDA SR_RECORD
                        CLC
                        ADC #SR_HEADER_SIZE
                        STA SR_LIMIT
                        LDA SR_RECORD+1
                        ADC #$00
                        STA SR_LIMIT+1
                        JSR RTS_EXTENT_ALLOWED
                        BCC RTS_NOT_ALLOWED
                        JSR SR_LOAD_HEADER
                        JSR SR_VALIDATE
                        BCC RTS_NOT_ALLOWED
                        JMP RTS_EXTENT_ALLOWED

; Find exactly one matching valid record, including pending records.
RTS_FIND:               STZ RTS_FOUND
                        JSR RTS_SCAN_BEGIN
RTS_FIND_NEXT:          BCC RTS_FIND_END
                        JSR RTS_RECORD_AT_CURSOR
                        BCC RTS_FIND_ADVANCE
                        LDY #$0F
RTS_FIND_NAME:          LDA SR_HEADER+8,Y
                        CMP SR_REQUEST+7,Y
                        BNE RTS_FIND_SKIP
                        DEY
                        BPL RTS_FIND_NAME
                        INC RTS_FOUND
                        LDA RTS_FOUND
                        CMP #$02
                        BCS RTS_FIND_AMBIGUOUS
                        LDA SR_RECORD
                        STA RTS_MATCH
                        LDA SR_RECORD+1
                        STA RTS_MATCH+1
                        LDA RTS_BANK
                        STA RTS_MATCH_BANK
RTS_FIND_SKIP:          JSR RTS_SCAN_SKIP
                        BRA RTS_FIND_NEXT
RTS_FIND_ADVANCE:       JSR RTS_SCAN_ADVANCE
                        BRA RTS_FIND_NEXT
RTS_FIND_AMBIGUOUS:     LDA #$05
                        CLC
                        RTS
RTS_FIND_END:           CMP #$08
                        BEQ RTS_FIND_FAIL
                        LDA RTS_FOUND
                        BEQ RTS_FIND_MISSING
                        LDA RTS_MATCH
                        STA SR_REQUEST+1
                        LDA RTS_MATCH+1
                        STA SR_REQUEST+2
                        LDA RTS_MATCH_BANK
                        STA SR_REQUEST
                        SEC
                        RTS
RTS_FIND_MISSING:       LDA #$06
RTS_FIND_FAIL:          CLC
                        RTS

; First fit in erased bytes, skipping entire valid records even if payload is FF.
RTS_ALLOCATE:           STZ RTS_RUN
                        STZ RTS_RUN+1
                        JSR RTS_SCAN_BEGIN
RTS_ALLOCATE_NEXT:      BCC RTS_ALLOCATE_END
                        JSR RTS_RECORD_AT_CURSOR
                        BCS RTS_ALLOCATE_SKIP
                        LDA SR_RECORD
                        STA SR_CURSOR
                        LDA SR_RECORD+1
                        STA SR_CURSOR+1
                        JSR SR_READ
                        CMP #$FF
                        BNE RTS_ALLOCATE_DIRTY
                        LDA RTS_RUN
                        ORA RTS_RUN+1
                        BNE RTS_ALLOCATE_COUNT
                        LDA SR_RECORD
                        STA SR_REQUEST+1
                        LDA SR_RECORD+1
                        STA SR_REQUEST+2
                        LDA RTS_BANK
                        STA SR_REQUEST
RTS_ALLOCATE_COUNT:     INC RTS_RUN
                        BNE RTS_ALLOCATE_COMPARE
                        INC RTS_RUN+1
RTS_ALLOCATE_COMPARE:   LDA RTS_RUN
                        CMP RTS_NEED
                        BNE RTS_ALLOCATE_ADVANCE
                        LDA RTS_RUN+1
                        CMP RTS_NEED+1
                        BEQ RTS_ALLOCATE_OK
RTS_ALLOCATE_ADVANCE:   JSR RTS_SCAN_ADVANCE
                        BRA RTS_ALLOCATE_NEXT
RTS_ALLOCATE_DIRTY:     STZ RTS_RUN
                        STZ RTS_RUN+1
                        BRA RTS_ALLOCATE_ADVANCE
RTS_ALLOCATE_SKIP:      STZ RTS_RUN
                        STZ RTS_RUN+1
                        JSR RTS_SCAN_SKIP
                        BRA RTS_ALLOCATE_NEXT
RTS_ALLOCATE_END:       CMP #$08
                        BEQ RTS_ALLOCATE_FAIL
                        LDA #$07
RTS_ALLOCATE_FAIL:      CLC
                        RTS
RTS_ALLOCATE_OK:        SEC
                        RTS

SR_CLI_TABLE:           JSR RTS_COMMAND_BEGIN
                        LDX #$01
                        JSR RTS_PARSE_FILTER
                        BCS RTS_TABLE_BEGIN
                        JMP SR_CLI_BAD
RTS_TABLE_BEGIN:        JSR RTS_SCAN_BEGIN
RTS_TABLE_NEXT:         BCC RTS_TABLE_END
                        JSR RTS_RECORD_AT_CURSOR
                        BCC RTS_TABLE_ADVANCE
                        LDA #'B'
                        JSR V2_PUTC
                        LDA RTS_BANK
                        ORA #'0'
                        JSR V2_PUTC
                        JSR SR_SPACE
                        JSR SR_TABLE_ROW
                        JSR RTS_SCAN_SKIP
                        BRA RTS_TABLE_NEXT
RTS_TABLE_ADVANCE:      JSR RTS_SCAN_ADVANCE
                        BRA RTS_TABLE_NEXT
RTS_TABLE_END:          CMP #$08
                        BNE RTS_TABLE_DONE
                        JMP RTS_CANCELLED
RTS_TABLE_DONE:         JMP RTS_COMMAND_DONE

; Policy: one mask per bank, bits 0..5 allow sectors 8..D. E/F always excluded.
; Default B1 only; Bank 2 is never searched unless explicitly enabled here.
RTS_SECTOR_BITS:        DB $01,$02,$04,$08,$10,$20
RTS_DONE_TEXT:          DB "Done",$00
RTS_BAD_TEXT:           DB "Bad hex/name",$00
RTS_ERROR_TEXT:         DB "RTS error ",$00
RTS_CANCEL_TEXT:        DB "Canceled",$00
