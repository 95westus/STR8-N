; Load through STR8-N L. No flash writes. Uses VIA1 Timer 1 at $7FC0.
; Refuses an already enabled VIA1 interrupt source. Saves/restores its ACR,
; timer latches, and RAM IRQ vector; leaves Timer 1 interrupts disabled.
; The actual timer IRQ must traverse the resident hardware vector, not a JSR.
; References: WDC W65C02SXB memory map and W65C22 Timer 1/IFR/IER datasheets.
                        ORG $2000
START:                  SEI
                        CLD
                        LDX #$FF
                        TXS
                        LDA $7FCE
                        AND #$7F
                        BEQ SAFE
                        LDX #<MSG_BUSY
                        LDY #>MSG_BUSY
                        JMP REPORT
SAFE:                   LDA $7FCB
                        STA SAVED_ACR
                        AND #$3F
                        STA $7FCB
                        LDA $7FC6
                        STA SAVED_T1L
                        LDA $7FC7
                        STA SAVED_T1H
                        LDA $7EFE
                        STA SAVED_IRQ
                        LDA $7EFF
                        STA SAVED_IRQ+1
                        LDA #<IRQ_HANDLER
                        STA $7EFE
                        LDA #>IRQ_HANDLER
                        STA $7EFF
                        STZ SEEN
                        STZ RESULT
                        STZ TIME_LO
                        STZ TIME_HI
                        LDA #$40
                        STA $7FCD
                        LDA #$C0
                        STA $7FCE
                        LDA #$FF
                        STA $7FC4
                        LDA #$3F
                        STA $7FC5
                        LDA #$55
                        LDX #$5A
                        LDY #$A5
                        CLI
WAIT_IRQ:               BIT SEEN
                        BNE GOT_IRQ
                        DEC TIME_LO
                        BNE WAIT_IRQ
                        DEC TIME_HI
                        BNE WAIT_IRQ
                        BRA CLEANUP
GOT_IRQ:                SEI
                        CMP #$55
                        BNE CLEANUP
                        CPX #$5A
                        BNE CLEANUP
                        CPY #$A5
                        BNE CLEANUP
                        TSX
                        CPX #$FF
                        BNE CLEANUP
                        LDA OBS_A
                        CMP #$55
                        BNE CLEANUP
                        LDA OBS_X
                        CMP #$5A
                        BNE CLEANUP
                        LDA OBS_Y
                        CMP #$A5
                        BNE CLEANUP
                        LDA OBS_P
                        AND #$1C
                        BNE CLEANUP
                        LDA OBS_IFR
                        AND #$C0
                        CMP #$C0
                        BNE CLEANUP
                        INC RESULT
CLEANUP:                SEI
                        LDA #$40
                        STA $7FCE
                        LDA $7FC4
                        LDA SAVED_T1L
                        STA $7FC6
                        LDA SAVED_T1H
                        STA $7FC7
                        LDA SAVED_ACR
                        STA $7FCB
                        LDA SAVED_IRQ
                        STA $7EFE
                        LDA SAVED_IRQ+1
                        STA $7EFF
                        LDX #<MSG_FAIL
                        LDY #>MSG_FAIL
                        LDA RESULT
                        BEQ REPORT
                        LDX #<MSG_PASS
                        LDY #>MSG_PASS
REPORT:                 STX $80
                        STY $81
                        LDY #0
PRINT:                  LDA ($80),Y
                        BEQ DONE
                        JSR $F019
                        INY
                        BRA PRINT
DONE:                   JMP $F000

IRQ_HANDLER:            STA OBS_A
                        STX OBS_X
                        STY OBS_Y
                        TSX
                        LDA $0101,X
                        STA OBS_P
                        LDA $7FCD
                        STA OBS_IFR
                        LDA #$40
                        STA $7FCE
                        LDA $7FC4
                        LDA #1
                        STA SEEN
                        LDY OBS_Y
                        LDX OBS_X
                        LDA OBS_A
                        RTI

SAVED_ACR:              DB 0
SAVED_T1L:              DB 0
SAVED_T1H:              DB 0
SAVED_IRQ:              DW 0
SEEN:                   DB 0
RESULT:                 DB 0
TIME_LO:                DB 0
TIME_HI:                DB 0
OBS_A:                  DB 0
OBS_X:                  DB 0
OBS_Y:                  DB 0
OBS_P:                  DB 0
OBS_IFR:                DB 0
MSG_PASS:               DB $0D,$0A,"V1.34 VIA1 TIMER IRQ / A-X-Y / STACK / B=0 / RTI: PASS",$0D,$0A,0
MSG_FAIL:               DB $0D,$0A,"V1.34 TIMER IRQ PROBE: FAIL (RAM OBS_* RETAINED)",$0D,$0A,0
MSG_BUSY:               DB $0D,$0A,"REFUSE: VIA1 INTERRUPTS ALREADY ENABLED",$0D,$0A,0
                        END
