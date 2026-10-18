        MODULE I2C_CLEAR
        XDEF START
        XDEF APP_END
        CODE
START:  PHP
        SEI
        CLD
        LDA $7FCF
        STA $3000
        LDA $7FC3
        STA $3001
        AND #$81
        BNE REFUSE
        LDA $3000
        AND #$7E
        STA $7FCF
        LDX #9
PULSE:  LDA $3001
        ORA #1
        STA $7FC3
        JSR DELAY
        LDA $3001
        STA $7FC3
        JSR DELAY
        DEX
        BNE PULSE
        LDA $3001
        ORA #$81
        STA $7FC3
        JSR DELAY
        LDA $3001
        ORA #$80
        STA $7FC3
        JSR DELAY
        LDA $3001
        STA $7FC3
        JSR DELAY
        LDA $3000
        STA $7FCF
        LDA $7FCF
        STA $3002
        AND #$81
        CMP #$81
        BNE REFUSE
        LDA #0
        BRA DONE
REFUSE: LDA #1
DONE:   STA $3003
        PLP
        JMP $7E67
DELAY:  LDY #$40
WAIT:   DEY
        BNE WAIT
        RTS
APP_END:
        ENDMOD
        END
