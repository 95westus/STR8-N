; ----------------------------------------------------------------------------
; str8-worker.asm
; RAM-resident STR8 flash-service worker.
;
; Every variant links for $0200 and must fit in the $0200-$09FF STR8 RAM worker
; tray. The full and jump workers are copied from high flash; the mutation-only
; worker is uploaded by I. Keep them independent: once running, they must not
; call ROM code because they switch flash banks and may erase Bank 3's top
; sector.
; ----------------------------------------------------------------------------

                        MODULE          STR8_WORKER_APP

                        XDEF            START
                        IF              STR8_WORKER_MUTATION_ONLY
                        ELSE
                        XDEF            STR8W_BANK_SELECT_SERVICE
                        ENDIF
                        XDEF            STR8_WORKER_END

                        INCLUDE         "str8-record-eq.inc"
                        INCLUDE         "str8-jump-eq.inc"
                        INCLUDE         "str8-worker-eq.inc"

; 2026-05-07T22:58-05:00        WLP2        Combined ROM layout moves STR8 to $F000.
; 2026-05-17T21:20-05:00        WLP2        Worker source storage formerly moved to $FC00.
; 2026-05-21T23:55-05:00        WLP2        Worker source is now packed down from $FFEF.
; 2026-07-23T13:07-05:00        Codex       Size pass shares buffer and flash-operation tails.
; 2026-07-23T17:27-05:00        Codex       Enrollment mode is removed with the E command.
; 2026-08-01T22:15-05:00        Codex       V0 copy/restore modes retire; unknown modes fail closed.
STR8_COPY_MODE_PROGRAM_STAGED EQU        $05
STR8_COPY_MODE_STAGE_BANK_SECTOR EQU    $06

STR8_RESET_VECTOR       EQU             $FFFC

STR8W_PTR_LO            EQU             $CD
STR8W_PTR_HI            EQU             $CE
STR8W_BUF_LO            EQU             $CF
STR8W_BUF_HI            EQU             $D0
STR8W_ADDR_LO           EQU             $D1
STR8W_ADDR_HI           EQU             $D2
STR8W_DATA              EQU             $D3
STR8W_TMO0              EQU             $D4
STR8W_TMO1              EQU             $D5
STR8W_TMO2              EQU             $D6

STR8_STATE_BASE         EQU             $1FE9
STR8_STATE_END          EQU             $1FFF
STR8_MARK_SECTOR_HI     EQU             $1FE9
STR8_MARK_ADDR_LO       EQU             $1FEA
STR8_MARK_ADDR_HI       EQU             $1FEB
STR8_COPY_SRC_BANK      EQU             $1FEE
STR8_COPY_DST_BANK      EQU             $1FEF
STR8_COPY_MODE          EQU             $1FF0
STR8_STAGE_BUF_HI       EQU             $1FF6

STR8_FTDI_VIA_PCR       EQU             STR8_BANK_STATE_BYTE
STR8_BANK_PCR_MASK      EQU             STR8_BANK_STATE_MASK

STR8_FLASH_UNLOCK1      EQU             $D555
STR8_FLASH_UNLOCK2      EQU             $AAAA
STR8_FLASH_ERASE_TMO_HI EQU             $08
STR8_FLASH_WRITE_TMO_HI EQU             $02

                        CODE
START:
                        IF              STR8_WORKER_MUTATION_ONLY
                        JMP             STR8W_START_BODY
STR8W_MUTATION_SIG:
                        DB              STR8_MUTATION_WORKER_SIG0
                        DB              STR8_MUTATION_WORKER_SIG1
                        DB              STR8_MUTATION_WORKER_SIG2
                        DB              STR8_MUTATION_WORKER_SIG3
                        ELSE
                        IF              STR8_WORKER_JUMP_ONLY
                        JMP             STR8W_JUMP_START
                        ELSE
                        JMP             STR8W_START_BODY
                        ENDIF
                        ENDIF

; Fixed $0203 entry used by the resident $F010 bank-selection service.
; IN: A=bank 0-3. OUT: C=1 selected; C=0 invalid. A/X are clobbered.
; The caller and return address must be in RAM below $8000.
                        IF              STR8_WORKER_MUTATION_ONLY
                        ELSE
STR8W_BANK_SELECT_SERVICE:
                        PHP
                        SEI
                        CMP             #STR8_BANK_COUNT
                        BCS             ?BAD_BANK
                        JSR             STR8W_BANK_SELECT_A
                        PLP
                        SEC
                        RTS
?BAD_BANK:             PLP
                        CLC
                        RTS
                        ENDIF

; Each linked worker accepts only its published mode subset. Any other value
; returns C=0 before selecting a bank or touching flash.
                        IF              STR8_WORKER_JUMP_ONLY
STR8W_JUMP_START:
                        LDA             STR8_COPY_MODE
                        CMP             #STR8_COPY_MODE_JUMP_BANK
                        BEQ             ?RUN_JUMP
                        CLC
                        RTS
?RUN_JUMP:
                        PHP
                        SEI
                        JSR             STR8W_JUMP_BANK
                        JSR             STR8W_SELECT_BANK3
                        PLP
                        CLC
                        RTS
                        ELSE
STR8W_START_BODY:
                        PHP
                        SEI
                        LDA             STR8_COPY_MODE
                        CMP             #STR8_COPY_MODE_PROGRAM_STAGED
                        BEQ             ?PROGRAM_STAGED
                        CMP             #STR8_COPY_MODE_STAGE_BANK_SECTOR
                        BEQ             ?STAGE_BANK_SECTOR
                        CMP             #STR8_COPY_MODE_PROGRAM_RECORD
                        BEQ             ?PROGRAM_RECORD
                        IF              STR8_WORKER_MUTATION_ONLY
                        ELSE
                        CMP             #STR8_COPY_MODE_JUMP_BANK
                        BEQ             ?JUMP_BANK
                        ENDIF
                        PLP
                        CLC
                        RTS
?PROGRAM_STAGED:
                        JSR             STR8W_PROGRAM_STAGED_SECTOR
                        BRA             ?DONE
?STAGE_BANK_SECTOR:
                        JSR             STR8W_STAGE_BANK_SECTOR
                        BRA             ?DONE
?PROGRAM_RECORD:
                        JSR             STR8W_PROGRAM_RECORD
                        BRA             ?DONE
                        IF              STR8_WORKER_MUTATION_ONLY
                        ELSE
?JUMP_BANK:
                        JSR             STR8W_JUMP_BANK
                        ENDIF
?DONE:
                        BCC             ?FAIL
                        JSR             STR8W_SELECT_BANK3
                        PLP
                        SEC
                        RTS
?FAIL:
                        JSR             STR8W_SELECT_BANK3
                        PLP
                        CLC
                        RTS
                        ENDIF

; Non-destructive opaque-bank handoff. Success resets CPU software state and
; never returns. Failure returns through START, which restores Bank 3 first.
                        IF              STR8_WORKER_MUTATION_ONLY
                        ELSE
STR8W_JUMP_BANK:
                        LDA             STR8_JUMP_BANK
                        CMP             #STR8_BANK_COUNT
                        BCS             ?BAD_BANK
                        JSR             STR8W_BANK_SELECT_A
                        LDA             STR8_RESET_VECTOR
                        STA             STR8_JUMP_VEC_LO
                        LDA             STR8_RESET_VECTOR+1
                        STA             STR8_JUMP_VEC_HI
                        CMP             #$80
                        BCC             ?LOW_VECTOR
                        CMP             #$FF
                        BNE             ?GO
                        LDA             STR8_JUMP_VEC_LO
                        CMP             #$FF
                        BEQ             ?ERASED_VECTOR
?GO:
                        LDA             #STR8_JUMP_STATUS_GO
                        STA             STR8_JUMP_STATUS
                        SEI
                        CLD
                        LDX             #$FF
                        TXS
                        STZ             STR8_BANK_JUMP_SIG1
                        LDA             STR8_JUMP_BANK
                        STA             STR8_BANK_LAST_JUMP
                        LDA             #STR8_BANK_JUMP_SIG0_VALUE
                        STA             STR8_BANK_JUMP_SIG0
                        LDA             #STR8_BANK_JUMP_SIG1_VALUE
                        STA             STR8_BANK_JUMP_SIG1
                        JMP             (STR8_JUMP_VEC_LO)
?BAD_BANK:
                        LDA             #STR8_JUMP_STATUS_BANK
                        BRA             ?FAIL
?LOW_VECTOR:
                        LDA             #STR8_JUMP_STATUS_LOW
                        BRA             ?FAIL
?ERASED_VECTOR:
                        LDA             #STR8_JUMP_STATUS_ERASED
?FAIL:
                        STA             STR8_JUMP_STATUS
                        CLC
                        RTS
                        ENDIF

                        IF              STR8_WORKER_JUMP_ONLY
                        ELSE
STR8W_PROGRAM_STAGED_SECTOR:
                        JSR             STR8W_ERASE_DST_SECTOR
                        BCC             ?FAIL
                        JSR             STR8W_PROGRAM_DST_SECTOR
                        BCC             ?FAIL
                        JSR             STR8W_VERIFY_DST_SECTOR
                        BCC             ?FAIL
                        SEC
                        RTS
?FAIL:
                        CLC
                        RTS

STR8W_STAGE_BANK_SECTOR:
                        LDA             STR8_COPY_SRC_BANK
                        JSR             STR8W_BANK_SELECT_A
                        STZ             STR8W_PTR_LO
                        LDA             STR8_MARK_SECTOR_HI
                        STA             STR8W_PTR_HI
                        STZ             STR8W_BUF_LO
                        LDA             STR8_STAGE_BUF_HI
                        STA             STR8W_BUF_HI
                        JMP             STR8W_COPY_PTR_TO_ACTIVE_BUF

; Program one preflighted record without erase. Repeat a complete one-to-zero
; preflight after selecting Bank 3, before the first byte write. This protects
; directory writes even if a resident-side preflight observed the wrong bank.
STR8W_PROGRAM_RECORD:
                        JSR             STR8W_SELECT_BANK3
                        JSR             STR8W_RECORD_INIT
                        LDX             STR8_REC_DATA_LEN
                        BEQ             ?OK
?PREFLIGHT:
                        LDY             #$00
                        LDA             (STR8W_BUF_LO),Y
                        STA             STR8W_DATA
                        LDA             (STR8W_ADDR_LO),Y
                        AND             STR8W_DATA
                        CMP             STR8W_DATA
                        BNE             ?FAIL
                        JSR             STR8W_RECORD_ADVANCE
                        DEX
                        BNE             ?PREFLIGHT

                        JSR             STR8W_RECORD_INIT
                        LDX             STR8_REC_DATA_LEN
?BYTE:
                        LDY             #$00
                        LDA             (STR8W_BUF_LO),Y
                        STA             STR8W_DATA
                        LDA             (STR8W_ADDR_LO),Y
                        CMP             STR8W_DATA
                        BEQ             ?NEXT
                        JSR             STR8W_FLASH_WRITE
                        BCC             ?FAIL
?NEXT:
                        JSR             STR8W_RECORD_ADVANCE
                        DEX
                        BNE             ?BYTE
?OK:
                        SEC
                        RTS
?FAIL:
                        LDA             STR8W_ADDR_LO
                        STA             STR8_REC_FAIL_LO
                        LDA             STR8W_ADDR_HI
                        STA             STR8_REC_FAIL_HI
                        LDY             #$00
                        LDA             (STR8W_ADDR_LO),Y
                        STA             STR8_REC_OBSERVED
                        LDA             STR8W_DATA
                        STA             STR8_REC_EXPECTED
                        CLC
                        RTS

STR8W_RECORD_INIT:
                        LDA             STR8_REC_ADDR_LO
                        STA             STR8W_ADDR_LO
                        LDA             STR8_REC_ADDR_HI
                        STA             STR8W_ADDR_HI
                        STZ             STR8W_BUF_LO
                        LDA             #STR8_REC_DATA_BUF_HI
                        STA             STR8W_BUF_HI
                        RTS

STR8W_RECORD_ADVANCE:
                        INC             STR8W_ADDR_LO
                        BNE             ?DATA
                        INC             STR8W_ADDR_HI
?DATA:
                        INC             STR8W_BUF_LO
                        ; V1 starts at $7B00 and accepts at most 252 bytes, so
                        ; the record-buffer low byte cannot wrap.
                        RTS

STR8W_COPY_PTR_TO_ACTIVE_BUF:
?PAGE:
                        LDY             #$00
?BYTE:
                        LDA             (STR8W_PTR_LO),Y
                        STA             (STR8W_BUF_LO),Y
                        INY
                        BNE             ?BYTE
                        INC             STR8W_PTR_HI
                        INC             STR8W_BUF_HI
                        JSR             STR8W_ACTIVE_BUF_END_REACHED
                        BNE             ?PAGE
                        RTS

; 2026-05-07T19:14-05:00        WLP2        Skip erased sectors and verify erase completion.
STR8W_ERASE_DST_SECTOR:
                        LDA             STR8_COPY_DST_BANK
                        JSR             STR8W_BANK_SELECT_A
                        JSR             STR8W_DST_SECTOR_ERASED
                        BCS             ?OK
                        LDA             STR8_MARK_ADDR_LO
                        STA             STR8W_ADDR_LO
                        LDA             STR8_MARK_ADDR_HI
                        STA             STR8W_ADDR_HI
                        JSR             STR8W_FLASH_ERASE
                        BCC             ?FAIL
                        JSR             STR8W_DST_SECTOR_ERASED
                        BCS             ?OK
?FAIL:
                        CLC
                        RTS
?OK:
                        SEC
                        RTS

; OUT: C=1 if the selected destination sector is all $FF.
;      C=0 and STR8_MARK_ADDR_* names the first non-erased byte otherwise.
STR8W_DST_SECTOR_ERASED:
                        STZ             STR8W_PTR_LO
                        LDA             STR8_MARK_SECTOR_HI
                        STA             STR8W_PTR_HI
?PAGE:
                        LDY             #$00
?BYTE:
                        LDA             (STR8W_PTR_LO),Y
                        CMP             #$FF
                        BNE             ?NOT_ERASED
                        INY
                        BNE             ?BYTE
                        INC             STR8W_PTR_HI
                        LDA             STR8W_PTR_HI
                        AND             #$0F
                        BNE             ?PAGE
                        SEC
                        RTS
?NOT_ERASED:
                        TYA
                        STA             STR8_MARK_ADDR_LO
                        LDA             STR8W_PTR_HI
                        STA             STR8_MARK_ADDR_HI
                        CLC
                        RTS

STR8W_PROGRAM_DST_SECTOR:
                        LDA             STR8_COPY_DST_BANK
                        JSR             STR8W_BANK_SELECT_A
                        STZ             STR8W_ADDR_LO
                        LDA             STR8_MARK_SECTOR_HI
                        STA             STR8W_ADDR_HI
                        STZ             STR8W_BUF_LO
                        LDA             STR8_STAGE_BUF_HI
                        STA             STR8W_BUF_HI
?BYTE:
                        LDY             #$00
                        LDA             (STR8W_BUF_LO),Y
                        CMP             #$FF
                        BEQ             ?NEXT
                        STA             STR8W_DATA
                        JSR             STR8W_FLASH_WRITE
                        BCS             ?NEXT
                        LDA             STR8W_ADDR_LO
                        STA             STR8_MARK_ADDR_LO
                        LDA             STR8W_ADDR_HI
                        STA             STR8_MARK_ADDR_HI
                        CLC
                        RTS
?NEXT:
                        INC             STR8W_ADDR_LO
                        INC             STR8W_BUF_LO
                        BNE             ?BYTE
                        INC             STR8W_ADDR_HI
                        INC             STR8W_BUF_HI
                        JSR             STR8W_ACTIVE_BUF_END_REACHED
                        BNE             ?BYTE
                        RTS

STR8W_VERIFY_DST_SECTOR:
                        LDA             STR8_COPY_DST_BANK
                        JSR             STR8W_BANK_SELECT_A
                        STZ             STR8W_PTR_LO
                        LDA             STR8_MARK_SECTOR_HI
                        STA             STR8W_PTR_HI
                        STZ             STR8W_BUF_LO
                        LDA             STR8_STAGE_BUF_HI
                        STA             STR8W_BUF_HI
?PAGE:
                        LDY             #$00
?BYTE:
                        LDA             (STR8W_PTR_LO),Y
                        CMP             (STR8W_BUF_LO),Y
                        BNE             ?FAIL
                        INY
                        BNE             ?BYTE
                        INC             STR8W_PTR_HI
                        INC             STR8W_BUF_HI
                        JSR             STR8W_ACTIVE_BUF_END_REACHED
                        BNE             ?PAGE
                        RTS
?FAIL:
                        TYA
                        STA             STR8_MARK_ADDR_LO
                        LDA             STR8W_PTR_HI
                        STA             STR8_MARK_ADDR_HI
                        CLC
                        RTS

STR8W_ACTIVE_BUF_END_REACHED:
                        LDA             STR8_STAGE_BUF_HI
                        CLC
                        ADC             #$10
                        CMP             STR8W_BUF_HI
                        RTS

STR8W_FLASH_ERASE:
                        JSR             STR8W_FLASH_UNLOCK
                        LDA             #$80
                        STA             STR8_FLASH_UNLOCK1
                        JSR             STR8W_FLASH_UNLOCK
                        LDA             #$30
                        LDY             #$00
                        STA             (STR8W_ADDR_LO),Y
                        LDA             #$FF
                        STA             STR8W_DATA
                        LDA             #STR8_FLASH_ERASE_TMO_HI
                        JMP             STR8W_FLASH_WAIT

STR8W_FLASH_WRITE:
                        LDY             #$00
                        LDA             (STR8W_ADDR_LO),Y
                        CMP             STR8W_DATA
                        BEQ             ?OK
                        AND             STR8W_DATA
                        CMP             STR8W_DATA
                        BNE             STR8W_FLASH_RESET_FAIL
                        JSR             STR8W_FLASH_UNLOCK
                        LDA             #$A0
                        STA             STR8_FLASH_UNLOCK1
                        LDA             STR8W_DATA
                        STA             (STR8W_ADDR_LO),Y
                        LDA             #STR8_FLASH_WRITE_TMO_HI
                        JMP             STR8W_FLASH_WAIT
?OK:
                        RTS

STR8W_FLASH_WAIT:
                        STZ             STR8W_TMO0
                        STZ             STR8W_TMO1
                        STA             STR8W_TMO2
?POLL:
                        LDY             #$00
                        LDA             (STR8W_ADDR_LO),Y
                        CMP             STR8W_DATA
                        BEQ             ?OK
                        DEC             STR8W_TMO0
                        BNE             ?POLL
                        DEC             STR8W_TMO1
                        BNE             ?POLL
                        DEC             STR8W_TMO2
                        BNE             ?POLL
                        BRA             STR8W_FLASH_RESET_FAIL
?OK:
                        RTS

STR8W_FLASH_UNLOCK:
                        LDA             #$AA
                        STA             STR8_FLASH_UNLOCK1
                        LDA             #$55
                        STA             STR8_FLASH_UNLOCK2
                        RTS

STR8W_FLASH_RESET_FAIL:
                        LDA             #$F0
                        STA             STR8_FLASH_UNLOCK1
                        CLC
                        RTS
                        ENDIF

STR8W_SELECT_BANK3:
                        LDA             #$03
STR8W_BANK_SELECT_A:
                        AND             #$03
                        TAX
                        LDA             STR8W_BANK_BIT_TABLE,X
                        PHA
                        LDA             #STR8_BANK_PCR_MASK
                        TRB             STR8_FTDI_VIA_PCR
                        PLA
                        TSB             STR8_FTDI_VIA_PCR
                        RTS

STR8W_BANK_BIT_TABLE:
                        DB              $CC,$CE,$EC,$EE

STR8_WORKER_END:
                        ENDMOD

                        END
