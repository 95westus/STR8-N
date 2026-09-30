; Optional STR8-N v2a25 EDU RTC display, resident Bank 3 E sector.
; Read-only MCP79411 registers $00-$06 via VIA1 PA0/PA7.
; Runs only during startup; no LED, buzzer, SPI, crypto or flash writes.
        MODULE V2_RTC_EXTENSION
        XDEF RTC_END
        INCLUDE "str8n-v2-public.inc"
        CODE
VORA    EQU $7FCF
VDDR    EQU $7FC3
SCL     EQU $01
SDA     EQU $80
; Private startup scratch. S/R/T uses this window only when commanded.
FIRST   EQU $7D90
EXPECTSEC EQU $7D91
TRIES   EQU $7D92
VALUE   EQU $7D93
BUSERR  EQU $7D94
SAVEORA EQU $7D95
SAVEDDR EQU $7D96
I2BYTE  EQU $7D97
I2ACK   EQU $7D98
RTCBUF  EQU $7D99

RTC_DESCRIPTOR: DB "RT",$01,$00
RTC_ENTRY: JMP RTC_START
RTC_START:
        JSR I2INIT
        BCC RTC_RESTORE
        JSR RTREAD
        BCC RTC_RESTORE
        JSR VALID
        BCC RTC_RESTORE
        LDA RTCBUF
        AND #$7F
        STA FIRST
        SED
        CLC
        ADC #1
        CLD
        CMP #$60
        BNE RTC_NEXT
        LDA #0
RTC_NEXT STA EXPECTSEC
        LDA #80
        STA TRIES
RTC_POLL:
        LDY #0
RTC_WAIT1 LDX #0
RTC_WAIT2 DEX
        BNE RTC_WAIT2
        DEY
        BNE RTC_WAIT1
        JSR RTREAD
        BCC RTC_RESTORE
        JSR VALID
        BCC RTC_RESTORE
        LDA RTCBUF
        AND #$7F
        CMP FIRST
        BEQ RTC_SAME
        CMP EXPECTSEC
        BNE RTC_RESTORE
        JMP RTC_SUCCESS
RTC_SAME:
        DEC TRIES
        BNE RTC_POLL
RTC_RESTORE:
        JSR I2REST
        JSR RTC_UNKNOWN
        RTS
RTC_SUCCESS:
        JSR I2REST
        JSR RTC_SHOW
        RTS

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

RTC_SHOW:
        JSR STR8V2_RAM_NEWLINE
        LDX #0
RTC_FOUND_LOOP LDA EDU_FOUND_TEXT,X
        BEQ RTC_FOUND_END
        JSR OUT
        INX
        BRA RTC_FOUND_LOOP
RTC_FOUND_END:
        JSR STR8V2_RAM_NEWLINE
        LDX #0
RTC_LABEL1 LDA RTC_TEXT,X
        BEQ RTC_YEAR
        JSR OUT
        INX
        BRA RTC_LABEL1
RTC_YEAR
        LDA RTCBUF+3
        AND #$07
        DEC A
        STA VALUE
        ASL A
        CLC
        ADC VALUE
        TAY
        LDX #3
DOW_PRINT LDA DOW_NAMES,Y
        JSR OUT
        INY
        DEX
        BNE DOW_PRINT
        LDA #' '
        JSR OUT
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
        LDA #' '
        JSR OUT
RTC_HOUR
        LDA RTCBUF+2
        AND #$40
        BEQ RTC_H24
        LDA RTCBUF+2
        AND #$1F
        STA VALUE
        LDA RTCBUF+2
        AND #$20
        BNE RTC_PM
        LDA VALUE
        CMP #$12
        BNE RTC_H12
        LDA #0
        BRA RTC_H12
RTC_PM  LDA VALUE
        CMP #$12
        BEQ RTC_H12
        SED
        CLC
        ADC #$12
        CLD
        BRA RTC_H12
RTC_H24 LDA RTCBUF+2
        AND #$3F
RTC_H12 JSR BCD
        LDA #':'
        JSR OUT
        LDA RTCBUF+1
        AND #$7F
        JSR BCD
        LDA #':'
        JSR OUT
        LDA RTCBUF
        AND #$7F
        JSR BCD
        RTS

RTC_UNKNOWN:
        JSR STR8V2_RAM_NEWLINE
        LDX #0
RTC_UNKNOWN_LOOP LDA EDU_UNKNOWN_TEXT,X
        BEQ RTC_UNKNOWN_END
        JSR OUT
        INX
        BRA RTC_UNKNOWN_LOOP
RTC_UNKNOWN_END RTS

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
EDU_FOUND_TEXT DB "EDU KIT       DETECTED",0
EDU_UNKNOWN_TEXT DB "EDU KIT       INCONCLUSIVE",0
RTC_TEXT DB "  RTC         ",0
DOW_NAMES DB "SunMonTueWedThuFriSat"
RTC_END:
        ENDMOD
        END
