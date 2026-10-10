; Borrow monitor staging, preserve the journal's complete scratch page.
LOCAL_DISPLAY:
        LDX #0
LOCAL_SAVE_SCRATCH:
        LDA $6B00,X
        STA LOCAL_SAVED,X
        INX
        BNE LOCAL_SAVE_SCRATCH
        LDA $F3
        PHA
        LDA #2
        STA $F3
        STZ $E2
        LDA #$E0
        STA $E2+1
        STZ $E6
        LDA #$68
        STA $E6+1
LOCAL_READ:
        LDA #16
        STA $EA
        JSR V2W_READ
        LDY #15
LOCAL_COPY:
        LDA $7C80,Y
        STA ($E6),Y
        DEY
        BPL LOCAL_COPY
        LDA $E2
        CLC
        ADC #16
        STA $E2
        BCC LOCAL_ADVANCE
        INC $E2+1
LOCAL_ADVANCE:
        LDA $E6
        CLC
        ADC #16
        STA $E6
        BCC LOCAL_READ
        INC $E6+1
        LDA $E6+1
        CMP #$6E
        BNE LOCAL_READ
        PLA
        STA $F3
        JSR AP_CRC_INIT
        STZ $E0
        LDA #$68
        STA $E1
        LDY #0
LOCAL_CRC:
        LDA ($E0),Y
        JSR AP_CRC_BYTE
        INY
        BNE LOCAL_CRC
        INC $E1
        LDA $E1
        CMP #$6E
        BNE LOCAL_CRC
        LDA $7D38
        ORA $7D39
        BNE LOCAL_BAD
        LDX #3
LOCAL_HEADER:
        LDA $6800,X
        CMP LOCAL_MAGIC,X
        BNE LOCAL_BAD
        DEX
        BPL LOCAL_HEADER
        LDA KIND
        JSR $6804
        BRA LOCAL_RESTORE
LOCAL_BAD:
        LDX #<LOCAL_ERROR_TEXT
        LDY #>LOCAL_ERROR_TEXT
        JSR PRINT
LOCAL_RESTORE:
        LDX #0
LOCAL_RESTORE_SCRATCH:
        LDA LOCAL_SAVED,X
        STA $6B00,X
        INX
        BNE LOCAL_RESTORE_SCRATCH
        RTS
LOCAL_MAGIC DB "LT",1,1
LOCAL_ERROR_TEXT DB 13,10,"Local display unavailable",0
LOCAL_SAVED DS 256
