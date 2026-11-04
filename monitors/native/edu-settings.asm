; Read-only saved EDU mode. Intended XIP in unused native-loader padding.
; Above BASE1; no public F ABI change, no I/O, flash writes or owner ZP.
; EC/1 helper; ED/1 records share9C00-9FFF with BN/TZ/BA/EI.
; Return A=mode0/1, C=valid. No saved record defaults ON. Conflicting newest
; sequence is refused. Caller leaves its session setting unchanged on C=0.
        MODULE EDU_SETTINGS
        INCLUDE "edu-settings-bindings.inc"
        CODE
EC_START:
        DB "EC",1,1,"PR05"
        JMP EC_READ
EC_PTR EQU $E0
EC_SEQ EQU $6700
EC_MODE EQU $6704
EC_FOUND EQU $6705
EC_ERROR EQU $6706
EC_CANDIDATE EQU $6707
EC_READ:
        LDX #3
EC_ZERO:
        STZ EC_SEQ,X
        DEX
        BPL EC_ZERO
        STZ EC_FOUND
        STZ EC_ERROR
        LDA #1
        STA EC_MODE
        STZ EC_PTR
        LDA #EC_SOURCE_PAGE
        STA EC_PTR+1
EC_SLOT:
        LDY #31
        LDA (EC_PTR),Y
        BNE EC_NEXT
        LDY #3
EC_MAGIC:
        LDA (EC_PTR),Y
        CMP EC_RECORD_MAGIC,Y
        BNE EC_NEXT
        DEY
        BPL EC_MAGIC
        LDY #8
        LDA (EC_PTR),Y
        CMP #2
        BCS EC_NEXT
        STA EC_CANDIDATE
        LDY #30
        LDA (EC_PTR),Y
        CMP #$FF
        BNE EC_NEXT
        LDY #9
EC_RESERVED:
        LDA (EC_PTR),Y
        CMP #$FF
        BNE EC_NEXT
        INY
        CPY #28
        BCC EC_RESERVED
        JSR EC_CRC_INIT
        LDY #0
EC_CRC:
        LDA (EC_PTR),Y
        JSR EC_CRC_BYTE
        INY
        CPY #28
        BCC EC_CRC
        LDA (EC_PTR),Y
        CMP EC_CRC_LOW
        BNE EC_NEXT
        INY
        LDA (EC_PTR),Y
        CMP EC_CRC_LOW+1
        BNE EC_NEXT
        LDY #7
        LDX #3
EC_COMPARE:
        LDA (EC_PTR),Y
        CMP EC_SEQ,X
        BCC EC_NEXT
        BNE EC_KEEP
        DEY
        DEX
        BPL EC_COMPARE
        ; Zero sequence cannot establish a record; it is ignored. An equal
        ; nonzero sequence must agree with the current value.
        LDA EC_FOUND
        BEQ EC_NEXT
        LDA EC_CANDIDATE
        CMP EC_MODE
        BEQ EC_NEXT
        LDA #$41
        STA EC_ERROR
        BRA EC_NEXT
EC_KEEP:
        STZ EC_ERROR
        LDY #7
        LDX #3
EC_COPY_SEQ:
        LDA (EC_PTR),Y
        STA EC_SEQ,X
        DEY
        DEX
        BPL EC_COPY_SEQ
        LDA EC_CANDIDATE
        STA EC_MODE
        INC EC_FOUND
EC_NEXT:
        CLC
        LDA EC_PTR
        ADC #32
        STA EC_PTR
        BCC EC_PAGE_READY
        INC EC_PTR+1
EC_PAGE_READY:
        LDA EC_PTR+1
        CMP #EC_SOURCE_END_PAGE
        BCC EC_SLOT
        LDA EC_ERROR
        BNE EC_BAD
        LDA EC_MODE
        SEC
        RTS
EC_BAD:
        CLC
        RTS
EC_RECORD_MAGIC: DB "ED",1,0
EC_END:
        ENDMOD
        END
