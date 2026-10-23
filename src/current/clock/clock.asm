; CLOCK 1.6. EUI binding in existing sector; explicit confirmed administration.
; Read/status never change clock settings. SET needs valid input and exact YES.
        MODULE CLOCK
        XDEF START
        XDEF APP_END
        INCLUDE "kernel-rtc-api.inc"
        INCLUDE "journal-eq.inc"
TEXT EQU $D0
PUTC EQU $7E6D
GETC EQU $7E70
HEX EQU $7E7C
NL EQU $7E7F
OF_PTR EQU $D2
H_PTR EQU $D4
        CODE
START: DB $80,4,"BT",1,1
B29_CLOCK_START:
        SEI
        CLD
        LDX #$FF
        TXS
        LDX #3
CHECK_CONSOLE:
        LDA $7E60,X
        CMP RA_MAGIC,X
                        BNE UNSUPPORTED
        DEX
                        BPL CHECK_CONSOLE
        LDX #<TITLE
        LDY #>TITLE
        JSR PRINT
        JSR CHECK_SERVICE
                        BCS CLOCK_LONG_31
                        JMP NO_SERVICE
CLOCK_LONG_31:
        JMP UI_SUMMARY
UNSUPPORTED:
        BRA UNSUPPORTED       ; No calls through an unverified console ABI.
MENU:
        LDX #$FF
        TXS
        JSR S_MENU_PROMPT
        NOP
        NOP
        NOP
        NOP
        JSR B29_CLOCK_LINE
                        BCS CLOCK_LONG_42
                        JMP CANCELED
CLOCK_LONG_42:
        LDA LINE_LENGTH
                        BEQ MENU
        LDX #<CMD_Q
        LDY #>CMD_Q
        JSR MATCH
                        BCC CLOCK_LONG_48
                        JMP QUIT
CLOCK_LONG_48:
        LDX #<CMD_QUIT
        LDY #>CMD_QUIT
        JSR MATCH
                        BCC CLOCK_LONG_52
                        JMP QUIT
CLOCK_LONG_52:
        LDX #<CMD_HELP
        LDY #>CMD_HELP
        JSR MATCH
                        BCC CLOCK_LONG_56
                        JMP HELP
CLOCK_LONG_56:
        LDX #<CMD_QUESTION
        LDY #>CMD_QUESTION
        JSR MATCH
                        BCC CLOCK_LONG_60
                        JMP HELP
CLOCK_LONG_60:
        LDX #<CMD_EUI
        LDY #>CMD_EUI
        JSR MATCH
                        BCC CLOCK_LONG_64
                        JMP EUI_COMMAND
CLOCK_LONG_64:
        JSR BT_TRY
        JSR S_TRY
        LDX #<CMD_TRIM
        LDY #>CMD_TRIM
        JSR MATCH
                        BCC CLOCK_LONG_70
                        JMP TRIM_COMMAND
CLOCK_LONG_70:
        JSR TRIM_PARSE
                        BCC CLOCK_LONG_72
                        JMP TRIM_CHANGE
CLOCK_LONG_72:
        LDX #<CMD_ACCEPT_EUI
        LDY #>CMD_ACCEPT_EUI
        JSR MATCH
                        BCC CLOCK_LONG_76
                        JMP EUI_ACCEPT_COMMAND
CLOCK_LONG_76:
        LDX #<CMD_HISTORY
        LDY #>CMD_HISTORY
        JSR MATCH
                        BCC CLOCK_LONG_80
                        JMP HISTORY
CLOCK_LONG_80:
        LDX #<CMD_CLEAR_ALL
        LDY #>CMD_CLEAR_ALL
        JSR MATCH
                        BCC CLOCK_LONG_84
                        JMP HISTORY_CLEAR_ALL
CLOCK_LONG_84:
        JSR HISTORY_PARSE
                        BCC CLOCK_LONG_86
                        JMP HISTORY_DISPATCH
CLOCK_LONG_86:
        JSR CHECK_SERVICE
                        BCC NO_SERVICE
        LDX #<CMD_R
        LDY #>CMD_R
        JSR MATCH
                        BCS READ_COMMAND
        LDX #<CMD_TIME
        LDY #>CMD_TIME
        JSR MATCH
                        BCS READ_COMMAND
        LDX #<CMD_S
        LDY #>CMD_S
        JSR MATCH
                        BCS STATUS_COMMAND
        LDX #<CMD_STATUS
        LDY #>CMD_STATUS
        JSR MATCH
                        BCS STATUS_COMMAND
        LDX #<CMD_ACK
        LDY #>CMD_ACK
        JSR MATCH
                        BCS ACK_COMMAND
        JSR PARSE_SET
                        BCC CLOCK_LONG_110
                        JMP SET_COMMAND
CLOCK_LONG_110:
BAD_COMMAND: JSR B29_CLOCK_ERROR

        LDX #<BAD_TEXT
        LDY #>BAD_TEXT
        JMP MESSAGE
NO_SERVICE: JSR B29_CLOCK_ERROR

        LDX #<NO_SERVICE_TEXT
        LDY #>NO_SERVICE_TEXT
        JMP MESSAGE
CANCELED: JSR B29_CLOCK_ERROR

        LDX #<CANCELED_TEXT
        LDY #>CANCELED_TEXT
        JMP MESSAGE
HELP:
        LDX #<HELP_TEXT
        LDY #>HELP_TEXT
MESSAGE:
        JSR PRINT
        JMP MENU
QUIT:
        JMP $7E67
READ_COMMAND:
        JSR READ_CLOCK
        JMP MENU
READ_CLOCK:
        JSR RTC_READ
                        BCC UI_READ_ERROR
        JSR COPY_TIME
        JSR TZ_SHOW_LOCAL
        JSR NL
        LDX #<UTC_TEXT
        LDY #>UTC_TEXT
        JSR PRINT
        JSR UI_WEEKDAY
        JSR FORMAT_TIME
        JMP NL
UI_READ_ERROR: JSR B29_CLOCK_ERROR

        JMP ERROR
STATUS_COMMAND:
        JSR RTC_STATUS
                        BCC STATUS_ERROR
        JSR SHOW_STATUS
        JSR TRIM_SHOW
        JSR EUI_SHOW
        JMP MENU
STATUS_ERROR:
        JSR ERROR
        JSR EUI_SHOW
        JMP MENU
ACK_COMMAND:
        JSR RTC_STATUS
                        BCC STATUS_ERROR
        JSR SHOW_STATUS
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
                        BEQ NO_EVENT
        LDX #<ACK_CONFIRM_TEXT
        LDY #>ACK_CONFIRM_TEXT
        JSR PRINT
        JSR READLINE
                        BCC CANCELED
        LDX #<CMD_YES
        LDY #>CMD_YES
        JSR MATCH
                        BCC CANCELED
        LDX #J_SAVE_ACK_OP
        JSR HISTORY_CALL
                        BCC ACK_FAILED
        JSR RTC_STATUS
                        BCC ACK_FAILED
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
                        BNE ACK_VERIFY_FAILED
        LDX #<ACK_DONE_TEXT
        LDY #>ACK_DONE_TEXT
        JSR PRINT
        JSR SHOW_STATUS
        JMP MENU
NO_EVENT:
        LDX #<NO_EVENT_TEXT
        LDY #>NO_EVENT_TEXT
        JMP MESSAGE
ACK_FAILED: JSR B29_CLOCK_ERROR

        JSR ERROR
ACK_VERIFY_FAILED: JSR B29_CLOCK_ERROR

        LDX #<ACK_FAILED_TEXT
        LDY #>ACK_FAILED_TEXT
        JMP MESSAGE
SET_COMMAND:
        ; Validate before setting intent keys, or asking for confirmation.
        JSR RTC_STATUS
                        BCC STATUS_ERROR
        JSR SHOW_STATUS
        LDA RTC_RAW+7
        AND #$30
                        BEQ CLOCK_LONG_205
                        JMP ALARMS_ENABLED
CLOCK_LONG_205:
        LDX #7
SET_DISPLAY:
        LDA REQUEST,X
        STA DISPLAY,X
        DEX
                        BPL SET_DISPLAY
        LDX #<NEW_TIME_TEXT
        LDY #>NEW_TIME_TEXT
        JSR PRINT
        JSR FORMAT_TIME
        JSR NL
        LDX #<CONFIRM_TEXT
        LDY #>CONFIRM_TEXT
        JSR PRINT
        JSR READLINE
                        BCS CLOCK_LONG_221
                        JMP CANCELED
CLOCK_LONG_221:
        LDX #<CMD_YES
        LDY #>CMD_YES
        JSR MATCH
                        BCS CLOCK_LONG_225
                        JMP CANCELED
CLOCK_LONG_225:
        LDX #7
        STZ H_SAVED
        JSR RTC_STATUS
                        BCS CLOCK_LONG_229
                        JMP STATUS_ERROR
CLOCK_LONG_229:
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
                        BEQ STAGE_TIME
        LDX #J_SAVE_OP
        JSR HISTORY_CALL
                        BCS CLOCK_LONG_235
                        JMP HISTORY_ERROR
CLOCK_LONG_235:
        INC H_SAVED
STAGE_TIME:
        LDX #7
STAGE_REQUEST:
        LDA REQUEST,X
        STA RTC_REQUEST,X
        DEX
                        BPL STAGE_REQUEST
        LDA #'S'
        STA RTC_KEY
        LDA #'T'
        STA RTC_KEY+1
        JSR RTC_SET
                        BCC SET_FAILED
        LDA H_SAVED
                        BEQ SET_REPORT
        LDX #J_RECONCILE_OP
        JSR HISTORY_CALL
SET_REPORT:
        LDX #<SET_DONE_TEXT
        LDY #>SET_DONE_TEXT
        JSR PRINT
        JSR READ_CLOCK
        JSR OFFSET_SETUP
        JMP MENU
ALARMS_ENABLED:
        LDX #<ALARMS_TEXT
        LDY #>ALARMS_TEXT
        JMP MESSAGE
SET_FAILED: JSR B29_CLOCK_ERROR

        JSR ERROR
        LDX #<SET_FAILED_TEXT
        LDY #>SET_FAILED_TEXT
        JMP MESSAGE
CHECK_SERVICE:
        LDX #2
CHECK_SV:
        LDA RTC_DISCOVERY,X
        CMP SV_MAGIC,X
                        BNE CHECK_FAILED
        DEX
                        BPL CHECK_SV
        LDA RTC_DISCOVERY+3
        AND #1
                        BEQ CHECK_FAILED
        LDA RTC_DISCOVERY+4
                        BNE CHECK_FAILED
        LDA RTC_DISCOVERY+5
        CMP #$65
                        BNE CHECK_FAILED
        LDA RTC_DISCOVERY+6
        CMP #$FF
                        BNE CHECK_FAILED
        LDA RTC_DISCOVERY+7
        CMP #$64
                        BNE CHECK_FAILED
        LDX #3
CHECK_RG:
        LDA RTC_SIGNATURE,X
        CMP RG_MAGIC,X
                        BNE CHECK_FAILED
        DEX
                        BPL CHECK_RG
        SEC
        RTS
CHECK_FAILED: JSR B29_CLOCK_ERROR

        CLC
        RTS
COPY_TIME:
        LDX #7
COPY_TIME_LOOP:
        LDA RTC_TIME,X
        STA DISPLAY,X
        DEX
                        BPL COPY_TIME_LOOP
        RTS
FORMAT_TIME:
        LDA #'2'
        JSR PUTC
        LDA #'0'
        JSR PUTC
        LDA DISPLAY
        SEC
        SBC #$D0             ; Low byte of 2000; modulo-256 gives 0..99.
        JSR DECIMAL_2
        LDA #'-'
        JSR PUTC
        LDA DISPLAY+2
        JSR DECIMAL_2
        LDA #'-'
        JSR PUTC
        LDA DISPLAY+3
        JSR DECIMAL_2
        LDA #' '
        JSR PUTC
        LDA DISPLAY+5
        JSR DECIMAL_2
        LDA #':'
        JSR PUTC
        LDA DISPLAY+6
        JSR DECIMAL_2
        LDA #':'
        JSR PUTC
        LDA DISPLAY+7
        JMP DECIMAL_2
DECIMAL_2:
        LDX #0
DECIMAL_TENS:
        CMP #10
                        BCC DECIMAL_OUTPUT
        SBC #10
        INX
                        BRA DECIMAL_TENS
DECIMAL_OUTPUT:
        PHA
        TXA
        ORA #'0'
        JSR PUTC
        PLA
        ORA #'0'
        JMP PUTC
SHOW_STATUS:
        LDX #<START_TEXT
        LDY #>START_TEXT
        JSR PRINT
        LDA #RTC_F_START
        JSR FLAG
        LDX #<RUNNING_TEXT
        LDY #>RUNNING_TEXT
        JSR PRINT
        LDA #RTC_F_RUNNING
        JSR FLAG
        LDX #<VALID_TEXT
        LDY #>VALID_TEXT
        JSR PRINT
        LDA #RTC_F_CALENDAR
        JSR FLAG
        LDX #<BACKUP_TEXT
        LDY #>BACKUP_TEXT
        JSR PRINT
        LDA #RTC_F_BACKUP_ENABLED
        JSR FLAG
        LDX #<POWERFAIL_TEXT
        LDY #>POWERFAIL_TEXT
        JSR PRINT
        LDA #RTC_F_POWERFAIL
        JSR FLAG
        LDX #<CONTINUITY_TEXT
        LDY #>CONTINUITY_TEXT
        JSR PRINT
        LDA RTC_FLAGS
        AND #RTC_F_CALENDAR
                        BEQ STATUS_RAW
        JSR COPY_TIME
        LDX #<CALENDAR_TEXT
        LDY #>CALENDAR_TEXT
        JSR PRINT
        JSR FORMAT_TIME
        JSR NL
STATUS_RAW:
        LDX #<RAW_TEXT
        LDY #>RAW_TEXT
        JSR PRINT
        STZ BYTE_INDEX
RAW_LOOP:
        LDX BYTE_INDEX
        LDA RTC_RAW,X
        JSR HEX_SPACE
        INC BYTE_INDEX
        LDA BYTE_INDEX
        CMP #9
                        BNE RAW_LOOP
        JSR NL
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
                        BEQ CAPTURE_STATUS
        LDX #<OUTAGE_TEXT
        LDY #>OUTAGE_TEXT
        JSR PRINT
        STZ BYTE_INDEX
OUTAGE_LOOP:
        LDX BYTE_INDEX
        LDA RTC_OUTAGE,X
        JSR HEX_SPACE
        INC BYTE_INDEX
        LDA BYTE_INDEX
        CMP #8
                        BNE OUTAGE_LOOP
        JSR NL
        LDA #<RTC_OUTAGE
        STA OF_PTR
        LDA #>RTC_OUTAGE
        STA OF_PTR+1
        JSR OUTAGE_PRETTY
CAPTURE_STATUS:
        LDA RTC_EVIDENCE
                        BEQ STATUS_DONE
        LDX #<CAPTURE_TEXT
        LDY #>CAPTURE_TEXT
        JSR PRINT
        STZ BYTE_INDEX
CAPTURE_LOOP:
        LDX BYTE_INDEX
        LDA RTC_CAPTURE,X
        JSR HEX_SPACE
        INC BYTE_INDEX
        LDA BYTE_INDEX
        CMP #8
                        BNE CAPTURE_LOOP
        JSR NL
        LDA #<RTC_CAPTURE
        STA OF_PTR
        LDA #>RTC_CAPTURE
        STA OF_PTR+1
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
                        BNE STATUS_DONE
        LDX #<CAPTURE_NOTE
        LDY #>CAPTURE_NOTE
        JSR PRINT
        JSR OUTAGE_PRETTY
STATUS_DONE:
        RTS
OUTAGE_PRETTY:
        LDX #<DOWN_TEXT
        LDY #>DOWN_TEXT
        JSR PRINT
        JSR OF_FORMAT
        JSR NL
        LDA OF_PTR
        CLC
        ADC #4
        STA OF_PTR
                        BCC OUTAGE_PTR_OK
        INC OF_PTR+1
OUTAGE_PTR_OK:
        LDX #<UP_TEXT
        LDY #>UP_TEXT
        JSR PRINT
        JSR D_CLOCK_UP
        JMP NL
HEX_SPACE:
        JSR HEX
        LDA #' '
        JMP PUTC
FLAG:
        AND RTC_FLAGS
                        BEQ FLAG_NO
        LDX #<YES_TEXT
        LDY #>YES_TEXT
        JMP PRINT
FLAG_NO:
        LDX #<NO_TEXT
        LDY #>NO_TEXT
        JMP PRINT
ERROR:
        STA LAST_ERROR
        LDX #<ERROR_TEXT
        LDY #>ERROR_TEXT
        JSR PRINT
        LDA LAST_ERROR
        JSR HEX
        LDA #':'
        JSR PUTC
        LDA #' '
        JSR PUTC
        LDA LAST_ERROR
        CMP #$80
                        BCC ERROR_LOW
        SEC
        SBC #$77             ; 80..82 -> table slots 9..11.
ERROR_LOW:
        CMP #12
                        BCS ERROR_UNKNOWN
        TAX
        LDA ERROR_HI,X
        TAY
        LDA ERROR_LO,X
        TAX
        JSR PRINT
        JMP NL
ERROR_UNKNOWN:
        LDX #<UNKNOWN_TEXT
        LDY #>UNKNOWN_TEXT
        JSR PRINT
        JMP NL
MATCH:
        STX TEXT
        STY TEXT+1
        LDY #0
MATCH_LOOP:
        LDA (TEXT),Y
        CMP LINE,Y
                        BNE MATCH_NO
        CMP #0
                        BEQ MATCH_YES
        INY
                        BRA MATCH_LOOP
MATCH_YES:
        SEC
        RTS
MATCH_NO:
        CLC
        RTS
PARSE_SET:
        LDA LINE_LENGTH
        CMP #23
                        BEQ CLOCK_LONG_543
                        JMP PARSE_BAD
CLOCK_LONG_543:
        LDX #10
PARSE_FIXED:
        LDY FIXED_POS,X
        LDA LINE,Y
        CMP FIXED_CHAR,X
                        BEQ CLOCK_LONG_549
                        JMP PARSE_BAD
CLOCK_LONG_549:
        DEX
                        BPL PARSE_FIXED
        LDX #6
        JSR PAIR
                        BCS CLOCK_LONG_554
                        JMP PARSE_BAD
CLOCK_LONG_554:
        STA YEAR_OFFSET
        CLC
        ADC #$D0
        STA REQUEST
        LDA #7
        ADC #0
        STA REQUEST+1
        LDX #9
        JSR PAIR
                        BCS CLOCK_LONG_564
                        JMP PARSE_BAD
CLOCK_LONG_564:
        CMP #1
                        BCS CLOCK_LONG_566
                        JMP PARSE_BAD
CLOCK_LONG_566:
        CMP #13
                        BCC CLOCK_LONG_568
                        JMP PARSE_BAD
CLOCK_LONG_568:
        STA REQUEST+2
        TAX
        DEX
        LDA MONTH_DAYS,X
        STA MAX_DAY
        LDA REQUEST+2
        CMP #2
                        BNE PARSE_DAY
        LDA YEAR_OFFSET
        AND #3
                        BNE PARSE_DAY
        INC MAX_DAY
PARSE_DAY:
        LDX #12
        JSR PAIR
                        BCS CLOCK_LONG_584
                        JMP PARSE_BAD
CLOCK_LONG_584:
        CMP #1
                        BCS CLOCK_LONG_586
                        JMP PARSE_BAD
CLOCK_LONG_586:
        CMP MAX_DAY
                        BEQ DAY_VALID
                        BCS PARSE_BAD
DAY_VALID:
        STA REQUEST+3
        LDX #15
        JSR PAIR
                        BCC PARSE_BAD
        CMP #24
                        BCS PARSE_BAD
        STA REQUEST+5
        LDX #18
        JSR PAIR
                        BCC PARSE_BAD
        CMP #60
                        BCS PARSE_BAD
        STA REQUEST+6
        LDX #21
        JSR PAIR
                        BCC PARSE_BAD
        CMP #60
                        BCS PARSE_BAD
        STA REQUEST+7
        ; Jan 1 2000 was Saturday (6). 365 mod 7 = 1.
        LDA YEAR_OFFSET
        CLC
        ADC #3
        LSR A
        LSR A
        CLC
        ADC YEAR_OFFSET
        ADC #5               ; Saturday 6, with day-1 folded into this 5.
        ADC REQUEST+3
        STA WEEK_SUM
        LDX REQUEST+2
        DEX
        LDA MONTH_MOD,X
        CLC
        ADC WEEK_SUM
        STA WEEK_SUM
        LDA REQUEST+2
        CMP #3
                        BCC WEEK_REDUCE
        LDA YEAR_OFFSET
        AND #3
                        BNE WEEK_REDUCE
        INC WEEK_SUM
WEEK_REDUCE:
        LDA WEEK_SUM
WEEK_LOOP:
        CMP #7
                        BCC WEEK_RESULT
        SBC #7
                        BRA WEEK_LOOP
WEEK_RESULT:
        CMP #0
                        BNE WEEK_STORE
        LDA #7
WEEK_STORE:
        STA REQUEST+4
        SEC
        RTS
PARSE_BAD:
        CLC
        RTS
PAIR:
        LDA LINE,X
        SEC
        SBC #'0'
        CMP #10
                        BCS PAIR_BAD
        STA DIGIT
        ASL A
        ASL A
        CLC
        ADC DIGIT
        ASL A
        STA DIGIT
        INX
        LDA LINE,X
        SEC
        SBC #'0'
        CMP #10
                        BCS PAIR_BAD
        CLC
        ADC DIGIT
        INX
        SEC
        RTS
PAIR_BAD:
        CLC
        RTS
READLINE:
        STZ LINE_LENGTH
        STZ OVERFLOW
LINE_WAIT:
        JSR GETC
        CMP #3
                        BEQ LINE_CANCEL
        CMP #$1B
                        BEQ LINE_CANCEL
        CMP #$0A
                        BEQ LINE_WAIT
        CMP #$0D
                        BEQ LINE_DONE
        CMP #8
                        BEQ LINE_BACK
        CMP #$7F
                        BEQ LINE_BACK
        CMP #$20
                        BCC LINE_WAIT
        CMP #'a'
                        BCC LINE_CHAR
        CMP #'z'+1
                        BCS LINE_CHAR
        AND #$DF
LINE_CHAR:
        LDX LINE_LENGTH
        CPX #39
                        BCS LINE_FULL
        STA LINE,X
        INC LINE_LENGTH
        JSR PUTC
                        JMP LINE_WAIT
LINE_FULL:
        LDA #1
        STA OVERFLOW
                        JMP LINE_WAIT
LINE_BACK:
        LDA LINE_LENGTH
                        BEQ LINE_WAIT
        DEC LINE_LENGTH
        LDA #8
        JSR PUTC
        LDA #' '
        JSR PUTC
        LDA #8
        JSR PUTC
                        JMP LINE_WAIT
LINE_DONE:
        LDX LINE_LENGTH
        STZ LINE,X
        JSR NL
        LDA OVERFLOW
                        BNE LINE_CANCEL
        SEC
        RTS
LINE_CANCEL: JSR B29_CLOCK_CANCEL

        JSR NL
        CLC
        RTS
PRINT:
        STX TEXT
        STY TEXT+1
        LDY #0
PRINT_LOOP:
        LDA (TEXT),Y
                        BEQ PRINT_DONE
        JSR PUTC
        INY
                        BNE PRINT_LOOP
        INC TEXT+1
                        BRA PRINT_LOOP
PRINT_DONE:
        RTS
; Journal commands use a separate verified service and do not require usable RTC time.
HISTORY_PARSE:
        LDA LINE_LENGTH
        CMP #6
                        BEQ HISTORY_SHOW_PARSE
        CMP #7
                        BNE HISTORY_PARSE_BAD
        LDX #5
HISTORY_CLEAR_PARSE:
        LDA LINE,X
        CMP CLEAR_PREFIX,X
                        BNE HISTORY_PARSE_BAD
        DEX
                        BPL HISTORY_CLEAR_PARSE
        LDA LINE+6
        LDX #J_CLEAR_OP
                        BRA HISTORY_NUMBER
HISTORY_SHOW_PARSE:
        LDX #4
HISTORY_SHOW_LOOP:
        LDA LINE,X
        CMP SHOW_PREFIX,X
                        BNE HISTORY_PARSE_BAD
        DEX
                        BPL HISTORY_SHOW_LOOP
        LDA LINE+5
        LDX #0
HISTORY_NUMBER:
        SEC
        SBC #'1'
        CMP #4
                        BCS HISTORY_PARSE_BAD
        STA H_SELECTED
        STX H_MODE
        SEC
        RTS
HISTORY_PARSE_BAD:
        CLC
        RTS
HISTORY_DISPATCH:
        LDA H_MODE
                        BEQ CLOCK_LONG_793
                        JMP HISTORY_CLEAR
CLOCK_LONG_793:
        LDX #J_SCAN_OP
        JSR HISTORY_CALL
                        BCS CLOCK_LONG_796
                        JMP HISTORY_ERROR
CLOCK_LONG_796:
        LDX H_SELECTED
        LDA H_MASKS,X
        AND J_VALID
                        BNE CLOCK_LONG_800
                        JMP HISTORY_EMPTY
CLOCK_LONG_800:
        JSR HISTORY_ROW
        JSR HISTORY_POINTER
        LDY #24
        LDA (H_PTR),Y
                        BPL HISTORY_CAPTURE_UNKNOWN
        LDY #20
HISTORY_COPY_CAPTURE:
        LDA (H_PTR),Y
        STA DISPLAY-20,Y
        INY
        CPY #28
                        BNE HISTORY_COPY_CAPTURE
        LDX #<H_CAPTURE_TEXT
        LDY #>H_CAPTURE_TEXT
        JSR PRINT
        JSR FORMAT_TIME
        JSR NL
        JMP MENU
HISTORY_CAPTURE_UNKNOWN:
        LDX #<H_CAPTURE_UNKNOWN
        LDY #>H_CAPTURE_UNKNOWN
        JMP MESSAGE
HISTORY:
        LDX #J_SCAN_OP
        JSR HISTORY_CALL
                        BCS CLOCK_LONG_826
                        JMP HISTORY_ERROR
CLOCK_LONG_826:
        LDA J_VALID
        STA H_REMAIN
                        BEQ HISTORY_EMPTY
HISTORY_LIST_NEXT:
        LDA #$FF
        STA H_BEST
        STZ H_SCAN
HISTORY_PICK:
        LDX H_SCAN
        LDA H_MASKS,X
        AND H_REMAIN
                        BEQ HISTORY_PICK_NEXT
        LDA H_BEST
        CMP #$FF
                        BEQ HISTORY_BETTER
        LDA H_SCAN
        JSR HISTORY_COMPARE
                        BCC HISTORY_PICK_NEXT
HISTORY_BETTER:
        LDA H_SCAN
        STA H_BEST
HISTORY_PICK_NEXT:
        INC H_SCAN
        LDA H_SCAN
        CMP #4
                        BNE HISTORY_PICK
        LDA H_BEST
        STA H_SELECTED
        JSR HISTORY_ROW
        LDX H_SELECTED
        LDA H_MASKS,X
        EOR #$FF
        AND H_REMAIN
        STA H_REMAIN
                        BNE HISTORY_LIST_NEXT
        JMP MENU
HISTORY_EMPTY:
        LDX #<H_EMPTY_TEXT
        LDY #>H_EMPTY_TEXT
        JMP MESSAGE
HISTORY_CLEAR:
        LDX #J_SCAN_OP
        JSR HISTORY_CALL
                        BCC HISTORY_ERROR
        JSR HISTORY_ROW
        LDX #<H_CLEAR_CONFIRM
        LDY #>H_CLEAR_CONFIRM
        JSR PRINT
        JSR READLINE
                        BCS CLOCK_LONG_876
                        JMP CANCELED
CLOCK_LONG_876:
        LDX #<CMD_YES
        LDY #>CMD_YES
        JSR MATCH
                        BCS CLOCK_LONG_880
                        JMP CANCELED
CLOCK_LONG_880:
        LDA H_SELECTED
        STA J_PARAM
        LDA #'C'
        STA J_KEY
        LDA #'L'
        STA J_KEY+1
        LDX #J_CLEAR_OP
        JSR HISTORY_CALL
                        BCC HISTORY_ERROR
                        BRA HISTORY_CLEARED
HISTORY_CLEAR_ALL:
        LDX #<H_CLEAR_ALL_CONFIRM
        LDY #>H_CLEAR_ALL_CONFIRM
        JSR PRINT
        JSR READLINE
                        BCS CLOCK_LONG_896
                        JMP CANCELED
CLOCK_LONG_896:
        LDX #<CMD_DELETE_ALL
        LDY #>CMD_DELETE_ALL
        JSR MATCH
                        BCS CLOCK_LONG_900
                        JMP CANCELED
CLOCK_LONG_900:
        LDA #'A'
        STA J_KEY
        LDA #'L'
        STA J_KEY+1
        LDX #J_CLEAR_ALL_OP
        JSR HISTORY_CALL
                        BCC HISTORY_ERROR
HISTORY_CLEARED:
        LDX #<H_CLEARED_TEXT
        LDY #>H_CLEARED_TEXT
        JMP MESSAGE
HISTORY_ERROR:
        PHA
        LDX #<H_ERROR_TEXT
        LDY #>H_ERROR_TEXT
        JSR PRINT
        PLA
        JSR HEX
        JSR NL
        JMP MENU
HISTORY_POINTER:
        LDA H_SELECTED
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA H_PTR
        LDA #$6B
        STA H_PTR+1
        RTS
HISTORY_COMPARE:
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #11
        TAX
        LDA H_BEST
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #11
        TAY
        LDA #4
        STA H_COMPARE_COUNT
HISTORY_COMPARE_LOOP:
        LDA J_CACHE,X
        SEC
        SBC J_CACHE,Y
                        BNE HISTORY_COMPARE_DONE
        DEX
        DEY
        DEC H_COMPARE_COUNT
                        BNE HISTORY_COMPARE_LOOP
        SEC
HISTORY_COMPARE_DONE:
        RTS
HISTORY_ROW:
        JSR S_HISTORY_POINTER
        LDX #<H_SLOT_TEXT
        LDY #>H_SLOT_TEXT
        JSR PRINT
        LDA H_SELECTED
        CLC
        ADC #'1'
        JSR PUTC
        LDX #<H_SEQ_TEXT
        LDY #>H_SEQ_TEXT
        JSR PRINT
        LDA #11
        STA H_INDEX
HISTORY_SEQ_LOOP:
        LDY H_INDEX
        LDA (H_PTR),Y
        JSR HEX
        DEC H_INDEX
        LDA H_INDEX
        CMP #7
                        BNE HISTORY_SEQ_LOOP
        LDY #30
        LDA (H_PTR),Y
                        BEQ HISTORY_ACKED
        LDX #<H_PENDING_TEXT
        LDY #>H_PENDING_TEXT
                        BRA HISTORY_ACK_TEXT
HISTORY_ACKED:
        LDX #<H_ACKED_TEXT
        LDY #>H_ACKED_TEXT
HISTORY_ACK_TEXT:
        JSR PRINT
        LDA H_PTR
        CLC
        ADC #12
        STA OF_PTR
        LDA #$6B
        STA OF_PTR+1
        JMP S_HISTORY_OUTAGE
HISTORY_CALL:
        STX H_OP
        LDX #7
HISTORY_DISCOVERY:
        LDA J_DESC,X
        CMP H_SIGNATURE,X
                        BNE HISTORY_UNAVAILABLE
        DEX
                        BPL HISTORY_DISCOVERY
        PHP
        SEI
        CLD
        LDA $7FEC
        STA H_PCR
        AND #$EE
        CMP #$EE
                        BEQ HISTORY_NMI_OK
        LDA $7E01
                        BMI HISTORY_NMI_BAD
HISTORY_NMI_OK:
        LDA H_PCR
        AND #$11
        ORA #$EE
        STA $7FEC
        LDX H_OP
        JSR HISTORY_EXECUTE
        STA H_RESULT
        LDA H_PCR
        STA $7FEC
        PLP
        LDA H_RESULT
                        BEQ HISTORY_GOOD
        CLC
        RTS
HISTORY_GOOD:
        SEC
        RTS
HISTORY_NMI_BAD:
        PLP
        LDA #$82
        CLC
        RTS
HISTORY_UNAVAILABLE:
        LDA #$80
        CLC
        RTS
HISTORY_EXECUTE:
        JMP (J_DESC+4)
TRIM_COMMAND:
        JSR CHECK_SERVICE
                        BCS CLOCK_LONG_1054
                        JMP NO_SERVICE
CLOCK_LONG_1054:
        JSR RTC_STATUS
                        BCS CLOCK_LONG_1056
                        JMP STATUS_ERROR
CLOCK_LONG_1056:
        JSR TRIM_SHOW
        JMP MENU
; Accept optional sign plus 1-3 decimal digits, magnitude <=127.
; Signed steps: + speeds up (SIGN=1), - slows down (SIGN=0).
TRIM_PARSE:
        LDA LINE_LENGTH
        CMP #6
                        BCC TRIM_PARSE_BAD
        CMP #10
                        BCS TRIM_PARSE_BAD
        LDX #4
TRIM_PREFIX_LOOP:
        LDA LINE,X
        CMP TRIM_PREFIX,X
                        BNE TRIM_PARSE_BAD
        DEX
                        BPL TRIM_PREFIX_LOOP
        STZ TRIM_REQUEST
        STZ TRIM_SIGN
        STZ TRIM_DIGITS
        LDX #5
        LDA LINE,X
        CMP #'-'
                        BEQ TRIM_NEGATIVE
        LDA #$80
        STA TRIM_SIGN
        LDA LINE,X
        CMP #'+'
                        BNE TRIM_DIGIT_LOOP
TRIM_NEGATIVE:
        INX
TRIM_DIGIT_LOOP:
        LDA LINE,X
                        BEQ TRIM_PARSE_END
        SEC
        SBC #'0'
        CMP #10
                        BCS TRIM_PARSE_BAD
        STA DIGIT
        INC TRIM_DIGITS
        LDA TRIM_DIGITS
        CMP #4
                        BCS TRIM_PARSE_BAD
        LDA TRIM_REQUEST
        CMP #13
                        BCS TRIM_PARSE_BAD
        ASL A
        ASL A
        CLC
        ADC TRIM_REQUEST
        ASL A
        CLC
        ADC DIGIT
        CMP #128
                        BCS TRIM_PARSE_BAD
        STA TRIM_REQUEST
        INX
                        BRA TRIM_DIGIT_LOOP
TRIM_PARSE_END:
        LDA TRIM_DIGITS
                        BEQ TRIM_PARSE_BAD
        LDA TRIM_REQUEST
                        BEQ TRIM_PARSE_GOOD
        ORA TRIM_SIGN
        STA TRIM_REQUEST
TRIM_PARSE_GOOD:
        SEC
        RTS
TRIM_PARSE_BAD:
        CLC
        RTS
TRIM_CHANGE:
        JSR CHECK_SERVICE
                        BCS CLOCK_LONG_1130
                        JMP NO_SERVICE
CLOCK_LONG_1130:
        JSR RTC_STATUS
                        BCS CLOCK_LONG_1132
                        JMP STATUS_ERROR
CLOCK_LONG_1132:
        JSR TRIM_SHOW
        LDX #<TRIM_REQUEST_TEXT
        LDY #>TRIM_REQUEST_TEXT
        JSR PRINT
        LDA TRIM_REQUEST
        JSR TRIM_PRINT_VALUE
        LDX #<TRIM_WARNING
        LDY #>TRIM_WARNING
        JSR PRINT
        JSR READLINE
                        BCS CLOCK_LONG_1143
                        JMP CANCELED
CLOCK_LONG_1143:
        LDX #<CMD_YES
        LDY #>CMD_YES
        JSR MATCH
                        BCS CLOCK_LONG_1147
                        JMP CANCELED
CLOCK_LONG_1147:
        LDA TRIM_REQUEST
        STA J_PARAM
        LDA #'T'
        STA J_KEY
        LDA #'R'
        STA J_KEY+1
        LDX #10
        JSR HISTORY_CALL
                        BCC TRIM_FAILURE
        JSR RTC_STATUS
                        BCS CLOCK_LONG_1158
                        JMP STATUS_ERROR
CLOCK_LONG_1158:
        JSR TRIM_SHOW
        JMP MENU
TRIM_FAILURE:
        CMP #6
                        BNE TRIM_OTHER_FAILURE
        LDX #<TRIM_BLOCKED_TEXT
        LDY #>TRIM_BLOCKED_TEXT
        JMP MESSAGE
TRIM_OTHER_FAILURE:
        JSR ERROR
        LDX #<TRIM_FAILURE_TEXT
        LDY #>TRIM_FAILURE_TEXT
        JMP MESSAGE
TRIM_SHOW:
        LDX #<TRIM_TEXT
        LDY #>TRIM_TEXT
        JSR PRINT
        LDA RTC_RAW+8
        JSR TRIM_PRINT_VALUE
        LDX #<TRIM_COARSE_TEXT
        LDY #>TRIM_COARSE_TEXT
        JSR PRINT
        LDA RTC_RAW+7
        AND #4
                        BEQ TRIM_COARSE_OFF
        LDX #<TRIM_ON_TEXT
        LDY #>TRIM_ON_TEXT
                        BRA TRIM_MODE_TEXT
TRIM_COARSE_OFF:
        LDX #<TRIM_OFF_TEXT
        LDY #>TRIM_OFF_TEXT
TRIM_MODE_TEXT:
        JSR PRINT
        LDX #<TRIM_RAW_TEXT
        LDY #>TRIM_RAW_TEXT
        JSR PRINT
        LDA RTC_RAW+8
        JSR HEX
        JMP NL
TRIM_PRINT_VALUE:
        STA TRIM_PRINT_RAW
        AND #$7F
                        BEQ TRIM_PRINT_ZERO
        LDA TRIM_PRINT_RAW
                        BMI TRIM_PRINT_PLUS
        LDA #'-'
                        BRA TRIM_PRINT_SIGN
TRIM_PRINT_PLUS:
        LDA #'+'
TRIM_PRINT_SIGN:
        JSR PUTC
        LDA TRIM_PRINT_RAW
        AND #$7F
        CMP #100
                        BCC TRIM_PRINT_UNDER_100
        SEC
        SBC #100
        PHA
        LDA #'1'
        JSR PUTC
        PLA
        JMP DECIMAL_2
TRIM_PRINT_UNDER_100:
        CMP #10
                        BCC CLOCK_LONG_1223
                        JMP DECIMAL_2
CLOCK_LONG_1223:
TRIM_PRINT_ZERO:
        ORA #'0'
        JMP PUTC
CMD_TRIM DB "TRIM",0
TRIM_PREFIX DB "TRIM "
TRIM_TEXT DB "RTCC: Trim ",0
TRIM_COARSE_TEXT DB " steps; coarse ",0
TRIM_ON_TEXT DB "ON",0
TRIM_OFF_TEXT DB "OFF",0
TRIM_RAW_TEXT DB "; OSCTRIM $",0
TRIM_REQUEST_TEXT DB "Requested trim: ",0
TRIM_WARNING DB " steps; coarse OFF.",13,10,"Positive speeds up; negative slows down; zero disables correction.",13,10,"Type YES to confirm: ",0
TRIM_FAILURE_TEXT DB "RTCC: Trim change not verified; inspect STATUS.",13,10,0
TRIM_BLOCKED_TEXT DB "RTCC: Trim change refused; alarm/square-wave output active.",13,10,0
TRIM_REQUEST DB 0
TRIM_SIGN DB 0
TRIM_DIGITS DB 0
TRIM_PRINT_RAW DB 0
EUI_COMMAND:
        JSR EUI_SHOW
        JMP MENU
EUI_SHOW:
        STZ J_CURRENT_VALID
        STZ J_BIND_STATUS
        LDX #5
EUI_RESET_REMEMBERED:
        STZ J_REMEMBERED,X
        DEX
                        BPL EUI_RESET_REMEMBERED
        LDX #J_BIND_CHECK_OP
        JSR HISTORY_CALL
                        BCC EUI_UNAVAILABLE
        LDA J_CURRENT_VALID
                        BEQ EUI_UNAVAILABLE
        LDX #5
EUI_COPY_CURRENT:
        LDA J_EUI,X
        STA EUI_DISPLAY,X
        DEX
                        BPL EUI_COPY_CURRENT
        LDX #<EUI_TEXT
        LDY #>EUI_TEXT
        JSR PRINT
        STZ BYTE_INDEX
EUI_NEXT:
        LDX BYTE_INDEX
        LDA J_EUI,X
        JSR HEX
        INC BYTE_INDEX
        LDA BYTE_INDEX
        CMP #6
                        BEQ EUI_DONE
        LDA #':'
        JSR PUTC
                        BRA EUI_NEXT
EUI_DONE:
        LDA J_BIND_STATUS
                        BEQ EUI_UNBOUND
        CMP #1
                        BEQ UI_EUI_MATCH
        CMP #2
                        BNE EUI_STATUS_DONE
        LDX #<EUI_CHANGED_TEXT
        LDY #>EUI_CHANGED_TEXT
                        BRA EUI_SUFFIX
UI_EUI_MATCH:
        LDX #<UI_EUI_MATCH_TEXT
        LDY #>UI_EUI_MATCH_TEXT
        JSR PRINT
        JMP NL
EUI_UNBOUND:
        LDX #<EUI_UNBOUND_TEXT
        LDY #>EUI_UNBOUND_TEXT
EUI_SUFFIX:
        JSR PRINT
EUI_STATUS_DONE:
        JSR NL
        LDA J_BIND_STATUS
                        BEQ EUI_RETURN
                        BRA EUI_REMEMBERED
EUI_UNAVAILABLE:
        LDX #<EUI_UNAVAILABLE_TEXT
        LDY #>EUI_UNAVAILABLE_TEXT
        JSR PRINT
        JSR NL
        LDA J_BIND_STATUS
        CMP #3
                        BNE EUI_RETURN
        LDA J_REMEMBERED
        ORA J_REMEMBERED+1
        ORA J_REMEMBERED+2
        ORA J_REMEMBERED+3
        ORA J_REMEMBERED+4
        ORA J_REMEMBERED+5
                        BEQ EUI_RETURN
EUI_REMEMBERED:
        LDX #<EUI_REMEMBERED_TEXT
        LDY #>EUI_REMEMBERED_TEXT
        JSR PRINT
        STZ BYTE_INDEX
EUI_REMEMBERED_NEXT:
        LDX BYTE_INDEX
        LDA J_REMEMBERED,X
        JSR HEX
        INC BYTE_INDEX
        LDA BYTE_INDEX
        CMP #6
                        BEQ EUI_REMEMBERED_DONE
        LDA #':'
        JSR PUTC
                        BRA EUI_REMEMBERED_NEXT
EUI_REMEMBERED_DONE:
        JSR NL
EUI_RETURN:
        RTS
EUI_ACCEPT_COMMAND:
        JSR EUI_SHOW
        LDA J_CURRENT_VALID
                        BNE CLOCK_LONG_1342
                        JMP MENU
CLOCK_LONG_1342:
        LDA J_BIND_STATUS
        CMP #1
                        BEQ EUI_ALREADY
        LDX #<EUI_CONFIRM_TEXT
        LDY #>EUI_CONFIRM_TEXT
        JSR PRINT
        JSR READLINE
                        BCS CLOCK_LONG_1350
                        JMP CANCELED
CLOCK_LONG_1350:
        LDX #<CMD_YES
        LDY #>CMD_YES
        JSR MATCH
                        BCS CLOCK_LONG_1354
                        JMP CANCELED
CLOCK_LONG_1354:
        LDX #5
EUI_STAGE:
        LDA EUI_DISPLAY,X
        STA J_BIND_REQUEST,X
        DEX
                        BPL EUI_STAGE
        LDA #'A'
        STA J_KEY
        LDA #'I'
        STA J_KEY+1
        LDX #J_BIND_ACCEPT_OP
        JSR HISTORY_CALL
                        BCC EUI_ACCEPT_FAILED
        LDX #<EUI_ACCEPTED_TEXT
        LDY #>EUI_ACCEPTED_TEXT
        JMP MESSAGE
EUI_ALREADY:
        LDX #<EUI_ALREADY_TEXT
        LDY #>EUI_ALREADY_TEXT
        JMP MESSAGE
EUI_ACCEPT_FAILED: JSR B29_CLOCK_ERROR

        CMP #J_BIND_FULL
                        BNE EUI_ACCEPT_OTHER_FAILURE
        LDX #<EUI_FULL_TEXT
        LDY #>EUI_FULL_TEXT
        JMP MESSAGE
EUI_ACCEPT_OTHER_FAILURE:
        LDX #<EUI_FAILED_TEXT
        LDY #>EUI_FAILED_TEXT
        JMP MESSAGE
EUI_TEXT DB "EUI: ",0
EUI_UNAVAILABLE_TEXT DB "EUI: unavailable",0
CMD_EUI DB "EUI",0
CMD_ACCEPT_EUI DB "ACCEPT EUI",0
EUI_UNBOUND_TEXT DB " (not remembered)",0
EUI_CHANGED_TEXT DB " (DIFFERS from remembered)",0
EUI_REMEMBERED_TEXT DB "Remembered EUI: ",0
EUI_CONFIRM_TEXT DB "Remember this EUI in flash? Type YES: ",0
EUI_ACCEPTED_TEXT DB "RTCC: EUI remembered.",13,10,0
EUI_ALREADY_TEXT DB "RTCC: EUI already remembered.",13,10,0
EUI_FAILED_TEXT DB "RTCC: EUI acceptance not verified.",13,10,0
EUI_FULL_TEXT DB "RTCC: Identity store full; no change.",13,10,0
EUI_DISPLAY DS 6
SHOW_PREFIX DB "SHOW "
CLEAR_PREFIX DB "CLEAR "
H_SIGNATURE DB "PJ",1,1,4,$90,0,$6B
H_MASKS DB 1,2,4,8
H_EMPTY_TEXT DB "No saved event in requested history",13,10,0
H_ERROR_TEXT DB "History unavailable/error ",0
H_SLOT_TEXT DB "UTC slot ",0
H_SEQ_TEXT DB " seq ",0
H_PENDING_TEXT DB " - latch clearance unconfirmed",13,10,0
H_ACKED_TEXT DB " - latch cleared",13,10,0
H_CAPTURE_TEXT DB "Recorded at (UTC): ",0
H_CAPTURE_UNKNOWN DB "Capture time unavailable; raw outage preserved.",13,10,0
H_CLEAR_CONFIRM DB "Clear this EEPROM event only? Type YES: ",0
H_CLEAR_ALL_CONFIRM DB "Clear/initialize all EEPROM journal slots (00-7F).",13,10,"UTC and live latch are unchanged. Type DELETE ALL: ",0
H_CLEARED_TEXT DB "History cleared. UTC and live latch unchanged.",13,10,0
H_OP DB 0
H_PCR DB 0
H_RESULT DB 0
H_MODE DB 0
H_SELECTED DB 0
H_REMAIN DB 0
H_BEST DB 0
H_SCAN DB 0
H_INDEX DB 0
H_COMPARE_COUNT DB 0
H_SAVED DB 0
RA_MAGIC DB "RA",1,13
SV_MAGIC DB "SV",1
RG_MAGIC DB "RG",1,4
CMD_R DB "R",0
CMD_TIME DB "TIME",0
CMD_S DB "S",0
CMD_STATUS DB "STATUS",0
CMD_Q DB "Q",0
CMD_QUIT DB "QUIT",0
CMD_HELP DB "HELP",0
CMD_QUESTION DB "?",0
CMD_YES DB "YES",0
CMD_ACK DB "ACK",0
CMD_HISTORY DB "HISTORY",0
CMD_CLEAR_ALL DB "CLEAR ALL",0
CMD_DELETE_ALL DB "DELETE ALL",0
FIXED_POS DB 0,1,2,3,4,5,8,11,14,17,20
FIXED_CHAR DB "SET 20-- ::"
MONTH_DAYS DB 31,28,31,30,31,30,31,31,30,31,30,31
MONTH_MOD DB 0,3,3,6,1,4,6,2,5,0,3,5
TITLE DB "CLOCK 1.11",13,10,0
PROMPT DB "CLOCK> ",0
HELP_TEXT DB "TIME/R STATUS/S EUI HISTORY SHOW n",13,10
        DB "SET yyyy-mm-dd hh:mm:ss UTC; OFFSET +/-HH:MM; TRIM -127..+127",13,10
        DB "ACK; ACCEPT EUI; CLEAR n/ALL; HELP/?; Q/QUIT",13,10
        DB "BATTERY [REPLACED | yyyy-mm-dd | LIMITS ww rr]",13,10
        DB "Limits: 01..99 30-day months, ww < rr. Changes confirmed.",13,10,0

UTC_TEXT DB "UTC:   ",0
CALENDAR_TEXT DB "Calendar (UTC convention): ",0
BAD_TEXT DB "Invalid command/date. Use SET yyyy-mm-dd hh:mm:ss or HELP.",13,10,0
NO_SERVICE_TEXT DB "RTCC: Services unavailable.",13,10,0
CANCELED_TEXT DB "Canceled.",13,10,0
LATCHED_TEXT DB "Power-fail evidence is latched; S shows details.",13,10,0
START_TEXT DB "Oscillator start: ",0
RUNNING_TEXT DB "Running: ",0
VALID_TEXT DB "Calendar valid: ",0
BACKUP_TEXT DB "Backup enabled: ",0
POWERFAIL_TEXT DB "Power-fail latched: ",0
CONTINUITY_TEXT DB "Time continuity and battery condition: unknown",13,10,0
RAW_TEXT DB "RTC registers (raw): ",0
OUTAGE_TEXT DB "Power-fail down/up (raw UTC, minute precision): ",0
CAPTURE_TEXT DB "Retained outage (RAM, raw): ",0
NEW_TIME_TEXT DB "Requested UTC: ",0
CONFIRM_TEXT DB "SET changes UTC and clears the chip's power-fail flag.",13,10,"Type YES to confirm: ",0
SET_DONE_TEXT DB "SET completed. Checking time:",13,10,0
ALARMS_TEXT DB "Alarms enabled; SET refused.",13,10,0
SET_FAILED_TEXT DB "SET failed; inspect S before any retry.",13,10,0
ACK_CONFIRM_TEXT DB "ACK clears the power-fail flag and outage timestamps.",13,10,"UTC time keeps running unchanged.",13,10,"The outage is saved and verified in EEPROM before ACK.",13,10,"Type YES to confirm: ",0
ACK_DONE_TEXT DB "Power-fail acknowledged; latch verified clear. Time unchanged.",13,10,0
ACK_FAILED_TEXT DB "ACK not verified; inspect S before retry.",13,10,0
NO_EVENT_TEXT DB "No latched power-fail event; nothing cleared.",13,10,0
CAPTURE_NOTE DB "Captured outage (UTC; no year/seconds):",13,10,0
DOWN_TEXT DB "Power down: ",0
UP_TEXT DB "Power up:   ",0
YES_TEXT DB "yes",13,10,0
NO_TEXT DB "no",13,10,0
ERROR_TEXT DB "RTCC: Error ",0
UNKNOWN_TEXT DB "unknown error",0
ERR_0 DB "completed",0
ERR_1 DB "bus not idle",0
ERR_2 DB "device did not acknowledge",0
ERR_3 DB "bus timeout",0
ERR_4 DB "time not usable; inspect S or try R after startup",0
ERR_5 DB "alarms enabled",0
ERR_6 DB "operation denied",0
ERR_7 DB "unstable clock snapshot",0
ERR_8 DB "service already in use",0
ERR_9 DB "RTC software unavailable",0
ERR_10 DB "RTC integrity failure",0
ERR_11 DB "unsupported cross-bank NMI handler",0
ERROR_LO DB <ERR_0,<ERR_1,<ERR_2,<ERR_3,<ERR_4,<ERR_5,<ERR_6,<ERR_7,<ERR_8,<ERR_9,<ERR_10,<ERR_11
ERROR_HI DB >ERR_0,>ERR_1,>ERR_2,>ERR_3,>ERR_4,>ERR_5,>ERR_6,>ERR_7,>ERR_8,>ERR_9,>ERR_10,>ERR_11
LINE_LENGTH DB 0
OVERFLOW DB 0
BYTE_INDEX DB 0
LAST_ERROR DB 0
DIGIT DB 0
YEAR_OFFSET DB 0
MAX_DAY DB 0
WEEK_SUM DB 0
REQUEST DS 8
DISPLAY DS 8
LINE DS 40
OF_MINUTE DB 0
OF_HOUR DB 0
OF_DAY DB 0
OF_MONTH DB 0
OF_TEMP DB 0
OF_UNITS DB 0
OF_RAW_HOUR DB 0
OF_MAX_DAY DB 0
        INCLUDE "outage-format.inc"
OFFSET_FLASH_BYTE EQU $7B03
; Read-only fixed-offset display. UTC snapshots and hardware remain unchanged.
; TZ records share the append-only identity tail; EI records are ignored.
TZ_PTR EQU $D6
TZ_READ:
        STZ TZ_OFFSET
        STZ TZ_OFFSET+1
        STZ TZ_FOUND
        STZ TZ_FREE+1
        LDX #3
TZ_ZERO_SEQ:
        STZ TZ_SEQ,X
        DEX
                        BPL TZ_ZERO_SEQ
        LDA $7FEC
        PHA
        AND #$11
        ORA #$EE
        STA $7FEC
        STZ TZ_PTR
        LDA #$9C
        STA TZ_PTR+1
TZ_SCAN:
        LDY #0
TZ_BLANK:
        LDA (TZ_PTR),Y
        CMP #$FF
                        BNE TZ_CHECK
        INY
        CPY #32
                        BNE TZ_BLANK
        LDA TZ_FREE+1
                        BNE TZ_NEXT
        LDA TZ_PTR
        STA TZ_FREE
        LDA TZ_PTR+1
        STA TZ_FREE+1
                        BRA TZ_NEXT
TZ_CHECK:
        LDY #31
        LDA (TZ_PTR),Y
                        BNE TZ_NEXT
        LDY #3
TZ_HEADER_CHECK:
        LDA (TZ_PTR),Y
        CMP TZ_MAGIC,Y
                        BNE TZ_NEXT
        DEY
                        BPL TZ_HEADER_CHECK
        JSR TZ_CRC
        LDY #28
        LDA (TZ_PTR),Y
        CMP TZ_SUM
                        BNE TZ_NEXT
        INY
        LDA (TZ_PTR),Y
        CMP TZ_SUM+1
                        BNE TZ_NEXT
        LDY #8
        LDA (TZ_PTR),Y
        STA TZ_WORK
        INY
        LDA (TZ_PTR),Y
        STA TZ_WORK+1
        JSR TZ_RANGE
                        BCC TZ_NEXT
        LDY #7
        LDX #3
TZ_NEWER:
        LDA (TZ_PTR),Y
        CMP TZ_SEQ,X
                        BCC TZ_NEXT
                        BNE TZ_KEEP
        DEY
        DEX
                        BPL TZ_NEWER
TZ_KEEP:
        LDY #7
        LDX #3
TZ_KEEP_SEQ:
        LDA (TZ_PTR),Y
        STA TZ_SEQ,X
        DEY
        DEX
                        BPL TZ_KEEP_SEQ
        LDY #8
        LDA (TZ_PTR),Y
        STA TZ_OFFSET
        INY
        LDA (TZ_PTR),Y
        STA TZ_OFFSET+1
        INC TZ_FOUND
TZ_NEXT:
        LDA TZ_PTR
        CLC
        ADC #32
        STA TZ_PTR
                        BCC TZ_SCAN_PAGE
        INC TZ_PTR+1
TZ_SCAN_PAGE:
        LDA TZ_PTR+1
        CMP #$A0
                        BEQ CLOCK_LONG_1619
                        JMP TZ_SCAN
CLOCK_LONG_1619:
        PLA
        STA $7FEC
        RTS
TZ_CRC:
        LDA #$FF
        STA TZ_SUM
        STA TZ_SUM+1
        LDY #0
TZ_CRC_BYTE:
        LDA (TZ_PTR),Y
        EOR TZ_SUM+1
        STA TZ_SUM+1
        LDX #8
TZ_CRC_BIT:
        ASL TZ_SUM
        ROL TZ_SUM+1
                        BCC TZ_CRC_NEXT
        LDA TZ_SUM
        EOR #$21
        STA TZ_SUM
        LDA TZ_SUM+1
        EOR #$10
        STA TZ_SUM+1
TZ_CRC_NEXT:
        DEX
                        BNE TZ_CRC_BIT
        INY
        CPY #28
                        BNE TZ_CRC_BYTE
        RTS
TZ_ABS:
        LDA TZ_WORK+1
                        BPL TZ_ABS_DONE
        LDA #0
        SEC
        SBC TZ_WORK
        STA TZ_WORK
        LDA #0
        SBC TZ_WORK+1
        STA TZ_WORK+1
TZ_ABS_DONE:
        RTS
; Signed minute range -12:00 through +14:00, no wrapping malformed values.
TZ_RANGE:
        LDA TZ_WORK+1
                        BMI TZ_RANGE_NEG
        CMP #3
                        BCC TZ_RANGE_OK
                        BNE TZ_RANGE_BAD
        LDA TZ_WORK
        CMP #$49
                        BCC TZ_RANGE_OK
                        BRA TZ_RANGE_BAD
TZ_RANGE_NEG:
        CMP #$FD
                        BCC TZ_RANGE_BAD
                        BNE TZ_RANGE_OK
        LDA TZ_WORK
        CMP #$30
                        BCC TZ_RANGE_BAD
TZ_RANGE_OK:
        SEC
        RTS
TZ_RANGE_BAD:
        CLC
        RTS
TZ_OFFSET_TEXT:
        LDA TZ_OFFSET
        STA TZ_WORK
        LDA TZ_OFFSET+1
        STA TZ_WORK+1
        LDA #'+'
        BIT TZ_OFFSET+1
                        BPL TZ_SIGN_READY
        LDA #'-'
TZ_SIGN_READY:
        JSR $7E6D
        JSR TZ_ABS
        STZ TZ_HOURS
TZ_HOUR_LOOP:
        LDA TZ_WORK+1
                        BNE TZ_HOUR_SUB
        LDA TZ_WORK
        CMP #60
                        BCC TZ_HOUR_DONE
TZ_HOUR_SUB:
        LDA TZ_WORK
        SEC
        SBC #60
        STA TZ_WORK
        LDA TZ_WORK+1
        SBC #0
        STA TZ_WORK+1
        INC TZ_HOURS
                        BRA TZ_HOUR_LOOP
TZ_HOUR_DONE:
        LDA TZ_HOURS
        JSR TZ_DECIMAL
        LDA #':'
        JSR $7E6D
        LDA TZ_WORK
        JMP TZ_DECIMAL
TZ_SHOW_LOCAL:
        LDA $66C0
                        BNE TZ_RENDER_DONE
        LDA $66C1
        AND #4
                        BEQ TZ_RENDER_DONE
        JSR TZ_READ
        LDX #7
TZ_COPY_DATE:
        LDA $66C2,X
        STA TZ_DATE,X
        DEX
                        BPL TZ_COPY_DATE
        LDA TZ_OFFSET
        STA TZ_WORK
        LDA TZ_OFFSET+1
        STA TZ_WORK+1
        JSR TZ_ABS
TZ_MINUTE_LOOP:
        LDA TZ_WORK
        ORA TZ_WORK+1
                        BNE CLOCK_LONG_1743
                        JMP TZ_RENDER
CLOCK_LONG_1743:
        LDA TZ_OFFSET+1
                        BMI TZ_BACKWARD
        JSR TZ_FORWARD
                        BRA TZ_COUNT_MINUTE
TZ_BACKWARD:
        JSR TZ_REVERSE
TZ_COUNT_MINUTE:
        LDA TZ_WORK
                        BNE TZ_COUNT_LOW
        DEC TZ_WORK+1
TZ_COUNT_LOW:
        DEC TZ_WORK
                        BRA TZ_MINUTE_LOOP
TZ_RENDER_DONE:
        RTS
TZ_FORWARD:
        INC TZ_DATE+6
        LDA TZ_DATE+6
        CMP #60
                        BNE TZ_DATE_DONE
        STZ TZ_DATE+6
        INC TZ_DATE+5
        LDA TZ_DATE+5
        CMP #24
                        BNE TZ_DATE_DONE
        STZ TZ_DATE+5
        INC TZ_DATE+4
        LDA TZ_DATE+4
        CMP #8
                        BNE TZ_F_DAY
        LDA #1
        STA TZ_DATE+4
TZ_F_DAY:
        JSR TZ_MONTH_DAYS
        INC TZ_DATE+3
        CMP TZ_DATE+3
                        BCS TZ_DATE_DONE
        LDA #1
        STA TZ_DATE+3
        INC TZ_DATE+2
        LDA TZ_DATE+2
        CMP #13
                        BNE TZ_DATE_DONE
        LDA #1
        STA TZ_DATE+2
        INC TZ_DATE
                        BNE TZ_DATE_DONE
        INC TZ_DATE+1
TZ_DATE_DONE:
        RTS
TZ_REVERSE:
        DEC TZ_DATE+6
                        BPL TZ_DATE_DONE
        LDA #59
        STA TZ_DATE+6
        DEC TZ_DATE+5
                        BPL TZ_DATE_DONE
        LDA #23
        STA TZ_DATE+5
        DEC TZ_DATE+4
                        BNE TZ_R_DAY
        LDA #7
        STA TZ_DATE+4
TZ_R_DAY:
        DEC TZ_DATE+3
                        BNE TZ_DATE_DONE
        DEC TZ_DATE+2
                        BNE TZ_R_MONTH
        LDA #12
        STA TZ_DATE+2
        LDA TZ_DATE
                        BNE TZ_R_YEAR_LOW
        DEC TZ_DATE+1
TZ_R_YEAR_LOW:
        DEC TZ_DATE
TZ_R_MONTH:
        JSR TZ_MONTH_DAYS
        STA TZ_DATE+3
        RTS
TZ_MONTH_DAYS:
        LDX TZ_DATE+2
        LDA TZ_MONTHS-1,X
        CPX #2
                        BNE TZ_DAYS_DONE
        LDX TZ_DATE
        CPX #$34             ; 2100 is not a leap year.
                        BEQ TZ_DAYS_DONE
        TXA
        AND #3
                        BNE TZ_FEB_NORMAL
        LDA #29
        RTS
TZ_FEB_NORMAL:
        LDA #28
TZ_DAYS_DONE:
        RTS
TZ_RENDER:
        LDX #<TZ_LOCAL_TEXT
        LDY #>TZ_LOCAL_TEXT
        JSR TZ_PRINT
        LDA TZ_DATE+4
        DEC A
        ASL A
        ASL A
        TAY
        LDX #4
TZ_WEEKDAY_CHAR:
        LDA TZ_WEEKDAYS,Y
        JSR $7E6D
        INY
        DEX
                        BNE TZ_WEEKDAY_CHAR
        LDA TZ_DATE
        CMP #$CF             ; 1999 / 2000..2099 / 2100
                        BNE TZ_YEAR_20
        LDA #'1'
        JSR $7E6D
        LDA #'9'
        JSR $7E6D
        LDA #99
                        BRA TZ_YEAR_LAST
TZ_YEAR_20:
        LDA #'2'
        JSR $7E6D
        LDA #'0'
        LDX TZ_DATE
        CPX #$34
                        BNE TZ_YEAR_PREFIX
        INC A
TZ_YEAR_PREFIX:
        JSR $7E6D
        LDA TZ_DATE
        SEC
        SBC #$D0
        CMP #100
                        BNE TZ_YEAR_LAST
        LDA #0
TZ_YEAR_LAST:
        JSR TZ_DECIMAL
        LDA #'-'
        JSR $7E6D
        LDA TZ_DATE+2
        JSR TZ_DECIMAL
        LDA #'-'
        JSR $7E6D
        LDA TZ_DATE+3
        JSR TZ_DECIMAL
        LDA #' '
        JSR $7E6D
        LDA TZ_DATE+5
        JSR TZ_DECIMAL
        LDA #':'
        JSR $7E6D
        LDA TZ_DATE+6
        JSR TZ_DECIMAL
        LDA #':'
        JSR $7E6D
        LDA TZ_DATE+7
        JSR TZ_DECIMAL
        LDA #' '
        JSR $7E6D
        LDA #'('
        JSR $7E6D
        JSR TZ_OFFSET_TEXT
        LDA #')'
        JMP $7E6D
TZ_DECIMAL:
        LDX #0
TZ_TENS:
        CMP #10
                        BCC TZ_DIGITS
        SBC #10
        INX
                        BRA TZ_TENS
TZ_DIGITS:
        PHA
        TXA
        ORA #'0'
        JSR $7E6D
        PLA
        ORA #'0'
        JMP $7E6D
TZ_PRINT:
        STX TZ_PTR
        STY TZ_PTR+1
        LDY #0
TZ_PRINT_NEXT:
        LDA (TZ_PTR),Y
                        BEQ TZ_PRINT_DONE
        JSR $7E6D
        INY
                        BNE TZ_PRINT_NEXT
TZ_PRINT_DONE:
        RTS
TZ_MAGIC DB "TZ",1,0
TZ_LOCAL_TEXT DB "Local: ",0
TZ_WEEKDAYS DB "Mon Tue Wed Thu Fri Sat Sun "
TZ_MONTHS DB 31,28,31,30,31,30,31,31,30,31,30,31
TZ_OFFSET DS 2
TZ_WORK DS 2
TZ_FREE DS 2
TZ_SEQ DS 4
TZ_SUM DS 2
TZ_FOUND DB 0
TZ_HOURS DB 0
TZ_DATE DS 8

; OFFSET changes only a separate TZ flash record, never RTC/EEPROM registers.
OFFSET_TRY:
        LDX #5
OFFSET_PREFIX_CHECK:
        LDA LINE,X
        CMP OFFSET_WORD,X
                        BEQ CLOCK_LONG_1957
                        JMP OFFSET_NOT_COMMAND
CLOCK_LONG_1957:
        DEX
                        BPL OFFSET_PREFIX_CHECK
        LDA LINE_LENGTH
        CMP #6
                        BNE CLOCK_LONG_1962
                        JMP OFFSET_QUERY
CLOCK_LONG_1962:
        CMP #8
                        BNE OFFSET_SET
        LDA LINE+6
        CMP #' '
                        BEQ CLOCK_LONG_1967
                        JMP OFFSET_BAD
CLOCK_LONG_1967:
        LDA LINE+7
        CMP #'?'
                        BNE CLOCK_LONG_1970
                        JMP OFFSET_QUERY
CLOCK_LONG_1970:
OFFSET_SET:
        LDA LINE_LENGTH
        CMP #13
                        BEQ CLOCK_LONG_1974
                        JMP OFFSET_BAD
CLOCK_LONG_1974:
        LDA LINE+6
        CMP #' '
                        BEQ CLOCK_LONG_1977
                        JMP OFFSET_BAD
CLOCK_LONG_1977:
        LDA LINE+10
        CMP #':'
                        BEQ CLOCK_LONG_1980
                        JMP OFFSET_BAD
CLOCK_LONG_1980:
        LDA LINE+7
        CMP #'+'
                        BEQ OFFSET_SIGN_OK
        CMP #'-'
                        BEQ CLOCK_LONG_1985
                        JMP OFFSET_BAD
CLOCK_LONG_1985:
OFFSET_SIGN_OK:
        STA OFFSET_SIGN
        LDX #8
        JSR PAIR
                        BCS CLOCK_LONG_1990
                        JMP OFFSET_BAD
CLOCK_LONG_1990:
        CMP #15
                        BCC CLOCK_LONG_1992
                        JMP OFFSET_BAD
CLOCK_LONG_1992:
        STA OFFSET_HOUR
        LDX #11
        JSR PAIR
                        BCS CLOCK_LONG_1996
                        JMP OFFSET_BAD
CLOCK_LONG_1996:
        CMP #60
                        BCC CLOCK_LONG_1998
                        JMP OFFSET_BAD
CLOCK_LONG_1998:
        STA OFFSET_PENDING
        STZ OFFSET_PENDING+1
OFFSET_HOUR_ADD:
        LDA OFFSET_HOUR
                        BEQ OFFSET_SIGN_APPLY
        LDA OFFSET_PENDING
        CLC
        ADC #60
        STA OFFSET_PENDING
                        BCC OFFSET_HOUR_LOW
        INC OFFSET_PENDING+1
OFFSET_HOUR_LOW:
        DEC OFFSET_HOUR
                        BRA OFFSET_HOUR_ADD
OFFSET_SIGN_APPLY:
        LDA OFFSET_SIGN
        CMP #'-'
                        BNE OFFSET_VALIDATE
        LDA #0
        SEC
        SBC OFFSET_PENDING
        STA OFFSET_PENDING
        LDA #0
        SBC OFFSET_PENDING+1
        STA OFFSET_PENDING+1
OFFSET_VALIDATE:
        LDA OFFSET_PENDING
        STA TZ_WORK
        LDA OFFSET_PENDING+1
        STA TZ_WORK+1
        JSR TZ_RANGE
                        BCC OFFSET_BAD
        JSR TZ_READ
        LDA OFFSET_PENDING
        CMP TZ_OFFSET
                        BNE OFFSET_CONFIRM
        LDA OFFSET_PENDING+1
        CMP TZ_OFFSET+1
                        BNE OFFSET_CONFIRM
        LDX #<OFFSET_NO_CHANGE
        LDY #>OFFSET_NO_CHANGE
        JMP MESSAGE
OFFSET_CONFIRM:
        LDX #<OFFSET_WARNING
        LDY #>OFFSET_WARNING
        JSR PRINT
        JSR READLINE
                        BCS CLOCK_LONG_2046
                        JMP CANCELED
CLOCK_LONG_2046:
        LDX #<CMD_YES
        LDY #>CMD_YES
        JSR MATCH
                        BCS CLOCK_LONG_2050
                        JMP CANCELED
CLOCK_LONG_2050:
        JSR OFFSET_SAVE
                        BCC OFFSET_FAILED
        JSR OFFSET_SHOW
        JMP MENU
OFFSET_QUERY:
        JSR OFFSET_SHOW
        JMP MENU
OFFSET_BAD: JSR B29_CLOCK_ERROR

        LDX #<OFFSET_BAD_TEXT
        LDY #>OFFSET_BAD_TEXT
        JMP MESSAGE
OFFSET_NOT_COMMAND:
        CLC
        RTS
OFFSET_FAILED: JSR B29_CLOCK_ERROR

        LDX #<OFFSET_FAILURE
        LDY #>OFFSET_FAILURE
        JMP MESSAGE
OFFSET_SHOW:
        JSR TZ_READ
        LDX #<OFFSET_LABEL
        LDY #>OFFSET_LABEL
        JSR PRINT
        JSR TZ_OFFSET_TEXT
        LDX #<OFFSET_NOTE
        LDY #>OFFSET_NOTE
        JMP PRINT
OFFSET_SETUP:
        JSR TZ_READ
        LDA TZ_FOUND
                        BNE OFFSET_SETUP_DONE
        LDX #<OFFSET_SETUP_TEXT
        LDY #>OFFSET_SETUP_TEXT
        JSR PRINT
        JSR READLINE
                        BCC OFFSET_SETUP_DONE
        LDA LINE_LENGTH
                        BEQ OFFSET_SETUP_DONE
        CMP #6
                        BNE OFFSET_BAD
        LDX #6
OFFSET_SETUP_MOVE:
        LDA LINE,X
        STA LINE+7,X
        DEX
                        BPL OFFSET_SETUP_MOVE
        LDX #5
OFFSET_SETUP_WORD:
        LDA OFFSET_WORD,X
        STA LINE,X
        DEX
                        BPL OFFSET_SETUP_WORD
        LDA #' '
        STA LINE+6
        LDA #13
        STA LINE_LENGTH
        JMP OFFSET_SET
OFFSET_SETUP_DONE:
        RTS
OFFSET_SAVE:
        LDA $7FEC
        PHA
        AND #$11
        ORA #$EE
        STA $7FEC
        LDX #3
OFFSET_FORMAT_CHECK:
        LDA $9000,X
        CMP OFFSET_JOURNAL_MAGIC,X
                        BNE OFFSET_FORMAT_BAD
        DEX
                        BPL OFFSET_FORMAT_CHECK
        PLA
        STA $7FEC
        JSR TZ_READ
        LDA TZ_FREE+1
                        BEQ OFFSET_REFUSE
        LDX #3
OFFSET_SEQ_FULL:
        LDA TZ_SEQ,X
        CMP #$FF
                        BNE OFFSET_RECORD
        DEX
                        BPL OFFSET_SEQ_FULL
OFFSET_REFUSE:
        CLC
        RTS
OFFSET_FORMAT_BAD:
        PLA
        STA $7FEC
                        JMP OFFSET_REFUSE
OFFSET_RECORD:
        LDX #31
        LDA #$FF
OFFSET_FILL:
        STA OFFSET_RECORD_BYTES,X
        DEX
                        BPL OFFSET_FILL
        LDX #3
OFFSET_HEADER:
        LDA TZ_MAGIC,X
        STA OFFSET_RECORD_BYTES,X
        DEX
                        BPL OFFSET_HEADER
        INC TZ_SEQ
                        BNE OFFSET_SEQUENCE_READY
        INC TZ_SEQ+1
                        BNE OFFSET_SEQUENCE_READY
        INC TZ_SEQ+2
                        BNE OFFSET_SEQUENCE_READY
        INC TZ_SEQ+3
OFFSET_SEQUENCE_READY:
        LDX #3
OFFSET_SEQUENCE:
        LDA TZ_SEQ,X
        STA OFFSET_RECORD_BYTES+4,X
        DEX
                        BPL OFFSET_SEQUENCE
        LDA OFFSET_PENDING
        STA OFFSET_RECORD_BYTES+8
        LDA OFFSET_PENDING+1
        STA OFFSET_RECORD_BYTES+9
        LDA #<OFFSET_RECORD_BYTES
        STA TZ_PTR
        LDA #>OFFSET_RECORD_BYTES
        STA TZ_PTR+1
        JSR TZ_CRC
        LDA TZ_SUM
        STA OFFSET_RECORD_BYTES+28
        LDA TZ_SUM+1
        STA OFFSET_RECORD_BYTES+29
        LDX #31
OFFSET_SAVE_ZP:
        LDA $E0,X
        STA OFFSET_ZP,X
        DEX
                        BPL OFFSET_SAVE_ZP
        LDA $7FEC
        STA OFFSET_BANK
        AND #$11
        ORA #$EE
        STA $7FEC
        LDA $7FA0
        STA OFFSET_LED
        LDA #3
        STA $F3
        LDA #1
        STA $F4
        STZ OFFSET_INDEX
        STZ OFFSET_ERROR
OFFSET_WRITE:
        LDX OFFSET_INDEX
        LDA OFFSET_RECORD_BYTES,X
        CMP #$FF
                        BEQ OFFSET_NEXT_BYTE
        STA $F0
        TXA
        CLC
        ADC TZ_FREE
        STA $E4
        LDA TZ_FREE+1
        ADC #0
        STA $E5
        JSR OFFSET_FLASH_BYTE
                        BCC OFFSET_WRITE_FAILED
OFFSET_NEXT_BYTE:
        INC OFFSET_INDEX
        LDA OFFSET_INDEX
        CMP #31
                        BNE OFFSET_WRITE
        LDA TZ_FREE
        STA TZ_PTR
        LDA TZ_FREE+1
        STA TZ_PTR+1
        LDY #30
OFFSET_VERIFY:
        LDA (TZ_PTR),Y
        CMP OFFSET_RECORD_BYTES,Y
                        BNE OFFSET_WRITE_FAILED
        DEY
                        BPL OFFSET_VERIFY
        LDA TZ_FREE
        CLC
        ADC #31
        STA $E4
        LDA TZ_FREE+1
        ADC #0
        STA $E5
        STZ $F0
        JSR OFFSET_FLASH_BYTE
                        BCC OFFSET_WRITE_FAILED
        LDY #31
        LDA (TZ_PTR),Y
                        BNE OFFSET_WRITE_FAILED
                        BRA OFFSET_RESTORE
OFFSET_WRITE_FAILED: JSR B29_CLOCK_ERROR

        INC OFFSET_ERROR
OFFSET_RESTORE:
        LDA OFFSET_LED
        STA $7FA0
        LDA OFFSET_BANK
        STA $7FEC
        LDX #31
OFFSET_RESTORE_ZP:
        LDA OFFSET_ZP,X
        STA $E0,X
        DEX
                        BPL OFFSET_RESTORE_ZP
        LDA OFFSET_ERROR
                        BEQ CLOCK_LONG_2260
                        JMP OFFSET_REFUSE
CLOCK_LONG_2260:
        JSR TZ_READ
        LDA TZ_OFFSET
        CMP OFFSET_PENDING
                        BEQ CLOCK_LONG_2264
                        JMP OFFSET_REFUSE
CLOCK_LONG_2264:
        LDA TZ_OFFSET+1
        CMP OFFSET_PENDING+1
                        BEQ CLOCK_LONG_2267
                        JMP OFFSET_REFUSE
CLOCK_LONG_2267:
        SEC
        RTS
OFFSET_WORD DB "OFFSET"
OFFSET_JOURNAL_MAGIC DB "PJ",6,1
OFFSET_LABEL DB "Local UTC offset: ",0
OFFSET_SETUP_TEXT DB "Local UTC offset +/-HH:MM (Enter keeps +00:00): ",0
OFFSET_NOTE DB " (fixed; adjust manually for daylight saving)",13,10,0
OFFSET_WARNING DB "Save display offset? UTC and clock settings stay unchanged.",13,10,"Type YES to confirm: ",0
OFFSET_BAD_TEXT DB "Use OFFSET +/-HH:MM (-12:00 through +14:00), OFFSET or OFFSET ?.",13,10,0
OFFSET_NO_CHANGE DB "No change.",13,10,0
OFFSET_FAILURE DB "Offset not saved. Record area full or write failed; no erase attempted.",13,10,0
OFFSET_PENDING DS 2
OFFSET_SIGN DB 0
OFFSET_HOUR DB 0
OFFSET_BANK DB 0
OFFSET_LED DB 0
OFFSET_INDEX DB 0
OFFSET_ERROR DB 0
OFFSET_RECORD_BYTES DS 32
OFFSET_ZP DS 32

; CLOCK opening summary. All device and record operations here are read-only.
UI_SUMMARY:
        JSR BN_READ
        LDA BN_LENGTH
                        BEQ UI_UNNAMED
        JSR BN_SHOW
                        BRA UI_BOARD_DONE
UI_UNNAMED:
        LDX #<UI_UNNAMED_TEXT
        LDY #>UI_UNNAMED_TEXT
        JSR PRINT
UI_BOARD_DONE:
        JSR NL
        JSR READ_CLOCK
        JSR UI_OFFSET
        JSR NL
        JSR RTC_STATUS
                        BCC UI_STATUS_ERROR
        JSR UI_FLAGS
        JSR UI_POWERFAIL
                        BRA UI_IDENTITY
UI_STATUS_ERROR: JSR B29_CLOCK_ERROR

        JSR ERROR
UI_IDENTITY:
        JSR EUI_SHOW
        JSR BT_PROCESS
        JSR NL
        LDX #<UI_COMMANDS
        LDY #>UI_COMMANDS
        JSR PRINT
        JMP MENU
UI_OFFSET:
        JSR TZ_READ
        LDX #<UI_OFFSET_TEXT
        LDY #>UI_OFFSET_TEXT
        JSR PRINT
        JSR TZ_OFFSET_TEXT
        LDX #<UI_FIXED_TEXT
        LDY #>UI_FIXED_TEXT
        JMP PRINT
UI_WEEKDAY:
        LDA DISPLAY+4
        DEC A
        ASL A
        ASL A
        TAY
        LDX #4
UI_WEEKDAY_NEXT:
        LDA TZ_WEEKDAYS,Y
        JSR PUTC
        INY
        DEX
                        BNE UI_WEEKDAY_NEXT
        RTS
UI_FLAGS:
        LDX #<UI_RTCC_TEXT
        LDY #>UI_RTCC_TEXT
        JSR PRINT
        LDA RTC_FLAGS
        AND #RTC_F_RUNNING
                        BEQ UI_STOPPED
        LDX #<UI_RUNNING_TEXT
        LDY #>UI_RUNNING_TEXT
                        BRA UI_RUNNING_READY
UI_STOPPED:
        LDX #<UI_STOPPED_TEXT
        LDY #>UI_STOPPED_TEXT
UI_RUNNING_READY:
        JSR PRINT
        LDA RTC_FLAGS
        AND #RTC_F_CALENDAR
                        BEQ UI_INVALID
        LDX #<UI_VALID_TEXT
        LDY #>UI_VALID_TEXT
                        BRA UI_VALID_READY
UI_INVALID:
        LDX #<UI_INVALID_TEXT
        LDY #>UI_INVALID_TEXT
UI_VALID_READY:
        JSR PRINT
        LDA RTC_FLAGS
        AND #RTC_F_BACKUP_ENABLED
                        BEQ UI_NO_BACKUP
        LDX #<UI_BACKUP_TEXT
        LDY #>UI_BACKUP_TEXT
        JMP PRINT
UI_NO_BACKUP:
        LDX #<UI_NO_BACKUP_TEXT
        LDY #>UI_NO_BACKUP_TEXT
        JMP PRINT
UI_POWERFAIL:
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
                        BNE UI_LATCHED
        LDX #<UI_NO_EVENT_TEXT
        LDY #>UI_NO_EVENT_TEXT
        JMP PRINT
UI_LATCHED:
        LDX #<UI_EVENT_TEXT
        LDY #>UI_EVENT_TEXT
        JSR PRINT
        LDA #<RTC_OUTAGE
        STA OF_PTR
        LDA #>RTC_OUTAGE
        STA OF_PTR+1
        JSR OUTAGE_PRETTY
        LDX #<UI_EVENT_HINT
        LDY #>UI_EVENT_HINT
        JMP PRINT
UI_UNNAMED_TEXT DB "Board: unnamed",13,10,0
UI_OFFSET_TEXT DB "Offset: ",0
UI_FIXED_TEXT DB " fixed (manual DST)",13,10,0
UI_RTCC_TEXT DB "RTCC: ",0
UI_RUNNING_TEXT DB "Running",0
UI_STOPPED_TEXT DB "STOPPED",0
UI_VALID_TEXT DB " | Calendar valid",0
UI_INVALID_TEXT DB " | Calendar INVALID",0
UI_BACKUP_TEXT DB " | Backup enabled",13,10,0
UI_NO_BACKUP_TEXT DB " | Backup DISABLED",13,10,0
UI_NO_EVENT_TEXT DB "Power-fail: None latched",13,10,0
UI_EVENT_TEXT DB "Power-fail: LATCHED (UTC)",13,10,0
UI_EVENT_HINT DB "Use ACK to save and acknowledge this event.",13,10,0
UI_COMMANDS DB "TIME  STATUS  HISTORY  HELP  Q",13,10,0

UI_EUI_MATCH_TEXT DB " (matches remembered)",0
; BN,1,0; sequence LE32; length 0..8; eight zero-padded printable bytes;
; reserved FF through byte 27; CRC16 LE at 28; FF at 30; commit 0 at 31.
; Shared append-only EI/TZ tail. Uncommitted and malformed slots stay occupied.
BN_READ:
        STZ BN_LENGTH
        STZ BN_FREE+1
        LDX #3
BN_RESET:
        STZ BN_SEQ,X
        DEX
                        BPL BN_RESET
        LDA $7FEC
        PHA
        AND #$11
        ORA #$EE
        STA $7FEC
        STZ TZ_PTR
        LDA #$9C
        STA TZ_PTR+1
BN_SLOT:
        LDY #0
BN_BLANK:
        LDA (TZ_PTR),Y
        CMP #$FF
                        BNE BN_CHECK
        INY
        CPY #32
                        BNE BN_BLANK
        LDA BN_FREE+1
                        BEQ CLOCK_LONG_2443
                        JMP BN_NEXT
CLOCK_LONG_2443:
        LDA TZ_PTR
        STA BN_FREE
        LDA TZ_PTR+1
        STA BN_FREE+1
                        JMP BN_NEXT
BN_CHECK:
        LDY #31
        LDA (TZ_PTR),Y
                        BEQ CLOCK_LONG_2452
                        JMP BN_NEXT
CLOCK_LONG_2452:
        LDY #3
BN_HEADER:
        LDA (TZ_PTR),Y
        CMP BN_MAGIC,Y
                        BNE BN_NEXT
        DEY
                        BPL BN_HEADER
        JSR TZ_CRC
        LDY #28
        LDA (TZ_PTR),Y
        CMP TZ_SUM
                        BNE BN_NEXT
        INY
        LDA (TZ_PTR),Y
        CMP TZ_SUM+1
                        BNE BN_NEXT
        LDY #8
        LDA (TZ_PTR),Y
        CMP #9
                        BCS BN_NEXT
        STA BN_WORK
        TAX
BN_CHAR_CHECK:
        INY
        CPY #17
                        BEQ BN_NEWEST
        LDA (TZ_PTR),Y
        CPX #0
                        BEQ BN_PADDING
        CMP #$21
                        BCC BN_NEXT
        CMP #$7F
                        BCS BN_NEXT
        DEX
                        JMP BN_CHAR_CHECK
BN_PADDING:
        CMP #0
                        BNE BN_NEXT
                        JMP BN_CHAR_CHECK
BN_NEWEST:
        LDY #7
        LDX #3
BN_NEWER:
        LDA (TZ_PTR),Y
        CMP BN_SEQ,X
                        BCC BN_NEXT
                        BNE BN_KEEP
        DEY
        DEX
                        BPL BN_NEWER
BN_KEEP:
        LDY #7
        LDX #3
BN_COPY_SEQ:
        LDA (TZ_PTR),Y
        STA BN_SEQ,X
        DEY
        DEX
                        BPL BN_COPY_SEQ
        LDA BN_WORK
        STA BN_LENGTH
        LDY #9
        LDX #0
BN_COPY:
        LDA (TZ_PTR),Y
        STA BN_TEXT,X
        INY
        INX
        CPX #8
                        BNE BN_COPY
BN_NEXT:
        LDA TZ_PTR
        CLC
        ADC #32
        STA TZ_PTR
                        BCC BN_PAGE
        INC TZ_PTR+1
BN_PAGE:
        LDA TZ_PTR+1
        CMP #$A0
                        BEQ CLOCK_LONG_2533
                        JMP BN_SLOT
CLOCK_LONG_2533:
        PLA
        STA $7FEC
        RTS
BN_SHOW:
        JSR BN_READ
        LDA BN_LENGTH
                        BEQ BN_SHOW_DONE
        LDX #<BN_LABEL
        LDY #>BN_LABEL
        JSR PRINT
        LDX #0
BN_PRINT:
        LDA BN_TEXT,X
        JSR $7E6D
        INX
        CPX BN_LENGTH
                        BNE BN_PRINT
        JSR $7E7F
BN_SHOW_DONE:
        RTS
BN_MAGIC DB "BN",1,0
BN_LABEL DB "Board: ",0
BN_LENGTH DB 0
BN_WORK DB 0
BN_TEXT DS 8
BN_SEQ DS 4
BN_FREE DS 2

BT_FLASH_BYTE EQU $7B03
; BA v1: sequence LE32; install day LE16 since 2000-01-01, warning/replacement
; in 30-day months, highest stage (0/1/2/3 uncertain), high-water day LE16.
; CRC16 LE at 28, commit zero at 31. Shared EI/TZ/BN append-only tail.
BT_READ:
        STZ BT_FOUND
        STZ BT_FREE+1
        LDX #3
BT_ZERO:
        STZ BT_SEQ,X
        DEX
                        BPL BT_ZERO
        LDA $7FEC
        PHA
        AND #$11
        ORA #$EE
        STA $7FEC
        STZ TZ_PTR
        LDA #$9C
        STA TZ_PTR+1
BT_SLOT:
        LDY #0
BT_BLANK:
        LDA (TZ_PTR),Y
        CMP #$FF
                        BNE BT_CHECK
        INY
        CPY #32
                        BNE BT_BLANK
        LDA BT_FREE+1
                        BEQ CLOCK_LONG_2592
                        JMP BT_NEXT
CLOCK_LONG_2592:
        LDA TZ_PTR
        STA BT_FREE
        LDA TZ_PTR+1
        STA BT_FREE+1
                        JMP BT_NEXT
BT_CHECK:
        LDY #31
        LDA (TZ_PTR),Y
                        BEQ CLOCK_LONG_2601
                        JMP BT_NEXT
CLOCK_LONG_2601:
        LDY #3
BT_HEADER:
        LDA (TZ_PTR),Y
        CMP BT_MAGIC,Y
                        BEQ CLOCK_LONG_2606
                        JMP BT_NEXT
CLOCK_LONG_2606:
        DEY
                        BPL BT_HEADER
        JSR TZ_CRC
        LDY #28
        LDA (TZ_PTR),Y
        CMP TZ_SUM
                        BEQ CLOCK_LONG_2613
                        JMP BT_NEXT
CLOCK_LONG_2613:
        INY
        LDA (TZ_PTR),Y
        CMP TZ_SUM+1
                        BNE BT_NEXT
        LDY #10
        LDA (TZ_PTR),Y
                        BEQ BT_NEXT
        CMP #99
                        BCS BT_NEXT
        INY
        CMP (TZ_PTR),Y
                        BCS BT_NEXT
        LDA (TZ_PTR),Y
        CMP #100
                        BCS BT_NEXT
        INY
        LDA (TZ_PTR),Y
        CMP #4
                        BCS BT_NEXT
        ; Both dates must fit 2000-2099; high-water cannot precede install.
        LDY #14
        LDA (TZ_PTR),Y
        CMP #$8E
                        BCC BT_DATE_RANGE
                        BNE BT_NEXT
        DEY
        LDA (TZ_PTR),Y
        CMP #$AD
                        BCS BT_NEXT
BT_DATE_RANGE:
        LDY #9
        LDA (TZ_PTR),Y
        LDY #14
        CMP (TZ_PTR),Y
                        BCC BT_NEWEST
                        BNE BT_NEXT
        LDY #8
        LDA (TZ_PTR),Y
        LDY #13
        CMP (TZ_PTR),Y
                        BCC BT_NEWEST
                        BNE BT_NEXT
BT_NEWEST:
        LDY #7
        LDX #3
BT_NEWER:
        LDA (TZ_PTR),Y
        CMP BT_SEQ,X
                        BCC BT_NEXT
                        BNE BT_KEEP
        DEY
        DEX
                        BPL BT_NEWER
BT_KEEP:
        LDY #7
        LDX #3
BT_COPY_SEQ:
        LDA (TZ_PTR),Y
        STA BT_SEQ,X
        DEY
        DEX
                        BPL BT_COPY_SEQ
        LDY #8
        LDX #0
BT_COPY:
        LDA (TZ_PTR),Y
        STA BT_PAYLOAD,X
        INY
        INX
        CPX #7
                        BNE BT_COPY
        LDA #1
        STA BT_FOUND
BT_NEXT:
        LDA TZ_PTR
        CLC
        ADC #32
        STA TZ_PTR
                        BCC BT_PAGE
        INC TZ_PTR+1
BT_PAGE:
        LDA TZ_PTR+1
        CMP #$A0
                        BEQ CLOCK_LONG_2697
                        JMP BT_SLOT
CLOCK_LONG_2697:
        PLA
        STA $7FEC
        RTS
; Validated binary Gregorian Y offset 0..99, month/day -> ordinal day.
BT_DATE:
        STZ BT_DAYNUM
        STZ BT_DAYNUM+1
        LDX #0
BT_YEARS:
        CPX BT_YEAR
                        BEQ BT_MONTHS
        LDA #$6D
        CLC
        ADC BT_DAYNUM
        STA BT_DAYNUM
        LDA BT_DAYNUM+1
        ADC #1
        STA BT_DAYNUM+1
        TXA
        AND #3
                        BNE BT_YEAR_NEXT
        INC BT_DAYNUM
                        BNE BT_YEAR_NEXT
        INC BT_DAYNUM+1
BT_YEAR_NEXT:
        INX
                        BRA BT_YEARS
BT_MONTHS:
        LDX #1
BT_MONTH_LOOP:
        CPX BT_MONTH
                        BEQ BT_ADD_DAY
        LDA BT_MONTH_LENGTH-1,X
        CPX #2
                        BNE BT_MONTH_ADD
        PHA
        LDA BT_YEAR
        AND #3
                        BNE BT_NO_LEAP
        PLA
        INC A
                        BRA BT_MONTH_ADD
BT_NO_LEAP:
        PLA
BT_MONTH_ADD:
        CLC
        ADC BT_DAYNUM
        STA BT_DAYNUM
                        BCC BT_MONTH_NEXT
        INC BT_DAYNUM+1
BT_MONTH_NEXT:
        INX
                        BRA BT_MONTH_LOOP
BT_ADD_DAY:
        LDA BT_DAY
        DEC A
        CLC
        ADC BT_DAYNUM
        STA BT_DAYNUM
                        BCC BT_DATE_DONE
        INC BT_DAYNUM+1
BT_DATE_DONE:
        RTS
BT_NOW:
        STZ BT_VALID
        LDA $7D2A
                        BEQ BT_NOW_DONE
        JSR $6504
                        BCC BT_NOW_DONE
        LDA $66C1
        AND #$16
        CMP #$16
                        BNE BT_NOW_DONE
        LDA $66C2
        SEC
        SBC #$D0
        STA BT_YEAR
        LDA $66C3
        SBC #7
                        BNE BT_NOW_DONE
        LDA BT_YEAR
        CMP #100
                        BCS BT_NOW_DONE
        LDA $66C4
        STA BT_MONTH
        LDA $66C5
        STA BT_DAY
        JSR BT_DATE
        LDA BT_DAYNUM
        STA BT_TODAY
        LDA BT_DAYNUM+1
        STA BT_TODAY+1
        INC BT_VALID
BT_NOW_DONE:
        RTS
BT_PENDING_COPY:
        LDX #6
BT_PENDING_LOOP:
        LDA BT_PAYLOAD,X
        STA BT_PENDING,X
        DEX
                        BPL BT_PENDING_LOOP
        RTS
; Latch only stage changes. No daily/monthly counter writes or erases.
BT_PROCESS:
        JSR BT_READ
        JSR BT_NOW
        LDA BT_FOUND
                        BNE CLOCK_LONG_2806
                        JMP BT_UNKNOWN
CLOCK_LONG_2806:
        JSR BT_PENDING_COPY
        LDA BT_VALID
                        BEQ BT_UNCERTAIN
        LDA BT_TODAY
        SEC
        SBC BT_PAYLOAD+5
        LDA BT_TODAY+1
        SBC BT_PAYLOAD+6
                        BCC BT_UNCERTAIN
        LDA BT_TODAY
        SEC
        SBC BT_PAYLOAD
        STA BT_AGE
        LDA BT_TODAY+1
        SBC BT_PAYLOAD+1
        STA BT_AGE+1
        STZ BT_MONTH_AGE
BT_DIVIDE:
        LDA BT_AGE+1
                        BNE BT_SUBTRACT
        LDA BT_AGE
        CMP #30
                        BCC BT_COMPARE
BT_SUBTRACT:
        LDA BT_AGE
        SEC
        SBC #30
        STA BT_AGE
        LDA BT_AGE+1
        SBC #0
        STA BT_AGE+1
        INC BT_MONTH_AGE
        LDA BT_MONTH_AGE
        CMP #100
                        BNE BT_DIVIDE
BT_COMPARE:
        LDX #0
        LDA BT_MONTH_AGE
        CMP BT_PAYLOAD+2
                        BCC BT_STAGE
        INX
        CMP BT_PAYLOAD+3
                        BCC BT_STAGE
        INX
                        BRA BT_STAGE
BT_UNCERTAIN:
        LDX #3
BT_STAGE:
        CPX BT_PAYLOAD+4
                        BCC BT_DISPLAY
                        BEQ BT_DISPLAY
        STX BT_PENDING+4
        LDA BT_VALID
                        BEQ BT_LATCH
        LDA BT_TODAY
        SEC
        SBC BT_PAYLOAD+5
        LDA BT_TODAY+1
        SBC BT_PAYLOAD+6
                        BCC BT_LATCH
        LDA BT_TODAY
        STA BT_PENDING+5
        LDA BT_TODAY+1
        STA BT_PENDING+6
BT_LATCH:
        JSR BT_SAVE
                        BCS BT_DISPLAY
        LDX #<BT_SAVE_ERROR
        LDY #>BT_SAVE_ERROR
        JSR PRINT
        ; Report the newly observed warning even if persistence failed.
        LDA BT_PENDING+4
        STA BT_PAYLOAD+4
BT_DISPLAY:
        LDA BT_PAYLOAD+4
                        BEQ BT_YOUNG
        CMP #1
                        BEQ BT_WARNING
        CMP #2
                        BEQ BT_DUE
        LDX #<BT_UNCERTAIN_TEXT
        LDY #>BT_UNCERTAIN_TEXT
                        JMP BT_PRINT
BT_YOUNG:
        LDX #<BT_YOUNG_TEXT
        LDY #>BT_YOUNG_TEXT
                        JMP BT_PRINT
BT_WARNING:
        LDX #<BT_WARNING_TEXT
        LDY #>BT_WARNING_TEXT
                        JMP BT_PRINT
BT_DUE:
        LDX #<BT_DUE_TEXT
        LDY #>BT_DUE_TEXT
                        JMP BT_PRINT
BT_UNKNOWN:
        LDX #<BT_UNKNOWN_TEXT
        LDY #>BT_UNKNOWN_TEXT
BT_PRINT:
        JMP PRINT
BT_MAGIC DB "BA",1,0
BT_MONTH_LENGTH DB 31,28,31,30,31,30,31,31,30,31,30,31
BT_UNKNOWN_TEXT DB "Battery age unknown. Back up SSRAM; use CLOCK BATTERY.",13,10,0
BT_YOUNG_TEXT DB "Battery: within age policy; condition unknown.",13,10,0
BT_WARNING_TEXT DB "Battery reminder: back up SSRAM; plan replacement.",13,10,0
BT_DUE_TEXT DB "Battery replacement due. Back up SSRAM before replacement.",13,10,0
BT_UNCERTAIN_TEXT DB "Battery age uncertain. Back up SSRAM; check clock/battery.",13,10,0
BT_SAVE_ERROR DB "Battery record not saved (full/incompatible/write failed); no erase.",13,10,0
BT_FOUND DB 0
BT_FREE DS 2
BT_SEQ DS 4
BT_PAYLOAD DS 7
BT_PENDING DS 7
BT_YEAR DB 0
BT_MONTH DB 0
BT_DAY DB 0
BT_DAYNUM DS 2
BT_TODAY DS 2
BT_VALID DB 0
BT_AGE DS 2
BT_MONTH_AGE DB 0
BT_SAVE:
        LDA $7FEC
        PHA
        AND #$11
        ORA #$EE
        STA $7FEC
        LDX #3
BT_FORMAT_CHECK:
        LDA $9000,X
        CMP BT_JOURNAL_MAGIC,X
                        BNE BT_FORMAT_BAD
        DEX
                        BPL BT_FORMAT_CHECK
        PLA
        STA $7FEC
        JSR BT_READ
        LDA BT_FREE+1
                        BEQ BT_REFUSE
        LDX #3
BT_SEQ_FULL:
        LDA BT_SEQ,X
        CMP #$FF
                        BNE BT_RECORD
        DEX
                        BPL BT_SEQ_FULL
BT_REFUSE:
        CLC
        RTS
BT_FORMAT_BAD:
        PLA
        STA $7FEC
                        JMP BT_REFUSE
BT_RECORD:
        LDX #31
        LDA #$FF
BT_FILL:
        STA BT_RECORD_BYTES,X
        DEX
                        BPL BT_FILL
        LDX #3
BT_RECORD_HEADER:
        LDA BT_MAGIC,X
        STA BT_RECORD_BYTES,X
        DEX
                        BPL BT_RECORD_HEADER
        INC BT_SEQ
                        BNE BT_SEQUENCE_READY
        INC BT_SEQ+1
                        BNE BT_SEQUENCE_READY
        INC BT_SEQ+2
                        BNE BT_SEQUENCE_READY
        INC BT_SEQ+3
BT_SEQUENCE_READY:
        LDX #3
BT_SEQUENCE:
        LDA BT_SEQ,X
        STA BT_RECORD_BYTES+4,X
        DEX
                        BPL BT_SEQUENCE
        LDX #6
BT_PAYLOAD_COPY:
        LDA BT_PENDING,X
        STA BT_RECORD_BYTES+8,X
        DEX
                        BPL BT_PAYLOAD_COPY
        LDA #<BT_RECORD_BYTES
        STA TZ_PTR
        LDA #>BT_RECORD_BYTES
        STA TZ_PTR+1
        JSR TZ_CRC
        LDA TZ_SUM
        STA BT_RECORD_BYTES+28
        LDA TZ_SUM+1
        STA BT_RECORD_BYTES+29
        LDX #31
BT_SAVE_ZP:
        LDA $E0,X
        STA BT_ZP,X
        DEX
                        BPL BT_SAVE_ZP
        LDA $7FEC
        STA BT_BANK
        AND #$11
        ORA #$EE
        STA $7FEC
        LDA $7FA0
        STA BT_LED
        LDA #3
        STA $F3
        LDA #1
        STA $F4
        STZ BT_INDEX
        STZ BT_ERROR
BT_WRITE:
        LDX BT_INDEX
        LDA BT_RECORD_BYTES,X
        CMP #$FF
                        BEQ BT_NEXT_BYTE
        STA $F0
        TXA
        CLC
        ADC BT_FREE
        STA $E4
        LDA BT_FREE+1
        ADC #0
        STA $E5
        JSR BT_FLASH_BYTE
                        BCC BT_WRITE_FAILED
BT_NEXT_BYTE:
        INC BT_INDEX
        LDA BT_INDEX
        CMP #31
                        BNE BT_WRITE
        LDA BT_FREE
        STA TZ_PTR
        LDA BT_FREE+1
        STA TZ_PTR+1
        LDY #30
BT_VERIFY:
        LDA (TZ_PTR),Y
        CMP BT_RECORD_BYTES,Y
                        BNE BT_WRITE_FAILED
        DEY
                        BPL BT_VERIFY
        LDA BT_FREE
        CLC
        ADC #31
        STA $E4
        LDA BT_FREE+1
        ADC #0
        STA $E5
        STZ $F0
        JSR BT_FLASH_BYTE
                        BCC BT_WRITE_FAILED
        LDY #31
        LDA (TZ_PTR),Y
                        BNE BT_WRITE_FAILED
                        BRA BT_RESTORE
BT_WRITE_FAILED:
        INC BT_ERROR
BT_RESTORE:
        LDA BT_LED
        STA $7FA0
        LDA BT_BANK
        STA $7FEC
        LDX #31
BT_RESTORE_ZP:
        LDA BT_ZP,X
        STA $E0,X
        DEX
                        BPL BT_RESTORE_ZP
        LDA BT_ERROR
                        BEQ CLOCK_LONG_3080
                        JMP BT_REFUSE
CLOCK_LONG_3080:
        JSR BT_READ
        LDA BT_FOUND
                        BNE CLOCK_LONG_3083
                        JMP BT_REFUSE
CLOCK_LONG_3083:
        LDX #6
BT_READBACK:
        LDA BT_PAYLOAD,X
        CMP BT_PENDING,X
                        BEQ CLOCK_LONG_3088
                        JMP BT_REFUSE
CLOCK_LONG_3088:
        DEX
                        BPL BT_READBACK
        SEC
        RTS
BT_JOURNAL_MAGIC DB "PJ",6,1
BT_BANK DB 0
BT_LED DB 0
BT_INDEX DB 0
BT_ERROR DB 0
BT_RECORD_BYTES DS 32
BT_ZP DS 32
; Whole-word command recognition. Only explicit replacement resets a latch.
BT_TRY:
        LDX #6
BT_WORD_MATCH:
        LDA LINE,X
        CMP BT_WORD,X
                        BEQ CLOCK_LONG_3106
                        JMP BT_NOT_COMMAND
CLOCK_LONG_3106:
        DEX
                        BPL BT_WORD_MATCH
        LDA LINE_LENGTH
        CMP #7
                        BNE CLOCK_LONG_3111
                        JMP BT_QUERY
CLOCK_LONG_3111:
        LDA LINE+7
        CMP #' '
                        BEQ CLOCK_LONG_3114
                        JMP BT_BAD
CLOCK_LONG_3114:
        JSR CHECK_SERVICE
                        BCS CLOCK_LONG_3116
                        JMP NO_SERVICE
CLOCK_LONG_3116:
        JSR BT_READ
        LDA LINE_LENGTH
        CMP #20
                        BNE CLOCK_LONG_3120
                        JMP BT_LIMITS
CLOCK_LONG_3120:
        CMP #16
                        BNE BT_INSTALL_DATE
        LDX #7
BT_REPLACED_MATCH:
        LDA LINE+8,X
        CMP BT_REPLACED_WORD,X
                        BEQ CLOCK_LONG_3127
                        JMP BT_BAD
CLOCK_LONG_3127:
        DEX
                        BPL BT_REPLACED_MATCH
        JSR BT_NOW
        LDA BT_VALID
                        BNE CLOCK_LONG_3132
                        JMP BT_BAD_CLOCK
CLOCK_LONG_3132:
                        JMP BT_INSTALL
BT_INSTALL_DATE:
        CMP #18
                        BEQ CLOCK_LONG_3136
                        JMP BT_BAD
CLOCK_LONG_3136:
        LDX #0
BT_MOVE_DATE:
        LDA LINE+8,X
        STA LINE+4,X
        INX
        CPX #10
                        BNE BT_MOVE_DATE
        LDX #3
BT_SET_PREFIX:
        LDA BT_SET_WORD,X
        STA LINE,X
        DEX
                        BPL BT_SET_PREFIX
        LDX #8
BT_MIDNIGHT:
        LDA BT_ZERO_TIME,X
        STA LINE+14,X
        DEX
                        BPL BT_MIDNIGHT
        LDA #23
        STA LINE_LENGTH
        JSR PARSE_SET
                        BCS CLOCK_LONG_3159
                        JMP BT_BAD
CLOCK_LONG_3159:
        JSR BT_NOW
        LDA BT_VALID
                        BNE CLOCK_LONG_3162
                        JMP BT_BAD_CLOCK
CLOCK_LONG_3162:
        LDA YEAR_OFFSET
        STA BT_YEAR
        LDA REQUEST+2
        STA BT_MONTH
        LDA REQUEST+3
        STA BT_DAY
        JSR BT_DATE
        LDA BT_DAYNUM
        SEC
        SBC BT_TODAY
        LDA BT_DAYNUM+1
        SBC BT_TODAY+1
                        BCC BT_DATE_ACCEPT
                        BEQ CLOCK_LONG_3176
                        JMP BT_BAD
CLOCK_LONG_3176:
        LDA BT_DAYNUM
        CMP BT_TODAY
                        BEQ CLOCK_LONG_3179
                        JMP BT_BAD
CLOCK_LONG_3179:
BT_DATE_ACCEPT:
        LDA BT_DAYNUM
        STA BT_TODAY
        LDA BT_DAYNUM+1
        STA BT_TODAY+1
BT_INSTALL:
        JSR BT_PENDING_COPY
        LDA BT_FOUND
                        BNE BT_KEEP_LIMITS
        LDA #12
        STA BT_PENDING+2
        LDA #24
        STA BT_PENDING+3
BT_KEEP_LIMITS:
        LDA BT_TODAY
        STA BT_PENDING
        STA BT_PENDING+5
        LDA BT_TODAY+1
        STA BT_PENDING+1
        STA BT_PENDING+6
        STZ BT_PENDING+4
                        BRA BT_CONFIRM
BT_LIMITS:
        LDA BT_FOUND
                        BNE CLOCK_LONG_3204
                        JMP BT_BAD
CLOCK_LONG_3204:
        LDX #6
BT_LIMITS_MATCH:
        LDA LINE+8,X
        CMP BT_LIMITS_WORD,X
                        BEQ CLOCK_LONG_3209
                        JMP BT_BAD
CLOCK_LONG_3209:
        DEX
                        BPL BT_LIMITS_MATCH
        LDA LINE+17
        CMP #' '
                        BEQ CLOCK_LONG_3214
                        JMP BT_BAD
CLOCK_LONG_3214:
        JSR BT_PENDING_COPY
        LDX #15
        JSR PAIR
                        BCC BT_BAD
                        BEQ BT_BAD
        STA BT_PENDING+2
        LDX #18
        JSR PAIR
                        BCC BT_BAD
        CMP BT_PENDING+2
                        BCC BT_BAD
                        BEQ BT_BAD
        STA BT_PENDING+3
BT_CONFIRM:
        LDX #<BT_CONFIRM_TEXT
        LDY #>BT_CONFIRM_TEXT
        JSR PRINT
        JSR READLINE
                        BCS CLOCK_LONG_3233
                        JMP CANCELED
CLOCK_LONG_3233:
        LDX #<CMD_YES
        LDY #>CMD_YES
        JSR MATCH
                        BCS CLOCK_LONG_3237
                        JMP CANCELED
CLOCK_LONG_3237:
        JSR BT_SAVE
                        BCC BT_FAILED
BT_QUERY:
        JSR CHECK_SERVICE
                        BCS CLOCK_LONG_3242
                        JMP NO_SERVICE
CLOCK_LONG_3242:
        JSR BT_PROCESS
        LDA BT_FOUND
                        BEQ BT_MENU
        LDX #<BT_LIMIT_LABEL
        LDY #>BT_LIMIT_LABEL
        JSR PRINT
        LDA BT_PAYLOAD+2
        JSR DECIMAL_2
        LDA #'/'
        JSR PUTC
        LDA BT_PAYLOAD+3
        JSR DECIMAL_2
        LDX #<BT_MONTH_NOTE
        LDY #>BT_MONTH_NOTE
        JSR PRINT
BT_MENU:
        JMP MENU
BT_FAILED: JSR B29_CLOCK_ERROR

        LDX #<BT_SAVE_ERROR
        LDY #>BT_SAVE_ERROR
        JMP MESSAGE
BT_BAD_CLOCK:
        LDX #<BT_CLOCK_TEXT
        LDY #>BT_CLOCK_TEXT
        JMP MESSAGE
BT_BAD: JSR B29_CLOCK_ERROR

        LDX #<BT_USAGE
        LDY #>BT_USAGE
        JMP MESSAGE
BT_NOT_COMMAND:
        CLC
        RTS
BT_WORD DB "BATTERY"
BT_REPLACED_WORD DB "REPLACED"
BT_LIMITS_WORD DB "LIMITS "
BT_SET_WORD DB "SET "
BT_ZERO_TIME DB " 00:00:00"
BT_CONFIRM_TEXT DB "Record battery date/policy? Back up SSRAM first. Type YES: ",0
BT_LIMIT_LABEL DB "Warning/replacement: ",0
BT_MONTH_NOTE DB " months (30 days each); age policy, not measured health.",13,10,0
BT_CLOCK_TEXT DB "Battery date needs running valid UTC and backup enabled.",13,10,0
BT_USAGE DB "BATTERY | BATTERY REPLACED | BATTERY yyyy-mm-dd",13,10
        DB "BATTERY LIMITS ww rr (01..99 months, ww < rr)",13,10,0

; Batchfix-r1 capability ABI: BA means checked UX/3/42 provider + new gate.
; B9 is accepted only on legacy B monitors, retaining their existing contract.
B29_CLOCK_VALID:
        LDA $7D30
        AND #$EF
        CMP #$A0
        BNE B29_CLOCK_NO
        LDA $7EF4
        CMP #$BA
        BEQ BFX_CLOCK_GATE
        CMP #$B9
        BNE B29_CLOCK_NO
        LDA $7D30
        CMP #$B0
        BNE B29_CLOCK_NO
BFX_CLOCK_GATE:
        LDA $7C94
        CMP #$A9
        BNE B29_CLOCK_NO
        LDA $7C9F
        CMP #$8D
        BNE B29_CLOCK_NO
        SEC
        RTS
B29_CLOCK_NO: CLC
        RTS
B29_CLOCK_LINE:
        JSR B29_CLOCK_VALID
        BCC B29_CLOCK_OLD
        JMP $7C94
B29_CLOCK_OLD: JMP READLINE
B29_CLOCK_ERROR:
        PHP
        PHA
        JSR B29_CLOCK_VALID
        BCC B29_CLOCK_ERROR_DONE
        LDA $7EE7
        CMP #2
        BEQ B29_CLOCK_ERROR_DONE
        JSR $7C98
B29_CLOCK_ERROR_DONE:
        PLA
        PLP
        RTS
B29_CLOCK_CANCEL:
        PHP
        PHA
        JSR B29_CLOCK_VALID
        BCC B29_CLOCK_CANCEL_DONE
        LDA #2
        STA $7EE7
B29_CLOCK_CANCEL_DONE:
        PLA
        PLP
        RTS
D_MIN DB 0
D_HOUR DB 0
D_DAY DB 0
D_MONTH DB 0
D_YEAR DB 0
D_VALID DB 0
D_DAYS DB 0
D_DAYS_HI DB 0
D_HUNDREDS DB 0
D_KIND DB 0
D_CLOCK_UP:
        JSR OF_FORMAT
        SEC
        LDA OF_PTR
        SBC #4
        STA OF_PTR
                        BCS D_CLOCK_PTR
        DEC OF_PTR+1
D_CLOCK_PTR:
        LDA D_HIST
                        BEQ D_LIVE_YEAR
        STZ D_HIST
        LDY #20
        LDA (H_PTR),Y
        STA D_YEAR
        LDY #22
        LDA OF_MONTH
        CMP (H_PTR),Y
                        BCC D_CAPTURE_YEAR
                        BNE D_CAPTURE_PREV
        INY
        LDA OF_DAY
        CMP (H_PTR),Y
                        BCC D_CAPTURE_YEAR
                        BEQ D_CAPTURE_YEAR
D_CAPTURE_PREV:
        DEC D_YEAR
D_CAPTURE_YEAR:
        LDY #24
        LDA (H_PTR),Y
        AND #$80
                        BRA D_YEAR_READY
D_LIVE_YEAR:
        LDA RTC_TIME
        STA D_YEAR
        LDA OF_MONTH
        CMP RTC_TIME+2
                        BCC D_LIVE_READY
                        BNE D_LIVE_PREV
        LDA OF_DAY
        CMP RTC_TIME+3
                        BCC D_LIVE_READY
                        BEQ D_LIVE_READY
D_LIVE_PREV:
        DEC D_YEAR
D_LIVE_READY:
        LDA RTC_FLAGS
        AND #7
        CMP #7
        LDA #0
        ROL A
D_YEAR_READY:
        STA D_VALID
        STZ D_KIND
        JMP D_PRINT
STATS:
        LDA #1
        STA S_STATS
        STZ S_SEEN
        LDX #<S_NOTE
        LDY #>S_NOTE
        JSR PRINT
        JMP HISTORY
S_GAP:
        LDA S_STATS
                        BNE C35_LONG_65
                        JMP S_GAP_DONE
C35_LONG_65:
        LDA S_SEEN
                        BNE C35_LONG_67
                        JMP S_REMEMBER
C35_LONG_67:
        STZ S_OK
        LDA S_VALID
                        BEQ S_GAP_CHECKED
        LDY #24
        LDA (H_PTR),Y
                        BPL S_GAP_CHECKED
        LDY #20
        LDA S_TIME
        SEC
        SBC (H_PTR),Y
        STA D_HUNDREDS
        INY
        LDA S_TIME+1
        SBC (H_PTR),Y
                        BNE S_GAP_CHECKED
        LDA D_HUNDREDS
        CMP #2
                        BCS S_GAP_CHECKED
        CMP #1
                        BNE S_COMPARE
        LDY #22
        LDA S_TIME+2
        CMP (H_PTR),Y
                        BCC S_COMPARE
                        BNE S_GAP_CHECKED
        INY
        LDA S_TIME+3
        CMP (H_PTR),Y
                        BEQ S_COMPARE
                        BCS S_GAP_CHECKED
S_COMPARE:
        LDX #6
S_COMPARE_NEXT:
        LDY S_ORDER,X
        LDA (H_PTR),Y
        CMP S_TIME-20,Y
                        BCC S_CHRONOLOGICAL
                        BNE S_GAP_CHECKED
        DEX
                        BPL S_COMPARE_NEXT
                        BRA S_GAP_CHECKED
S_CHRONOLOGICAL:
        LDA #$80
        STA S_OK
S_GAP_CHECKED:
        LDY #3
S_COPY_PAIR:
        LDA S_DOWN,Y
        STA S_PACKET+4,Y
        TYA
        CLC
        ADC #16
        TAX
        PHY
        TXA
        TAY
        LDA (H_PTR),Y
        PLY
        STA S_PACKET,Y
        DEY
                        BPL S_COPY_PAIR
        LDA #<S_PACKET
        STA OF_PTR
        LDA #>S_PACKET
        STA OF_PTR+1
        LDA S_YEAR
        STA D_YEAR
        LDA S_OK
        STA D_VALID
        LDA #1
        STA D_KIND
        JSR D_PRINT
        JSR NL
S_REMEMBER:
        LDY #27
S_TIME_COPY:
        LDA (H_PTR),Y
        STA S_TIME-20,Y
        DEY
        CPY #19
                        BNE S_TIME_COPY
        LDY #0
S_COPY_DOWN:
        TYA
        CLC
        ADC #12
        TAX
        PHY
        TXA
        TAY
        LDA (H_PTR),Y
        PLY
        STA S_DOWN,Y
        INY
        CPY #4
                        BNE S_COPY_DOWN
        LDY #20
        LDA (H_PTR),Y
        STA S_YEAR
        LDY #24
        LDA (H_PTR),Y
        AND #$80
        STA S_VALID
        LDY #19
        LDA (H_PTR),Y
        AND #$1F
        STA S_MONTH
        JSR OF_BCD
        LDY #22
        CMP (H_PTR),Y
                        BCC S_UP_YEAR
                        BNE S_UP_PREVIOUS
        LDY #18
        LDA (H_PTR),Y
        AND #$3F
        JSR OF_BCD
        LDY #23
        CMP (H_PTR),Y
                        BCC S_UP_YEAR
                        BEQ S_UP_YEAR
S_UP_PREVIOUS:
        DEC S_YEAR
S_UP_YEAR:
        LDA S_DOWN+3
        AND #$1F
        CMP S_MONTH
                        BCC S_READY
                        BNE S_PREV_YEAR
        LDY #18
        LDA (H_PTR),Y
        AND #$3F
        STA S_MONTH
        LDA S_DOWN+2
        AND #$3F
        CMP S_MONTH
                        BCC S_READY
                        BEQ S_READY
S_PREV_YEAR:
        DEC S_YEAR
S_READY:
        LDA #1
        STA S_SEEN
S_GAP_DONE:
        RTS
S_MENU_PROMPT:
        STZ S_STATS
        STZ D_HIST
        LDX #<PROMPT
        LDY #>PROMPT
        JMP PRINT
S_TRY:
        JSR OFFSET_TRY
        LDX #<S_COMMAND
        LDY #>S_COMMAND
        JSR MATCH
                        BCC S_NOT_COMMAND
        JMP STATS
S_NOT_COMMAND:
        RTS
S_HISTORY_POINTER:
        JSR HISTORY_POINTER
        JMP S_GAP
S_HISTORY_OUTAGE:
        LDA #1
        STA D_HIST
        JMP OUTAGE_PRETTY
S_COMMAND DB "STATS",0
S_NOTE DB "Recent estimates: minutes; year inferred; <1yr assumed.",13,10,0
S_STATS DB 0
S_SEEN DB 0
S_YEAR DB 0
S_VALID DB 0
S_MONTH DB 0
S_OK DB 0
S_ORDER DB 27,26,25,23,22,20,21
S_TIME DS 8
S_DOWN DS 4
S_PACKET DS 8
D_HIST DB 0
        INCLUDE "outage-duration.inc"
APP_END:
        ENDMOD
        END
