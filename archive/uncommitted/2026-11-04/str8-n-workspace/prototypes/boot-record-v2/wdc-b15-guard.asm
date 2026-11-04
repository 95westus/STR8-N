; Factory bootstrap preflight. Uses only the linked RAM worker and RAM data.
; Reject changed installer/tables or any changed complete source bank before
; the first erase. No assumption about the vendor-occupied C/D contents.
        MODULE WDC_B15_GUARD
        XDEF GUARD_END
V2_PTR EQU $E0
V2_SELECTED EQU $F3
MIG_HASH_RANGE EQU $2222
V2W_SELECT EQU $7848
G_BANK EQU $6230
G_HASHES EQU $3500
G_SELF_HASH EQU $3F00
        CODE
GUARD_ENTRY:
        SEI
        CLD
        STZ V2_PTR
        LDA #$20
        STA V2_PTR+1
        LDA #$3F
        STA $620C
        JSR MIG_HASH_RANGE
        LDX #3
GUARD_SELF:
        LDA G_SELF_HASH,X
        CMP $6204,X
        BNE GUARD_BAD
        DEX
        BPL GUARD_SELF
        STZ G_BANK
GUARD_BANK:
        LDA G_BANK
        STA V2_SELECTED
        JSR V2W_SELECT
        STZ V2_PTR
        LDA #$80
        STA V2_PTR+1
        STZ $620C
        JSR MIG_HASH_RANGE
        LDA G_BANK
        ASL A
        ASL A
        TAX
        LDY #0
GUARD_COMPARE:
        LDA G_HASHES,X
        CMP $6204,Y
        BNE GUARD_BAD
        INX
        INY
        CPY #4
        BNE GUARD_COMPARE
        INC G_BANK
        LDA G_BANK
        CMP #4
        BNE GUARD_BANK
        JSR GUARD_CLEANUP
        SEC
        RTS
GUARD_BAD:
        JSR GUARD_CLEANUP
        CLC
        RTS
GUARD_CLEANUP:
        LDA #3
        STA V2_SELECTED
        JSR V2W_SELECT
        RTS
GUARD_END:
        ENDMOD
        END
