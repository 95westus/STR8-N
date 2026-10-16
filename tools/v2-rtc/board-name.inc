; BN,1,0; sequence LE32; length 0..8; eight zero-padded printable bytes;
; reserved FF through byte 27; CRC16 LE at 28; FF at 30; commit 0 at 31.
; Shared append-only EI/TZ tail. Uncommitted and malformed slots stay occupied.
BN_READ:
        STZ BN_LENGTH
        STZ BN_FREE+1
        LDX #3
BN_RESET:
        STZ BN_SEQ,X
        DEX
        BPL BN_RESET
        LDA $7FEC
        PHA
        AND #$11
        ORA #$EE
        STA $7FEC
        STZ TZ_PTR
        LDA #$9C
        STA TZ_PTR+1
BN_SLOT:
        LDY #0
BN_BLANK:
        LDA (TZ_PTR),Y
        CMP #$FF
        BNE BN_CHECK
        INY
        CPY #32
        BNE BN_BLANK
        LDA BN_FREE+1
        BNE BN_NEXT
        LDA TZ_PTR
        STA BN_FREE
        LDA TZ_PTR+1
        STA BN_FREE+1
        BRA BN_NEXT
BN_CHECK:
        LDY #31
        LDA (TZ_PTR),Y
        BNE BN_NEXT
        LDY #3
BN_HEADER:
        LDA (TZ_PTR),Y
        CMP BN_MAGIC,Y
        BNE BN_NEXT
        DEY
        BPL BN_HEADER
        JSR TZ_CRC
        LDY #28
        LDA (TZ_PTR),Y
        CMP TZ_SUM
        BNE BN_NEXT
        INY
        LDA (TZ_PTR),Y
        CMP TZ_SUM+1
        BNE BN_NEXT
        LDY #8
        LDA (TZ_PTR),Y
        CMP #9
        BCS BN_NEXT
        STA BN_WORK
        TAX
BN_CHAR_CHECK:
        INY
        CPY #17
        BEQ BN_NEWEST
        LDA (TZ_PTR),Y
        CPX #0
        BEQ BN_PADDING
        CMP #$21
        BCC BN_NEXT
        CMP #$7F
        BCS BN_NEXT
        DEX
        BRA BN_CHAR_CHECK
BN_PADDING:
        CMP #0
        BNE BN_NEXT
        BRA BN_CHAR_CHECK
BN_NEWEST:
        LDY #7
        LDX #3
BN_NEWER:
        LDA (TZ_PTR),Y
        CMP BN_SEQ,X
        BCC BN_NEXT
        BNE BN_KEEP
        DEY
        DEX
        BPL BN_NEWER
BN_KEEP:
        LDY #7
        LDX #3
BN_COPY_SEQ:
        LDA (TZ_PTR),Y
        STA BN_SEQ,X
        DEY
        DEX
        BPL BN_COPY_SEQ
        LDA BN_WORK
        STA BN_LENGTH
        LDY #9
        LDX #0
BN_COPY:
        LDA (TZ_PTR),Y
        STA BN_TEXT,X
        INY
        INX
        CPX #8
        BNE BN_COPY
BN_NEXT:
        LDA TZ_PTR
        CLC
        ADC #32
        STA TZ_PTR
        BCC BN_PAGE
        INC TZ_PTR+1
BN_PAGE:
        LDA TZ_PTR+1
        CMP #$A0
        BNE BN_SLOT
        PLA
        STA $7FEC
        RTS
BN_SHOW:
        JSR BN_READ
        LDA BN_LENGTH
        BEQ BN_SHOW_DONE
        LDX #<BN_LABEL
        LDY #>BN_LABEL
        JSR PRINT
        LDX #0
BN_PRINT:
        LDA BN_TEXT,X
        JSR $7E6D
        INX
        CPX BN_LENGTH
        BNE BN_PRINT
        JSR $7E7F
BN_SHOW_DONE:
        RTS
BN_MAGIC DB "BN",1,0
BN_LABEL DB "Board: ",0
BN_LENGTH DB 0
BN_WORK DB 0
BN_TEXT DS 8
BN_SEQ DS 4
BN_FREE DS 2
