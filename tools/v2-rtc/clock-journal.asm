; CLOCK 1.1. Read-only views; explicit confirmed SET and outage ACK.
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
START:
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
        BCC NO_SERVICE
        JSR READ_CLOCK
        JMP HELP
UNSUPPORTED:
        JMP UNSUPPORTED       ; No calls through an unverified console ABI.
MENU:
        LDX #$FF
        TXS
        LDX #<PROMPT
        LDY #>PROMPT
        JSR PRINT
        JSR READLINE
        BCC CANCELED
        LDA LINE_LENGTH
        BEQ MENU
        LDX #<CMD_Q
        LDY #>CMD_Q
        JSR MATCH
        BCS QUIT
        LDX #<CMD_QUIT
        LDY #>CMD_QUIT
        JSR MATCH
        BCS QUIT
        LDX #<CMD_HELP
        LDY #>CMD_HELP
        JSR MATCH
        BCS HELP
        LDX #<CMD_QUESTION
        LDY #>CMD_QUESTION
        JSR MATCH
        BCS HELP
        LDX #<CMD_HISTORY
        LDY #>CMD_HISTORY
        JSR MATCH
        BCS HISTORY
        LDX #<CMD_CLEAR_ALL
        LDY #>CMD_CLEAR_ALL
        JSR MATCH
        BCS HISTORY_CLEAR_ALL
        JSR HISTORY_PARSE
        BCS HISTORY_DISPATCH
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
        BCS SET_COMMAND
BAD_COMMAND:
        LDX #<BAD_TEXT
        LDY #>BAD_TEXT
        JMP MESSAGE
NO_SERVICE:
        LDX #<NO_SERVICE_TEXT
        LDY #>NO_SERVICE_TEXT
        JMP MESSAGE
CANCELED:
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
        BCC ERROR
        JSR COPY_TIME
        LDX #<UTC_TEXT
        LDY #>UTC_TEXT
        JSR PRINT
        JSR FORMAT_TIME
        JSR NL
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
        BEQ READ_DONE
        LDX #<LATCHED_TEXT
        LDY #>LATCHED_TEXT
        JSR PRINT
READ_DONE:
        RTS
STATUS_COMMAND:
        JSR RTC_STATUS
        BCC STATUS_ERROR
        JSR SHOW_STATUS
        JMP MENU
STATUS_ERROR:
        JSR ERROR
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
ACK_FAILED:
        JSR ERROR
ACK_VERIFY_FAILED:
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
        BNE ALARMS_ENABLED
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
        BCC CANCELED
        LDX #<CMD_YES
        LDY #>CMD_YES
        JSR MATCH
        BCC CANCELED
        LDX #7
        STZ H_SAVED
        JSR RTC_STATUS
        BCC STATUS_ERROR
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
        BEQ STAGE_TIME
        LDX #J_SAVE_OP
        JSR HISTORY_CALL
        BCC HISTORY_ERROR
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
        JMP MENU
ALARMS_ENABLED:
        LDX #<ALARMS_TEXT
        LDY #>ALARMS_TEXT
        JMP MESSAGE
SET_FAILED:
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
CHECK_FAILED:
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
        JSR OF_FORMAT
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
        BNE PARSE_BAD
        LDX #10
PARSE_FIXED:
        LDY FIXED_POS,X
        LDA LINE,Y
        CMP FIXED_CHAR,X
        BNE PARSE_BAD
        DEX
        BPL PARSE_FIXED
        LDX #6
        JSR PAIR
        BCC PARSE_BAD
        STA YEAR_OFFSET
        CLC
        ADC #$D0
        STA REQUEST
        LDA #7
        ADC #0
        STA REQUEST+1
        LDX #9
        JSR PAIR
        BCC PARSE_BAD
        CMP #1
        BCC PARSE_BAD
        CMP #13
        BCS PARSE_BAD
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
        BCC PARSE_BAD
        CMP #1
        BCC PARSE_BAD
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
        BRA LINE_WAIT
LINE_FULL:
        LDA #1
        STA OVERFLOW
        BRA LINE_WAIT
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
        BRA LINE_WAIT
LINE_DONE:
        LDX LINE_LENGTH
        STZ LINE,X
        JSR NL
        LDA OVERFLOW
        BNE LINE_CANCEL
        SEC
        RTS
LINE_CANCEL:
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
        BNE HISTORY_CLEAR
        LDX #J_SCAN_OP
        JSR HISTORY_CALL
        BCC HISTORY_ERROR
        LDX H_SELECTED
        LDA H_MASKS,X
        AND J_VALID
        BEQ HISTORY_EMPTY
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
        BCC HISTORY_ERROR
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
        BCC CANCELED
        LDX #<CMD_YES
        LDY #>CMD_YES
        JSR MATCH
        BCC CANCELED
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
        BCC CANCELED
        LDX #<CMD_DELETE_ALL
        LDY #>CMD_DELETE_ALL
        JSR MATCH
        BCC CANCELED
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
        JSR HISTORY_POINTER
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
        JMP OUTAGE_PRETTY
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
SHOW_PREFIX DB "SHOW "
CLEAR_PREFIX DB "CLEAR "
H_SIGNATURE DB "PJ",1,1,4,$90,0,$6B
H_MASKS DB 1,2,4,8
H_EMPTY_TEXT DB "No saved event in requested history.",13,10,0
H_ERROR_TEXT DB "History unavailable/error ",0
H_SLOT_TEXT DB "Slot ",0
H_SEQ_TEXT DB " seq ",0
H_PENDING_TEXT DB " - latch clearance unconfirmed",13,10,0
H_ACKED_TEXT DB " - latch cleared",13,10,0
H_CAPTURE_TEXT DB "Recorded at (UTC convention): ",0
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
TITLE DB "CLOCK 1.2 - UTC",13,10,0
PROMPT DB "CLOCK> ",0
HELP_TEXT DB "R/TIME S/STATUS ACK SET yyyy-mm-dd hh:mm:ss Q/QUIT",13,10,"HISTORY SHOW n CLEAR n CLEAR ALL (slots 1-4)",13,10,"SET/ACK/CLEAR require confirmation; years 2000-2099.",13,10,0
UTC_TEXT DB "UTC ",0
CALENDAR_TEXT DB "Calendar (UTC convention): ",0
BAD_TEXT DB "Invalid command/date. Use SET yyyy-mm-dd hh:mm:ss or HELP.",13,10,0
NO_SERVICE_TEXT DB "RTC software unavailable.",13,10,0
CANCELED_TEXT DB "Canceled.",13,10,0
LATCHED_TEXT DB "Power-fail evidence is latched; S shows details.",13,10,0
START_TEXT DB "Oscillator start: ",0
RUNNING_TEXT DB "Running: ",0
VALID_TEXT DB "Calendar valid: ",0
BACKUP_TEXT DB "Backup enabled: ",0
POWERFAIL_TEXT DB "Power-fail latched: ",0
CONTINUITY_TEXT DB "Time continuity and battery condition: unknown",13,10,0
RAW_TEXT DB "RTC registers (raw): ",0
OUTAGE_TEXT DB "Power-fail down/up (raw, minute precision): ",0
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
CAPTURE_NOTE DB "Captured outage (RTC time; no year/seconds):",13,10,0
DOWN_TEXT DB "Power down: ",0
UP_TEXT DB "Power up:   ",0
YES_TEXT DB "yes",13,10,0
NO_TEXT DB "no",13,10,0
ERROR_TEXT DB "RTC error ",0
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
APP_END:
        ENDMOD
        END
