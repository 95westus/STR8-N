; RAM-only bank handoff. No calls or data references into the flash window.
                        MODULE  V2_WORKER
                        XDEF    START
                        XDEF    V2W_END
                        INCLUDE "str8n-v2-eq.inc"
                        CODE
START:
                        SEI
                        LDA     V2_TARGET
                        CMP     #$04
                        BCS     V2W_FAIL
                        JSR     V2W_SELECT
                        LDA     $FFFC
                        STA     V2_VECTOR
                        LDA     $FFFD
                        STA     V2_VECTOR+1
                        BPL     V2W_RESTORE
                        CMP     #$FF
                        BNE     V2W_GO
                        LDA     V2_VECTOR
                        CMP     #$FF
                        BEQ     V2W_RESTORE
V2W_GO:
                        CLD
                        LDX     #$FF
                        TXS
                        STZ     V2_LED
                        JMP     (V2_VECTOR)
V2W_RESTORE:
                        LDA     V2_RESIDENT
                        JSR     V2W_SELECT
V2W_FAIL:
                        CLC
                        RTS
V2W_SELECT:
                        TAX
                        LDA     V2_PCR
                        AND     #$11
                        ORA     V2W_BITS,X
                        STA     V2_PCR
                        RTS
V2W_BITS:               DB      $CC,$CE,$EC,$EE
V2W_END:
                        ENDMOD
                        END
