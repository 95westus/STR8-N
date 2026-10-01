        MODULE V2_EEPROM_DISPLAY
        XDEF DISPLAY_END
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "eeprom-symbols.inc"
        INCLUDE "extra-symbols.inc"
        CODE
DISPLAY_ENTRY:
        JSR EE_READ
        JSR CR_START
        LDX #<HEADER
        LDY #>HEADER
        JSR TEXT
        LDA RTC_OK
        BEQ UNKNOWN_EDU
        LDX #<EDU_YES
        LDY #>EDU_YES
        BRA EDU_PRINT
UNKNOWN_EDU:
        LDX #<EDU_UNKNOWN
        LDY #>EDU_UNKNOWN
EDU_PRINT:
        JSR TEXT
        LDX #<VIA_TEXT
        LDY #>VIA_TEXT
        JSR TEXT
        LDX #<TABLE_HEAD
        LDY #>TABLE_HEAD
        JSR TEXT
        LDX #<RTC_ROW
        LDY #>RTC_ROW
        JSR TEXT
        LDA RTC_OK
        BEQ RTC_UNAVAILABLE
        LDX #<RUNNING
        LDY #>RUNNING
        JSR TEXT
        LDA RTCBUF+6
        JSR BCD
        LDA #'-'
        JSR STR8V2_RAM_PUTC
        LDA RTCBUF+5
        AND #$1F
        JSR BCD
        LDA #'-'
        JSR STR8V2_RAM_PUTC
        LDA RTCBUF+4
        AND #$3F
        JSR BCD
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA RTCBUF+2
        AND #$40
        BEQ HOUR24
        LDA RTCBUF+2
        AND #$1F
        STA $E2
        LDA RTCBUF+2
        AND #$20
        BNE HOUR_PM
        LDA $E2
        CMP #$12
        BNE HOUR_OUT
        LDA #0
        BRA HOUR_OUT
HOUR_PM:
        LDA $E2
        CMP #$12
        BEQ HOUR_OUT
        SED
        CLC
        ADC #$12
        CLD
        BRA HOUR_OUT
HOUR24:
        LDA RTCBUF+2
        AND #$3F
HOUR_OUT:
        JSR BCD
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA RTCBUF+1
        AND #$7F
        JSR BCD
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA RTCBUF
        AND #$7F
        JSR BCD
        BRA RTC_DONE
RTC_UNAVAILABLE:
        LDX #<UNAVAILABLE
        LDY #>UNAVAILABLE
        JSR TEXT
RTC_DONE:
        LDX #<SRAM_ROW
        LDY #>SRAM_ROW
        JSR TEXT
        LDX #<EEPROM_ROW
        LDY #>EEPROM_ROW
        JSR TEXT
        LDA EE_STATE
        ASL A
        TAX
        LDA STATES,X
        LDY STATES+1,X
        TAX
        JSR TEXT
        LDX #<CRYPTO_ROW
        LDY #>CRYPTO_ROW
        JSR TEXT
        LDA CR_OK
        BEQ CRYPTO_UNAVAILABLE
        LDX #<RESPONDING
        LDY #>RESPONDING
        JSR TEXT
        BRA SPI_ROW
CRYPTO_UNAVAILABLE:
        LDX #<UNAVAILABLE
        LDY #>UNAVAILABLE
        JSR TEXT
SPI_ROW:
        LDX #<SPI_TEXT
        LDY #>SPI_TEXT
        JSR TEXT
        LDX #<CR_HEAD
        LDY #>CR_HEAD
        JSR TEXT
        LDA CR_OK
        BNE CR_STATUS_READY
        JMP CR_STATUS_UNKNOWN
CR_STATUS_READY:
        LDX #<REVISION
        LDY #>REVISION
        JSR TEXT
        LDX #0
REV_LOOP:
        LDA CR_DATA,X
        JSR STR8V2_RAM_HEX_OUT
        INX
        CPX #4
        BNE REV_LOOP
        LDX #<CONFIG_LOCK
        LDY #>CONFIG_LOCK
        JSR TEXT
        LDA CR_DATA+7
        JSR LOCK_TEXT
        LDX #<DATA_LOCK
        LDY #>DATA_LOCK
        JSR TEXT
        LDA CR_DATA+6
        JSR LOCK_TEXT
        LDX #<COUNTERS
        LDY #>COUNTERS
        JSR TEXT
        LDX #11
COUNT0:
        LDA CR_DATA,X
        JSR STR8V2_RAM_HEX_OUT
        DEX
        CPX #7
        BNE COUNT0
        LDX #<SLASH
        LDY #>SLASH
        JSR TEXT
        LDX #12
        JSR COUNTER_PRINT
        BRA SETTINGS
COUNTER_PRINT:
        TXA
        CLC
        ADC #3
        TAX
        LDY #4
COUNT_HEX:
        LDA CR_DATA,X
        JSR STR8V2_RAM_HEX_OUT
        DEX
        DEY
        BNE COUNT_HEX
        RTS
CR_STATUS_UNKNOWN:
        JSR STR8V2_RAM_NEWLINE
        LDX #<UNAVAILABLE
        LDY #>UNAVAILABLE
        JSR TEXT
SETTINGS:
        LDX #<SET_HEAD
        LDY #>SET_HEAD
        JSR TEXT
        LDA EE_STATE
        CMP #3
        BCC SET_NO
        JMP SHOW_SETTINGS
SET_NO:
        LDX #<SET_UNREADABLE
        LDY #>SET_UNREADABLE
        JMP TEXT
LOCK_TEXT:
        CMP #$55
        BNE LOCKED_CHECK
        LDX #<UNLOCKED
        LDY #>UNLOCKED
        JMP TEXT
LOCKED_CHECK:
        CMP #0
        BNE LOCK_UNKNOWN
        LDX #<LOCKED
        LDY #>LOCKED
        JMP TEXT
LOCK_UNKNOWN:
        JMP STR8V2_RAM_HEX_OUT
STATES: DW UNAVAILABLE,EMPTY,INVALID,VALID_TEXT,VALID_TEXT
EDU_YES DB $0D,$0A,"  EDU KIT",$89,"DETECTED",0
EDU_UNKNOWN DB $0D,$0A,"  EDU KIT",$89,"UNKNOWN",0
RTC_ROW DB $0D,$0A,"MCP79XXX RTC",$84,"I2C",$83,"$6F  ",0
RUNNING DB "RUNNING ",0
SRAM_ROW DB $0D,$0A,"MCP79XXX SRAM",$83,"I2C",$83,"$6F  64 BYTES",0
EEPROM_ROW DB $0D,$0A,"MCP79XXX EEPROM I2C",$83,"$57  ",0
UNAVAILABLE DB "UNAVAILABLE",0

EMPTY DB "EMPTY",0
INVALID DB "INVALID",0
VALID_TEXT DB "VALID",0
CRYPTO_ROW DB $0D,$0A,"ATECC608",$88,"I2C",$83,"$60  ",0
SPI_TEXT DB $0D,$0A,"23LCV1024 SRAM  SPI",$84,"--  128 KB LIST",0
REVISION DB $0D,$0A,"  REVISION",$87,"",0
CONFIG_LOCK DB $0D,$0A,"  CONFIG LOCK",$84,"",0
DATA_LOCK DB $0D,$0A,"  DATA/OTP LOCK  ",0
UNLOCKED DB "UNLOCKED",0
LOCKED DB "LOCKED",0
COUNTERS DB $0D,$0A,"  COUNTERS",$87,"",0
SLASH DB " / ",0
SET_UNREADABLE DB $0D,$0A,"  SETTINGS",$87,"UNKNOWN",0
DISPLAY_END:
        ENDMOD
        END
