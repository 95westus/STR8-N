; Integrated-kernel fixture, not an installer. Caller RAM $2000-$23FF.
; G 2000 READ, 2003 STATUS, 2006 SET, 2009 ACK, 200C bank calls, 200F I2C.
; SET/ACK require explicit input staging; no default clock data writes.
        MODULE KERNEL_CLIENT
        XDEF START
        XDEF CLIENT_END
        INCLUDE "i2c-api.inc"
PTR EQU $D0
RTC_FLAGS EQU $66C1
RTC_RAW EQU $66CB
        CODE
START   JMP READ_CLOCK
        JMP STATUS_CLOCK
        JMP SET_CLOCK
        JMP ACK_CLOCK
        JMP BANK_CALLS
        JMP BUS_READ
READ_CLOCK LDA #1
        JSR CHECK
        BCC HOLD
        JSR $6504
        BRA REPORT
STATUS_CLOCK LDA #1
        JSR CHECK
        BCC HOLD
        JSR $6507
        BRA REPORT
SET_CLOCK LDA #1
        JSR CHECK
        BCC HOLD
        JSR $650A
        BRA REPORT
ACK_CLOCK LDA #1
        JSR CHECK
        BCC HOLD
        JSR $650D
REPORT  PHA
        LDX #<STATUS_TEXT
        LDY #>STATUS_TEXT
        JSR PUTS
        PLA
        JSR HEX
        LDX #<FLAGS_TEXT
        LDY #>FLAGS_TEXT
        JSR PUTS
        LDA RTC_FLAGS
        JSR HEX
        LDX #<RAW_TEXT
        LDY #>RAW_TEXT
        JSR PUTS
        LDX #0
RAW_LOOP LDA RTC_RAW,X
        JSR HEX
        LDA #' '
        JSR $7E6D
        INX
        CPX #9
        BNE RAW_LOOP
        JSR CRLF
HOLD    JMP $7E67
BUS_READ LDA #2
        JSR CHECK
        BCC HOLD
        STZ $2400
        LDX #7
BUS_REQUEST LDA BUS_DATA,X
        STA I2C_REQUEST,X
        DEX
        BPL BUS_REQUEST
        JSR I2C_TRANSFER
        PHA
        LDX #<BUS_TEXT
        LDY #>BUS_TEXT
        JSR PUTS
        PLA
        JSR HEX
        LDA #' '
        JSR $7E6D
        LDA I2C_WRITTEN
        JSR HEX
        LDA #'/'
        JSR $7E6D
        LDA I2C_READ
        JSR HEX
        JSR CRLF
        JMP HOLD
BANK_CALLS LDA #1
        JSR CHECK
        BCC HOLD
        STZ BANK_INDEX
BANK_NEXT LDX BANK_INDEX
        LDA $7FEC
        AND #$11
        ORA BANK_BITS,X
        STA $7FEC
        JSR $6504
        LDX BANK_INDEX
        STA $2450,X
        LDA $7FEC
        AND #$EE
        CMP BANK_BITS,X
        BNE BANK_FAIL
        INC BANK_INDEX
        LDA BANK_INDEX
        CMP #4
        BNE BANK_NEXT
        LDX #<BANK_TEXT
        LDY #>BANK_TEXT
        JSR PUTS
        JMP HOLD
BANK_FAIL LDX #<BANK_BAD
        LDY #>BANK_BAD
        JSR PUTS
        JMP HOLD
CHECK   STA REQUIRED
        LDX #3
RA_LOOP LDA $7E60,X
        CMP RA_MAGIC,X
        BNE MISSING
        DEX
        BPL RA_LOOP
        LDX #2
SV_LOOP LDA $7D04,X
        CMP SV_MAGIC,X
        BNE MISSING
        DEX
        BPL SV_LOOP
        LDA $7D07
        AND REQUIRED
        BEQ MISSING
        LDA $7D08
        BNE MISSING
        LDA $7D09
        CMP #$65
        BNE MISSING
        SEC
        RTS
MISSING LDX #<MISSING_TEXT
        LDY #>MISSING_TEXT
        JSR PUTS
        CLC
        RTS
PUTS    STX PTR
        STY PTR+1
        LDY #0
PUT_LOOP LDA (PTR),Y
        BEQ PUT_DONE
        JSR $7E6D
        INY
        BRA PUT_LOOP
PUT_DONE RTS
HEX     PHA
        LSR A
        LSR A
        LSR A
        LSR A
        JSR NIBBLE
        PLA
        AND #$0F
NIBBLE  CMP #10
        BCC DIGIT
        ADC #6
DIGIT   ADC #'0'
        JMP $7E6D
CRLF    LDA #13
        JSR $7E6D
        LDA #10
        JMP $7E6D
REQUIRED DB 0
BANK_INDEX DB 0
BANK_BITS DB $CC,$CE,$EC,$EE
RA_MAGIC DB "RA",1,13
SV_MAGIC DB "SV",1
BUS_DATA DB $6F,1,0,$24,1,$20,$24,9
STATUS_TEXT DB "RTC status=",0
FLAGS_TEXT DB " flags=",0
RAW_TEXT DB " raw=",0
BUS_TEXT DB "I2C status/counts=",0
BANK_TEXT DB "RTC banks preserved",13,10,0
BANK_BAD DB "RTC BANK ERROR",13,10,0
MISSING_TEXT DB "Services unavailable",13,10,0
CLIENT_END
        ENDMOD
        END
