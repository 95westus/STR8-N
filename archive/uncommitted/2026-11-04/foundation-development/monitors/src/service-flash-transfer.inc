; Pre-WB router. Optional gate in BANK MAINT padding avoids another sector.
; Only recognized raw/record commands displace the PROGRAM cache.
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
        BRA SX_LOAD
SX_STORE:
        LDX #<SX_STORE_WORD
        LDY #>SX_STORE_WORD
        JSR S_MATCH
        BCS SX_STORE_ARG
        LDX #<SX_S_WORD
        LDY #>SX_S_WORD
        JSR S_MATCH
        BCC SX_RESTORE
SX_STORE_ARG:
        JSR S_SKIP
        CMP #'P'
        BEQ SX_ARGUMENT_END
        BRA SX_FLASH_ARG
SX_RESTORE:
        LDX #<SX_RESTORE_WORD
        LDY #>SX_RESTORE_WORD
        JSR S_MATCH
        BCS SX_RESTORE_ARG
        LDX #<SX_R_WORD
        LDY #>SX_R_WORD
        JSR S_MATCH
        BCC SX_NO
SX_RESTORE_ARG:
        JSR S_SKIP
SX_FLASH_ARG:
        SEC
        SBC #'0'
        CMP #2
        BCS SX_NO
SX_ARGUMENT_END:
        LDA S_LINE+1,X
        CMP #' '
        BNE SX_NO
SX_LOAD:
        LDA #1
        STA S_READ_BANK
        LDA #$80
        STA S_ADDR
        LDA #$A3
        STA S_ADDR+1
        STZ S_COPY
        LDA #$73
        STA S_COPY+1
        LDA #16
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
        LDA #$73
        STA S_PTR+1
        LDX #4
        JSR S_CRC_PAGES
        LDA S_CRC
        ORA S_CRC+1
        BNE SX_INVALID
        LDX #7
SX_ID:
        LDA $7300,X
        CMP SX_GATE_MAGIC,X
        BNE SX_INVALID
        DEX
        BPL SX_ID
        ; The gate tail-calls payloads. Their RTS returns here even when a
        ; PROGRAM load has overwritten the RAM gate itself.
        JSR $7308
        LDA $69F9
        BEQ SX_NO
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
SX_GATE_MAGIC: DB "FG",1,5,"PR05"
SX_S19_WORD: DB "S19",0
SX_STORE_WORD: DB "STORE",0
SX_S_WORD: DB "S",0
SX_RESTORE_WORD: DB "RESTORE",0
SX_R_WORD: DB "R",0
