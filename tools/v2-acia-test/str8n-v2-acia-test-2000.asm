; RAM-only W65C51N diagnostic. It bypasses STR8-N console selection and writes
; the stock ACIA directly at 19200 8N1. Q/q returns through public HOLD.
                        MODULE  V2_ACIA_TEST
                        XDEF    START
                        XDEF    PROBE_END
                        CODE

ACIA_DATA               EQU     $7F80
ACIA_STATUS             EQU     $7F81
ACIA_COMMAND            EQU     $7F82
ACIA_CONTROL            EQU     $7F83
ACIA_RDRF               EQU     $08
DELAY_OUTER             EQU     $D0
RX_BYTE                 EQU     $D1
FT_CTRL                 EQU     $7FE0
FT_DATA                 EQU     $7FE1
FT_DDRB                 EQU     $7FE2
FT_DDRA                 EQU     $7FE3
STR8V2_HOLD             EQU     $F007

START:                  SEI
                        CLD
                        LDX     #$FF
                        TXS
; Programmed reset clears any receiver state left by the monitor or a warm
; restart.  Reapply control and command immediately afterward.
                        STZ     ACIA_STATUS
                        LDA     #$1F
                        STA     ACIA_CONTROL
                        LDA     #$0B
                        STA     ACIA_COMMAND
                        LDA     #$0C
                        STA     FT_CTRL
                        STA     FT_DDRB
                        STZ     FT_DDRA
                        LDY     #$00
FT_ANNOUNCE:            LDA     FT_MESSAGE,Y
                        BEQ     ANNOUNCE
                        JSR     FT_PUTC
                        INY
                        BRA     FT_ANNOUNCE

ANNOUNCE:               LDY     #$00
PRINT:                  LDA     MESSAGE,Y
                        BEQ     DELAY_START
                        JSR     PUTC
                        INY
                        BRA     PRINT

; Roughly one second at 8 MHz. RDRF is sampled about every 160 us so typed
; characters are consumed while the repeating banner is paced.
DELAY_START:            LDA     #$18
                        STA     DELAY_OUTER
DELAY_PAGE:             LDY     #$00
DELAY_CHUNK:            LDX     #$00
DELAY_INNER:            DEX
                        BNE     DELAY_INNER
                        LDA     #ACIA_RDRF
                        BIT     ACIA_STATUS
                        BNE     RECEIVE
DELAY_CONTINUE:         DEY
                        BNE     DELAY_CHUNK
                        DEC     DELAY_OUTER
                        BNE     DELAY_PAGE
                        LDA     ACIA_STATUS
                        STA     RX_BYTE
                        LDY     #$00
FT_STATUS_PREFIX:       LDA     FT_STATUS_MESSAGE,Y
                        BEQ     FT_STATUS_VALUE
                        JSR     FT_PUTC
                        INY
                        BRA     FT_STATUS_PREFIX
FT_STATUS_VALUE:        LDA     RX_BYTE
                        JSR     FT_HEX
                        LDA     #$0D
                        JSR     FT_PUTC
                        LDA     #$0A
                        JSR     FT_PUTC
                        BRA     ANNOUNCE

RECEIVE:                LDA     ACIA_DATA
                        STA     RX_BYTE
                        LDY     #$00
FT_RX_PREFIX:           LDA     FT_RX_MESSAGE,Y
                        BEQ     FT_RX_VALUE
                        JSR     FT_PUTC
                        INY
                        BRA     FT_RX_PREFIX
FT_RX_VALUE:            LDA     RX_BYTE
                        JSR     FT_HEX
                        LDA     #$0D
                        JSR     FT_PUTC
                        LDA     #$0A
                        JSR     FT_PUTC
                        LDA     RX_BYTE
                        CMP     #'Q'
                        BEQ     QUIT
                        CMP     #'q'
                        BEQ     QUIT
                        PHA
                        JSR     PUTC
                        PLA
                        CMP     #$0D
                        BNE     DELAY_CONTINUE
                        LDA     #$0A
                        JSR     PUTC
                        BRA     DELAY_CONTINUE

QUIT:                   LDY     #$00
QUIT_PRINT:             LDA     QUIT_MESSAGE,Y
                        BEQ     QUIT_DONE
                        JSR     PUTC
                        INY
                        BRA     QUIT_PRINT
QUIT_DONE:              JMP     STR8V2_HOLD

; W65C51N TDRE remains set and cannot pace output. This loop is more than one
; complete 10-bit frame (4167 CPU cycles at 8 MHz and 19200 baud).
PUTC:                   STA     ACIA_DATA
                        PHX
                        PHY
                        LDY     #$04
PUTC_OUTER:             LDX     #$D0
PUTC_INNER:             DEX
                        BNE     PUTC_INNER
                        DEY
                        BNE     PUTC_OUTER
                        PLY
                        PLX
                        RTS

; The primary FT245 remains a diagnostic channel while the ACIA is exercised.
FT_HEX:                 PHA
                        LSR     A
                        LSR     A
                        LSR     A
                        LSR     A
                        JSR     FT_NIBBLE
                        PLA
                        AND     #$0F
FT_NIBBLE:              ORA     #'0'
                        CMP     #'9'+1
                        BCC     FT_PUTC
                        ADC     #$06
FT_PUTC:                PHA
                        STZ     FT_DDRA
                        LDA     #$01
FT_TX_WAIT:             BIT     FT_CTRL
                        BNE     FT_TX_WAIT
                        PLA
                        STA     FT_DATA
                        NOP
                        NOP
                        LDA     #$04
                        TSB     FT_CTRL
                        DEC     FT_DDRA
                        NOP
                        NOP
                        LDA     #$04
                        TRB     FT_CTRL
                        STZ     FT_DDRA
                        RTS

MESSAGE:                DB      $0D,$0A,"ACIA 19200 8N1 - TYPE; Q EXITS",$0D,$0A,$00
QUIT_MESSAGE:           DB      $0D,$0A,"ACIA EXIT",$0D,$0A,$00
FT_MESSAGE:             DB      $0D,$0A,"ACIA RX MONITOR; SEND Q",$0D,$0A,$00
FT_RX_MESSAGE:          DB      "ACIA RX $",$00
FT_STATUS_MESSAGE:      DB      "ACIA STATUS $",$00
PROBE_END:
                        ENDMOD
                        END
