; Read-only Bank 3 top identity for public HIMON/ASM-F2 sessions.
; Runs entirely in RAM, prints through the FT245, restores the prior overlay.
                        MODULE  V2_BANK3_ID
                        XDEF    START
                        CODE
                        ORG     $2000

FTDI_CTRL               EQU     $7FE0
FTDI_DATA               EQU     $7FE1
FTDI_DDRA               EQU     $7FE3
VIA_PCR                 EQU     $7FEC

START:                  SEI
                        CLD
                        PHX
                        PHY
                        LDA     VIA_PCR
                        PHA
                        AND     #$11
                        ORA     #$EE
                        STA     VIA_PCR
                        LDX     #$00
PRINT_LABEL:            LDA     LABEL_TEXT,X
                        BEQ     PRINT_ID
                        JSR     OUT
                        INX
                        BRA     PRINT_LABEL
PRINT_ID:               LDA     $F000
                        JSR     HEX
                        LDA     $F001
                        JSR     HEX
                        LDA     $F002
                        JSR     HEX
                        LDA     $F003
                        JSR     HEX
                        LDX     #$00
PRINT_VECTOR_LABEL:     LDA     VECTOR_TEXT,X
                        BEQ     PRINT_VECTOR
                        JSR     OUT
                        INX
                        BRA     PRINT_VECTOR_LABEL
PRINT_VECTOR:           LDA     $FFFD
                        JSR     HEX
                        LDA     $FFFC
                        JSR     HEX
                        LDA     #$0D
                        JSR     OUT
                        LDA     #$0A
                        JSR     OUT
                        PLA
                        STA     VIA_PCR
                        PLY
                        PLX
                        RTS

HEX:                    PHA
                        LSR     A
                        LSR     A
                        LSR     A
                        LSR     A
                        JSR     NIBBLE
                        PLA
                        AND     #$0F
NIBBLE:                 CMP     #$0A
                        BCC     DIGIT
                        ADC     #$06
DIGIT:                  ADC     #'0'
                        JMP     OUT

OUT:                    PHA
                        STZ     FTDI_DDRA
                        STA     FTDI_DATA
TX_READY:               LDA     #$01
                        BIT     FTDI_CTRL
                        BNE     TX_READY
                        LDA     #$04
                        TSB     FTDI_CTRL
                        DEC     FTDI_DDRA
                        NOP
                        NOP
                        TRB     FTDI_CTRL
                        STZ     FTDI_DDRA
                        PLA
                        RTS

LABEL_TEXT:             DB      "B3:F HEAD=",0
VECTOR_TEXT:            DB      " RESET=",0
                        ENDMOD
                        END
