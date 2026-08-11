; STR8-N v1.2 resident CHARIN/CHAROUT hardware probe.
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

                        LDX             #<CAT_MSG_TITLE
                        LDY             #>CAT_MSG_TITLE
                        JSR             CAT_PRINT_XY
                        LDX             #<CAT_MSG_CHAROUT_OK
                        LDY             #>CAT_MSG_CHAROUT_OK
                        JSR             CAT_PRINT_XY
                        LDX             #<CAT_MSG_TYPE_Q
                        LDY             #>CAT_MSG_TYPE_Q
                        JSR             CAT_PRINT_XY

; A CR/LF left behind by the S9 transport is raw input, but is not the
; operator's test byte. Ignore only leading line endings before lowercase q.
CAT_WAIT_Q:             JSR             CAT_GET_TESTED
                        CMP             #$0D
                        BEQ             CAT_WAIT_Q
                        CMP             #$0A
                        BEQ             CAT_WAIT_Q
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

CAT_DATA_FAIL:          LDX             #<CAT_MSG_DATA_FAIL
                        LDY             #>CAT_MSG_DATA_FAIL
                        JSR             CAT_PRINT_XY
                        BRA             CAT_HALT

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

CAT_MSG_TITLE:          DB              $0D,$0A,"STR8-N 1.2 CONSOLE ABI TEST",$0D,$0A,0
CAT_MSG_CHAROUT_OK:     DB              "CHAROUT $F019 A/X/Y/C: PASS",$0D,$0A,0
CAT_MSG_TYPE_Q:         DB              "TYPE q THEN ENTER> ",0
CAT_MSG_Q_OK:           DB              " <- $71 RAW: PASS",$0D,$0A,0
CAT_MSG_ENTER_CR:       DB              "$0D RAW ENTER: PASS",$0D,$0A,0
CAT_MSG_ENTER_LF:       DB              "$0A RAW ENTER: PASS",$0D,$0A,0
CAT_MSG_CHARIN_OK:      DB              "CHARIN $F013 X/Y/C: PASS",$0D,$0A,0
CAT_MSG_BRK:            DB              "BRK VECTOR $F0DB: ",0
CAT_MSG_PASS_WORD:      DB              "PASS",$0D,$0A,0
CAT_MSG_PASS:           DB              "CONSOLE ABI TEST: PASS",$0D,$0A
                        DB              "PRESS PHYSICAL RESET",$0D,$0A,0
CAT_MSG_CHARIN_FAIL:    DB              $0D,$0A,"CHARIN CONTRACT: FAIL",$0D,$0A,0
CAT_MSG_DATA_FAIL:      DB              $0D,$0A,"RAW INPUT DATA: FAIL",$0D,$0A,0
