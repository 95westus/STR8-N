; STR8-N v2 RAM-only BRK and VIA1 Timer-1 IRQ probe.
; Load with L and start with G 2000. No flash writes. Refuses to run if any
; VIA1 interrupt source is already enabled. Restores ACR, timer latches, and
; both v2 handler pointers, then returns through the public HOLD entry.
                        INCLUDE "str8n-v2-public.inc"

START:                  SEI
                        CLD
                        LDX     #$FF
                        TXS
                        LDA     $7FCE
                        AND     #$7F
                        BEQ     SAFE
                        LDX     #<MSG_BUSY
                        LDY     #>MSG_BUSY
                        JMP     REPORT
SAFE:                   LDA     $7FCB
                        STA     SAVED_ACR
                        AND     #$3F
                        STA     $7FCB
                        LDA     $7FC6
                        STA     SAVED_T1L
                        LDA     $7FC7
                        STA     SAVED_T1H
                        LDX     #$03
SAVE_POINTERS:          LDA     $7E02,X
                        STA     SAVED_POINTERS,X
                        DEX
                        BPL     SAVE_POINTERS
                        LDA     #<BRK_HANDLER
                        STA     $7E02
                        LDA     #>BRK_HANDLER
                        STA     $7E03
                        LDA     #<IRQ_HANDLER
                        STA     $7E04
                        LDA     #>IRQ_HANDLER
                        STA     $7E05
                        STZ     BRK_SEEN
                        STZ     IRQ_SEEN
                        STZ     RESULT

; BRK must use the BRK pointer and preserve the interrupted registers/frame.
                        LDA     #$55
                        LDX     #$5A
                        LDY     #$A5
                        BRK
                        NOP
AFTER_BRK:              CMP     #$55
                        BNE     CLEANUP
                        CPX     #$5A
                        BNE     CLEANUP
                        CPY     #$A5
                        BNE     CLEANUP
                        TSX
                        CPX     #$FF
                        BNE     CLEANUP
                        LDA     BRK_SEEN
                        CMP     #$01
                        BNE     CLEANUP
                        LDA     BRK_P
                        AND     #$1C
                        CMP     #$14
                        BNE     CLEANUP

; Timer IRQ must use the IRQ pointer with B clear and restore A/X/Y and stack.
                        STZ     TIME_LO
                        STZ     TIME_HI
                        LDA     #$40
                        STA     $7FCD
                        LDA     #$C0
                        STA     $7FCE
                        LDA     #$FF
                        STA     $7FC4
                        LDA     #$3F
                        STA     $7FC5
                        LDA     #$55
                        LDX     #$5A
                        LDY     #$A5
                        CLI
WAIT_IRQ:               BIT     IRQ_SEEN
                        BNE     GOT_IRQ
                        DEC     TIME_LO
                        BNE     WAIT_IRQ
                        DEC     TIME_HI
                        BNE     WAIT_IRQ
                        BRA     CLEANUP
GOT_IRQ:                SEI
                        CMP     #$55
                        BNE     CLEANUP
                        CPX     #$5A
                        BNE     CLEANUP
                        CPY     #$A5
                        BNE     CLEANUP
                        TSX
                        CPX     #$FF
                        BNE     CLEANUP
                        LDA     IRQ_P
                        AND     #$1C
                        BNE     CLEANUP
                        LDA     IRQ_IFR
                        AND     #$C0
                        CMP     #$C0
                        BNE     CLEANUP
                        INC     RESULT

CLEANUP:                SEI
                        LDA     #$40
                        STA     $7FCE
                        LDA     $7FC4
                        LDA     SAVED_T1L
                        STA     $7FC6
                        LDA     SAVED_T1H
                        STA     $7FC7
                        LDA     SAVED_ACR
                        STA     $7FCB
                        LDX     #$03
RESTORE_POINTERS:       LDA     SAVED_POINTERS,X
                        STA     $7E02,X
                        DEX
                        BPL     RESTORE_POINTERS
                        LDX     #<MSG_FAIL
                        LDY     #>MSG_FAIL
                        LDA     RESULT
                        BEQ     REPORT
                        LDX     #<MSG_PASS
                        LDY     #>MSG_PASS
REPORT:                 STX     $80
                        STY     $81
                        LDY     #$00
PRINT:                  LDA     ($80),Y
                        BEQ     DONE
                        JSR     STR8V2_PUTC
                        INY
                        BRA     PRINT
DONE:                   JMP     STR8V2_HOLD

BRK_HANDLER:            STA     BRK_A
                        STX     BRK_X
                        STY     BRK_Y
                        TSX
                        LDA     $0101,X
                        STA     BRK_P
                        INC     BRK_SEEN
                        LDY     BRK_Y
                        LDX     BRK_X
                        LDA     BRK_A
                        RTI

IRQ_HANDLER:            STA     IRQ_A
                        STX     IRQ_X
                        STY     IRQ_Y
                        TSX
                        LDA     $0101,X
                        STA     IRQ_P
                        LDA     $7FCD
                        STA     IRQ_IFR
                        LDA     #$40
                        STA     $7FCE
                        LDA     $7FC4
                        LDA     #$01
                        STA     IRQ_SEEN
                        LDY     IRQ_Y
                        LDX     IRQ_X
                        LDA     IRQ_A
                        RTI

SAVED_ACR:              DB      $00
SAVED_T1L:              DB      $00
SAVED_T1H:              DB      $00
SAVED_POINTERS:         DS      4
BRK_SEEN:               DB      $00
IRQ_SEEN:               DB      $00
RESULT:                 DB      $00
TIME_LO:                DB      $00
TIME_HI:                DB      $00
BRK_A:                  DB      $00
BRK_X:                  DB      $00
BRK_Y:                  DB      $00
BRK_P:                  DB      $00
IRQ_A:                  DB      $00
IRQ_X:                  DB      $00
IRQ_Y:                  DB      $00
IRQ_P:                  DB      $00
IRQ_IFR:                DB      $00
MSG_PASS:               DB      $0D,$0A,"V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS",$0D,$0A,$00
MSG_FAIL:               DB      $0D,$0A,"V2 BRK/IRQ PROBE: FAIL",$0D,$0A,$00
MSG_BUSY:               DB      $0D,$0A,"REFUSE: VIA1 INTERRUPTS ALREADY ENABLED",$0D,$0A,$00
PROBE_END:
                        END
