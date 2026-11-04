; Mutation admission is stricter than F's boot-record-only reader.
; A committed same-sequence SNBT page must agree in every byte. Refuse even
; if a disagreeing candidate has a bad body CRC: history is then uncertain.
; Uncommitted/torn pages and other formats/sequences do not participate.
JE_CHECK_DUPLICATES:
        STZ V2_PTR
        LDA #$C0
        STA V2_PTR+1
JE_DUP_PAGE:
        LDY #$FF
        LDA (V2_PTR),Y
        BNE JE_DUP_NEXT
        LDY #5
JE_DUP_MAGIC:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BNE JE_DUP_NEXT
        DEY
        BPL JE_DUP_MAGIC
        LDY #11
JE_DUP_SEQUENCE:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BNE JE_DUP_NEXT
        DEY
        CPY #7
        BNE JE_DUP_SEQUENCE
        LDY #0
JE_DUP_BYTES:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BNE JE_DUP_REFUSED
        INY
        BNE JE_DUP_BYTES
JE_DUP_NEXT:
        INC V2_PTR+1
        LDA V2_PTR+1
        CMP #$E0
        BNE JE_DUP_PAGE
        SEC
        RTS
JE_DUP_REFUSED:
        CLC
        RTS
