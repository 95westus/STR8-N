; Read-only EDU MCP79411 probe for STR8-N v2; load/run at $2000.
; Adapted from the Codex-authored R-YORS edu-rtc-read-7000.a.
; PA0=SCL, PA7=SDA, VIA1=$7FC0. No RTC register data writes.
; ABI: 65C02 or 816 emulation, D=DBR=PBR=0; monitor G entry.
; Uses local RAM, VIA1 PA0/PA7, and existing RAM console ABI.
; Returns to HOLD; no LED/buzzer, flash, crypto or SPI access.
        MODULE V2_RTC_TEST
        XDEF START
        XDEF PROBE_END
        INCLUDE "str8n-v2-public.inc"
        CODE
VORA    EQU $7FCF
VDDR    EQU $7FC3
SCL     EQU $01
SDA     EQU $80

START   SEI
        CLD
        LDX #3
ABI     LDA STR8V2_RAM_SIGNATURE,X
        CMP EXPECT,X
        BEQ ABIOK
        RTS
ABIOK
        DEX
        BPL ABI
        JSR I2INIT
        BCC IOFAIL
        JSR RTREAD
        BCC IOFAIL
        JSR VALID
        BCC INVALID
        JSR SHOW
        LDA RTCBUF
        AND #$7F
        STA FIRST
        SED
        CLC
        ADC #1
        CLD
        CMP #$60
        BNE NEXTSEC
        LDA #0
NEXTSEC STA EXPECTSEC
        LDA #80
        STA TRIES
POLL    LDY #0
WAIT1   LDX #0
WAIT2   DEX
        BNE WAIT2
        DEY
        BNE WAIT1
        JSR RTREAD
        BCC IOFAIL
        JSR VALID
        BCC INVALID
        LDA RTCBUF
        AND #$7F
        CMP FIRST
        BEQ SAMESEC
        CMP EXPECTSEC
        BEQ PRESENT
        BRA INVALID
SAMESEC
        DEC TRIES
        BNE POLL
INVALID LDX #<UNKNOWN
        LDY #>UNKNOWN
        BRA FINISH
PRESENT JSR SHOW
        LDX #<FOUND
        LDY #>FOUND
FINISH  JSR I2REST
        JSR PUTS
        JSR CRLF
        JMP STR8V2_RAM_HOLD
IOFAIL  STA ERROR
        JSR I2REST
        LDX #<IOMSG
        LDY #>IOMSG
        JSR PUTS
        LDA ERROR
        JSR HEX
        JSR CRLF
        JMP STR8V2_RAM_HOLD
BADABI  RTS
EXPECT  DB "RA",STR8V2_RAM_FORMAT,STR8V2_RAM_CALLS
FIRST   DB 0
EXPECTSEC DB 0
TRIES   DB 0
; Validate packed BCD, calendar ranges, ST and OSCRUN.
VALID   LDA RTCBUF
        BPL VFAIL
        LDA RTCBUF+3
        AND #$20
        BEQ VFAIL
        LDX #6
VLOOP   LDA RTCBUF,X
        AND MASKS,X
        STA VALUE
        AND #$0F
        CMP #10
        BCS VFAIL
        LDA VALUE
        CMP LOWS,X
        BCC VFAIL
        CMP HIGHS,X
        BCS VFAIL
        DEX
        BPL VLOOP
        LDA RTCBUF+2
        AND #$40
        BEQ V24
        LDA RTCBUF+2
        AND #$1F
        BEQ VFAIL
        CMP #$13
        BCS VFAIL
        BRA VDATE
V24     LDA RTCBUF+2
        AND #$3F
        CMP #$24
        BCS VFAIL
VDATE   LDA RTCBUF+5
        AND #$1F
        TAX
        LDA DAYS,X
        CPX #2
        BNE VDAY
        LDA RTCBUF+6
        LSR A
        LSR A
        LSR A
        LSR A
        AND #1
        ASL A
        STA VALUE
        LDA RTCBUF+6
        AND #$0F
        CLC
        ADC VALUE
        AND #3
        BNE VFEB
        LDA #$29
        BRA VDAY
VFEB    LDA #$28
VDAY    CMP RTCBUF+4
        BCC VFAIL
        SEC
        RTS
VFAIL   CLC
        RTS
MASKS   DB $7F,$7F,$1F,$07,$FF,$1F,$FF
LOWS    DB 0,0,0,1,1,1,0
HIGHS   DB $60,$60,$24,8,$32,$13,$A0
DAYS    DB 0,$31,$28,$31,$30,$31,$30,$31,$31,$30,0,0,0,0,0,0,$31,$30,$31
VALUE   DB 0
FOUND   DB "EDU detected (RTC valid and advancing)",0
UNKNOWN DB "EDU detection inconclusive (invalid or stopped RTC)",0

; Save driven output levels and DDRA. Release before latching lows.
; Input-pin hidden latch values cannot be recovered by VIA reads.
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

; MCP79411 BUFFERED SEQUENTIAL READ OF $00-$06.
RTREAD  STZ BUSERR
        JSR I2START
        LDA #$DE
        JSR I2WRITE
        BCC RTNACK
        LDA #$00
        JSR I2WRITE
        BCC RTNACK
        JSR I2START
        LDA #$DF
        JSR I2WRITE
        BCC RTNACK
        LDX #$00
RTLOOP  LDY #$00
        CPX #$06
        BNE RTACK
        LDY #$01
RTACK   JSR I2READ
        STA RTCBUF,X
        INX
        CPX #$07
        BNE RTLOOP
        JSR I2STOP
        LDA BUSERR
        BNE RTBUS
        SEC
        RTS
RTBUS   LDA #$03
        CLC
        RTS
RTNACK  JSR I2STOP
        LDA #$02
        CLC
        RTS

; START AND STOP CONDITIONS. LINES ARE NEVER DRIVEN HIGH.
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

SHOW    LDX #<DATEMSG
        LDY #>DATEMSG
        JSR PUTS
        LDA RTCBUF+6
        JSR BCD
        LDA #'-'
        JSR OUT
        LDA RTCBUF+5
        AND #$1F
        JSR BCD
        LDA #'-'
        JSR OUT
        LDA RTCBUF+4
        AND #$3F
        JSR BCD
        LDX #<TIMEMSG
        LDY #>TIMEMSG
        JSR PUTS
        LDA RTCBUF+2
        PHA
        AND #$40
        BNE SHOW12
        PLA
        AND #$3F
        JSR BCD
        BRA SHOWMIN
SHOW12  PLA
        AND #$1F
        JSR BCD
SHOWMIN LDA #':'
        JSR OUT
        LDA RTCBUF+1
        AND #$7F
        JSR BCD
        LDA #':'
        JSR OUT
        LDA RTCBUF
        AND #$7F
        JSR BCD
        LDA RTCBUF+2
        AND #$40
        BEQ SHOWEOL
        LDA #' '
        JSR OUT
        LDA RTCBUF+2
        AND #$20
        BEQ SHOWAM
        LDA #'P'
        BRA SHOWAP
SHOWAM  LDA #'A'
SHOWAP  JSR OUT
        LDA #'M'
        JSR OUT
SHOWEOL JSR CRLF
        LDA RTCBUF+3
        AND #$20
        BNE SHOWPWR
        LDX #<STOPMSG
        LDY #>STOPMSG
        JSR PUTS
        JSR CRLF
SHOWPWR LDA RTCBUF+3
        AND #$10
        BEQ SHOWEND
        LDX #<PWRMSG
        LDY #>PWRMSG
        JSR PUTS
        JSR CRLF
SHOWEND RTS

; PRINT ONE PACKED-BCD BYTE AS TWO ASCII DIGITS.
BCD     PHA
        LSR A
        LSR A
        LSR A
        LSR A
        ORA #'0'
        JSR OUT
        PLA
        AND #$0F
        ORA #'0'
        JMP OUT

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

DATEMSG DB "DATE YY-MM-DD ",0
TIMEMSG DB "  TIME ",0
IOMSG   DB "EDU detection inconclusive: RTC I2C error $",0
STOPMSG DB "WARNING: RTC OSCILLATOR IS NOT RUNNING",0
PWRMSG  DB "NOTICE: RTC POWER-FAIL FLAG IS SET",0

BUSERR  DB 0
SAVEORA DB $00
SAVEDDR DB $00
I2BYTE  DB $00
I2ACK   DB $00
ERROR   DB $00
RTCBUF  DB $00,$00,$00,$00,$00,$00,$00

PROBE_END
        ENDMOD
        END
