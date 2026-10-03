; Included by the a24c1 builder in place of the fixed B0 preservation gate.
W2I_CHOOSE_BACKUP:      STZ W2I_NO_BACKUP
                        LDX #<W2I_MSG_DEST
                        LDY #>W2I_MSG_DEST
                        JSR W2I_PUTS
                        JSR W2I_READ_LINE
                        LDX #<W2I_TOKEN_NONE
                        LDY #>W2I_TOKEN_NONE
                        JSR W2I_MATCH_INPUT
                        BCS W2I_WITHOUT_BACKUP
                        LDA W2I_INPUT+1
                        BNE W2I_POLICY_INVALID
                        LDA W2I_INPUT
                        SEC
                        SBC #'0'
                        CMP #$03
                        BCS W2I_POLICY_INVALID
                        STA W2I_BACK_BANK
                        LDX #<W2I_MSG_RANGE
                        LDY #>W2I_MSG_RANGE
                        JSR W2I_PUTS
                        JSR W2I_READ_LINE
                        LDA W2I_INPUT
                        JSR W2I_PARSE_SECTOR
                        BCC W2I_POLICY_INVALID
                        STA W2I_BACK_FIRST
                        STA W2I_BACK_LAST
                        LDA W2I_INPUT+1
                        BEQ W2I_RANGE_VALID
                        CMP #'-'
                        BNE W2I_POLICY_INVALID
                        LDA W2I_INPUT+3
                        BNE W2I_POLICY_INVALID
                        LDA W2I_INPUT+2
                        JSR W2I_PARSE_SECTOR
                        BCC W2I_POLICY_INVALID
                        CMP W2I_BACK_FIRST
                        BCC W2I_POLICY_INVALID
                        STA W2I_BACK_LAST
W2I_RANGE_VALID:        LDA W2I_BACK_LAST
                        CLC
                        ADC #$10
                        STA W2I_BACK_END
                        JSR W2I_SHOW_BACKUP_PLAN
; Read and validate the entire destination range before any flash mutation.
                        JSR W2I_COMPARE_B0_B3_EXACT
                        BCS W2I_BACKUP_PROVEN
                        JSR W2I_BACKUP_ERASED
                        BCS W2I_BACKUP_EMPTY
                        LDX #<W2I_MSG_DEST_USED
                        LDY #>W2I_MSG_DEST_USED
                        JMP W2I_ABORT_XY
W2I_BACKUP_EMPTY:       LDX #<W2I_MSG_BACK_CONFIRM
                        LDY #>W2I_MSG_BACK_CONFIRM
                        JSR W2I_PUTS
                        JSR W2I_READ_LINE
                        LDX #<W2I_TOKEN_BACKUP
                        LDY #>W2I_TOKEN_BACKUP
                        JSR W2I_MATCH_INPUT
                        BCC W2I_POLICY_INVALID
                        JSR W2I_COPY_B3_TO_B0
                        BCC W2I_BACKUP_FAILED
                        JSR W2I_COMPARE_B0_B3_EXACT
                        BCC W2I_BACKUP_FAILED
W2I_BACKUP_PROVEN:      LDX #<W2I_MSG_BACK_VERIFIED
                        LDY #>W2I_MSG_BACK_VERIFIED
                        JSR W2I_PUTS
                        JMP W2I_BACKUP_READY
W2I_BACKUP_FAILED:      LDX #<W2I_MSG_BACK_FAILED
                        LDY #>W2I_MSG_BACK_FAILED
                        JMP W2I_ABORT_XY
W2I_POLICY_INVALID:     LDX #<W2I_MSG_POLICY_CANCEL
                        LDY #>W2I_MSG_POLICY_CANCEL
                        JMP W2I_ABORT_XY
W2I_WITHOUT_BACKUP:     LDX #<W2I_MSG_NO_FIRST
                        LDY #>W2I_MSG_NO_FIRST
                        JSR W2I_PUTS
                        JSR W2I_READ_LINE
                        LDX #<W2I_TOKEN_NO_FIRST
                        LDY #>W2I_TOKEN_NO_FIRST
                        JSR W2I_MATCH_INPUT
                        BCC W2I_POLICY_INVALID
                        LDX #<W2I_MSG_NO_SECOND
                        LDY #>W2I_MSG_NO_SECOND
                        JSR W2I_PUTS
                        JSR W2I_READ_LINE
                        LDX #<W2I_TOKEN_NO_SECOND
                        LDY #>W2I_TOKEN_NO_SECOND
                        JSR W2I_MATCH_INPUT
                        BCC W2I_POLICY_INVALID
                        LDA #$01
                        STA W2I_NO_BACKUP
                        LDX #<W2I_MSG_NO_READY
                        LDY #>W2I_MSG_NO_READY
                        JSR W2I_PUTS
W2I_BACKUP_READY:       JSR W2I_LED_RELEASE
                        LDA #$03
                        JSR W2I_SELECT_BANK_A
                        JMP W2I_RECEIVE_READY

W2I_PARSE_SECTOR:       CMP #'8'
                        BEQ W2I_PARSE_NUMERIC
                        CMP #'9'
                        BEQ W2I_PARSE_NUMERIC
                        CMP #'A'
                        BCC W2I_PARSE_BAD
                        CMP #'G'
                        BCS W2I_PARSE_BAD
                        SEC
                        SBC #$37
                        BRA W2I_PARSE_SHIFT
W2I_PARSE_NUMERIC:      SEC
                        SBC #'0'
W2I_PARSE_SHIFT:        ASL A
                        ASL A
                        ASL A
                        ASL A
                        SEC
                        RTS
W2I_PARSE_BAD:          CLC
                        RTS

W2I_SHOW_BACKUP_PLAN:   LDX #<W2I_MSG_PLAN
                        LDY #>W2I_MSG_PLAN
                        JSR W2I_PUTS
                        LDA W2I_BACK_FIRST
                        JSR W2I_HEX
                        LDA #'-'
                        JSR W2I_OUT
                        LDA W2I_BACK_LAST
                        JSR W2I_HEX
                        LDX #<W2I_MSG_TO_BANK
                        LDY #>W2I_MSG_TO_BANK
                        JSR W2I_PUTS
                        LDA W2I_BACK_BANK
                        CLC
                        ADC #'0'
                        JSR W2I_OUT
                        JMP W2I_CRLF

W2I_BACKUP_ERASED:      LDA W2I_BACK_BANK
                        JSR W2I_SELECT_BANK_A
                        LDA W2I_BACK_FIRST
                        STA W2I_SECTOR_HI
W2I_ERASE_CHECK_SECTOR: STZ W2I_PTR_LO
                        LDA W2I_SECTOR_HI
                        STA W2I_PTR_HI
                        LDX #$10
                        LDY #$00
W2I_ERASE_CHECK_BYTE:   LDA (W2I_PTR_LO),Y
                        CMP #$FF
                        BNE W2I_ERASE_CHECK_FAIL
                        INY
                        BNE W2I_ERASE_CHECK_BYTE
                        INC W2I_PTR_HI
                        DEX
                        BNE W2I_ERASE_CHECK_BYTE
                        LDA W2I_SECTOR_HI
                        CLC
                        ADC #$10
                        STA W2I_SECTOR_HI
                        CMP W2I_BACK_END
                        BNE W2I_ERASE_CHECK_SECTOR
                        SEC
                        RTS
W2I_ERASE_CHECK_FAIL:   CLC
                        RTS

W2I_BACK_BANK:          DB 0
W2I_BACK_FIRST:         DB 0
W2I_BACK_LAST:          DB 0
W2I_BACK_END:           DB 0
W2I_NO_BACKUP:          DB 0
W2I_MSG_DEST:           DB "CHOOSE BACKUP BANK: TYPE ONLY 0, 1, 2 OR NONE; PRESS ENTER",$0D,$0A,"BANK> ",0
W2I_MSG_RANGE:          DB "CHOOSE B3 SECTORS: TYPE F OR 8-F (EXAMPLES); PRESS ENTER",$0D,$0A,"SECTORS 8-F> ",0
W2I_MSG_PLAN:           DB "BACKUP B3 SECTOR HI ",0
W2I_MSG_TO_BANK:        DB " TO SAME SECTORS IN B",0
W2I_MSG_DEST_USED:      DB "REFUSE: BACKUP RANGE USED AND DIFFERENT; NOTHING WRITTEN",$0D,$0A,0
W2I_MSG_BACK_CONFIRM:   DB "TO COPY THE SHOWN RANGE, TYPE BACKUP B3 AND PRESS ENTER",$0D,$0A,"TYPE BACKUP B3> ",0
W2I_MSG_BACK_VERIFIED:  DB "BACKUP RANGE == ORIGINAL B3 VERIFIED",$0D,$0A,0
W2I_MSG_BACK_FAILED:    DB "BACKUP FAILED; B3 UNCHANGED",$0D,$0A,0
W2I_MSG_POLICY_CANCEL:  DB "CANCELED: INVALID BACKUP CHOICE OR CONFIRMATION",$0D,$0A,0
W2I_MSG_NO_FIRST:       DB "NO RECOVERY COPY WILL BE MADE. TYPE NO BACKUP> ",0
W2I_MSG_NO_SECOND:      DB "CONFIRM AGAIN: TYPE INSTALL WITHOUT BACKUP> ",0
W2I_MSG_NO_READY:       DB "NO BACKUP CONFIRMED TWICE",$0D,$0A,0
W2I_TOKEN_NONE:         DB "NONE",0
W2I_TOKEN_BACKUP:       DB "BACKUP B3",0
W2I_TOKEN_NO_FIRST:     DB "NO BACKUP",0
W2I_TOKEN_NO_SECOND:    DB "INSTALL WITHOUT BACKUP",0
