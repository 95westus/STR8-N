MM_X_COPY:
        LDA BQ_MAGIC
        CMP #BQ_ON
        BEQ MM_BM_BAD
        LDX #0
MB_X_LINE:
        LDA MM_BM_LINE,X
        STA $6740,X
        BEQ MB_X_MARK
        INX
        CPX #41
        BCC MB_X_LINE
        JMP MM_BM_BAD
MB_X_MARK:
        LDX #7
MB_X_MAGIC:
        LDA MB_X_MAGIC_BYTES,X
        STA $6770,X
        DEX
        BPL MB_X_MAGIC
        LDA #3
        STA $6778
        LDX #0
MB_X_ORIGINAL:
        LDA $6500,X
        STA $6A00,X
        INX
        CPX #$D0
        BCC MB_X_ORIGINAL
        LDX #0
MB_X_ZP:
        LDA $6400,X
        STA $00,X
        INX
        CPX #$E0
        BCC MB_X_ZP
        LDX #HC_IMAGE_END-HC_IMAGE-1
MB_X_TAIL:
        LDA HC_IMAGE,X
        STA $6B00,X
        DEX
        BPL MB_X_TAIL
        JMP $6B00
MB_X_MAGIC_BYTES: DB "BX",1,1,"PR05"
        INCLUDE "handoff-image.inc"
