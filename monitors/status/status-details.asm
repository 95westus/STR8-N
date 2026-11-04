; Shared, read-only BN/TZ/BA records and local-calendar/policy presentation.
        MODULE STATUS_DETAILS
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "status-interface.inc"
        INCLUDE "status-text.inc"
        CODE
        JMP SM_SCAN
        JMP SD_DISPLAY
        JMP SB_DISPLAY
        JMP MS_SRAM_READ
SM_SCAN:
        LDX #31
SM_ZERO:
        STZ ST_RECORD+32,X
        DEX
        BPL SM_ZERO
        STZ ST_ADDR
        LDA #$9C
        STA ST_ADDR+1
SM_SLOT:
        JSR ST_READ32
        JSR SM_VALIDATE
        BCC SM_NEXT
        LDA #<ST_SEQUENCES
        CLC
        ADC SI_KIND
        STA ST_SEQ_PTR
        LDA #>ST_SEQUENCES
        STA ST_SEQ_PTR+1
        LDY #3
SM_NEWER:
        LDA ST_RECORD+4,Y
        CMP (ST_SEQ_PTR),Y
        BCC SM_NEXT
        BNE SM_KEEP
        DEY
        BPL SM_NEWER
SM_KEEP:
        LDY #3
SM_SEQUENCE:
        LDA ST_RECORD+4,Y
        STA (ST_SEQ_PTR),Y
        DEY
        BPL SM_SEQUENCE
        LDA SI_KIND
        BNE SM_NOT_NAME
        LDA ST_RECORD+8
        STA ST_BN_LEN
        LDX #7
SM_NAME_COPY:
        LDA ST_RECORD+9,X
        STA ST_BN_TEXT,X
        DEX
        BPL SM_NAME_COPY
        BRA SM_NEXT
SM_NOT_NAME:
        CMP #4
        BNE SM_BATTERY
        LDA ST_RECORD+8
        STA ST_OFFSET
        LDA ST_RECORD+9
        STA ST_OFFSET+1
        INC ST_TZ_FOUND
        BRA SM_NEXT
SM_BATTERY:
        LDX #3
SM_BAT_COPY:
        LDA ST_RECORD+8,X
        STA ST_INSTALL,X
        DEX
        BPL SM_BAT_COPY
        LDA ST_RECORD+13
        STA ST_HIGHWATER
        LDA ST_RECORD+14
        STA ST_HIGHWATER+1
        LDA ST_RECORD+12
        STA ST_STAGE
        INC ST_BAT_FOUND
SM_NEXT:
        LDA ST_ADDR
        CLC
        ADC #32
        STA ST_ADDR
        BCC SM_PAGE
        INC ST_ADDR+1
SM_PAGE:
        LDA ST_ADDR+1
        CMP #$A0
        BCC SM_SLOT
        RTS
SM_VALIDATE:
        LDA ST_RECORD+31
        ORA ST_RECORD+3
        BNE SM_BAD
        LDA ST_RECORD+2
        CMP #1
        BNE SM_BAD
        LDA ST_RECORD+30
        CMP #$FF
        BNE SM_BAD
        JSR ST_CRC_INIT
        LDY #0
SM_CRC:
        LDA ST_RECORD,Y
        JSR ST_CRC_BYTE
        INY
        CPY #28
        BCC SM_CRC
        LDA SI_CRC
        CMP ST_RECORD+28
        BNE SM_BAD
        LDA SI_CRC+1
        CMP ST_RECORD+29
        BNE SM_BAD
        LDA ST_RECORD
        CMP #'T'
        BNE SM_B_KIND
        LDA ST_RECORD+1
        CMP #'Z'
        BNE SM_BAD
        LDA #4
        STA SI_KIND
        LDX #10
        JSR SM_RESERVED
        BCC SM_BAD
        LDA ST_RECORD+8
        STA ST_WORD
        LDA ST_RECORD+9
        STA ST_WORD+1
        BPL SM_POS_OFFSET
        JSR ST_ABSOLUTE
        LDX #2
        LDY #$D1
        BRA SM_OFFSET_LIMIT
SM_POS_OFFSET:
        LDX #3
        LDY #$49
SM_OFFSET_LIMIT:
        STX SI_TEMP
        LDA ST_WORD+1
        CMP SI_TEMP
        BCC SM_OFFSET_OK
        BNE SM_BAD
        STY SI_TEMP
        LDA ST_WORD
        CMP SI_TEMP
        BCS SM_BAD
SM_OFFSET_OK:
        SEC
        RTS
SM_BAD:
        CLC
        RTS
SM_B_KIND:
        CMP #'B'
        BNE SM_BAD
        LDA ST_RECORD+1
        CMP #'N'
        BNE SM_BA
        STZ SI_KIND
        LDA ST_RECORD+8
        CMP #9
        BCS SM_BAD
        TAX
        LDY #9
SM_NAME:
        LDA ST_RECORD,Y
        CPX #0
        BEQ SM_NAME_ZERO
        CMP #$21
        BCC SM_BAD
        CMP #$7F
        BCS SM_BAD
        DEX
        BRA SM_NAME_NEXT
SM_NAME_ZERO:
        CMP #0
        BNE SM_BAD
SM_NAME_NEXT:
        INY
        CPY #17
        BCC SM_NAME
        LDX #17
        JMP SM_RESERVED
SM_BA:
        CMP #'A'
        BNE SM_BAD
        LDA #8
        STA SI_KIND
        LDX #15
        JSR SM_RESERVED
        BCC SM_BAD
        LDA ST_RECORD+10
        BEQ SM_BAD
        CMP ST_RECORD+11
        BCS SM_BAD
        LDA ST_RECORD+11
        CMP #100
        BCS SM_BAD
        LDA ST_RECORD+12
        CMP #4
        BCS SM_BAD
        LDA ST_RECORD+14
        CMP #$8E
        BCC SM_BA_DATE
        BNE SM_BAD
        LDA ST_RECORD+13
        CMP #$AD
        BCS SM_BAD
SM_BA_DATE:
        LDA ST_RECORD+14
        CMP ST_RECORD+9
        BNE SM_BA_ORDER
        LDA ST_RECORD+13
        CMP ST_RECORD+8
SM_BA_ORDER:
        BCC SM_BAD
SM_OK:
        SEC
        RTS
SM_RESERVED:
        LDA ST_RECORD,X
        CMP #$FF
        BNE SM_BAD
        INX
        CPX #28
        BCC SM_RESERVED
        SEC
        RTS
SD_DISPLAY:
        SAY ST_RTCC
        LDA ST_RTC_VALID
        BNE SD_VALID
        SAY ST_NONE
        RTS
SD_VALID:
        CLC
        LDA ST_RTC_TIME+6
        ADC #$D0
        STA ST_DATE
        LDA #7
        ADC #0
        STA ST_DATE+1
        ; Map the reverse RTC order to year,month,date,weekday,hour,min,sec.
        LDX #5
        LDY #2
SD_DATE_COPY:
        LDA ST_RTC_TIME,X
        STA ST_DATE,Y
        INY
        DEX
        BPL SD_DATE_COPY
        STZ ST_WORD+1
        LDA ST_DATE+6
        STA ST_WORD
        LDX ST_DATE+5
SD_MINUTES:
        CPX #0
        BEQ SD_ADD_OFFSET
        CLC
        LDA ST_WORD
        ADC #60
        STA ST_WORD
        BCC SD_HOUR_ADDED
        INC ST_WORD+1
SD_HOUR_ADDED:
        DEX
        BRA SD_MINUTES
SD_ADD_OFFSET:
        CLC
        LDA ST_WORD
        ADC ST_OFFSET
        STA ST_WORD
        LDA ST_WORD+1
        ADC ST_OFFSET+1
        STA ST_WORD+1
        BPL SD_FORWARD
        CLC
        LDA ST_WORD
        ADC #$A0
        STA ST_WORD
        LDA ST_WORD+1
        ADC #5
        STA ST_WORD+1
        JSR SD_PREVIOUS_DAY
SD_FORWARD:
        LDA ST_WORD+1
        CMP #5
        BCC SD_CLOCK
        BNE SD_DAY_FORWARD
        LDA ST_WORD
        CMP #$A0
        BCC SD_CLOCK
SD_DAY_FORWARD:
        SEC
        LDA ST_WORD
        SBC #$A0
        STA ST_WORD
        LDA ST_WORD+1
        SBC #5
        STA ST_WORD+1
        JSR SD_NEXT_DAY
SD_CLOCK:
        JSR ST_HOURS
        LDA ST_TEMP
        STA ST_DATE+5
        LDA ST_WORD
        STA ST_DATE+6
        LDA ST_DATE+4
        DEC A
        ASL A
        ASL A
        TAY
SD_WEEKDAY:
        LDA ST_WEEKDAYS,Y
        CMP #' '
        BEQ SD_WEEKDAY_END
        JSR STR8V2_RAM_PUTC
        INY
        BRA SD_WEEKDAY
SD_WEEKDAY_END:
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA ST_DATE
        STA ST_NUM
        LDA ST_DATE+1
        STA ST_NUM+1
        STZ ST_NUM+2
        JSR ST_DECIMAL
        LDA #'-'
        JSR STR8V2_RAM_PUTC
        LDA ST_DATE+2
        JSR ST_TWO
        LDA #'-'
        JSR STR8V2_RAM_PUTC
        LDA ST_DATE+3
        JSR ST_TWO
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA ST_DATE+5
        JSR ST_TWO
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA ST_DATE+6
        JSR ST_TWO
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA ST_DATE+7
        JSR ST_TWO
        LDA ST_TZ_FOUND
        BNE SD_OFFSET
        SAY ST_UTC
        JMP STR8V2_RAM_NEWLINE
SD_OFFSET:
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA #'('
        JSR STR8V2_RAM_PUTC
        LDA ST_OFFSET
        STA ST_WORD
        LDA ST_OFFSET+1
        STA ST_WORD+1
        LDA #'+'
        BIT ST_WORD+1
        BPL SD_SIGN
        LDA #'-'
SD_SIGN:
        JSR STR8V2_RAM_PUTC
        JSR ST_ABSOLUTE
        JSR ST_HOURS
        LDA ST_TEMP
        JSR ST_TWO
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA ST_WORD
        JSR ST_TWO
        LDA #')'
        JSR STR8V2_RAM_PUTC
        JMP STR8V2_RAM_NEWLINE
SD_MONTH_DAYS:
        LDA ST_DAYS-1,X
        CPX #2
        BNE SD_MONTH_DONE
        PHA
        LDA ST_DATE
        AND #3
        BNE SD_NOT_LEAP
        PLA
        INC A
        RTS
SD_NOT_LEAP:
        PLA
SD_MONTH_DONE:
        RTS
SD_PREVIOUS_DAY:
        DEC ST_DATE+4
        BNE SD_PREV_WEEK_OK
        LDA #7
        STA ST_DATE+4
SD_PREV_WEEK_OK:
        DEC ST_DATE+3
        BNE SD_DATE_DONE
        DEC ST_DATE+2
        BNE SD_PREV_MONTH_OK
        LDA #12
        STA ST_DATE+2
        LDA ST_DATE
        BNE SD_PREV_YEAR_LOW
        DEC ST_DATE+1
SD_PREV_YEAR_LOW:
        DEC ST_DATE
SD_PREV_MONTH_OK:
        LDX ST_DATE+2
        JSR SD_MONTH_DAYS
        STA ST_DATE+3
SD_DATE_DONE:
        RTS
SD_NEXT_DAY:
        INC ST_DATE+4
        LDA ST_DATE+4
        CMP #8
        BCC SD_NEXT_WEEK_OK
        LDA #1
        STA ST_DATE+4
SD_NEXT_WEEK_OK:
        LDX ST_DATE+2
        JSR SD_MONTH_DAYS
        INC ST_DATE+3
        CMP ST_DATE+3
        BCS SD_DATE_DONE
        LDA #1
        STA ST_DATE+3
        INC ST_DATE+2
        LDA ST_DATE+2
        CMP #13
        BCC SD_DATE_DONE
        LDA #1
        STA ST_DATE+2
        INC ST_DATE
        BNE SD_DATE_DONE
        INC ST_DATE+1
        RTS
SB_DISPLAY:
        SAY ST_BATTERY
        LDA ST_BAT_FOUND
        BEQ SB_NONE
        LDA ST_RTC_VALID
        BEQ SB_NONE
        LDA ST_STAGE
        CMP #3
        BEQ SB_UNCERTAIN
        JSR SB_DAY_NUMBER
        LDA ST_NUM+1
        CMP ST_HIGHWATER+1
        BNE SB_HIGH_TEST
        LDA ST_NUM
        CMP ST_HIGHWATER
SB_HIGH_TEST:
        BCC SB_UNCERTAIN
        SEC
        LDA ST_NUM
        SBC ST_INSTALL
        STA ST_NUM
        LDA ST_NUM+1
        SBC ST_INSTALL+1
        STA ST_NUM+1
        BCC SB_UNCERTAIN
        LDA ST_REPLACE
        JSR SB_LIMIT
        BCS SB_REPLACEMENT
        LDA ST_WARN
        JSR SB_LIMIT
        BCS SB_WARNING
        SAY ST_WITHIN
        BRA SB_LINE
SB_REPLACEMENT:
        SAY ST_REPLACE_TEXT
        BRA SB_LINE
SB_WARNING:
        SAY ST_WARN_TEXT
        BRA SB_LINE
SB_UNCERTAIN:
        SAY ST_UNCERTAIN
        BRA SB_LINE
SB_NONE:
        SAY ST_UNKNOWN
SB_LINE:
        JMP STR8V2_RAM_NEWLINE
SB_LIMIT:
        TAX
        STZ ST_WORD
        STZ ST_WORD+1
SB_MULTIPLY:
        CLC
        LDA ST_WORD
        ADC #30
        STA ST_WORD
        BCC SB_MULTIPLY_NEXT
        INC ST_WORD+1
SB_MULTIPLY_NEXT:
        DEX
        BNE SB_MULTIPLY
        LDA ST_NUM+1
        CMP ST_WORD+1
        BNE SB_LIMIT_DONE
        LDA ST_NUM
        CMP ST_WORD
SB_LIMIT_DONE:
        RTS
SB_DAY_NUMBER:
        LDA ST_RTC_TIME+6
        STA ST_DATE
        STZ ST_NUM
        STZ ST_NUM+1
        STZ SI_YEAR
SB_YEAR:
        LDA SI_YEAR
        CMP ST_RTC_TIME+6
        BEQ SB_MONTHS
        CLC
        LDA ST_NUM
        ADC #$6D
        STA ST_NUM
        LDA ST_NUM+1
        ADC #1
        STA ST_NUM+1
        LDA SI_YEAR
        AND #3
        BNE SB_YEAR_NEXT
        INC ST_NUM
        BNE SB_YEAR_NEXT
        INC ST_NUM+1
SB_YEAR_NEXT:
        INC SI_YEAR
        BRA SB_YEAR
SB_MONTHS:
        LDX #1
SB_MONTH:
        CPX ST_RTC_TIME+5
        BEQ SB_ADD_DATE
        JSR SD_MONTH_DAYS
SB_MONTH_ADD:
        CLC
        ADC ST_NUM
        STA ST_NUM
        BCC SB_MONTH_NEXT
        INC ST_NUM+1
SB_MONTH_NEXT:
        INX
        BRA SB_MONTH
SB_ADD_DATE:
        LDA ST_RTC_TIME+4
        DEC A
        CLC
        ADC ST_NUM
        STA ST_NUM
        BCC SB_DAY_DONE
        INC ST_NUM+1
SB_DAY_DONE:
        RTS
        INCLUDE "status-mon-sram.inc"
SD_END:
        ENDMOD
        END
