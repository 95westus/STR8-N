; STR8-N v1.32 RAM-worker LED hardware probe.
; Load with STR8-N L; S9 starts at $2000. The probe requires scratch sector
; B2:8 to be erased, programs and verifies a dense test pattern, then erases
; and verifies it with the production worker. B2:8 ends erased and the
; protected B1:F recovery backup is untouched.

                        ORG             $2000

                        INCLUDE         "str8-console-eq.inc"
                        INCLUDE         "str8-jump-eq.inc"
                        INCLUDE         "str8-led-eq.inc"
                        INCLUDE         "str8-ram-abi.inc"
                        INCLUDE         "str8-record-eq.inc"
                        INCLUDE         "str8-worker-eq.inc"

LWT_PTR0_LO             EQU             $80
LWT_PTR0_HI             EQU             $81
LWT_PTR1_LO             EQU             $82
LWT_PTR1_HI             EQU             $83
LWT_FILL_VALUE          EQU             $84
LWT_STAGE_HI            EQU             $30
LWT_TARGET_BANK         EQU             $02
LWT_LIVE_BANK           EQU             $03
LWT_TARGET_SECTOR_HI    EQU             $80
LWT_PROGRAM_STAGED      EQU             $05
LWT_PROGRAM_RECORD      EQU             $07
LWT_INVALID_RECORD_HI   EQU             $F0
LWT_TEST_PATTERN        EQU             $A5

LWT_START:              SEI
                        CLD
                        LDX             #$FF
                        TXS

; Consume only the S9 transport line ending before asking for confirmation.
?DRAIN:                 JSR             STR8_CHAR_READY_SERVICE
                        BCC             ?DRAINED
                        JSR             STR8_CHARIN_SERVICE
                        BRA             ?DRAIN
?DRAINED:               LDX             #<LWT_MSG_TITLE
                        LDY             #>LWT_MSG_TITLE
                        JSR             LWT_PRINT_XY
                        LDX             #<LWT_MSG_CONFIRM
                        LDY             #>LWT_MSG_CONFIRM
                        JSR             LWT_PRINT_XY
                        JSR             STR8_CHARIN_SERVICE
                        CMP             #'Y'
                        BEQ             ?CONFIRMED
                        LDX             #<LWT_MSG_ABORT
                        LDY             #>LWT_MSG_ABORT
                        JSR             LWT_PRINT_XY
                        JMP             LWT_HALT

?CONFIRMED:             JSR             LWT_STAGE_ERASED
                        JSR             LWT_COPY_WORKER
                        BCS             ?COPY_OK
                        JMP             LWT_COPY_FAIL
?COPY_OK:

; Refuse the mutation unless the designated scratch sector is already erased.
; The direct RAM selector returns to this RAM application.
                        LDA             #LWT_TARGET_BANK
                        JSR             STR8_BANK_SELECT_RAM
                        BCS             ?SELECT1_OK
                        JMP             LWT_SELECT_FAIL
?SELECT1_OK:
                        JSR             LWT_COMPARE_STAGE_TOP
                        PHP
                        LDA             #LWT_LIVE_BANK
                        JSR             STR8_BANK_SELECT_RAM
                        BCS             ?SELECT2_OK
                        JMP             LWT_SELECT_FAIL
?SELECT2_OK:
                        PLP
                        BCS             ?PREFLIGHT_OK
                        JMP             LWT_PREFLIGHT_FAIL
?PREFLIGHT_OK:

; Pre-arm the same all-red warning so it is human-visible before the actual
; mutation starts. The production worker reasserts $F0 at every unlock.
                        JSR             LWT_STAGE_PATTERN
                        LDX             #<LWT_MSG_ARMED
                        LDY             #>LWT_MSG_ARMED
                        JSR             LWT_PRINT_XY
                        LDA             #STR8_LED_STATUS_FLASH_MUTATE
                        STA             STR8_LED_PIA_PORTA
                        JSR             STR8_CHARIN_SERVICE
                        CMP             #'Y'
                        BEQ             ?ARMED_OK
                        JMP             LWT_ARMED_ABORT
?ARMED_OK:
                        LDX             #<LWT_MSG_PROGRAM
                        LDY             #>LWT_MSG_PROGRAM
                        JSR             LWT_PRINT_XY
                        JSR             LWT_RUN_STAGED_WORKER
                        BCS             ?PROGRAM_OK
                        JMP             LWT_WORKER_FAIL
?PROGRAM_OK:
                        JSR             LWT_REQUIRE_RUN_LED
                        BCS             ?PROGRAM_LED_OK
                        JMP             LWT_RETURN_LED_FAIL
?PROGRAM_LED_OK:

; Independently verify the dense pattern, then erase/verify B2:8 back to its
; original all-$FF state.
                        LDA             #LWT_TARGET_BANK
                        JSR             STR8_BANK_SELECT_RAM
                        BCS             ?SELECT3_OK
                        JMP             LWT_SELECT_FAIL
?SELECT3_OK:
                        JSR             LWT_COMPARE_STAGE_TOP
                        PHP
                        LDA             #LWT_LIVE_BANK
                        JSR             STR8_BANK_SELECT_RAM
                        BCS             ?SELECT4_OK
                        JMP             LWT_SELECT_FAIL
?SELECT4_OK:
                        PLP
                        BCS             ?PATTERN_VERIFY_OK
                        JMP             LWT_VERIFY_FAIL
?PATTERN_VERIFY_OK:
                        LDX             #<LWT_MSG_RESTORE
                        LDY             #>LWT_MSG_RESTORE
                        JSR             LWT_PRINT_XY
                        JSR             LWT_STAGE_ERASED
                        JSR             LWT_RUN_STAGED_WORKER
                        BCS             ?RESTORE_OK
                        JMP             LWT_RESTORE_FAIL
?RESTORE_OK:
                        JSR             LWT_REQUIRE_RUN_LED
                        BCS             ?RESTORE_LED_OK
                        JMP             LWT_RETURN_LED_FAIL
?RESTORE_LED_OK:
                        LDA             #LWT_TARGET_BANK
                        JSR             STR8_BANK_SELECT_RAM
                        BCS             ?SELECT5_OK
                        JMP             LWT_SELECT_FAIL
?SELECT5_OK:
                        JSR             LWT_COMPARE_STAGE_TOP
                        PHP
                        LDA             #LWT_LIVE_BANK
                        JSR             STR8_BANK_SELECT_RAM
                        BCS             ?SELECT6_OK
                        JMP             LWT_SELECT_FAIL
?SELECT6_OK:
                        PLP
                        BCS             ?RESTORE_VERIFY_OK
                        JMP             LWT_RESTORE_VERIFY_FAIL
?RESTORE_VERIFY_OK:

; Exercise a real known-mode failure before its write boundary. Requesting
; $FF over a programmed Bank-3 $F000 byte must fail the one-to-zero preflight,
; touch no flash, restore Bank 3, and restore the RUN LED.
                        LDA             #STR8_LED_STATUS_INPUT_WAIT
                        STA             STR8_LED_PIA_PORTA
                        STZ             STR8_REC_ADDR_LO
                        LDA             #LWT_INVALID_RECORD_HI
                        STA             STR8_REC_ADDR_HI
                        LDA             #$01
                        STA             STR8_REC_DATA_LEN
                        LDA             #$FF
                        STA             STR8_REC_DATA_BUF
                        LDA             #LWT_PROGRAM_RECORD
                        STA             STR8_COPY_MODE
                        JSR             STR8_WORKER_RUN
                        BCC             ?FAIL_CLOSED_OK
                        JMP             LWT_FAIL_CLOSED_FAIL
?FAIL_CLOSED_OK:
                        JSR             LWT_REQUIRE_RUN_LED
                        BCS             ?FAIL_LED_OK
                        JMP             LWT_RETURN_LED_FAIL
?FAIL_LED_OK:
                        LDX             #<LWT_MSG_FAIL_CLOSED_PASS
                        LDY             #>LWT_MSG_FAIL_CLOSED_PASS
                        JSR             LWT_PRINT_XY
                        LDX             #<LWT_MSG_PASS
                        LDY             #>LWT_MSG_PASS
                        JSR             LWT_PRINT_XY
LWT_HALT:               BRA             LWT_HALT

LWT_ARMED_ABORT:        LDA             #STR8_LED_STATUS_RUNNING
                        STA             STR8_LED_PIA_PORTA
                        LDX             #<LWT_MSG_ABORT
                        LDY             #>LWT_MSG_ABORT
                        JSR             LWT_PRINT_XY
                        BRA             LWT_HALT

LWT_COPY_FAIL:          LDX             #<LWT_MSG_COPY_FAIL
                        LDY             #>LWT_MSG_COPY_FAIL
                        BRA             LWT_REPORT_FAIL
LWT_PREFLIGHT_FAIL:     LDX             #<LWT_MSG_PREFLIGHT_FAIL
                        LDY             #>LWT_MSG_PREFLIGHT_FAIL
                        BRA             LWT_REPORT_FAIL
LWT_WORKER_FAIL:        LDX             #<LWT_MSG_WORKER_FAIL
                        LDY             #>LWT_MSG_WORKER_FAIL
                        BRA             LWT_REPORT_FAIL
LWT_VERIFY_FAIL:        LDX             #<LWT_MSG_VERIFY_FAIL
                        LDY             #>LWT_MSG_VERIFY_FAIL
                        BRA             LWT_REPORT_FAIL
LWT_RESTORE_FAIL:       LDX             #<LWT_MSG_RESTORE_FAIL
                        LDY             #>LWT_MSG_RESTORE_FAIL
                        BRA             LWT_REPORT_FAIL
LWT_RESTORE_VERIFY_FAIL:
                        LDX             #<LWT_MSG_RESTORE_VERIFY_FAIL
                        LDY             #>LWT_MSG_RESTORE_VERIFY_FAIL
                        BRA             LWT_REPORT_FAIL
LWT_RETURN_LED_FAIL:    LDX             #<LWT_MSG_RETURN_LED_FAIL
                        LDY             #>LWT_MSG_RETURN_LED_FAIL
                        BRA             LWT_REPORT_FAIL
LWT_FAIL_CLOSED_FAIL:   LDX             #<LWT_MSG_FAIL_CLOSED_FAIL
                        LDY             #>LWT_MSG_FAIL_CLOSED_FAIL
LWT_REPORT_FAIL:        JSR             LWT_PRINT_XY
                        BRA             LWT_HALT

; A selector failure can leave a non-Bank-3 image visible, so it cannot safely
; call resident console code. Publish a red stop pattern and halt in RAM.
LWT_SELECT_FAIL:        LDA             #$E0
                        STA             STR8_LED_PIA_PORTA
                        BRA             LWT_SELECT_FAIL

LWT_STAGE_PATTERN:      LDA             #LWT_TEST_PATTERN
                        BRA             LWT_FILL_STAGE
LWT_STAGE_ERASED:       LDA             #$FF
LWT_FILL_STAGE:         STA             LWT_FILL_VALUE
                        STZ             LWT_PTR1_LO
                        LDA             #LWT_STAGE_HI
                        STA             LWT_PTR1_HI
                        LDX             #$10
?PAGE:                 LDY             #$00
                        LDA             LWT_FILL_VALUE
?BYTE:                 STA             (LWT_PTR1_LO),Y
                        INY
                        BNE             ?BYTE
                        INC             LWT_PTR1_HI
                        DEX
                        BNE             ?PAGE
                        RTS

LWT_RUN_STAGED_WORKER:  LDA             #LWT_TARGET_BANK
                        STA             STR8_COPY_DST_BANK
                        LDA             #LWT_TARGET_SECTOR_HI
                        STA             STR8_MARK_SECTOR_HI
                        LDA             #LWT_STAGE_HI
                        STA             STR8_STAGE_BUF_HI
                        LDA             #LWT_PROGRAM_STAGED
                        STA             STR8_COPY_MODE
                        JMP             STR8_WORKER_RUN

LWT_REQUIRE_RUN_LED:    LDA             STR8_LED_PIA_PORTA
                        CMP             #STR8_LED_STATUS_RUNNING
                        BNE             ?FAIL
                        SEC
                        RTS
?FAIL:                 CLC
                        RTS

; Copy and read back the exact published production worker into $0200.
LWT_COPY_WORKER:        LDA             #<STR8_WORKER_STORE
                        STA             LWT_PTR0_LO
                        LDA             #>STR8_WORKER_STORE
                        STA             LWT_PTR0_HI
                        STZ             LWT_PTR1_LO
                        LDA             #>STR8_WORKER_RUN
                        STA             LWT_PTR1_HI
                        LDX             #>STR8_WORKER_SIZE
?PAGE:                 LDY             #$00
?BYTE:                 LDA             (LWT_PTR0_LO),Y
                        STA             (LWT_PTR1_LO),Y
                        CMP             (LWT_PTR1_LO),Y
                        BNE             ?FAIL
                        INY
                        BNE             ?BYTE
                        INC             LWT_PTR0_HI
                        INC             LWT_PTR1_HI
                        DEX
                        BNE             ?PAGE
?TAIL:                 CPY             #<STR8_WORKER_SIZE
                        BEQ             ?OK
                        LDA             (LWT_PTR0_LO),Y
                        STA             (LWT_PTR1_LO),Y
                        CMP             (LWT_PTR1_LO),Y
                        BNE             ?FAIL
                        INY
                        BRA             ?TAIL
?OK:                   SEC
                        RTS
?FAIL:                 CLC
                        RTS

; Compare the selected bank's CPU $8000-$8FFF with staged RAM $3000-$3FFF.
LWT_COMPARE_STAGE_TOP:  STZ             LWT_PTR0_LO
                        LDA             #LWT_TARGET_SECTOR_HI
                        STA             LWT_PTR0_HI
                        STZ             LWT_PTR1_LO
                        LDA             #LWT_STAGE_HI
                        STA             LWT_PTR1_HI
                        LDX             #$10
?PAGE:                 LDY             #$00
?BYTE:                 LDA             (LWT_PTR0_LO),Y
                        CMP             (LWT_PTR1_LO),Y
                        BNE             ?FAIL
                        INY
                        BNE             ?BYTE
                        INC             LWT_PTR0_HI
                        INC             LWT_PTR1_HI
                        DEX
                        BNE             ?PAGE
                        SEC
                        RTS
?FAIL:                 CLC
                        RTS

LWT_PRINT_XY:           STX             LWT_PTR0_LO
                        STY             LWT_PTR0_HI
                        LDY             #$00
?BYTE:                 LDA             (LWT_PTR0_LO),Y
                        BEQ             ?DONE
                        JSR             STR8_CHAROUT_SERVICE
                        INY
                        BNE             ?BYTE
                        INC             LWT_PTR0_HI
                        BRA             ?BYTE
?DONE:                 RTS

LWT_MSG_TITLE:          DB              $0D,$0A,"STR8-N LED WORKER TEST",$0D,$0A
                        DB              "TARGET B2:8 ERASED SCRATCH",$0D,$0A,0
LWT_MSG_CONFIRM:        DB              "TYPE Y TO PREFLIGHT B2:8> ",0
LWT_MSG_ABORT:          DB              $0D,$0A,"ABORT; NOTHING WRITTEN",$0D,$0A,0
LWT_MSG_ARMED:          DB              $0D,$0A,"LED $F0 PRE-ARMED; TYPE Y TO PROGRAM B2:8> ",0
LWT_MSG_PROGRAM:        DB              $0D,$0A,"PROGRAM/VERIFY $A5; WORKER OWNS $F0",$0D,$0A,0
LWT_MSG_RESTORE:        DB              "ERASE/VERIFY B2:8 BACK TO $FF",$0D,$0A,0
LWT_MSG_FAIL_CLOSED_PASS:
                        DB              "FAILED WRITE PREFLIGHT RETURN LED $01: PASS",$0D,$0A,0
LWT_MSG_PASS:           DB              "B2:8 ERASED; LED WORKER TEST: PASS",$0D,$0A
                        DB              "PRESS PHYSICAL RESET",$0D,$0A,0
LWT_MSG_COPY_FAIL:      DB              $0D,$0A,"WORKER COPY: FAIL",$0D,$0A,0
LWT_MSG_PREFLIGHT_FAIL: DB              $0D,$0A,"REFUSE: B2:8 NOT ERASED",$0D,$0A,0
LWT_MSG_WORKER_FAIL:    DB              $0D,$0A,"B2:8 PATTERN WORKER: FAIL",$0D,$0A,0
LWT_MSG_VERIFY_FAIL:    DB              $0D,$0A,"B2:8 PATTERN VERIFY: FAIL",$0D,$0A,0
LWT_MSG_RESTORE_FAIL:   DB              $0D,$0A,"B2:8 ERASE WORKER: FAIL",$0D,$0A,0
LWT_MSG_RESTORE_VERIFY_FAIL:
                        DB              $0D,$0A,"B2:8 ERASE VERIFY: FAIL",$0D,$0A,0
LWT_MSG_RETURN_LED_FAIL:
                        DB              $0D,$0A,"WORKER RETURN LED $01: FAIL",$0D,$0A,0
LWT_MSG_FAIL_CLOSED_FAIL:
                        DB              $0D,$0A,"FAILED WRITE PREFLIGHT CONTRACT: FAIL",$0D,$0A,0

                        END
