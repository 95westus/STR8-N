MA_CHECK_DUPLICATES:

        STZ V2_PTR
        LDA #$C0
        STA V2_PTR+1
MDUP_DUP_PAGE:
        LDY #$FF
        LDA (V2_PTR),Y
        BEQ MD_LONG_1
        JMP MDUP_DUP_NEXT
MD_LONG_1:
        LDY #5
MDUP_DUP_MAGIC:
        LDA (V2_PTR),Y
        CMP MA_JOURNAL,Y
        BEQ MD_LONG_2
        JMP MDUP_DUP_NEXT
MD_LONG_2:
        DEY
        BMI MD_LONG_3
        JMP MDUP_DUP_MAGIC
MD_LONG_3:
        LDY #11
MDUP_DUP_SEQUENCE:
        LDA (V2_PTR),Y
        CMP MA_JOURNAL,Y
        BEQ MD_LONG_4
        JMP MDUP_DUP_NEXT
MD_LONG_4:
        DEY
        CPY #7
        BEQ MD_LONG_5
        JMP MDUP_DUP_SEQUENCE
MD_LONG_5:
        LDY #0
MDUP_DUP_BYTES:
        LDA (V2_PTR),Y
        CMP MA_JOURNAL,Y
        BEQ MD_LONG_6
        JMP MDUP_DUP_REFUSED
MD_LONG_6:
        INY
        BEQ MD_LONG_7
        JMP MDUP_DUP_BYTES
MD_LONG_7:
MDUP_DUP_NEXT:
        INC V2_PTR+1
        LDA V2_PTR+1
        CMP #$E0
        BEQ MD_LONG_8
        JMP MDUP_DUP_PAGE
MD_LONG_8:
        SEC
        RTS
MDUP_DUP_REFUSED:
        CLC
        RTS

