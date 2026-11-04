; Pre-WB commands. No owner RAM is borrowed by admission/loading.
; The SL+WS overlay occupies existing storage-image padding at B1:D900.
SX_DISPATCH:
        LDA BQ_MAGIC
        CMP #BQ_ON
        BEQ SX_NO
        LDX #<SX_S19_WORD
        LDY #>SX_S19_WORD
        JSR S_MATCH
        BCC SX_STORE
        JSR S_END_ARGS
        BCC SX_NO
        LDA #0
        BRA SX_LOAD
SX_STORE:
        LDX #<SX_STORE_WORD
        LDY #>SX_STORE_WORD
        JSR S_MATCH
        BCS SX_PROGRAM
        LDX #<SX_S_WORD
        LDY #>SX_S_WORD
        JSR S_MATCH
        BCC SX_NO
SX_PROGRAM:
        JSR S_SKIP
        CMP #'P'
        BNE SX_NO
        INX
        LDA S_LINE,X
        CMP #' '
        BNE SX_NO
        LDA #1
SX_LOAD:
        STA $69F8
        LDA #1
        STA S_READ_BANK
        STZ S_ADDR
        LDA #$D9
        STA S_ADDR+1
        STZ S_COPY
        LDA #$6B
        STA S_COPY+1
        LDA #24
        STA S_CHUNKS
SX_READ:
        JSR S_READ64
        LDY #63
SX_COPY:
        LDA S_BUFFER,Y
        STA (S_COPY),Y
        DEY
        BPL SX_COPY
        CLC
        LDA S_ADDR
        ADC #64
        STA S_ADDR
        BCC SX_READ_READY
        INC S_ADDR+1
SX_READ_READY:
        CLC
        LDA S_COPY
        ADC #64
        STA S_COPY
        BCC SX_DEST_READY
        INC S_COPY+1
SX_DEST_READY:
        DEC S_CHUNKS
        BNE SX_READ
        STZ S_PTR
        LDA #$6B
        STA S_PTR+1
        LDX #6
        JSR S_CRC_PAGES
        LDA S_CRC
        ORA S_CRC+1
        BNE SX_INVALID
        LDX #7
SX_ID:
        LDA $6B00,X
        CMP SX_MAGIC,X
        BNE SX_INVALID
        DEX
        BPL SX_ID
        LDA $69F8
        BNE SX_CALL_STORE
        JSR $6B08
        BRA SX_DONE
SX_CALL_STORE:
        LDX #7
SX_STORE_ID:
        LDA $6D00,X
        CMP SX_STORE_MAGIC,X
        BNE SX_INVALID
        DEX
        BPL SX_STORE_ID
        LDX #<S_LINE
        LDY #>S_LINE
        JSR $6D08
SX_DONE:
        LDA $6A00
        STA S_BANK
        SEC
        RTS
SX_INVALID:
        LDX #<S_LOAD_FAILED_TEXT
        LDY #>S_LOAD_FAILED_TEXT
        JSR S_PUTS
        BRA SX_DONE
SX_NO:
        CLC
        RTS
SX_MAGIC: DB "SL",1,6,"PR05"
SX_STORE_MAGIC: DB "WS",1,4,"PR05"
SX_S19_WORD: DB "S19",0
SX_STORE_WORD: DB "STORE",0
SX_S_WORD: DB "S",0
