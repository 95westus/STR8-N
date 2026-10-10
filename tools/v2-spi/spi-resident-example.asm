; G 2000: read 16 bytes at nominal workspace address 10000 to 2300.
; G 2003: submit caller-prepared request at 2400 (READ/WRITE/PROBE).
; Uses software discovery, preserves result at 2410 before HOLD.
        MODULE SPI_EXAMPLE
        XDEF START
        XDEF APP_END
        CODE
START:  JMP READ_DEMO
        JMP PREPARED
READ_DEMO:
        LDX #15
MAKE_REQUEST:
        LDA READ_REQUEST,X
        STA $2400,X
        DEX
        BPL MAKE_REQUEST
PREPARED:
        CLD
        LDA $7D04
        CMP #'S'
        BNE ABSENT
        LDA $7D05
        CMP #'V'
        BNE ABSENT
        LDA $7D06
        CMP #1
        BNE ABSENT
        LDA $7D07
        AND #8
        BEQ ABSENT
        LDA $7D08
        BNE ABSENT
        LDA $7D09
        CMP #$65
        BNE ABSENT
        LDX #3
CHECK_SM:
        LDA $66A2,X
        CMP MEMORY_EXPECTED,X
        BNE ABSENT
        DEX
        BPL CHECK_SM
        LDX #15
COPY_REQUEST:
        LDA $2400,X
        STA $6650,X
        DEX
        BPL COPY_REQUEST
        JSR $66A6
        PHA
        LDX #15
COPY_RESULT:
        LDA $6650,X
        STA $2410,X
        DEX
        BPL COPY_RESULT
        LDA #'S'
        JSR $7E6D
        LDA #'M'
        JSR $7E6D
        LDA #':'
        JSR $7E6D
        LDA #' '
        JSR $7E6D
        PLA
        JSR $7E7C
        JSR $7E7F
        JMP $7E67
ABSENT:
        LDA #$80
        STA $2418
        JMP $7E67
MEMORY_EXPECTED DB "SM",1,1
READ_REQUEST DB 1,0,0,0,1,0,$23,16,0,0,0,0,0,0,0,0
APP_END:
        ENDMOD
        END
