; STR8-N v1.21 resident raw console ABI hardware probe.
; Load with STR8-N L; S9 starts the probe at $2000.
; Type lowercase q followed by Enter when prompted. Physical RESET exits.

                        ORG             $2000

                        INCLUDE         "str8-console-eq.inc"

CAT_PTR_LO              EQU             $80
CAT_PTR_HI              EQU             $81
CAT_SAVED_A             EQU             $82
CAT_X_SENTINEL          EQU             $5A
CAT_Y_SENTINEL          EQU             $A5

CAT_START:              SEI
                        CLD
                        LDX             #$FF
                        TXS

; Old images return C=0 from the former $F006 tombstone. The new query must
; advertise the exact ABI version/capability byte without disturbing Y.
                        LDY             #CAT_Y_SENTINEL
                        CLC
                        JSR             STR8_ABI_QUERY_SERVICE
                        BCC             CAT_ABI_BAD
                        CMP             #STR8_RESIDENT_ABI_VERSION
                        BNE             CAT_ABI_BAD
                        CPX             #STR8_RESIDENT_ABI_CAPS
                        BNE             CAT_ABI_BAD
                        CPY             #CAT_Y_SENTINEL
                        BEQ             CAT_ABI_GOOD
CAT_ABI_BAD:            JMP             CAT_ABI_FAIL
CAT_ABI_GOOD:

; Reinitialize through the public gate. Test A/X/Y and both incoming carry
; states because CONSOLE_INIT promises to preserve carry.
                        LDX             #CAT_X_SENTINEL
                        LDY             #CAT_Y_SENTINEL
                        SEC
                        JSR             STR8_CONSOLE_INIT_SERVICE
                        BCC             CAT_INIT_BAD
                        CMP             #$0C
                        BNE             CAT_INIT_BAD
                        CPX             #CAT_X_SENTINEL
                        BNE             CAT_INIT_BAD
                        CPY             #CAT_Y_SENTINEL
                        BNE             CAT_INIT_BAD
                        LDX             #CAT_X_SENTINEL
                        LDY             #CAT_Y_SENTINEL
                        CLC
                        JSR             STR8_CONSOLE_INIT_SERVICE
                        BCS             CAT_INIT_BAD
                        CMP             #$0C
                        BNE             CAT_INIT_BAD
                        CPX             #CAT_X_SENTINEL
                        BNE             CAT_INIT_BAD
                        CPY             #CAT_Y_SENTINEL
                        BEQ             CAT_INIT_GOOD
CAT_INIT_BAD:           JMP             CAT_INIT_FAIL
CAT_INIT_GOOD:

                        LDX             #<CAT_MSG_TITLE
                        LDY             #>CAT_MSG_TITLE
                        JSR             CAT_PRINT_XY
                        LDX             #<CAT_MSG_ABI_OK
                        LDY             #>CAT_MSG_ABI_OK
                        JSR             CAT_PRINT_XY
                        LDX             #<CAT_MSG_INIT_OK
                        LDY             #>CAT_MSG_INIT_OK
                        JSR             CAT_PRINT_XY
                        LDX             #<CAT_MSG_CHAROUT_OK
                        LDY             #>CAT_MSG_CHAROUT_OK
                        JSR             CAT_PRINT_XY

; Consume only S9 transport line endings. Each ready result is followed by
; CHARIN, proving that CHAR_READY did not consume the reported byte.
CAT_DRAIN_INITIAL:      JSR             CAT_POLL_TESTED
                        BCC             CAT_DRAINED
                        JSR             CAT_GET_TESTED
                        CMP             #$0D
                        BEQ             CAT_DRAIN_INITIAL
                        CMP             #$0A
                        BEQ             CAT_DRAIN_INITIAL
                        JMP             CAT_DATA_FAIL
CAT_DRAINED:
                        LDX             #<CAT_MSG_TYPE_Q
                        LDY             #>CAT_MSG_TYPE_Q
                        JSR             CAT_PRINT_XY

; Poll until lowercase q arrives, then consume it through blocking CHARIN.
; Empty and ready paths both validate carry plus X/Y preservation.
CAT_WAIT_Q:             JSR             CAT_POLL_TESTED
                        BCC             CAT_WAIT_Q
                        JSR             CAT_GET_TESTED
                        CMP             #'q'
                        BEQ             CAT_HAVE_Q
                        JMP             CAT_DATA_FAIL
CAT_HAVE_Q:
                        JSR             CAT_PUT_TESTED
                        LDX             #<CAT_MSG_Q_OK
                        LDY             #>CAT_MSG_Q_OK
                        JSR             CAT_PRINT_XY

; Enter normally supplies CR, LF, or CR/LF. Report the exact first byte.
                        JSR             CAT_GET_TESTED
                        CMP             #$0D
                        BEQ             CAT_ENTER_CR
                        CMP             #$0A
                        BEQ             CAT_ENTER_LF
                        JMP             CAT_DATA_FAIL
CAT_ENTER_LF:
                        LDX             #<CAT_MSG_ENTER_LF
                        LDY             #>CAT_MSG_ENTER_LF
                        BRA             CAT_ENTER_REPORT
CAT_ENTER_CR:           LDX             #<CAT_MSG_ENTER_CR
                        LDY             #>CAT_MSG_ENTER_CR
CAT_ENTER_REPORT:       JSR             CAT_PRINT_XY
                        LDX             #<CAT_MSG_CHAR_READY_OK
                        LDY             #>CAT_MSG_CHAR_READY_OK
                        JSR             CAT_PRINT_XY
                        LDX             #<CAT_MSG_CHARIN_OK
                        LDY             #>CAT_MSG_CHARIN_OK
                        JSR             CAT_PRINT_XY
                        LDX             #<CAT_MSG_BRK
                        LDY             #>CAT_MSG_BRK
                        JSR             CAT_PRINT_XY
                        BRK
                        NOP
                        LDX             #<CAT_MSG_PASS_WORD
                        LDY             #>CAT_MSG_PASS_WORD
                        JSR             CAT_PRINT_XY
                        LDX             #<CAT_MSG_PASS
                        LDY             #>CAT_MSG_PASS
                        JSR             CAT_PRINT_XY
CAT_HALT:               BRA             CAT_HALT

; Validate the complete public CHAROUT contract on every displayed byte.
; On failure, attempt one raw '!' and halt; no output or '!' is a hard fail.
CAT_PUT_TESTED:         STA             CAT_SAVED_A
                        LDX             #CAT_X_SENTINEL
                        LDY             #CAT_Y_SENTINEL
                        CLC
                        JSR             STR8_CHAROUT_SERVICE
                        BCC             CAT_CHAROUT_FAIL
                        CMP             CAT_SAVED_A
                        BNE             CAT_CHAROUT_FAIL
                        CPX             #CAT_X_SENTINEL
                        BNE             CAT_CHAROUT_FAIL
                        CPY             #CAT_Y_SENTINEL
                        BNE             CAT_CHAROUT_FAIL
                        LDA             CAT_SAVED_A
                        RTS

CAT_CHAROUT_FAIL:       LDA             #'!'
                        JSR             STR8_CHAROUT_SERVICE
                        BRA             CAT_HALT

; Validate carry and X/Y preservation while returning the exact raw byte in A.
CAT_GET_TESTED:         LDX             #CAT_X_SENTINEL
                        LDY             #CAT_Y_SENTINEL
                        CLC
                        JSR             STR8_CHARIN_SERVICE
                        BCC             CAT_CHARIN_FAIL
                        CPX             #CAT_X_SENTINEL
                        BNE             CAT_CHARIN_FAIL
                        CPY             #CAT_Y_SENTINEL
                        BNE             CAT_CHARIN_FAIL
                        RTS

CAT_CHARIN_FAIL:        LDX             #<CAT_MSG_CHARIN_FAIL
                        LDY             #>CAT_MSG_CHARIN_FAIL
                        JSR             CAT_PRINT_XY
                        BRA             CAT_HALT

; Validate both public CHAR_READY returns. CPX/CPY change carry, so restore
; the service result explicitly after testing X and Y.
CAT_POLL_TESTED:        LDX             #CAT_X_SENTINEL
                        LDY             #CAT_Y_SENTINEL
                        SEC
                        JSR             STR8_CHAR_READY_SERVICE
                        BCC             CAT_POLL_EMPTY
                        CPX             #CAT_X_SENTINEL
                        BNE             CAT_CHAR_READY_FAIL
                        CPY             #CAT_Y_SENTINEL
                        BNE             CAT_CHAR_READY_FAIL
                        SEC
                        RTS
CAT_POLL_EMPTY:         CPX             #CAT_X_SENTINEL
                        BNE             CAT_CHAR_READY_FAIL
                        CPY             #CAT_Y_SENTINEL
                        BNE             CAT_CHAR_READY_FAIL
                        CLC
                        RTS

CAT_CHAR_READY_FAIL:    LDX             #<CAT_MSG_CHAR_READY_FAIL
                        LDY             #>CAT_MSG_CHAR_READY_FAIL
                        JSR             CAT_PRINT_XY
                        JMP             CAT_HALT

CAT_ABI_FAIL:           LDX             #<CAT_MSG_ABI_FAIL
                        LDY             #>CAT_MSG_ABI_FAIL
                        JSR             CAT_PRINT_XY
                        JMP             CAT_HALT

CAT_INIT_FAIL:          LDX             #<CAT_MSG_INIT_FAIL
                        LDY             #>CAT_MSG_INIT_FAIL
                        JSR             CAT_PRINT_XY
                        JMP             CAT_HALT

CAT_DATA_FAIL:          LDX             #<CAT_MSG_DATA_FAIL
                        LDY             #>CAT_MSG_DATA_FAIL
                        JSR             CAT_PRINT_XY
                        JMP             CAT_HALT

CAT_PRINT_XY:           STX             CAT_PTR_LO
                        STY             CAT_PTR_HI
CAT_PRINT_NEXT:         LDY             #$00
                        LDA             (CAT_PTR_LO),Y
                        BEQ             CAT_PRINT_DONE
                        JSR             CAT_PUT_TESTED
                        INC             CAT_PTR_LO
                        BNE             CAT_PRINT_NEXT
                        INC             CAT_PTR_HI
                        BRA             CAT_PRINT_NEXT
CAT_PRINT_DONE:         RTS

CAT_MSG_TITLE:          DB              $0D,$0A,"STR8-N 1.21 CONSOLE ABI TEST",$0D,$0A,0
CAT_MSG_ABI_OK:         DB              "ABI_QUERY $F006 V1 CAPS $3F/Y/C: PASS",$0D,$0A,0
CAT_MSG_INIT_OK:        DB              "CONSOLE_INIT $F003 A/X/Y/C: PASS",$0D,$0A,0
CAT_MSG_CHAROUT_OK:     DB              "CHAROUT $F019 A/X/Y/C: PASS",$0D,$0A,0
CAT_MSG_TYPE_Q:         DB              "TYPE q THEN ENTER> ",0
CAT_MSG_Q_OK:           DB              " <- $71 RAW: PASS",$0D,$0A,0
CAT_MSG_ENTER_CR:       DB              "$0D RAW ENTER: PASS",$0D,$0A,0
CAT_MSG_ENTER_LF:       DB              "$0A RAW ENTER: PASS",$0D,$0A,0
CAT_MSG_CHAR_READY_OK:  DB              "CHAR_READY $F03E EMPTY/READY/X/Y/C: PASS",$0D,$0A,0
CAT_MSG_CHARIN_OK:      DB              "CHARIN $F013 X/Y/C: PASS",$0D,$0A,0
CAT_MSG_BRK:            DB              "BRK VECTOR $F0E6: ",0
CAT_MSG_PASS_WORD:      DB              "PASS",$0D,$0A,0
CAT_MSG_PASS:           DB              "CONSOLE ABI TEST: PASS",$0D,$0A
                        DB              "PRESS PHYSICAL RESET",$0D,$0A,0
CAT_MSG_CHARIN_FAIL:    DB              $0D,$0A,"CHARIN CONTRACT: FAIL",$0D,$0A,0
CAT_MSG_CHAR_READY_FAIL: DB             $0D,$0A,"CHAR_READY CONTRACT: FAIL",$0D,$0A,0
CAT_MSG_ABI_FAIL:       DB              $0D,$0A,"ABI_QUERY CONTRACT: FAIL",$0D,$0A,0
CAT_MSG_INIT_FAIL:      DB              $0D,$0A,"CONSOLE_INIT CONTRACT: FAIL",$0D,$0A,0
CAT_MSG_DATA_FAIL:      DB              $0D,$0A,"RAW INPUT DATA: FAIL",$0D,$0A,0
