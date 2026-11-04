; Session selection and confirmed append-only ED/1. No erase or RTC access.
MB_EDU_PENDING EQU $6270
MB_EDU_SAVE EQU $6271
MB_EDU_COMMAND:
        LDA BQ_MAGIC
        CMP #BQ_ON
        BEQ MB_EDU_BAD
        STZ MB_EDU_SAVE
        JSR MM_SPACES
        BEQ MB_EDU_SHOW
        CMP #'S'
        BNE MB_EDU_MODE
        LDX #<MB_EDU_SAVE_WORD
        LDY #>MB_EDU_SAVE_WORD
        JSR MB_MATCH
        BCC MB_EDU_BAD
        INC MB_EDU_SAVE
        JSR MM_SPACES
MB_EDU_MODE:
        CMP #'O'
        BNE MB_EDU_BAD
        INC MM_INDEX
        LDX MM_INDEX
        LDA MM_BM_LINE,X
        CMP #'N'
        BEQ MB_EDU_ON
        CMP #'F'
        BNE MB_EDU_BAD
        INX
        LDA MM_BM_LINE,X
        CMP #'F'
        BNE MB_EDU_BAD
        LDA #0
        BRA MB_EDU_MODE_END
MB_EDU_ON:
        LDA #1
MB_EDU_MODE_END:
        STA MB_EDU_PENDING
        INX
        STX MM_INDEX
        JSR MM_ENDLINE
        BCC MB_EDU_BAD
        LDA MB_EDU_SAVE
        BEQ MB_EDU_SESSION
        JSR MB_EDU_ADMIT
        BCC MB_EDU_FAILED
        JSR BE_READ
        BCC MB_EDU_FAILED
        LDA BE_FOUND
        BEQ MB_EDU_CONFIRM
        LDA BE_MODE
        CMP MB_EDU_PENDING
        BEQ MB_EDU_SESSION
MB_EDU_CONFIRM:
        LDX #<MB_EDU_CONFIRM_TEXT
        LDY #>MB_EDU_CONFIRM_TEXT
        JSR MM_PRINT
        JSR MM_READLINE
        BCC MM_BM_CANCEL
        LDA MM_LINELEN
        CMP #3
        BNE MM_BM_CANCEL
        LDX #2
MB_EDU_YES:
        LDA MM_BM_LINE,X
        CMP MM_BN_YES_TEXT,X
        BNE MM_BM_CANCEL
        DEX
        BPL MB_EDU_YES
        JSR MB_EDU_APPEND
        BCC MB_EDU_FAILED
MB_EDU_SESSION:
        LDA MB_EDU_PENDING
        STA MU_EDU
        STA $6520 ; saved MON session restored by Q
MB_EDU_SHOW:
        LDA $6520
        JSR MB_EDU_PRINT_MODE
        LDX #<MB_EDU_SAVED_TEXT
        LDY #>MB_EDU_SAVED_TEXT
        JSR MM_PRINT
        JSR BE_READ
        BCC MB_EDU_FAILED
        JSR MB_EDU_PRINT_MODE
        JMP MM_BM_MENU
MB_EDU_PRINT_MODE:
        PHA
        LDX #<MB_EDU_OFF_TEXT
        LDY #>MB_EDU_OFF_TEXT
        PLA
        BEQ MB_EDU_PRINT
        LDX #<MB_EDU_ON_TEXT
        LDY #>MB_EDU_ON_TEXT
MB_EDU_PRINT:
        JMP MM_PRINT
MB_EDU_ADMIT:
        LDA #3
        JSR MM_V2W_SELECT
        LDX #3
MB_EDU_FORMAT:
        LDA MB_META_FORMAT,X
        CMP MM_BN_JOURNAL_MAGIC,X
        BNE MB_EDU_ADMIT_BAD
        DEX
        BPL MB_EDU_FORMAT
        SEC
        RTS
MB_EDU_ADMIT_BAD:
        CLC
        RTS
MB_EDU_APPEND:
        JSR MB_EDU_ADMIT
        BCC MB_EDU_ADMIT_BAD
        JSR BE_READ
        BCC MB_EDU_ADMIT_BAD
        LDA BE_SEQ
        AND BE_SEQ+1
        AND BE_SEQ+2
        AND BE_SEQ+3
        CMP #$FF
        BEQ MB_EDU_ADMIT_BAD
        JSR MM_BN_READ ; only a wholly erased slot is eligible
        LDA MM_BN_FREE+1
        BEQ MB_EDU_ADMIT_BAD
        LDX #31
        LDA #$FF
MB_EDU_FILL:
        STA MM_BN_RECORD_BYTES,X
        DEX
        BPL MB_EDU_FILL
        LDX #3
MB_EDU_HEADER:
        LDA BE_RECORD_MAGIC,X
        STA MM_BN_RECORD_BYTES,X
        DEX
        BPL MB_EDU_HEADER
        INC BE_SEQ
        BNE MB_EDU_SEQ_READY
        INC BE_SEQ+1
        BNE MB_EDU_SEQ_READY
        INC BE_SEQ+2
        BNE MB_EDU_SEQ_READY
        INC BE_SEQ+3
MB_EDU_SEQ_READY:
        LDX #3
MB_EDU_SEQUENCE:
        LDA BE_SEQ,X
        STA MM_BN_RECORD_BYTES+4,X
        DEX
        BPL MB_EDU_SEQUENCE
        LDA MB_EDU_PENDING
        STA MM_BN_RECORD_BYTES+8
        LDA #<MM_BN_RECORD_BYTES
        STA MM_TZ_PTR
        LDA #>MM_BN_RECORD_BYTES
        STA MM_TZ_PTR+1
        JSR MM_TZ_CRC
        LDA MM_TZ_SUM
        STA MM_BN_RECORD_BYTES+28
        LDA MM_TZ_SUM+1
        STA MM_BN_RECORD_BYTES+29
        JSR MB_META_PROGRAM
        BCC MB_EDU_ADMIT_BAD
        JSR BE_READ
        BCC MB_EDU_ADMIT_BAD
        CMP MB_EDU_PENDING
        BNE MB_EDU_ADMIT_BAD
        SEC
        RTS
MB_EDU_BAD:
        LDX #<MB_EDU_USAGE
        LDY #>MB_EDU_USAGE
        JMP MM_MESSAGE
MB_EDU_FAILED:
        JSR B29_ERROR_HOOK
        LDX #<MB_EDU_FAILED_TEXT
        LDY #>MB_EDU_FAILED_TEXT
        JMP MM_MESSAGE
MB_EDU_WORD: DB "EDU",0
MB_EDU_SAVE_WORD: DB "EDU SAVE",0
MB_EDU_USAGE: DB "EDU [ON|OFF] / EDU SAVE ON|OFF (YES)",13,10,0
MB_EDU_CONFIRM_TEXT: DB "Save EDU mode? Type YES: ",0
MB_EDU_SAVED_TEXT: DB "Saved/default: ",0
MB_EDU_ON_TEXT: DB "EDU ON",13,10,0
MB_EDU_OFF_TEXT: DB "EDU OFF",13,10,0
MB_EDU_FAILED_TEXT: DB "EDU not saved: full/conflict/format/write. No erase.",13,10,0
        INCLUDE "bank-edu-reader.inc"
