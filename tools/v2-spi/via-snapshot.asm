        MODULE SPI_VIA_SNAPSHOT
        XDEF START
        XDEF APP_END
        CODE
START:  LDA $7FCD
        STA $2400
        LDA $7FCE
        STA $2401
        LDA $7FCC
        STA $2402
        LDA $7FCB
        STA $2403
        LDA $7FC2
        STA $2404
        JMP $7E67
APP_END:
        ENDMOD
        END
