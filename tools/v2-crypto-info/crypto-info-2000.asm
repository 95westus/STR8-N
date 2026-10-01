; RAM-only ATECC608 information probe. Fixed read-only command table.
; VIA1 PA0=SCL PA7=SDA; default 7-bit address $60. No NVM writes.
        MODULE CRYPTO_INFO
        XDEF START
        XDEF PROBE_END
        INCLUDE "str8n-v2-public.inc"
        CODE
VORA EQU $7FCF
VDDR EQU $7FC3
SCL EQU $01
SDA EQU $80
START   SEI
        CLD
        LDX #3
ABI     LDA STR8V2_RAM_SIGNATURE,X
        CMP EXPECT,X
        BEQ ABIOK
        RTS
ABIOK   DEX
        BPL ABI
        STZ INDEX
        LDA #<COMMANDS
        STA CMDLOAD+1
        LDA #>COMMANDS
        STA CMDLOAD+2
        JSR I2INIT
        BCS NEXT
        JMP FAIL
NEXT    STZ BUSERR
        JSR WAKE
        BCS AWAKE
        JMP FAIL
AWAKE   JSR I2START
        LDA #$C0
        JSR I2WRITE
        BCC FAIL
        LDA #3
        JSR I2WRITE
        BCC FAIL
        LDX #0
CMDLOAD LDA COMMANDS,X
        JSR I2WRITE
        BCC FAIL
        INX
        CPX #7
        BNE CMDLOAD
        JSR I2STOP
        JSR DELAY
        JSR RECEIVE
        BCC FAIL
        JSR SLEEP
        LDA BUSERR
        BNE FAIL
        LDA INDEX
        JSR HEX
        LDA #':'
        JSR OUT
        LDX #0
PRINT   LDA #' '
        JSR OUT
        LDA RESPONSE,X
        JSR HEX
        INX
        CPX LENGTH
        BNE PRINT
        JSR CRLF
        CLC
        LDA CMDLOAD+1
        ADC #7
        STA CMDLOAD+1
        BCC ADVANCE
        INC CMDLOAD+2
ADVANCE INC INDEX
        LDA INDEX
        CMP #COMMAND_COUNT
        BNE NEXT
        JSR I2REST
        LDX #<DONE
        LDY #>DONE
        JSR PUTS
        JMP STR8V2_RAM_HOLD
FAIL    JSR I2STOP
        JSR SLEEP
        JSR I2REST
        LDX #<ERRORMSG
        LDY #>ERRORMSG
        JSR PUTS
        LDA INDEX
        JSR HEX
        JSR CRLF
        JMP STR8V2_RAM_HOLD
; Wake low about 80 us at 8 MHz; wait about 41 ms after release.
WAKE    JSR SDAREL
        JSR SCLREL
        JSR SDALOW
        LDX #128
WLOW    DEX
        BNE WLOW
        JSR SDAREL
        JSR DELAY
        JSR RECEIVE
        BCC WBAD
        LDX #3
WCHECK  LDA RESPONSE,X
        CMP WEXPECTED,X
        BNE WBAD
        DEX
        BPL WCHECK
        SEC
        RTS
WBAD    CLC
        RTS
WEXPECTED DB $04,$11,$33,$43
SLEEP   JSR I2START
        LDA #$C0
        JSR I2WRITE
        BCC SLEEPEND
        LDA #1
        JSR I2WRITE
SLEEPEND JMP I2STOP
; All requested responses are 4 or 7 bytes. Bound count before buffering.
RECEIVE JSR I2START
        LDA #$C1
        JSR I2WRITE
        BCC RXBAD
        LDY #0
        JSR I2READ
        STA RESPONSE
        STA LENGTH
        CMP #4
        BEQ RXOK
        CMP #7
        BNE RXBAD
RXOK    LDX #1
RXLOOP  LDY #0
        TXA
        INC A
        CMP LENGTH
        BNE RXMORE
        INY
RXMORE  JSR I2READ
        STA RESPONSE,X
        INX
        CPX LENGTH
        BNE RXLOOP
        JSR I2STOP
        LDA BUSERR
        BNE RXBAD
        SEC
        RTS
RXBAD   JSR I2STOP
        CLC
        RTS
DELAY   LDY #255
DOUTER  LDX #0
DINNER  DEX
        BNE DINNER
        DEY
        BNE DOUTER
        RTS
I2INIT  LDA VORA
        STA SAVEORA
        LDA VDDR
        STA SAVEDDR
        AND #$7E
        STA VDDR
        LDA SAVEORA
        AND #$7E
        STA VORA
        NOP
        NOP
        LDA VORA
        AND #$81
        CMP #$81
        BEQ I2GOOD
        LDA #$01
        CLC
        RTS
I2GOOD  SEC
        RTS

I2REST  LDA SAVEORA
        STA VORA
        LDA SAVEDDR
        STA VDDR
        RTS

I2START JSR SDAREL
        JSR SCLREL
        JSR SDALOW
        JMP SCLLOW

I2STOP  JSR SDALOW
        JSR SCLREL
        JMP SDAREL

; WRITE A BYTE MSB FIRST; C=1 FOR SLAVE ACK, C=0 FOR NACK.
I2WRITE STA I2BYTE
        PHX
        LDX #$08
IWLOOP  ASL I2BYTE
        BCC IWZERO
        JSR SDAREL
        BRA IWCLOCK
IWZERO  JSR SDALOW
IWCLOCK JSR SCLREL
        JSR SCLLOW
        DEX
        BNE IWLOOP
        JSR SDAREL
        JSR SCLREL
        LDA VORA
        AND #SDA
        STA I2ACK
        JSR SCLLOW
        PLX
        LDA I2ACK
        BNE IWNACK
        SEC
        RTS
IWNACK  CLC
        RTS

; READ A BYTE MSB FIRST. Y=0 SENDS ACK; Y<>0 SENDS FINAL NACK.
I2READ  PHX
        STZ I2BYTE
        JSR SDAREL
        LDX #$08
IRLOOP  JSR SCLREL
        LDA VORA
        AND #SDA
        BEQ IRZERO
        SEC
        BRA IRROLL
IRZERO  CLC
IRROLL  ROL I2BYTE
        JSR SCLLOW
        DEX
        BNE IRLOOP
        CPY #$00
        BNE IRNACK
        JSR SDALOW
        BRA IRPULSE
IRNACK  JSR SDAREL
IRPULSE JSR SCLREL
        JSR SCLLOW
        JSR SDAREL
        PLX
        LDA I2BYTE
        RTS

; DDRA=0 RELEASES A PIN TO THE BOARD PULL-UP; DDRA=1 DRIVES
; THE LOW ORA LATCH. DELAYS KEEP THE BUS BELOW 400 KHZ.
SDAREL  LDA VDDR
        AND #$7F
        STA VDDR
        NOP
        NOP
        RTS
SDALOW  LDA VDDR
        ORA #SDA
        STA VDDR
        NOP
        NOP
        RTS
SCLREL  LDA VDDR
        AND #$FE
        STA VDDR
        NOP
        NOP
        RTS
SCLLOW  LDA VORA
        AND #SCL
        BNE SCLOK
        INC BUSERR
SCLOK   LDA VDDR
        ORA #SCL
        STA VDDR
        NOP
        NOP
        RTS

OUT     JMP STR8V2_RAM_PUTC
HEX     JMP STR8V2_RAM_HEX_OUT
CRLF    JMP STR8V2_RAM_NEWLINE
PUTS    STX TEXTLOAD+1
        STY TEXTLOAD+2
        PHX
        LDX #0
TEXTLOAD LDA $FFFF,X
        BEQ TEXTEND
        JSR OUT
        INX
        BNE TEXTLOAD
TEXTEND PLX
        RTS

EXPECT DB "RA",STR8V2_RAM_FORMAT,STR8V2_RAM_CALLS
DONE DB "CRYPTO INFO DONE",$0D,$0A,0
ERRORMSG DB "CRYPTO TRANSPORT FAIL AT ",0
BUSERR DB 0
SAVEORA DB 0
SAVEDDR DB 0
I2BYTE DB 0
I2ACK DB 0
INDEX DB 0
LENGTH DB 0
RESPONSE DB 0,0,0,0,0,0,0
        INCLUDE "commands.inc"
PROBE_END
        ENDMOD
        END
