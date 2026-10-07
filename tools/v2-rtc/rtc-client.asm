; Separate RAM client. No write operations are issued by the default entry.
; Service must be loaded at $3000 first. Client $2000 does not overlap it.
; SET at $2003 and ACK at $2006 are explicit entries after request/key staging.
        MODULE RTC_CLIENT
        XDEF START
        XDEF CLIENT_END
        INCLUDE "rtc-api.inc"
PTR EQU $D0
        CODE
START   JMP READ_CLOCK
        JMP SET_CLOCK
        JMP ACK_POWER
        JMP BANK_CALLS
READ_CLOCK
        JSR CHECK
        BCC HOLD
        JSR BEFORE_IO
        JSR RTC_READ
        BRA REPORT
SET_CLOCK JSR CHECK
        BCC HOLD
        JSR BEFORE_IO
        JSR RTC_SET
        BRA REPORT
ACK_POWER JSR CHECK
        BCC HOLD
        JSR BEFORE_IO
        JSR RTC_ACK_POWER
REPORT  PHA
        JSR AFTER_IO
        LDX #<RESULT_TEXT
        LDY #>RESULT_TEXT
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
        LDX #<END_TEXT
        LDY #>END_TEXT
        JSR PUTS
HOLD    JMP $7E67
BANK_CALLS
        JSR CHECK
        BCC HOLD
        STZ BANK_INDEX
BANK_NEXT LDX BANK_INDEX
        LDA $7FEC
        AND #$11
        ORA BANK_BITS,X
        STA $7FEC
        JSR RTC_READ
        LDX BANK_INDEX
        STA $3F3C,X
        LDA $7FEC
        AND #$EE
        CMP BANK_BITS,X
        BNE BANK_FAIL
        INC BANK_INDEX
        LDA BANK_INDEX
        CMP #4
        BNE BANK_NEXT
        LDX #<BANK_PASS_TEXT
        LDY #>BANK_PASS_TEXT
        JSR PUTS
        BRA HOLD
BANK_FAIL LDX #<BANK_FAIL_TEXT
        LDY #>BANK_FAIL_TEXT
        JSR PUTS
        BRA HOLD
BEFORE_IO LDA $7FC3
        STA $3F38
        LDA $7FCF
        STA $3F39
        RTS
AFTER_IO LDA $7FC3
        STA $3F3A
        LDA $7FCF
        STA $3F3B
        RTS
CHECK   LDX #3
CHECK_LOOP LDA $7E60,X
        CMP RAM_MAGIC,X
        BNE NO_ABI
        DEX
        BPL CHECK_LOOP
        LDX #3
SERVICE_CHECK LDA RTC_SIGNATURE,X
        CMP RTC_MAGIC,X
        BNE NO_SERVICE
        DEX
        BPL SERVICE_CHECK
        SEC
        RTS
NO_ABI  ; Caller must launch under a qualified STR8-N RAM ABI.
        CLC
        RTS
NO_SERVICE LDX #<MISSING_TEXT
        LDY #>MISSING_TEXT
        JSR PUTS
        CLC
        RTS
PUTS    STX PTR
        STY PTR+1
        LDY #0
PUT_NEXT LDA (PTR),Y
        BEQ PUT_DONE
        JSR $7E6D
        INY
        BRA PUT_NEXT
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
RAM_MAGIC DB "RA",1,13
RTC_MAGIC DB "RC",1,4
RESULT_TEXT DB "RTC status=",0
FLAGS_TEXT DB " flags=",0
RAW_TEXT DB " raw=",0
END_TEXT DB $0D,$0A,0
MISSING_TEXT DB "RTC service unavailable",$0D,$0A,0
BANK_INDEX DB 0
BANK_BITS DB $CC,$CE,$EC,$EE
BANK_PASS_TEXT DB "RTC calls B0-B3: bank preserved",$0D,$0A,0
BANK_FAIL_TEXT DB "RTC calls: BANK FAIL",$0D,$0A,0
CLIENT_END
        ENDMOD
        END
