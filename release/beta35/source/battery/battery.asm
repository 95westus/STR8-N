        MODULE BATTERY
        XDEF START
        XDEF APP_END
TZ_PTR EQU $D6
BT_FLASH_BYTE EQU $7B03
        CODE
START:  DB "BS",1,3
        JMP BT_ENTRY
BT_ENTRY:
        JSR WEAR_SHOW
        LDA $7D27
        CMP #2
                        BEQ BT_ENTRY_DONE
        JSR $7E7F
        JSR BT_PROCESS
BT_ENTRY_DONE:
        SEC
        RTS
PRINT:  STX $D0
        STY $D1
        LDY #0
BT_PRINT_LOOP:
        LDA ($D0),Y
                        BEQ BT_PRINT_DONE
        JSR $7E6D
        INY
                        BNE BT_PRINT_LOOP
        INC $D1
                        BRA BT_PRINT_LOOP
BT_PRINT_DONE:
        RTS
TZ_SUM DS 2
TZ_CRC:
        LDA #$FF
        STA TZ_SUM
        STA TZ_SUM+1
        LDY #0
TZ_CRC_BYTE:
        LDA (TZ_PTR),Y
        EOR TZ_SUM+1
        STA TZ_SUM+1
        LDX #8
TZ_CRC_BIT:
        ASL TZ_SUM
        ROL TZ_SUM+1
                        BCC TZ_CRC_NEXT
        LDA TZ_SUM
        EOR #$21
        STA TZ_SUM
        LDA TZ_SUM+1
        EOR #$10
        STA TZ_SUM+1
TZ_CRC_NEXT:
        DEX
                        BNE TZ_CRC_BIT
        INY
        CPY #28
                        BNE TZ_CRC_BYTE
        RTS
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
                        BEQ BAT_LONG_88
                        JMP BT_NEXT
BAT_LONG_88:
        LDA TZ_PTR
        STA BT_FREE
        LDA TZ_PTR+1
        STA BT_FREE+1
                        JMP BT_NEXT
BT_CHECK:
        LDY #31
        LDA (TZ_PTR),Y
                        BEQ BAT_LONG_97
                        JMP BT_NEXT
BAT_LONG_97:
        LDY #3
BT_HEADER:
        LDA (TZ_PTR),Y
        CMP BT_MAGIC,Y
                        BEQ BAT_LONG_102
                        JMP BT_NEXT
BAT_LONG_102:
        DEY
                        BPL BT_HEADER
        JSR TZ_CRC
        LDY #28
        LDA (TZ_PTR),Y
        CMP TZ_SUM
                        BEQ BAT_LONG_109
                        JMP BT_NEXT
BAT_LONG_109:
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
                        BEQ BAT_LONG_193
                        JMP BT_SLOT
BAT_LONG_193:
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
                        BNE BAT_LONG_302
                        JMP BT_UNKNOWN
BAT_LONG_302:
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
                        JMP BT_PRINT
BT_YOUNG:
        LDX #<BT_YOUNG_TEXT
        LDY #>BT_YOUNG_TEXT
                        JMP BT_PRINT
BT_WARNING:
        LDX #<BT_WARNING_TEXT
        LDY #>BT_WARNING_TEXT
                        JMP BT_PRINT
BT_DUE:
        LDX #<BT_DUE_TEXT
        LDY #>BT_DUE_TEXT
                        JMP BT_PRINT
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
BT_SAVE:
        LDA $7FEC
        PHA
        AND #$11
        ORA #$EE
        STA $7FEC
        LDX #3
BT_FORMAT_CHECK:
        LDA $9000,X
        CMP BT_JOURNAL_MAGIC,X
                        BNE BT_FORMAT_BAD
        DEX
                        BPL BT_FORMAT_CHECK
        PLA
        STA $7FEC
        JSR BT_READ
        LDA BT_FREE+1
                        BEQ BT_REFUSE
        LDX #3
BT_SEQ_FULL:
        LDA BT_SEQ,X
        CMP #$FF
                        BNE BT_RECORD
        DEX
                        BPL BT_SEQ_FULL
BT_REFUSE:
        CLC
        RTS
BT_FORMAT_BAD:
        PLA
        STA $7FEC
                        JMP BT_REFUSE
BT_RECORD:
        LDX #31
        LDA #$FF
BT_FILL:
        STA BT_RECORD_BYTES,X
        DEX
                        BPL BT_FILL
        LDX #3
BT_RECORD_HEADER:
        LDA BT_MAGIC,X
        STA BT_RECORD_BYTES,X
        DEX
                        BPL BT_RECORD_HEADER
        INC BT_SEQ
                        BNE BT_SEQUENCE_READY
        INC BT_SEQ+1
                        BNE BT_SEQUENCE_READY
        INC BT_SEQ+2
                        BNE BT_SEQUENCE_READY
        INC BT_SEQ+3
BT_SEQUENCE_READY:
        LDX #3
BT_SEQUENCE:
        LDA BT_SEQ,X
        STA BT_RECORD_BYTES+4,X
        DEX
                        BPL BT_SEQUENCE
        LDX #6
BT_PAYLOAD_COPY:
        LDA BT_PENDING,X
        STA BT_RECORD_BYTES+8,X
        DEX
                        BPL BT_PAYLOAD_COPY
        LDA #<BT_RECORD_BYTES
        STA TZ_PTR
        LDA #>BT_RECORD_BYTES
        STA TZ_PTR+1
        JSR TZ_CRC
        LDA TZ_SUM
        STA BT_RECORD_BYTES+28
        LDA TZ_SUM+1
        STA BT_RECORD_BYTES+29
        LDX #31
BT_SAVE_ZP:
        LDA $E0,X
        STA BT_ZP,X
        DEX
                        BPL BT_SAVE_ZP
        LDA $7FEC
        STA BT_BANK
        AND #$11
        ORA #$EE
        STA $7FEC
        LDA $7FA0
        STA BT_LED
        LDA #3
        STA $F3
        LDA #1
        STA $F4
        STZ BT_INDEX
        STZ BT_ERROR
BT_WRITE:
        LDX BT_INDEX
        LDA BT_RECORD_BYTES,X
        CMP #$FF
                        BEQ BT_NEXT_BYTE
        STA $F0
        TXA
        CLC
        ADC BT_FREE
        STA $E4
        LDA BT_FREE+1
        ADC #0
        STA $E5
        JSR BT_FLASH_BYTE
                        BCC BT_WRITE_FAILED
BT_NEXT_BYTE:
        INC BT_INDEX
        LDA BT_INDEX
        CMP #31
                        BNE BT_WRITE
        LDA BT_FREE
        STA TZ_PTR
        LDA BT_FREE+1
        STA TZ_PTR+1
        LDY #30
BT_VERIFY:
        LDA (TZ_PTR),Y
        CMP BT_RECORD_BYTES,Y
                        BNE BT_WRITE_FAILED
        DEY
                        BPL BT_VERIFY
        LDA BT_FREE
        CLC
        ADC #31
        STA $E4
        LDA BT_FREE+1
        ADC #0
        STA $E5
        STZ $F0
        JSR BT_FLASH_BYTE
                        BCC BT_WRITE_FAILED
        LDY #31
        LDA (TZ_PTR),Y
                        BNE BT_WRITE_FAILED
                        BRA BT_RESTORE
BT_WRITE_FAILED:
        INC BT_ERROR
BT_RESTORE:
        LDA BT_LED
        STA $7FA0
        LDA BT_BANK
        STA $7FEC
        LDX #31
BT_RESTORE_ZP:
        LDA BT_ZP,X
        STA $E0,X
        DEX
                        BPL BT_RESTORE_ZP
        LDA BT_ERROR
                        BEQ BAT_LONG_576
                        JMP BT_REFUSE
BAT_LONG_576:
        JSR BT_READ
        LDA BT_FOUND
                        BNE BAT_LONG_579
                        JMP BT_REFUSE
BAT_LONG_579:
        LDX #6
BT_READBACK:
        LDA BT_PAYLOAD,X
        CMP BT_PENDING,X
                        BEQ BAT_LONG_584
                        JMP BT_REFUSE
BAT_LONG_584:
        DEX
                        BPL BT_READBACK
        SEC
        RTS
BT_JOURNAL_MAGIC DB "PJ",6,1
BT_BANK DB 0
BT_LED DB 0
BT_INDEX DB 0
BT_ERROR DB 0
BT_RECORD_BYTES DS 32
BT_ZP DS 32
; Read the existing CRC/commit-validated C/D journal. Counts are conservative
; managed erase attempts since provisioning, not complete physical history.
; Thresholds apply to the worst individual 4 KiB sector, never a chip average.
WEAR_SHOW:
        LDA $7FEC
        PHA
        AND #$11
        ORA #$EE
        STA $7FEC
        JSR $F0B2
                        BCS WEAR_VALID
        PLA
        STA $7FEC
        LDX #<WEAR_UNKNOWN
        LDY #>WEAR_UNKNOWN
        JMP PRINT
WEAR_VALID:
        PLA
        STA $7FEC
        STZ WEAR_INDEX
        STZ WEAR_SECTOR
        LDX #2
WEAR_ZERO:
        STZ WEAR_MAX,X
        DEX
                        BPL WEAR_ZERO
WEAR_SCAN:
        LDA WEAR_INDEX
        ASL A
        CLC
        ADC WEAR_INDEX
        TAX
        LDA $671A,X
        CMP WEAR_MAX+2
                        BCC WEAR_NEXT
                        BNE WEAR_KEEP
        LDA $6719,X
        CMP WEAR_MAX+1
                        BCC WEAR_NEXT
                        BNE WEAR_KEEP
        LDA $6718,X
        CMP WEAR_MAX
                        BCC WEAR_NEXT
                        BEQ WEAR_NEXT
WEAR_KEEP:
        LDA $6718,X
        STA WEAR_MAX
        LDA $6719,X
        STA WEAR_MAX+1
        LDA $671A,X
        STA WEAR_MAX+2
        LDA WEAR_INDEX
        STA WEAR_SECTOR
WEAR_NEXT:
        INC WEAR_INDEX
        LDA WEAR_INDEX
        CMP #32
                        BNE WEAR_SCAN
        ; 50,000 = $00C350; 80,000 = $013880. Compare all 24 bits.
        LDA WEAR_MAX+2
                        BNE WEAR_HIGH
        LDA WEAR_MAX+1
        CMP #$C3
                        BCC WEAR_DONE
                        BNE WEAR_WARNING
        LDA WEAR_MAX
        CMP #$50
                        BCC WEAR_DONE
                        BRA WEAR_WARNING
WEAR_HIGH:
        CMP #1
                        BNE WEAR_DUE
        LDA WEAR_MAX+1
        CMP #$38
                        BCC WEAR_WARNING
                        BNE WEAR_DUE
        LDA WEAR_MAX
        CMP #$80
                        BCS WEAR_DUE
WEAR_WARNING:
        LDX #<WEAR_WARNING_TEXT
        LDY #>WEAR_WARNING_TEXT
                        BRA WEAR_PRINT
WEAR_DUE:
        LDX #<WEAR_DUE_TEXT
        LDY #>WEAR_DUE_TEXT
WEAR_PRINT:
        JSR PRINT
        LDA #'B'
        JSR $7E6D
        LDA WEAR_SECTOR
        LSR A
        LSR A
        LSR A
        ORA #'0'
        JSR $7E6D
        LDA #':'
        JSR $7E6D
        LDA WEAR_SECTOR
        AND #7
        CLC
        ADC #8
        CMP #10
                        BCC WEAR_NIBBLE
        ADC #6
WEAR_NIBBLE:
        CLC
        ADC #'0'
        JSR $7E6D
        LDX #<WEAR_MAX_TEXT
        LDY #>WEAR_MAX_TEXT
        JSR PRINT
        JSR WEAR_DECIMAL
        LDX #<WEAR_NOTE
        LDY #>WEAR_NOTE
        JMP PRINT
WEAR_DONE:
        LDX #<WEAR_OK_TEXT
        LDY #>WEAR_OK_TEXT
        BRA WEAR_PRINT
WEAR_OK_TEXT DB "FLASH: wear check OK. Sector ",0
WEAR_WARNING_TEXT DB "FLASH: wear check WARNING: >=50,000 tracked erase attempts. Back up; plan replacement. Sector ",0
WEAR_DUE_TEXT DB "FLASH: wear check HIGH: >=80,000 tracked erase attempts. Back up now; replace flash soon. Sector ",0
WEAR_MAX_TEXT DB ", max ",0
WEAR_NOTE DB " tracked erases.",13,10,"Prior/direct wear unknown. W lists counts (hex).",13,10,0
WEAR_UNKNOWN DB "FLASH: wear check UNKNOWN. Wear history unavailable; back up. W lists counts.",13,10,0
WEAR_INDEX DB 0
WEAR_SECTOR DB 0
WEAR_MAX DS 3

; Print the intact 24-bit maximum as unsigned decimal, using only the
; helper's existing borrowed staging region. At most eight digits.
WEAR_DECIMAL:
        LDX #2
WEAR_DEC_COPY:
        LDA WEAR_MAX,X
        STA WEAR_QUOTIENT,X
        DEX
        BPL WEAR_DEC_COPY
        STZ WEAR_DIGIT_COUNT
WEAR_DEC_DIVIDE:
        LDA #0
        LDX #24
WEAR_DEC_BIT:
        ASL WEAR_QUOTIENT
        ROL WEAR_QUOTIENT+1
        ROL WEAR_QUOTIENT+2
        ROL A
        CMP #10
        BCC WEAR_DEC_NEXT
        SBC #10
        INC WEAR_QUOTIENT
WEAR_DEC_NEXT:
        DEX
        BNE WEAR_DEC_BIT
        CLC
        ADC #'0'
        LDX WEAR_DIGIT_COUNT
        STA WEAR_DIGITS,X
        INC WEAR_DIGIT_COUNT
        LDA WEAR_QUOTIENT
        ORA WEAR_QUOTIENT+1
        ORA WEAR_QUOTIENT+2
        BNE WEAR_DEC_DIVIDE
        LDX WEAR_DIGIT_COUNT
WEAR_DEC_PRINT:
        DEX
        LDA WEAR_DIGITS,X
        JSR $7E6D
        CPX #0
        BNE WEAR_DEC_PRINT
        RTS
WEAR_QUOTIENT DS 3
WEAR_DIGIT_COUNT DB 0
WEAR_DIGITS DS 8

APP_END:
        ENDMOD
