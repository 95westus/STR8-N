; RAM-only bank access and flash mutation. No code/constants fetched from ROM.
                        MODULE  V2_WORKER
                        XDEF    START
                        XDEF    V2W_END
                        XDEF    V2W_READ
                        XDEF    V2W_EXECUTE
                        XDEF    V2W_BOOT_DELAY
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
; INC A tests for FF by wrapping to zero; the stored vector is unchanged.
                        INC     A
                        BNE     V2W_GO
                        LDA     V2_VECTOR
                        INC     A
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
                        BRA     V2W_RETURN
V2W_RESTORE:
                        JSR     V2W_RETURN
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
                        INCLUDE "str8n-v2-ram-console.inc"
; One reset wait tick, with no console I/O and Y preserved.
V2W_BOOT_DELAY:         LDX     #$00
V2W_BOOT_DELAY_OUTER:
V2W_BOOT_DELAY_MIDDLE:  LDA     #$00
V2W_BOOT_DELAY_INNER:   DEC     A
                        BNE     V2W_BOOT_DELAY_INNER
                        DEX
                        BNE     V2W_BOOT_DELAY_OUTER
V2W_BOOT_DELAY_DONE:    RTS
; Caller supplies FLASH_PTR/DATA. All reads during busy polling stay in RAM.
V2W_BYTE:               STZ V2_FLASH_ERROR
                        JSR V2W_UNLOCK
                        LDA #$A0
                        STA $D555
                        LDA V2_FLASH_DATA
                        STA (V2_FLASH_PTR)
                        LDA #$02
                        JSR V2W_WAIT
                        PHP
                        LDA #$F0
                        STA $D555
                        PLP
                        RTS
V2W_ERASE_RAW:          STZ V2_FLASH_ERROR
                        JSR V2W_UNLOCK
                        LDA #$80
                        STA $D555
                        JSR V2W_UNLOCK
                        LDA #$30
                        STA (V2_FLASH_PTR)
                        LDA #$FF
                        STA V2_FLASH_DATA
                        LDA #$08
                        JSR V2W_WAIT
                        PHP
                        LDA #$F0
                        STA $D555
                        PLP
                        RTS
; Log a conservative attempt before issuing an erase. Restore the target bank.
; The fixed F journal saves all monitor ZP, so staging and transfer state survive.
V2W_ACCOUNT:            LDA V2_SELECTED
                        ASL A
                        ASL A
                        ASL A
                        STA J_COUNTINDEX
                        LDA V2_SECTOR
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        ORA J_COUNTINDEX
                        STA J_COUNTINDEX
                        LDA #$03
                        JSR V2W_SELECT
                        JSR BOOT_API_ERASE
                        PHP
                        JSR V2W_BEGIN
                        PLP
                        BCS V2W_ACCOUNT_OK
                        LDA #$03
                        STA V2_FLASH_ERROR
                        CLC
V2W_ACCOUNT_OK:         RTS
V2W_READY:              LDA #$03
                        JSR V2W_SELECT
                        JSR $F0B2
                        PHP
                        JSR V2W_BEGIN
                        PLP
                        BCS V2W_READY_OK
                        LDA #$03
                        STA V2_FLASH_ERROR
                        CLC
V2W_READY_OK:           RTS
V2W_END:
                        ENDMOD
                        END
