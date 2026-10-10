; Saved per-board EDU mode. No calls or accesses to service RAM $6500-$66FF.
        MODULE EDU
        XDEF START
        XDEF APP_END
        INCLUDE "edu-fixed.inc"
PTR EQU $D0
CFG EQU $7D80
PUTC EQU $7E6D
GETC EQU $7E70
        CODE
START:  SEI
        CLD
        LDA $7FEC
        STA OLD_BANK
        AND #$11
        ORA #$EE
        STA $7FEC
        LDX #3
CHECK:  LDA EDU_MAGIC_ADDRESS,X
        CMP MAGIC,X
        BNE ABSENT
        DEX
        BPL CHECK
        LDA $7D27
        BEQ ABSENT
        CMP #3
        BCS ABSENT
        LDX #<TITLE
        LDY #>TITLE
        JSR PRINT
PROMPT: LDX #<PROMPT_TEXT
        LDY #>PROMPT_TEXT
        JSR PRINT
        JSR READ_LINE
        BCC PROMPT
        LDA LINE
        BEQ PROMPT
        CMP #'O'
        BEQ SET_MODE
        LDA LINE+1
        BNE BAD
        LDA LINE
        CMP #'Q'
        BEQ QUIT
        CMP #'?'
        BNE BAD
        JSR READ_CONFIG
        BCC CONFIG_BAD
        LDX #<ACTIVE_TEXT
        LDY #>ACTIVE_TEXT
        JSR PRINT
        LDA $7D27
        CMP #2
        JSR MODE_TEXT
        LDX #<SAVED_TEXT
        LDY #>SAVED_TEXT
        JSR PRINT
        LDA CFG+13
        CMP #$A5
        JSR MODE_TEXT
        BRA PROMPT
SET_MODE:
        LDA LINE+1
        CMP #'N'
        BEQ SET_ON
        CMP #'F'
        BNE BAD
        LDA LINE+2
        CMP #'F'
        BNE BAD
        LDA LINE+3
        BNE BAD
        LDA #$A5
        BRA SET_TARGET
SET_ON: LDA LINE+2
        BNE BAD
SET_TARGET:
        STA TARGET
        JSR READ_CONFIG
        BCC CONFIG_BAD
        LDA CFG+13
        CMP TARGET
        BNE CONFIRM
        LDX #<UNCHANGED_TEXT
        LDY #>UNCHANGED_TEXT
        BRA MESSAGE
CONFIRM:
        LDX #<SAVED_TEXT
        LDY #>SAVED_TEXT
        JSR PRINT
        LDA TARGET
        CMP #$A5
        JSR MODE_TEXT
        LDX #<CONFIRM_TEXT
        LDY #>CONFIRM_TEXT
        JSR PRINT
        JSR READ_LINE
        BCC CANCEL
        LDA LINE
        CMP #'Y'
        BNE CANCEL
        LDA LINE+1
        BNE CANCEL
        LDA TARGET
        STA CFG+13
        ; The validated format remains 1. EF50 computes F6/F7 even when the
        ; changed mode makes the old checksum disagree; publish the new sums.
        JSR EDU_CONFIG_ENTRY
        LDA $F6
        STA CFG+14
        LDA $F7
        STA CFG+15
        JSR BOOT_API_PROMOTE
        BCC SAVE_BAD
        JSR READ_CONFIG
        BCC SAVE_BAD
        LDA CFG+13
        CMP TARGET
        BNE SAVE_BAD
        STA $7D28
        LDX #<SAVED_OK
        LDY #>SAVED_OK
        BRA MESSAGE
CANCEL: LDX #<CANCEL_TEXT
        LDY #>CANCEL_TEXT
        BRA MESSAGE
BAD:    LDX #<BAD_TEXT
        LDY #>BAD_TEXT
        BRA MESSAGE
CONFIG_BAD:
        LDX #<CONFIG_TEXT
        LDY #>CONFIG_TEXT
        BRA MESSAGE
SAVE_BAD:
        LDX #<FAILED_TEXT
        LDY #>FAILED_TEXT
MESSAGE:
        JSR PRINT
        JMP PROMPT
ABSENT: LDX #<ABSENT_TEXT
        LDY #>ABSENT_TEXT
        JSR PRINT
QUIT:   LDA OLD_BANK
        STA $7FEC
        JMP $7E67
READ_CONFIG:
        JSR BOOT_API_READ
        BCC RETURN
        JMP EDU_CONFIG_ENTRY
MODE_TEXT:
        BNE MODE_ON
        LDX #<OFF_TEXT
        LDY #>OFF_TEXT
        BRA PRINT
MODE_ON:
        LDX #<ON_TEXT
        LDY #>ON_TEXT
PRINT:  STX PTR
        STY PTR+1
        LDY #0
PRINT_NEXT:
        LDA (PTR),Y
        BEQ RETURN
        JSR PUTC
        INY
        BRA PRINT_NEXT
RETURN: RTS
READ_LINE:
        STZ COUNT
        STZ OVERFLOW
READ_NEXT:
        JSR GETC
        CMP #3
        BEQ READ_CANCEL
        CMP #$1B
        BEQ READ_CANCEL
        CMP #10
        BEQ READ_NEXT
        CMP #13
        BEQ READ_DONE
        CMP #'a'
        BCC READ_CHAR
        CMP #'z'+1
        BCS READ_CHAR
        AND #$DF
READ_CHAR:
        LDX COUNT
        CPX #7
        BCS READ_FULL
        STA LINE,X
        INC COUNT
        JSR PUTC
        BRA READ_NEXT
READ_FULL:
        LDA #1
        STA OVERFLOW
        BRA READ_NEXT
READ_DONE:
        LDX COUNT
        STZ LINE,X
        JSR $7E7F
        LDA OVERFLOW
        BNE READ_CANCEL
        SEC
        RTS
READ_CANCEL:
        JSR $7E7F
        CLC
        RTS
MAGIC DB "ED",1,1
TITLE DB "EDU 1.0",13,10,"? status; ON OFF Q",13,10,0
PROMPT_TEXT DB "EDU> ",0
ACTIVE_TEXT DB "EDU active: ",0
SAVED_TEXT DB "EDU saved: ",0
OFF_TEXT DB "OFF",13,10,0
ON_TEXT DB "ON",13,10,0
CONFIRM_TEXT DB "Apply after RESET? [y/N]: ",0
UNCHANGED_TEXT DB "No change.",13,10,0
SAVED_OK DB "Saved; RESET required.",13,10,0
CANCEL_TEXT DB "Canceled.",13,10,0
BAD_TEXT DB "Use ? ON OFF Q.",13,10,0
CONFIG_TEXT DB "No valid startup settings.",13,10,0
FAILED_TEXT DB "Save failed.",13,10,0
ABSENT_TEXT DB "EDU mode software unavailable.",13,10,0
LINE DS 8
COUNT DB 0
OVERFLOW DB 0
TARGET DB 0
OLD_BANK DB 0
APP_END:
        ENDMOD
