; NAME [1..8 non-space printable characters | CLEAR]. READLINE canonicalizes case.
; Recognize the whole word before the existing N (new-sector buffer) command.
BN_TRY:
        LDX #3
BN_COMMAND_WORD:
        LDA BM_LINE,X
        CMP BN_WORD,X
        BNE BN_NOT_COMMAND
        DEX
        BPL BN_COMMAND_WORD
        LDA LINELEN
        CMP #4
        BEQ BN_QUERY
        LDA BM_LINE+4
        CMP #' '
        BNE BN_BAD
        LDA LINELEN
        SEC
        SBC #5
        BEQ BN_BAD
        CMP #9
        BCS BN_BAD
        STA BN_PENDING_LENGTH
        LDX #7
BN_ZERO_PENDING:
        STZ BN_PENDING,X
        DEX
        BPL BN_ZERO_PENDING
        LDX #0
BN_ARGUMENT:
        LDA BM_LINE+5,X
        CMP #$21
        BCC BN_BAD
        CMP #$7F
        BCS BN_BAD
        STA BN_PENDING,X
        INX
        CPX BN_PENDING_LENGTH
        BNE BN_ARGUMENT
        LDA BN_PENDING_LENGTH
        CMP #5
        BNE BN_PREPARE
        LDX #4
BN_CLEAR_WORD:
        LDA BN_PENDING,X
        CMP BN_CLEAR_TEXT,X
        BNE BN_PREPARE
        DEX
        BPL BN_CLEAR_WORD
        STZ BN_PENDING_LENGTH
        LDX #7
BN_CLEAR_PENDING:
        STZ BN_PENDING,X
        DEX
        BPL BN_CLEAR_PENDING
BN_PREPARE:
        JSR BN_READ
        LDA BN_PENDING_LENGTH
        CMP BN_LENGTH
        BNE BN_CONFIRM
        BEQ BN_COMPARE_START
BN_COMPARE_START:
        TAX
        BEQ BN_QUERY
        DEX
BN_COMPARE:
        LDA BN_PENDING,X
        CMP BN_TEXT,X
        BNE BN_CONFIRM
        DEX
        BPL BN_COMPARE
        BRA BN_QUERY
BN_CONFIRM:
        LDX #<BN_WARNING
        LDY #>BN_WARNING
        JSR PRINT
        JSR READLINE
        BCC BM_CANCEL
        LDA LINELEN
        CMP #3
        BNE BM_CANCEL
        LDX #2
BN_YES:
        LDA BM_LINE,X
        CMP BN_YES_TEXT,X
        BNE BM_CANCEL
        DEX
        BPL BN_YES
        JSR BN_SAVE
        BCC BN_FAILED
BN_QUERY:
        JSR BN_SHOW
        LDA BN_LENGTH
        BNE BN_MENU
        LDX #<BN_UNNAMED
        LDY #>BN_UNNAMED
        JSR PRINT
BN_MENU:
        JMP BM_MENU
BN_BAD:
        LDX #<BN_USAGE
        LDY #>BN_USAGE
        JMP MESSAGE
BN_FAILED:
        LDX #<BN_FAILURE
        LDY #>BN_FAILURE
        JMP MESSAGE
BN_NOT_COMMAND:
        CLC
        RTS
BN_WORD DB "NAME"
BN_CLEAR_TEXT DB "CLEAR"
BN_YES_TEXT DB "YES"
BN_WARNING DB "Save board name? Type YES: ",0
BN_USAGE DB "NAME [1-8 characters | CLEAR]",13,10,0
BN_UNNAMED DB "Board: unnamed",13,10,0
BN_FAILURE DB "Name not saved; full, incompatible or write failed. No erase.",13,10,0
BN_PENDING_LENGTH DB 0
BN_PENDING DS 8
