; RAM-only exact-image B3:E EDU status update; B3:F is a required preimage.
; Includes exact old/new E and required F; only E is written.
                        MODULE  V2_E_REPAIR
                        XDEF    START
                        XDEF    E_NEW
                        XDEF    E_OLD
                        XDEF    E_END
                        XDEF    E_REQUIRED
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "e-worker-addresses.inc"

E_SRC                   EQU     $C0
E_DST                   EQU     $C2
E_MSG                   EQU     $C4

                        CODE
START:                  SEI
                        CLD
                        LDX     #$FF
                        TXS
                        LDA     V2_RESIDENT
                        CMP     #$03
                        BNE     E_WRONG_BANK
                        LDA     #$03
                        STA     V2_SELECTED
                        LDA     #$F0
                        STA     V2_SECTOR
                        JSR     V2W_SNAPSHOT
                        JSR     E_COMPARE_REQUIRED
                        BCC     E_REQUIRED_BAD
                        LDA     #$E0
                        STA     V2_SECTOR
                        JSR     V2W_SNAPSHOT
                        JSR     E_COMPARE_OLD
                        BCC     E_MISMATCH
                        LDX     #<E_PROMPT
                        LDY     #>E_PROMPT
                        JSR     E_PRINT
                        JSR     $F010
                        CMP     #'Y'
                        BNE     E_ABORT
                        JSR     E_STAGE_NEW
                        JSR     E_MUTATE
                        BCS     E_ROLLBACK
                        JSR     V2W_SNAPSHOT
                        JSR     E_COMPARE_NEW
                        BCC     E_ROLLBACK
                        LDX     #<E_SUCCESS
                        LDY     #>E_SUCCESS
                        JSR     E_PRINT
                        JMP     $F004

E_ROLLBACK:             JSR     E_STAGE_OLD
                        JSR     E_MUTATE
                        BCS     E_REPAIR_FAIL
                        JSR     V2W_SNAPSHOT
                        JSR     E_COMPARE_OLD
                        BCC     E_REPAIR_FAIL
                        LDX     #<E_RESTORED
                        LDY     #>E_RESTORED
                        JSR     E_PRINT
                        JMP     $F004
E_REPAIR_FAIL:          LDX     #<E_FAILED
                        LDY     #>E_FAILED
                        JSR     E_PRINT
                        JMP     $F007
E_REQUIRED_BAD:         LDX     #<E_F_BAD
                        LDY     #>E_F_BAD
                        JSR     E_PRINT
                        JMP     $F007
E_MISMATCH:             LDX     #<E_OLD_BAD
                        LDY     #>E_OLD_BAD
                        JSR     E_PRINT
                        JMP     $F007
E_WRONG_BANK:           LDX     #<E_BANK_BAD
                        LDY     #>E_BANK_BAD
                        JSR     E_PRINT
                        JMP     $F007
E_ABORT:                LDX     #<E_ABORTED
                        LDY     #>E_ABORTED
                        JSR     E_PRINT
                        JMP     $F007

E_MUTATE:               LDA     #$01
                        STA     V2_ERASE
                        STZ     V2_SELF
                        JSR     V2W_MUTATE
                        RTS
E_STAGE_NEW:            LDA     #<E_NEW
                        STA     E_SRC
                        LDA     #>E_NEW
                        STA     E_SRC+1
                        JMP     E_COPY_IMAGE
E_STAGE_OLD:            LDA     #<E_OLD
                        STA     E_SRC
                        LDA     #>E_OLD
                        STA     E_SRC+1
                        JMP     E_COPY_IMAGE
E_COMPARE_REQUIRED:     LDA     #<E_REQUIRED
                        STA     E_SRC
                        LDA     #>E_REQUIRED
                        STA     E_SRC+1
                        JMP     E_COMPARE_IMAGE
E_COMPARE_NEW:          LDA     #<E_NEW
                        STA     E_SRC
                        LDA     #>E_NEW
                        STA     E_SRC+1
                        JMP     E_COMPARE_IMAGE
E_COMPARE_OLD:          LDA     #<E_OLD
                        STA     E_SRC
                        LDA     #>E_OLD
                        STA     E_SRC+1
                        JMP     E_COMPARE_IMAGE

E_COPY_IMAGE:           STZ     E_DST
                        LDA     #$69
                        STA     E_DST+1
                        LDX     #$10
                        LDY     #$00
E_COPY_BYTE:            LDA     (E_SRC),Y
                        STA     (E_DST),Y
                        INY
                        BNE     E_COPY_BYTE
                        INC     E_SRC+1
                        INC     E_DST+1
                        DEX
                        BNE     E_COPY_BYTE
                        RTS
E_COMPARE_IMAGE:        STZ     E_DST
                        LDA     #$69
                        STA     E_DST+1
                        LDX     #$10
                        LDY     #$00
E_COMPARE_BYTE:         LDA     (E_SRC),Y
                        CMP     (E_DST),Y
                        BNE     E_NOT_EQUAL
                        INY
                        BNE     E_COMPARE_BYTE
                        INC     E_SRC+1
                        INC     E_DST+1
                        DEX
                        BNE     E_COMPARE_BYTE
                        SEC
                        RTS
E_NOT_EQUAL:            CLC
                        RTS

; X/Y point to a short zero-terminated message in RAM.
E_PRINT:                STX     E_MSG
                        STY     E_MSG+1
                        LDY     #$00
E_PRINT_BYTE:           LDA     (E_MSG),Y
                        BEQ     E_PRINT_DONE
                        JSR     $F00D
                        INY
                        BNE     E_PRINT_BYTE
E_PRINT_DONE:           RTS

E_F_BAD:               DB      $0D,$0A,"B3:F REQUIRED IMAGE MISMATCH",$0D,$0A,0
E_PROMPT:               DB      $0D,$0A,"B3:E exact; TYPE Y to repair> ",0
E_SUCCESS:              DB      $0D,$0A,"B3:E VERIFIED; RESET",$0D,$0A,0
E_RESTORED:             DB      $0D,$0A,"B3:E OLD RESTORED; RESET",$0D,$0A,0
E_FAILED:               DB      $0D,$0A,"B3:E REPAIR FAILED",$0D,$0A,0
E_OLD_BAD:              DB      $0D,$0A,"B3:E OLD IMAGE MISMATCH",$0D,$0A,0
E_BANK_BAD:             DB      $0D,$0A,"B3 RESIDENCY REQUIRED",$0D,$0A,0
E_ABORTED:              DB      $0D,$0A,"B3:E REPAIR ABORTED",$0D,$0A,0
E_REQUIRED:             INCLUDE "e-required-image.inc"
E_NEW:                  INCLUDE "e-new-image.inc"
E_OLD:                  INCLUDE "e-old-image.inc"
E_END:
                        ENDMOD
                        END
