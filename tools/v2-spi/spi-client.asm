; RAM qualification client. Parameters/request at 3E00; copied results 3E10.
; G 2000 one request; G 2003 reads 128*64 = 8192 bytes to CPU 4000-5FFF.
        MODULE SPI_CLIENT
        XDEF START
        XDEF APP_END
PARAM EQU $3E00
OUTPUT EQU $3E10
TYPE EQU $3E20
BANK EQU $3E21
MANAGER EQU $3E22
OLDPCR EQU $3E30
REPEATS EQU $3E31
MODE EQU $3E32
BEFORE_PCR EQU $3E33
AFTER_PCR EQU $3E34
DDROUT EQU $3E35
GPIO_OLD EQU $3E36
FLAGS EQU $3E37
RETURN_STATUS EQU $3E38
PCR EQU $7FEC
PUTC EQU $7E6D
HEX EQU $7E7C
NL EQU $7E7F
HOLD EQU $7E67
        CODE
START:  JMP SINGLE
        JMP BULK
SINGLE:
        STZ REPEATS
        BRA BEGIN
BULK:
        LDA #128
        STA REPEATS
BEGIN:
        SEI
        CLD
        LDA BANK
        CMP #4
        BCS BAD
        LDA TYPE
        CMP #2
        BCS BAD
        LDX #3
CHECK_SIGNATURE:
        LDA $3000,X
        CMP EXPECTED,X
        BNE ABSENT
        DEX
        BPL CHECK_SIGNATURE
        LDX #3
CHECK_MEMORY:
        LDA $3007,X
        CMP MEMORY_EXPECTED,X
        BNE ABSENT
        DEX
        BPL CHECK_MEMORY
        LDA PCR
        STA OLDPCR
        LDX BANK
        AND #$11
        ORA BANK_BITS,X
        STA PCR
        STA BEFORE_PCR
        LDA MANAGER
        STA $3DF0
CALL_NEXT:
        LDX #15
COPY_REQUEST:
        LDA PARAM,X
        STA $6650,X
        DEX
        BPL COPY_REQUEST
        LDA TYPE
        BEQ RAW
        JSR $300B
        BRA RESULT
RAW:    JSR $3004
RESULT:
        STA RETURN_STATUS
        PHP
        PLA
        STA FLAGS
        LDA PCR
        STA AFTER_PCR
        LDX #15
COPY_RESULT:
        LDA $6650,X
        STA OUTPUT,X
        DEX
        BPL COPY_RESULT
        LDA $6672
        STA MODE
        LDA $7FC2
        STA DDROUT
        LDA $666B
        STA GPIO_OLD
        LDA RETURN_STATUS
        BNE FINISH
        LDA REPEATS
        BEQ FINISH
        DEC REPEATS
        BEQ FINISH
        LDA PARAM+2
        CLC
        ADC #64
        STA PARAM+2
        BCC ADDRESS_READY
        INC PARAM+3
        BNE ADDRESS_READY
        INC PARAM+4
ADDRESS_READY:
        LDA PARAM+5
        CLC
        ADC #64
        STA PARAM+5
        BCC CALL_NEXT
        INC PARAM+6
        BRA CALL_NEXT
FINISH:
        LDA OLDPCR
        STA PCR
        LDA #'S'
        JSR PUTC
        LDA #'P'
        JSR PUTC
        LDA #'I'
        JSR PUTC
        LDA #':'
        JSR PUTC
        LDA #' '
        JSR PUTC
        LDA RETURN_STATUS
        JSR HEX
        JSR NL
        JMP HOLD
BAD:
        LDA #9
        BRA EARLY
ABSENT:
        LDA #$80
EARLY:
        STA OUTPUT+8
        STA RETURN_STATUS
        JMP HOLD
EXPECTED DB "SP",1,1
MEMORY_EXPECTED DB "SM",1,1
BANK_BITS DB $CC,$CE,$EC,$EE
APP_END:
        ENDMOD
        END
