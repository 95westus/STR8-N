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
        LDX #<WEAR_NOTE
        LDY #>WEAR_NOTE
        JMP PRINT
WEAR_DONE:
        RTS
WEAR_WARNING_TEXT DB "Flash wear: >=50,000 tracked erase attempts. Back up; plan replacement. Sector ",0
WEAR_DUE_TEXT DB "Flash wear HIGH: >=80,000 tracked erase attempts. Back up now; replace flash soon. Sector ",0
WEAR_NOTE DB ". W lists counts (hex). Prior/direct wear unknown.",13,10,0
WEAR_UNKNOWN DB "Flash wear history unavailable. Back up; counters do not certify flash health.",13,10,0
WEAR_INDEX DB 0
WEAR_SECTOR DB 0
WEAR_MAX DS 3
