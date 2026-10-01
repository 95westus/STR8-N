; Optional STR8-N v2a31 EDU RTC display, resident Bank 3 E sector.
; Read-only MCP79411 registers $00-$06 via VIA1 PA0/PA7.
; Runs only during startup; no LED, buzzer, SPI, crypto or flash writes.
        MODULE V2_RTC_EXTENSION
        XDEF RTC_END
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "sr-monitor-symbols.inc"
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

RTC_DESCRIPTOR: DB "RT",$02,$00
RTC_ENTRY: JMP RTC_START
EE_READ_ENTRY: JMP EE_READ
EE_WRITE_ENTRY: JMP EE_SAVE
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
        JMP $ED00
RTC_SUCCESS:
        JSR I2REST
        JSR RTC_SHOW
        JMP $ED00

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
        LDA #1
        STA RTC_OK
        RTS
RTC_UNKNOWN:
        STZ RTC_OK
        RTS

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
RTC_OK EQU $7DE0
; Read-only ATECC608 startup metadata. Separate scratch from EEPROM/S/R.
CR_OK EQU $7DE1
CR_INDEX EQU $7DE2
CR_CRCLO EQU $7DE3
CR_CRCHI EQU $7DE4
CR_BYTE EQU $7DE5
CR_MIX EQU $7DE6
CR_COUNT EQU $7DE7
CR_BUF EQU $7DE8
CR_DATA EQU $7DF0
CR_START:
        STZ CR_OK
        JSR I2INIT
        BCS CR_INIT_OK
        JMP CR_EXIT
CR_INIT_OK:
        JSR SDAREL
        JSR SCLREL
        JSR SDALOW
        LDX #128
CR_WAKELOW:
        DEX
        BNE CR_WAKELOW
        JSR SDAREL
        JSR CR_DELAY
        JSR CR_READ
        BCC CR_SLEEP
        LDA CR_COUNT
        CMP #4
        BNE CR_SLEEP
        LDA CR_BUF+1
        CMP #$11
        BNE CR_SLEEP
        STZ CR_INDEX
CR_NEXT:
        JSR I2START
        LDA #$C0
        JSR I2WRITE
        BCC CR_SLEEP
        LDA #3
        JSR I2WRITE
        BCC CR_SLEEP
        LDX CR_INDEX
        LDA CR_OFFSETS,X
        TAX
        LDY #7
CR_SEND:
        LDA CR_CMDS,X
        JSR I2WRITE
        BCC CR_SLEEP
        INX
        DEY
        BNE CR_SEND
        JSR I2STOP
        JSR CR_DELAY
        JSR CR_READ
        BCC CR_SLEEP
        LDA CR_COUNT
        CMP #7
        BNE CR_SLEEP
        LDA CR_INDEX
        ASL A
        ASL A
        TAX
        LDY #1
CR_SAVE:
        LDA CR_BUF,Y
        STA CR_DATA,X
        INX
        INY
        CPY #5
        BNE CR_SAVE
        INC CR_INDEX
        LDA CR_INDEX
        CMP #4
        BNE CR_NEXT
        LDA #1
        STA CR_OK
CR_SLEEP:
        JSR I2START
        LDA #$C0
        JSR I2WRITE
        BCC CR_STOP
        LDA #1
        JSR I2WRITE
CR_STOP:
        JSR I2STOP
CR_EXIT:
        JSR I2REST
        RTS
; Response count is bounded before buffering. Validate CRC on every reply.
CR_READ:
        JSR I2START
        LDA #$C1
        JSR I2WRITE
        BCS CR_ADDRESS_OK
        JMP CR_BAD
CR_ADDRESS_OK:
        LDY #0
        JSR I2READ
        STA CR_BUF
        STA CR_COUNT
        CMP #4
        BEQ CR_LENGTH
        CMP #7
        BEQ CR_LENGTH
        JMP CR_BAD
CR_LENGTH:
        LDX #1
CR_RX:
        LDY #0
        TXA
        INC A
        CMP CR_COUNT
        BNE CR_MORE
        INY
CR_MORE:
        JSR I2READ
        STA CR_BUF,X
        INX
        CPX CR_COUNT
        BNE CR_RX
        JSR I2STOP
        LDA BUSERR
        BNE CR_BAD
        STZ CR_CRCLO
        STZ CR_CRCHI
        LDX #0
CR_CRCBYTE:
        LDA CR_BUF,X
        STA CR_BYTE
        LDY #8
CR_CRCBIT:
        LDA CR_BYTE
        AND #1
        STA CR_MIX
        LSR CR_BYTE
        ASL CR_CRCLO
        ROL CR_CRCHI
        BCC CR_NOCARRY
        LDA CR_MIX
        EOR #1
        STA CR_MIX
CR_NOCARRY:
        LDA CR_MIX
        BEQ CR_NOPOLY
        LDA CR_CRCLO
        EOR #5
        STA CR_CRCLO
        LDA CR_CRCHI
        EOR #$80
        STA CR_CRCHI
CR_NOPOLY:
        DEY
        BNE CR_CRCBIT
        INX
        TXA
        CLC
        ADC #2
        CMP CR_COUNT
        BNE CR_CRCBYTE
        LDA CR_CRCLO
        CMP CR_BUF,X
        BNE CR_BAD
        INX
        LDA CR_CRCHI
        CMP CR_BUF,X
        BNE CR_BAD
        SEC
        RTS
CR_BAD:
        JSR I2STOP
        CLC
        RTS
CR_DELAY:
        LDY #255
CR_WAIT1:
        LDX #0
CR_WAIT2:
        DEX
        BNE CR_WAIT2
        DEY
        BNE CR_WAIT1
        RTS
CR_OFFSETS DB 0,7,14,21
CR_CMDS DB $07,$30,$00,$00,$00,$03,$5D
        DB $07,$02,$00,$15,$00,$17,$5D
        DB $07,$24,$00,$00,$00,$0C,$FD
        DB $07,$24,$00,$01,$00,$05,$7D
        XDEF SHOW_SETTINGS
        XDEF TEXT
SHOW_SETTINGS:
        LDX #<LABEL_AUTO
        LDY #>LABEL_AUTO
        JSR TEXT
        LDX #<DISABLED
        LDY #>DISABLED
        LDA EE_CFG+1
        BEQ AUTO_TEXT
        LDX #<ENABLED
        LDY #>ENABLED
AUTO_TEXT:
        JSR TEXT
        LDX #<LABEL_TARGET
        LDY #>LABEL_TARGET
        JSR TEXT
        LDA EE_CFG+2
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        LDA EE_CFG+6
        BEQ FIXED
        LDX #<VECTOR
        LDY #>VECTOR
        JSR TEXT
        BRA DELAY
FIXED:
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA #'$'
        JSR STR8V2_RAM_PUTC
        LDA EE_CFG+4
        JSR STR8V2_RAM_HEX_OUT
        LDA EE_CFG+3
        JSR STR8V2_RAM_HEX_OUT
DELAY:
        LDX #<LABEL_DELAY
        LDY #>LABEL_DELAY
        JSR TEXT
        LDA EE_CFG+5
        LDX #0
DIV10:  CMP #10
        BCC TENTHS
        SBC #10
        INX
        BRA DIV10
TENTHS: PHA
        TXA
        LDX #0
DIV100: CMP #10
        BCC SECONDS
        SBC #10
        INX
        BRA DIV100
SECONDS:
        PHA
        TXA
        BEQ ONES
        ORA #'0'
        JSR STR8V2_RAM_PUTC
ONES:   PLA
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        LDA #'.'
        JSR STR8V2_RAM_PUTC
        PLA
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        LDX #<SEC_TEXT
        LDY #>SEC_TEXT
        JMP TEXT
TEXT:   STX $E0
        STY $E1
        LDY #0
TEXT_LOOP:
        LDA ($E0),Y
        BEQ TEXT_DONE
        CMP #$80
        BCC TEXT_CHAR
        AND #$7F
        TAX
TEXT_SPACES:
        LDA #' '
        JSR STR8V2_RAM_PUTC
        DEX
        BNE TEXT_SPACES
        BRA TEXT_NEXT
TEXT_CHAR:
        JSR STR8V2_RAM_PUTC
TEXT_NEXT:
        INY
        BRA TEXT_LOOP
TEXT_DONE:
        RTS
LABEL_AUTO DB $0D,$0A,"  AUTOSTART",$86,"",0
ENABLED DB "ENABLED",0
DISABLED DB "DISABLED",0
LABEL_TARGET DB $0D,$0A,"  TARGET",$89,"B",0
VECTOR DB " RESET VECTOR",0
LABEL_DELAY DB $0D,$0A,"  DELAY",$8A,"",0
SEC_TEXT DB " SEC",0
        XDEF CR_HEAD
        XDEF SET_HEAD
CR_HEAD DB $0D,$0A,$0D,$0A,"CRYPTO STATUS",0
SET_HEAD DB $0D,$0A,$0D,$0A,"BOOT SETTINGS",0
        XDEF HEADER
HEADER DB $0D,$0A,"SYSTEM CONFIGURATION",0
        INCLUDE "str8n-v2-eeprom.inc"
RTC_END:
        ENDMOD
        END
