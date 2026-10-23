 ; A=bank, X=start page, Y=last page; C=1 is reserved. No I/O or mutation.
MS_RESERVED:
        CMP #0
        BEQ MS_RESERVED_B0
        CMP #1
        BNE MS_RESERVED_NO
        TYA
        CMP #$90
        BCC MS_RESERVED_NO
        TXA
        CMP #$B0
        BCC MS_RESERVED_YES
        TYA
        CMP #$E0
        BCS MS_RESERVED_YES
MS_RESERVED_NO:
        CLC
        RTS
MS_RESERVED_B0:
        TXA
        CMP #$E0
        BCS MS_RESERVED_NO
MS_RESERVED_YES:
        SEC
        RTS
