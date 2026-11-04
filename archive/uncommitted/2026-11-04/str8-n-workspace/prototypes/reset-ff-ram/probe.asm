; RAM-only FT245/VIA isolation probe. No flash, PCR, ACR, IER, RTC or PIA writes.
; Zero-page-free except the existing monitor NMI hold byte at $F4.
        MODULE RESET_FF_PROBE
        XDEF PROBE_END
        CODE
CAP EQU $6400
ROW EQU $6410
HOLD EQU $F4
CTRL EQU $7FE0
DATA EQU $7FE1
DDRB EQU $7FE2
DDRA EQU $7FE3
ACR EQU $7FEB
PCR EQU $7FEC
IFR EQU $7FED
IER EQU $7FEE
DATA_NH EQU $7FEF
PUTC EQU $F00D
PROMPT EQU $B160
PROBE_START:
        SEI
        CLD
        LDA HOLD
        PHA
        LDA #1
        STA HOLD
        DB $A9
PROBE_SELECTOR: DB 0
        PHA
        LDX #0
RP_CLEAR:
        STZ CAP,X
        INX
        CPX #$F0
        BNE RP_CLEAR
        PLA
        STA CAP+5
        PLA
        STA CAP+9
        LDA #'R'
        STA CAP
        LDA #'F'
        STA CAP+1
        LDA #'P'
        STA CAP+2
        LDA #'1'
        STA CAP+3
        LDA #1
        STA CAP+4
        LDA #0
        JSR RP_SNAPSHOT
        LDA IER
        CMP #$80
        BNE RP_BAD_IER
        LDA DDRA
        BNE RP_BAD_DDR
        LDA DDRB
        CMP #$0C
        BNE RP_BAD_DDR
        LDA PCR
        AND #$EE
        CMP #$EE
        BNE RP_BAD_PCR
        LDA ACR
        BNE RP_BAD_ACR
        LDA CTRL
        AND #8
        BEQ RP_BAD_RD
        LDA $7D02
        CMP #1
        BNE RP_BAD_CONSOLE
        LDA $7C2B
        BNE RP_BAD_CONSOLE
        LDA CTRL
        AND #1
        BNE RP_BAD_TX
        LDA #0
        LDX #15
RP_NONCE:
        ORA CAP+$F0,X
        DEX
        BPL RP_NONCE
        CMP #0
        BEQ RP_BAD_NONCE
        LDA CAP+5
        BEQ RP_DONE
        CMP #1
        BEQ RP_INIT
        CMP #2
        BEQ RP_RELEASE
        CMP #3
        BEQ RP_A5
        CMP #4
        BEQ RP_ZERO
        CMP #5
        BEQ RP_UNSAFE
        CMP #8
        BCC RP_BAD_CASE
        CMP #12
        BCS RP_BAD_CASE
        JMP RP_ARM
RP_BAD_IER:
        LDA #1
        BRA RP_REFUSE
RP_BAD_DDR:
        LDA #2
        BRA RP_REFUSE
RP_BAD_PCR:
        LDA #3
        BRA RP_REFUSE
RP_BAD_ACR:
        LDA #4
        BRA RP_REFUSE
RP_BAD_RD:
        LDA #5
        BRA RP_REFUSE
RP_BAD_CONSOLE:
        LDA #6
        BRA RP_REFUSE
RP_BAD_NONCE:
        LDA #7
        BRA RP_REFUSE
RP_BAD_CASE:
        LDA #8
RP_REFUSE:
        STA CAP+8
        LDA #$80
        STA CAP+7
        LDA #$E0
        STA CAP+12
        JSR RP_COMMIT
RP_REFUSED_HALT:
        JMP RP_REFUSED_HALT
RP_INIT:
        LDA #$0C
        STA CTRL
        LDA #$11
        JSR RP_SNAPSHOT
        LDA #$0C
        STA DDRB
        LDA #$12
        JSR RP_SNAPSHOT
        STZ DDRA
        LDA #$13
        JSR RP_SNAPSHOT
        JMP RP_DONE
RP_RELEASE:
        LDA #8
        STA DDRB
        JSR RP_SETTLE
        LDA #$21
        JSR RP_SNAPSHOT
        LDA #$0C
        STA CTRL
        LDA #$22
        JSR RP_SNAPSHOT
        LDA #$0C
        STA DDRB
        LDA #$23
        JSR RP_SNAPSHOT
        JMP RP_DONE
RP_A5:
        LDA #$A5
        BRA RP_STROBE
RP_ZERO:
        LDA #0
RP_STROBE:
        STA DATA
        LDA #4
        TSB CTRL
        LDA #$31
        JSR RP_SNAPSHOT
        LDA #$FF
        STA DDRA
        NOP
        NOP
        LDA #$32
        JSR RP_SNAPSHOT
        LDA #4
        TRB CTRL
        LDA #$33
        JSR RP_SNAPSHOT
        STZ DDRA
        LDA #$34
        JSR RP_SNAPSHOT
        JMP RP_DONE
RP_UNSAFE:
        ; Establish high before release so the test deliberately supplies an
        ; undriven falling edge. The sampled DATA value remains hardware-specific.
        LDA #4
        TSB CTRL
        LDA #8
        STA DDRB
        JSR RP_SETTLE
        LDA #$51
        JSR RP_SNAPSHOT
        LDA #8
        STA CTRL
        LDA #$52
        JSR RP_SNAPSHOT
        LDA CTRL
        AND #1
        BNE RP_BAD_TX
        LDA #$0C
        STA DDRB
        LDA #$53
        JSR RP_SNAPSHOT
        JMP RP_DONE
RP_DONE:
        LDA #$0C
        STA CTRL
        STA DDRB
        STZ DDRA
        LDA #$F0
        JSR RP_SNAPSHOT
        LDA #1
        STA CAP+7
        JSR RP_COMMIT
        LDA CAP+9
        STA HOLD
RP_RETURN:
        JMP PROMPT
RP_ARM:
        LDA CTRL
        AND #1
        BNE RP_BAD_TX
        LDX #0
RP_READY:
        LDA RP_ARM_TEXT,X
        BEQ RP_READY_CASE
        JSR RP_PUTC
        INX
        BRA RP_READY
RP_READY_CASE:
        LDA #'0'
        JSR RP_PUTC
        LDX CAP+5
        LDA RP_HEX,X
        JSR RP_PUTC
        LDA #13
        JSR RP_PUTC
        LDA #10
        JSR RP_PUTC
        ; The last READY character was normally sent with valid driven data,
        ; leaving WR low/DDRA input. No text or polling follows final setup.
        LDA CAP+5
        CMP #8
        BEQ RP_ARM_LOW
        CMP #10
        BEQ RP_ARM_INPUT
        LDA #4
        TSB CTRL
        LDA CAP+5
        CMP #11
        BNE RP_ARM_FINAL
        LDA #$A5
        STA DATA
        LDA #$FF
        STA DDRA
        BRA RP_ARM_FINAL
RP_ARM_LOW:
        LDA #4
        TRB CTRL
        BRA RP_ARM_FINAL
RP_ARM_INPUT:
        LDA #8
        STA DDRB
RP_ARM_FINAL:
        JSR RP_SETTLE
        LDA #$A0
        ORA CAP+5
        JSR RP_SNAPSHOT
        LDA #2
        STA CAP+7
        JSR RP_COMMIT
RP_ARMED_HALT:
        JMP RP_ARMED_HALT
RP_BAD_TX:
        LDA #9
        JMP RP_REFUSE
RP_PUTC:
        PHA
        LDA CTRL
        AND #1
        BNE RP_PUTC_BLOCKED
        PLA
        JMP PUTC
RP_PUTC_BLOCKED:
        PLA
        JMP RP_BAD_TX
; Nominal 1 ms at 8 MHz, no I/O, no zero-page scratch.
RP_SETTLE:
        LDY #8
RP_SETTLE_OUTER:
        LDX #200
RP_SETTLE_INNER:
        DEX
        BNE RP_SETTLE_INNER
        DEY
        BNE RP_SETTLE_OUTER
        RTS
; Rows are snapshots of physical readback, not hidden output-latch backups.
; ORB/ORA accesses can acknowledge CB/CA flags: capture IFR on both sides.
RP_SNAPSHOT:
        STA CAP+12
        PHA
        LDA CAP+6
        ASL A
        ASL A
        ASL A
        ASL A
        TAX
        PLA
        STA ROW,X
        LDA DDRA
        STA ROW+1,X
        LDA DDRB
        STA ROW+2,X
        LDA IFR
        STA ROW+3,X
        LDA IER
        STA ROW+4,X
        LDA PCR
        STA ROW+5,X
        LDA ACR
        STA ROW+6,X
        LDA CTRL
        STA ROW+7,X
        LDA DATA_NH
        STA ROW+8,X
        LDA IFR
        STA ROW+9,X
        LDA IER
        STA ROW+10,X
        INC CAP+6
        RTS
RP_COMMIT:
        LDA CAP+5
        EOR #$FF
        STA CAP+10
        LDA CAP+7
        EOR #$FF
        STA CAP+11
        LDA CAP+12
        EOR #$FF
        STA CAP+13
        STZ CAP+14
        LDA #0
        LDX #0
RP_CHECKSUM:
        EOR CAP,X
        INX
        BNE RP_CHECKSUM
        STA CAP+14
        LDA #$A5
        STA CAP+15
        RTS
RP_ARM_TEXT: DB 13,10,"RFP1 ARM ",0
RP_HEX: DB "0123456789ABCDEF"
PROBE_END:
        ENDMOD
        END
