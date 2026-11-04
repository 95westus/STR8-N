; Raw REC> L payload. Never flash this image. Body is patched in by the builder.
        MODULE WB_LOADER
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "workbench-layout.inc"
        INCLUDE "workbench-foundation.inc"
        CODE
WL_START:
        SEI
        CLD
        LDX #$FF
        TXS
        LDX #3
WL_ABI:
        LDA STR8V2_RAM_SIGNATURE,X
        CMP WL_RA,X
        BNE WL_LOCK
        DEX
        BPL WL_ABI
        ; F is visible at entry from REC> L. Pin the entire frozen sector.
        LDA #$F0
        LDX #16
        JSR WL_CRC_PAGES
        LDA W_CRC
        CMP #WB_F_CRC_LO
        BNE WL_BAD
        LDA W_CRC+1
        CMP #WB_F_CRC_HI
        BNE WL_BAD
        LDA #3
        LDX #WB_PAGES
        JSR WL_CRC_PAGES
        LDA W_CRC
        ORA W_CRC+1
        BNE WL_BAD
        STZ W_PTR
        STZ W_COPY
        LDA #3
        STA W_PTR+1
        LDA #>WB_ORIGIN
        STA W_COPY+1
        LDX #WB_PAGES
        LDY #0
WL_COPY:
        LDA (W_PTR),Y
        STA (W_COPY),Y
        INY
        BNE WL_COPY
        INC W_PTR+1
        INC W_COPY+1
        DEX
        BNE WL_COPY
        JMP WB_SHELL
WL_BAD:
        LDA #'!'
        JSR STR8V2_RAM_PUTC
        JMP WB_F_RECOVERY
WL_LOCK:
        BRA WL_LOCK
WL_CRC_PAGES:
        STZ W_PTR
        STA W_PTR+1
        LDA #$FF
        STA W_CRC
        STA W_CRC+1
        LDY #0
WL_CRC_NEXT:
        LDA (W_PTR),Y
        EOR W_CRC+1
        STA W_CRC+1
        PHY
        LDY #8
WL_CRC_BIT:
        ASL W_CRC
        ROL W_CRC+1
        BCC WL_CRC_SKIP
        LDA W_CRC
        EOR #$21
        STA W_CRC
        LDA W_CRC+1
        EOR #$10
        STA W_CRC+1
WL_CRC_SKIP:
        DEY
        BNE WL_CRC_BIT
        PLY
        INY
        BNE WL_CRC_NEXT
        INC W_PTR+1
        DEX
        BNE WL_CRC_NEXT
        RTS
WL_RA: DB "RA",1,13
WL_END:
        ENDMOD
        END
