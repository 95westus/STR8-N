; Whole-word command recognition. Only explicit replacement resets a latch.
BT_TRY:
        LDX #6
BT_WORD_MATCH:
        LDA LINE,X
        CMP BT_WORD,X
        BNE BT_NOT_COMMAND
        DEX
        BPL BT_WORD_MATCH
        LDA LINE_LENGTH
        CMP #7
        BEQ BT_QUERY
        LDA LINE+7
        CMP #' '
        BNE BT_BAD
        JSR CHECK_SERVICE
        BCC NO_SERVICE
        JSR BT_READ
        LDA LINE_LENGTH
        CMP #20
        BEQ BT_LIMITS
        CMP #16
        BNE BT_INSTALL_DATE
        LDX #7
BT_REPLACED_MATCH:
        LDA LINE+8,X
        CMP BT_REPLACED_WORD,X
        BNE BT_BAD
        DEX
        BPL BT_REPLACED_MATCH
        JSR BT_NOW
        LDA BT_VALID
        BEQ BT_BAD_CLOCK
        BRA BT_INSTALL
BT_INSTALL_DATE:
        CMP #18
        BNE BT_BAD
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
        BCC BT_BAD
        JSR BT_NOW
        LDA BT_VALID
        BEQ BT_BAD_CLOCK
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
        BNE BT_BAD
        LDA BT_DAYNUM
        CMP BT_TODAY
        BNE BT_BAD
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
        BEQ BT_BAD
        LDX #6
BT_LIMITS_MATCH:
        LDA LINE+8,X
        CMP BT_LIMITS_WORD,X
        BNE BT_BAD
        DEX
        BPL BT_LIMITS_MATCH
        LDA LINE+17
        CMP #' '
        BNE BT_BAD
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
        BCC CANCELED
        LDX #<CMD_YES
        LDY #>CMD_YES
        JSR MATCH
        BCC CANCELED
        JSR BT_SAVE
        BCC BT_FAILED
BT_QUERY:
        JSR CHECK_SERVICE
        BCC NO_SERVICE
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
BT_FAILED:
        LDX #<BT_SAVE_ERROR
        LDY #>BT_SAVE_ERROR
        JMP MESSAGE
BT_BAD_CLOCK:
        LDX #<BT_CLOCK_TEXT
        LDY #>BT_CLOCK_TEXT
        JMP MESSAGE
BT_BAD:
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
