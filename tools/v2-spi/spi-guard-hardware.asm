        MODULE SPI_GUARD_HARDWARE
        XDEF START
        XDEF APP_END
        CODE
START:  SEI
        CLD
        LDA $7FCD
        STA $2450
        LDA $7FCE
        STA $2451
        LDA $7FCC
        STA $2452
        LDA $7FCB
        STA $2453
        LDA $7FC2
        STA $2454
        JSR REQUEST
        JSR $66A6
        STA $2455
        JSR $2000
        STA $2456
        JSR REQUEST
        JSR $66A6
        STA $2457
        LDA $7FCD
        STA $2458
        LDA $7FC2
        STA $2459
        LDA $6659
        STA $245A
        JMP $7E67
REQUEST:
        LDX #15
COPY:   LDA $2400,X
        STA $6650,X
        DEX
        BPL COPY
        RTS
APP_END:
        ENDMOD
        END
