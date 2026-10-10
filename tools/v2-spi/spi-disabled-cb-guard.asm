; Candidate preflight for the pending-flag case only; not installed firmware.
; Only default input CB modes, disabled CB IRQs, no shift/latch owner, and
; input SPI pins permit an ORB read. Existing INIT ownership checks follow.
        MODULE SPI_DISABLED_CB_GUARD
        XDEF START
        XDEF APP_END
        CODE
START:
        PHP
        SEI
        LDA $7FCE
        AND #$18
        BNE REFUSE
        LDA $7FCD
        AND #$18
        BEQ SAFE
        LDA $7FCC
        AND #$F0
        BNE REFUSE
        LDA $7FCB
        AND #$1E
        BNE REFUSE
        LDA $7FC2
        AND #$0F
        BNE REFUSE
        LDA $7FC0
        LDA $7FCD
        AND #$18
        BNE REFUSE
SAFE:   PLP
        LDA #0
        SEC
        RTS
REFUSE:
        PLP
        LDA #1
        CLC
        RTS
APP_END:
        ENDMOD
        END
