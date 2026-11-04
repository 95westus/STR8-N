; Native SNBT reservation extension for the exact qualified integrated template.
; The generic transaction loop and its copied NOR worker remain unchanged.
; Host composition verifies every referenced template opcode before overlaying.
        MODULE NATIVE_RESERVE
        XDEF NATIVE_END
        CODE
NATIVE_START:
        SEI
        CLD
        STZ $6236
        JSR $305F             ; exact four-bank and complete $3600-page FNV
        BCC NATIVE_BAD
        LDA $3510
        BNE NATIVE_BAD        ; native snapshots are page aligned
        LDA $3511
        AND #$E0
        CMP #$C0
        BNE NATIVE_BAD
        LDX #5
NATIVE_MAGIC_CHECK:
        LDA $3600,X
        CMP NATIVE_MAGIC,X
        BNE NATIVE_BAD
        DEX
        BPL NATIVE_MAGIC_CHECK
        LDA $36FF
        BNE NATIVE_BAD
        LDA $36FE
        CMP #$FF
        BNE NATIVE_BAD
        JSR $30F0             ; unchanged CRC loop, length/expected bytes patched
        BCC NATIVE_BAD
        LDA #3
        STA $F3
        JSR $7848
        JSR $31F7             ; set $E4/E5 to reservation address
        LDY #0
NATIVE_BLANK:
        LDA ($E4),Y
        CMP #$FF
        BNE NATIVE_BAD
        INY
        BNE NATIVE_BLANK
        LDA #1
        STA $F4
        JSR $3214             ; qualified BYTE loop, bound changed 127 -> 255
        BCC NATIVE_BAD
        JSR NATIVE_VERIFY_BODY
        BCC NATIVE_BAD
        LDA #$FF
        STA $E4
        STZ $F0
        JSR $7AF9             ; existing RAM-only NOR BYTE, commit255 last
        BCC NATIVE_BAD
        JSR $31F7
        LDY #0
NATIVE_VERIFY_ALL:
        LDA ($E4),Y
        CMP $3600,Y
        BNE NATIVE_BAD
        INY
        BNE NATIVE_VERIFY_ALL
        JSR $3055             ; restore B3 and clear NMI hold
        SEC
        RTS
NATIVE_BAD:
        INC $6236
        JSR $3055
        CLC
        RTS
NATIVE_VERIFY_BODY:
        JSR $31F7
        LDY #0
NATIVE_BODY_BYTE:
        LDA ($E4),Y
        CMP $3600,Y
        BNE NATIVE_VERIFY_BAD
        INY
        CPY #$FF
        BNE NATIVE_BODY_BYTE
        LDA ($E4),Y
        CMP #$FF
        BNE NATIVE_VERIFY_BAD
        SEC
        RTS
NATIVE_VERIFY_BAD:
        CLC
        RTS
NATIVE_MAGIC: DB "SNBT",1,32
NATIVE_END:
        ENDMOD
        END
