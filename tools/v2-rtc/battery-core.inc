; BA v1: sequence LE32; install day LE16 since 2000-01-01, warning/replacement
; in 30-day months, highest stage (0/1/2/3 uncertain), high-water day LE16.
; CRC16 LE at 28, commit zero at 31. Shared EI/TZ/BN append-only tail.
BT_READ:
        STZ BT_FOUND
        STZ BT_FREE+1
        LDX #3
BT_ZERO:
        STZ BT_SEQ,X
        DEX
        BPL BT_ZERO
        LDA $7FEC
        PHA
        AND #$11
        ORA #$EE
        STA $7FEC
        STZ TZ_PTR
        LDA #$9C
        STA TZ_PTR+1
BT_SLOT:
        LDY #0
BT_BLANK:
        LDA (TZ_PTR),Y
        CMP #$FF
        BNE BT_CHECK
        INY
        CPY #32
        BNE BT_BLANK
        LDA BT_FREE+1
        BNE BT_NEXT
        LDA TZ_PTR
        STA BT_FREE
        LDA TZ_PTR+1
        STA BT_FREE+1
        BRA BT_NEXT
BT_CHECK:
        LDY #31
        LDA (TZ_PTR),Y
        BNE BT_NEXT
        LDY #3
BT_HEADER:
        LDA (TZ_PTR),Y
        CMP BT_MAGIC,Y
        BNE BT_NEXT
        DEY
        BPL BT_HEADER
        JSR TZ_CRC
        LDY #28
        LDA (TZ_PTR),Y
        CMP TZ_SUM
        BNE BT_NEXT
        INY
        LDA (TZ_PTR),Y
        CMP TZ_SUM+1
        BNE BT_NEXT
        LDY #10
        LDA (TZ_PTR),Y
        BEQ BT_NEXT
        CMP #99
        BCS BT_NEXT
        INY
        CMP (TZ_PTR),Y
        BCS BT_NEXT
        LDA (TZ_PTR),Y
        CMP #100
        BCS BT_NEXT
        INY
        LDA (TZ_PTR),Y
        CMP #4
        BCS BT_NEXT
        ; Both dates must fit 2000-2099; high-water cannot precede install.
        LDY #14
        LDA (TZ_PTR),Y
        CMP #$8E
        BCC BT_DATE_RANGE
        BNE BT_NEXT
        DEY
        LDA (TZ_PTR),Y
        CMP #$AD
        BCS BT_NEXT
BT_DATE_RANGE:
        LDY #9
        LDA (TZ_PTR),Y
        LDY #14
        CMP (TZ_PTR),Y
        BCC BT_NEWEST
        BNE BT_NEXT
        LDY #8
        LDA (TZ_PTR),Y
        LDY #13
        CMP (TZ_PTR),Y
        BCC BT_NEWEST
        BNE BT_NEXT
BT_NEWEST:
        LDY #7
        LDX #3
BT_NEWER:
        LDA (TZ_PTR),Y
        CMP BT_SEQ,X
        BCC BT_NEXT
        BNE BT_KEEP
        DEY
        DEX
        BPL BT_NEWER
BT_KEEP:
        LDY #7
        LDX #3
BT_COPY_SEQ:
        LDA (TZ_PTR),Y
        STA BT_SEQ,X
        DEY
        DEX
        BPL BT_COPY_SEQ
        LDY #8
        LDX #0
BT_COPY:
        LDA (TZ_PTR),Y
        STA BT_PAYLOAD,X
        INY
        INX
        CPX #7
        BNE BT_COPY
        LDA #1
        STA BT_FOUND
BT_NEXT:
        LDA TZ_PTR
        CLC
        ADC #32
        STA TZ_PTR
        BCC BT_PAGE
        INC TZ_PTR+1
BT_PAGE:
        LDA TZ_PTR+1
        CMP #$A0
        BNE BT_SLOT
        PLA
        STA $7FEC
        RTS
; Validated binary Gregorian Y offset 0..99, month/day -> ordinal day.
BT_DATE:
        STZ BT_DAYNUM
        STZ BT_DAYNUM+1
        LDX #0
BT_YEARS:
        CPX BT_YEAR
        BEQ BT_MONTHS
        LDA #$6D
        CLC
        ADC BT_DAYNUM
        STA BT_DAYNUM
        LDA BT_DAYNUM+1
        ADC #1
        STA BT_DAYNUM+1
        TXA
        AND #3
        BNE BT_YEAR_NEXT
        INC BT_DAYNUM
        BNE BT_YEAR_NEXT
        INC BT_DAYNUM+1
BT_YEAR_NEXT:
        INX
        BRA BT_YEARS
BT_MONTHS:
        LDX #1
BT_MONTH_LOOP:
        CPX BT_MONTH
        BEQ BT_ADD_DAY
        LDA BT_MONTH_LENGTH-1,X
        CPX #2
        BNE BT_MONTH_ADD
        PHA
        LDA BT_YEAR
        AND #3
        BNE BT_NO_LEAP
        PLA
        INC A
        BRA BT_MONTH_ADD
BT_NO_LEAP:
        PLA
BT_MONTH_ADD:
        CLC
        ADC BT_DAYNUM
        STA BT_DAYNUM
        BCC BT_MONTH_NEXT
        INC BT_DAYNUM+1
BT_MONTH_NEXT:
        INX
        BRA BT_MONTH_LOOP
BT_ADD_DAY:
        LDA BT_DAY
        DEC A
        CLC
        ADC BT_DAYNUM
        STA BT_DAYNUM
        BCC BT_DATE_DONE
        INC BT_DAYNUM+1
BT_DATE_DONE:
        RTS
BT_NOW:
        STZ BT_VALID
        LDA $7D2A
        BEQ BT_NOW_DONE
        JSR $6504
        BCC BT_NOW_DONE
        LDA $66C1
        AND #$16
        CMP #$16
        BNE BT_NOW_DONE
        LDA $66C2
        SEC
        SBC #$D0
        STA BT_YEAR
        LDA $66C3
        SBC #7
        BNE BT_NOW_DONE
        LDA BT_YEAR
        CMP #100
        BCS BT_NOW_DONE
        LDA $66C4
        STA BT_MONTH
        LDA $66C5
        STA BT_DAY
        JSR BT_DATE
        LDA BT_DAYNUM
        STA BT_TODAY
        LDA BT_DAYNUM+1
        STA BT_TODAY+1
        INC BT_VALID
BT_NOW_DONE:
        RTS
BT_PENDING_COPY:
        LDX #6
BT_PENDING_LOOP:
        LDA BT_PAYLOAD,X
        STA BT_PENDING,X
        DEX
        BPL BT_PENDING_LOOP
        RTS
; Latch only stage changes. No daily/monthly counter writes or erases.
BT_PROCESS:
        JSR BT_READ
        JSR BT_NOW
        LDA BT_FOUND
        BEQ BT_UNKNOWN
        JSR BT_PENDING_COPY
        LDA BT_VALID
        BEQ BT_UNCERTAIN
        LDA BT_TODAY
        SEC
        SBC BT_PAYLOAD+5
        LDA BT_TODAY+1
        SBC BT_PAYLOAD+6
        BCC BT_UNCERTAIN
        LDA BT_TODAY
        SEC
        SBC BT_PAYLOAD
        STA BT_AGE
        LDA BT_TODAY+1
        SBC BT_PAYLOAD+1
        STA BT_AGE+1
        STZ BT_MONTH_AGE
BT_DIVIDE:
        LDA BT_AGE+1
        BNE BT_SUBTRACT
        LDA BT_AGE
        CMP #30
        BCC BT_COMPARE
BT_SUBTRACT:
        LDA BT_AGE
        SEC
        SBC #30
        STA BT_AGE
        LDA BT_AGE+1
        SBC #0
        STA BT_AGE+1
        INC BT_MONTH_AGE
        LDA BT_MONTH_AGE
        CMP #100
        BNE BT_DIVIDE
BT_COMPARE:
        LDX #0
        LDA BT_MONTH_AGE
        CMP BT_PAYLOAD+2
        BCC BT_STAGE
        INX
        CMP BT_PAYLOAD+3
        BCC BT_STAGE
        INX
        BRA BT_STAGE
BT_UNCERTAIN:
        LDX #3
BT_STAGE:
        CPX BT_PAYLOAD+4
        BCC BT_DISPLAY
        BEQ BT_DISPLAY
        STX BT_PENDING+4
        LDA BT_VALID
        BEQ BT_LATCH
        LDA BT_TODAY
        SEC
        SBC BT_PAYLOAD+5
        LDA BT_TODAY+1
        SBC BT_PAYLOAD+6
        BCC BT_LATCH
        LDA BT_TODAY
        STA BT_PENDING+5
        LDA BT_TODAY+1
        STA BT_PENDING+6
BT_LATCH:
        JSR BT_SAVE
        BCS BT_DISPLAY
        LDX #<BT_SAVE_ERROR
        LDY #>BT_SAVE_ERROR
        JSR PRINT
        ; Report the newly observed warning even if persistence failed.
        LDA BT_PENDING+4
        STA BT_PAYLOAD+4
BT_DISPLAY:
        LDA BT_PAYLOAD+4
        BEQ BT_YOUNG
        CMP #1
        BEQ BT_WARNING
        CMP #2
        BEQ BT_DUE
        LDX #<BT_UNCERTAIN_TEXT
        LDY #>BT_UNCERTAIN_TEXT
        BRA BT_PRINT
BT_YOUNG:
        LDX #<BT_YOUNG_TEXT
        LDY #>BT_YOUNG_TEXT
        BRA BT_PRINT
BT_WARNING:
        LDX #<BT_WARNING_TEXT
        LDY #>BT_WARNING_TEXT
        BRA BT_PRINT
BT_DUE:
        LDX #<BT_DUE_TEXT
        LDY #>BT_DUE_TEXT
        BRA BT_PRINT
BT_UNKNOWN:
        LDX #<BT_UNKNOWN_TEXT
        LDY #>BT_UNKNOWN_TEXT
BT_PRINT:
        JMP PRINT
BT_MAGIC DB "BA",1,0
BT_MONTH_LENGTH DB 31,28,31,30,31,30,31,31,30,31,30,31
BT_UNKNOWN_TEXT DB "Battery age unknown. Back up SSRAM; use CLOCK BATTERY.",13,10,0
BT_YOUNG_TEXT DB "Battery: within age policy; condition unknown.",13,10,0
BT_WARNING_TEXT DB "Battery reminder: back up SSRAM; plan replacement.",13,10,0
BT_DUE_TEXT DB "Battery replacement due. Back up SSRAM before replacement.",13,10,0
BT_UNCERTAIN_TEXT DB "Battery age uncertain. Back up SSRAM; check clock/battery.",13,10,0
BT_SAVE_ERROR DB "Battery record not saved (full/incompatible/write failed); no erase.",13,10,0
BT_FOUND DB 0
BT_FREE DS 2
BT_SEQ DS 4
BT_PAYLOAD DS 7
BT_PENDING DS 7
BT_YEAR DB 0
BT_MONTH DB 0
BT_DAY DB 0
BT_DAYNUM DS 2
BT_TODAY DS 2
BT_VALID DB 0
BT_AGE DS 2
BT_MONTH_AGE DB 0
