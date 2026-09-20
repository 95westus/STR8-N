; RAM-only bank access and flash mutation. No code/constants fetched from ROM.
                        MODULE  V2_WORKER
                        XDEF    START
                        XDEF    V2W_END
                        XDEF    V2W_READ
                        XDEF    V2W_EXECUTE
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
; Explicit G handoff uses the preflighted address and selected overlay.
V2W_EXECUTE:
                        SEI
                        LDA     V2_SELECTED
                        JSR     V2W_SELECT
                        BRA     V2W_GO
; Snapshot up to 16 preflighted bytes, then restore ROM before returning.
V2W_READ:
                        LDA     V2_SELECTED
                        JSR     V2W_SELECT
                        LDY     #$00
V2W_READ_BYTE:         LDA     (V2_ADDR),Y
                        STA     V2_BYTES,Y
                        INY
                        CPY     V2_COUNT
                        BNE     V2W_READ_BYTE
                        LDA     V2_RESIDENT
                        JMP     V2W_SELECT
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
                        INCLUDE "str8n-v2-flash-worker.inc"
V2W_END:
                        ENDMOD
                        END
