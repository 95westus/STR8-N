; Eight 8-byte metadata rows in SPI workspace, cached two rows (16 bytes) at a time.
; Load paired WORK library at 4000 and this client at 2000. No format/resize.
        MODULE WORK_EXAMPLE
        XDEF START
        XDEF APP_END
REQ EQU $2400
CACHE EQU $2500
        CODE
START:  SEI
        CLD
        LDX #3
CHECK_LIBRARY:
        LDA $4006,X
        CMP EXPECTED_API,X
        BNE ABSENT
        DEX
        BPL CHECK_LIBRARY
        LDX #31
ZERO_REQUEST:
        STZ REQ,X
        DEX
        BPL ZERO_REQUEST
        LDA #$EF
        STA REQ+2
        LDA #$BE
        STA REQ+3
        LDA #64
        STA REQ+18
        LDA #1
        JSR CALL
        BNE DONE
        LDA #16
        STA REQ+15
        STZ REQ+16
        LDA #$25
        STA REQ+17
        STZ BASE
WRITE_LINE:
        LDY #0
FILL_CACHE:
        TYA
        CLC
        ADC BASE
        TAX
        LDA TABLE,X
        STA CACHE,Y
        INY
        CPY #16
        BNE FILL_CACHE
        LDA BASE
        STA REQ+12
        LDA #4
        JSR CALL
        BNE RELEASE_ERROR
        JSR NEXT_LINE
        BNE WRITE_LINE
        STZ BASE
READ_LINE:
        LDX #15
CLEAR_CACHE:
        STZ CACHE,X
        DEX
        BPL CLEAR_CACHE
        LDA BASE
        STA REQ+12
        LDA #3
        JSR CALL
        BNE RELEASE_ERROR
        LDY #0
CHECK_CACHE:
        TYA
        CLC
        ADC BASE
        TAX
        LDA TABLE,X
        CMP CACHE,Y
        BNE VERIFY_ERROR
        INY
        CPY #16
        BNE CHECK_CACHE
        JSR NEXT_LINE
        BNE READ_LINE
        LDA #2
        JSR CALL
        BRA DONE
VERIFY_ERROR:
        LDA #$45
RELEASE_ERROR:
        PHA
        LDA #2
        JSR CALL
        PLA
DONE:   PHA
        LDA #'W'
        JSR $7E6D
        LDA #':'
        JSR $7E6D
        LDA #' '
        JSR $7E6D
        PLA
        JSR $7E7C
        JSR $7E7F
        JMP $7E67
ABSENT: LDA #$80
        BRA DONE
CALL:   STA REQ
        LDA #<REQ
        LDX #>REQ
        JSR $4003
        CMP #0
        RTS
NEXT_LINE:
        LDA BASE
        CLC
        ADC #16
        STA BASE
        CMP #64
        RTS
EXPECTED_API DB "WK",1,1
; row: id, length, original load address, flags (four LE16 fields).
TABLE DW 0,16,$2000,1,1,24,$2010,1,2,32,$2028,1,3,8,$2048,0
      DW 4,64,$2050,1,5,16,$2090,0,6,24,$20A0,1,7,48,$20B8,0
BASE DB 0
APP_END:
        ENDMOD
        END
