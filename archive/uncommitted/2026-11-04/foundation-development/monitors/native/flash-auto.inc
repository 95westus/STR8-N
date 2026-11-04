; AREA lives at6A29, outside the0200-66FF source. Scan the complete bank
; so a record starting before AREA cannot expose FF payload as free space.
FA_SETUP:
        STZ FR_NEXT
        LDA #$80
        STA FR_NEXT+1
        LDA FR_AUTO
        BEQ FA_OK
        LDA BQ_AREA
        CMP #1
        BNE FA_BAD
        LDA BQ_AREA+1
        CMP FR_BANK
        BNE FA_BAD
        LDA BQ_AREA+3
        CMP #$80
        BCC FA_BAD
        LDA BQ_AREA+2
        CMP BQ_AREA+4
        LDA BQ_AREA+3
        SBC BQ_AREA+5
        BCS FA_BAD
        LDA BQ_AREA+5
        CMP #$E0
        BCC FA_FIRST
        BNE FA_BAD
        LDA BQ_AREA+4
        BNE FA_BAD
FA_FIRST:
        LDA BQ_AREA+2
        STA FR_NEXT
        LDA BQ_AREA+3
        STA FR_NEXT+1
FA_OK:
        SEC
        RTS
FA_BAD:
        CLC
        RTS
FA_IN_AREA:
        LDA V2_FLASH_PTR
        CMP BQ_AREA+2
        LDA V2_FLASH_PTR+1
        SBC BQ_AREA+3
        BCC FA_BAD
        LDA V2_FLASH_PTR
        CMP BQ_AREA+4
        LDA V2_FLASH_PTR+1
        SBC BQ_AREA+5
        BCS FA_BAD
        SEC
        RTS
FA_RECORD:
        JSR FA_IN_AREA
        BCS FA_RECORD_INSIDE
        LDA V2_FLASH_PTR
        CMP BQ_AREA+2
        LDA V2_FLASH_PTR+1
        SBC BQ_AREA+3
        BCS FA_OK
        ; Before AREA: ending exactly at its first byte is safe.
        LDA BQ_AREA+2
        CMP FR_RECORD_END
        LDA BQ_AREA+3
        SBC FR_RECORD_END+1
        BCC FA_BAD
        SEC
        RTS
FA_RECORD_INSIDE:
        LDA BQ_AREA+4
        CMP FR_RECORD_END
        LDA BQ_AREA+5
        SBC FR_RECORD_END+1
        BCC FA_BAD
        LDA FR_RECORD_END
        STA FR_NEXT
        LDA FR_RECORD_END+1
        STA FR_NEXT+1
        SEC
        RTS
FA_FITS:
        LDA BQ_AREA+4
        CMP FR_END
        LDA BQ_AREA+5
        SBC FR_END+1
        RTS
