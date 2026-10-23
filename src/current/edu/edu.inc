; Saved per-board EDU mode. No calls or accesses to service RAM $6500-$66FF.
ED_PTR EQU $D0
ED_CFG EQU $7D80
ED_PUTC EQU $7E6D
ED_GETC EQU $7E70
ED_START:  SEI
        CLD
        LDX #3
ED_CHECK:  JSR X28_R0
        CMP ED_MAGIC,X
                        BEQ ED_BM_LONG_20
                        JMP ED_ABSENT
ED_BM_LONG_20:
        DEX
                        BPL ED_CHECK
        LDA $7D27
                        BNE ED_BM_LONG_24
                        JMP ED_ABSENT
ED_BM_LONG_24:
        CMP #3
                        BCC ED_BM_LONG_26
                        JMP ED_ABSENT
ED_BM_LONG_26:
        LDX #<ED_TITLE
        LDY #>ED_TITLE
        JSR ED_PRINT
        LDA #1
        JSR X28_C1
        LDX #<ED_COMMAND_TEXT
        LDY #>ED_COMMAND_TEXT
        JSR ED_PRINT
ED_PROMPT: LDX #<ED_PROMPT_TEXT
        LDY #>ED_PROMPT_TEXT
        JSR ED_PRINT
        JSR B29_LINE_4
                        BCC ED_PROMPT
        LDA ED_LINE
                        BEQ ED_PROMPT
        CMP #'O'
                        BEQ ED_SET_MODE
        LDA ED_LINE+1
                        BEQ ED_BM_LONG_45
                        JMP ED_BAD
ED_BM_LONG_45:
        LDA ED_LINE
        CMP #'Q'
                        BNE ED_BM_LONG_48
                        JMP ED_QUIT
ED_BM_LONG_48:
        CMP #'?'
                        BEQ ED_BM_LONG_50
                        JMP ED_BAD
ED_BM_LONG_50:
        LDA #1
        JSR X28_C1
                        JMP ED_PROMPT
ED_SET_MODE:
        LDA ED_LINE+1
        CMP #'N'
                        BEQ ED_SET_ON
        CMP #'F'
                        BNE ED_BAD
        LDA ED_LINE+2
        CMP #'F'
                        BNE ED_BAD
        LDA ED_LINE+3
                        BNE ED_BAD
        LDA #$A5
                        BRA ED_SET_TARGET
ED_SET_ON: LDA ED_LINE+2
                        BNE ED_BAD
ED_SET_TARGET:
        STA ED_TARGET
        JSR ED_READ_CONFIG
                        BCC ED_CONFIG_BAD
        LDA ED_CFG+13
        CMP ED_TARGET
                        BNE ED_CONFIRM
        LDX #<ED_UNCHANGED_TEXT
        LDY #>ED_UNCHANGED_TEXT
                        JMP ED_MESSAGE
ED_CONFIRM:
        LDX #<ED_CONFIRM_TEXT
        LDY #>ED_CONFIRM_TEXT
        JSR ED_PRINT
        JSR ED_READ_LINE
                        BCC ED_CANCEL
        LDA ED_LINE
        CMP #'Y'
                        BNE ED_CANCEL
        LDA ED_LINE+1
                        BNE ED_CANCEL
        LDA ED_TARGET
        STA ED_CFG+13
        ; The validated format remains 1. EF50 computes F6/F7 even when the
        ; changed mode makes the old checksum disagree; publish the new sums.
        JSR X28_C2
        LDA $F6
        STA ED_CFG+14
        LDA $F7
        STA ED_CFG+15
        JSR X28_C3
                        BCC ED_SAVE_BAD
        JSR ED_READ_CONFIG
                        BCC ED_SAVE_BAD
        LDA ED_CFG+13
        CMP ED_TARGET
                        BNE ED_SAVE_BAD
        STA $7D28
        LDX #<ED_SAVED_OK
        LDY #>ED_SAVED_OK
                        JMP ED_MESSAGE
ED_CANCEL: JSR B29_ERROR_HOOK
 LDX #<ED_CANCEL_TEXT
        LDY #>ED_CANCEL_TEXT
                        JMP ED_MESSAGE
ED_BAD: JSR B29_ERROR_HOOK
    LDX #<ED_BAD_TEXT
        LDY #>ED_BAD_TEXT
                        JMP ED_MESSAGE
ED_CONFIG_BAD: JSR B29_ERROR_HOOK

        LDX #<ED_CONFIG_TEXT
        LDY #>ED_CONFIG_TEXT
                        JMP ED_MESSAGE
ED_SAVE_BAD: JSR B29_ERROR_HOOK

        LDX #<ED_FAILED_TEXT
        LDY #>ED_FAILED_TEXT
ED_MESSAGE:
        JSR ED_PRINT
        JMP ED_PROMPT
ED_ABSENT: JSR B29_ERROR_HOOK
 LDX #<ED_ABSENT_TEXT
        LDY #>ED_ABSENT_TEXT
        JSR ED_PRINT
ED_QUIT:   JMP X28_C0
ED_READ_CONFIG:
        JSR X28_C4
                        BCC ED_RETURN
        JMP X28_C2
ED_PRINT:  STX ED_PTR
        STY ED_PTR+1
        LDY #0
ED_PRINT_NEXT:
        LDA (ED_PTR),Y
                        BEQ ED_RETURN
        JSR ED_PUTC
        INY
                        BRA ED_PRINT_NEXT
ED_RETURN: RTS
ED_READ_LINE:
        STZ ED_COUNT
        STZ ED_OVERFLOW
ED_READ_NEXT:
        JSR ED_GETC
        CMP #3
                        BEQ ED_READ_CANCEL
        CMP #$1B
                        BEQ ED_READ_CANCEL
        CMP #10
                        BEQ ED_READ_NEXT
        CMP #13
                        BEQ ED_READ_DONE
        CMP #'a'
                        BCC ED_READ_CHAR
        CMP #'z'+1
                        BCS ED_READ_CHAR
        AND #$DF
ED_READ_CHAR:
        LDX ED_COUNT
        CPX #7
                        BCS ED_READ_FULL
        STA ED_LINE,X
        INC ED_COUNT
        JSR ED_PUTC
                        JMP ED_READ_NEXT
ED_READ_FULL:
        LDA #1
        STA ED_OVERFLOW
                        JMP ED_READ_NEXT
ED_READ_DONE:
        LDX ED_COUNT
        STZ ED_LINE,X
        JSR $7E7F
        LDA ED_OVERFLOW
                        BNE ED_READ_CANCEL
        SEC
        RTS
ED_READ_CANCEL: JSR B29_CANCEL_HOOK

        JSR $7E7F
        CLC
        RTS
ED_MAGIC DB "ED",1,3
ED_TITLE DB "EDU 1.4",0
ED_COMMAND_TEXT DB "ON OFF ? Q",13,10,0
ED_PROMPT_TEXT DB "EDU> ",0
ED_CONFIRM_TEXT DB "Apply after RESET? [y/N]: ",0
ED_UNCHANGED_TEXT DB "No change.",13,10,0
ED_SAVED_OK DB "Saved; RESET required.",13,10,0
ED_CANCEL_TEXT DB "Canceled.",13,10,0
ED_BAD_TEXT DB "Use ? ON OFF Q.",13,10,0
ED_CONFIG_TEXT DB "No valid startup settings.",13,10,0
ED_FAILED_TEXT DB "Save failed.",13,10,0
ED_ABSENT_TEXT DB "EDU mode software unavailable.",13,10,0
ED_LINE EQU $7CF0
ED_COUNT EQU $7CF8
ED_OVERFLOW EQU $7CF9
ED_TARGET EQU $7CFA
ED_OLD_BANK EQU $7CFB
ED_APP_END:
X28_C0:
        PHP
        PHA
        LDA #<$7E67
        STA X28_CALL+1
        LDA #>$7E67
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_TAIL

X28_C1:
        PHP
        PHA
        LDA #<$EF09
        STA X28_CALL+1
        LDA #>$EF09
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C2:
        PHP
        PHA
        LDA #<$EF00
        STA X28_CALL+1
        LDA #>$EF00
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C3:
        PHP
        PHA
        LDA #<$F039
        STA X28_CALL+1
        LDA #>$F039
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C4:
        PHP
        PHA
        LDA #<$F0B2
        STA X28_CALL+1
        LDA #>$F0B2
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C5:
        PHP
        PHA
        LDA #<K_V2W_MUTATE
        STA X28_CALL+1
        LDA #>K_V2W_MUTATE
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C6:
        PHP
        PHA
        LDA #<K_V2W_SNAPSHOT
        STA X28_CALL+1
        LDA #>K_V2W_SNAPSHOT
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C7:
        PHP
        PHA
        LDA #<K_V2W_ANALYZE
        STA X28_CALL+1
        LDA #>K_V2W_ANALYZE
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C8:
        PHP
        PHA
        LDA #<K_V2W_READ
        STA X28_CALL+1
        LDA #>K_V2W_READ
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C9:
        PHP
        PHA
        LDA #<K_V2W_BYTE
        STA X28_CALL+1
        LDA #>K_V2W_BYTE
        STA X28_CALL+2
        LDA V2_SELECTED
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C10:
        PHP
        PHA
        LDA #<$E011
        STA X28_CALL+1
        LDA #>$E011
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C11:
        PHP
        PHA
        LDA #<BOOT_SLOT_CHECK
        STA X28_CALL+1
        LDA #>BOOT_SLOT_CHECK
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C12:
        PHP
        PHA
        LDA #<$FAB4
        STA X28_CALL+1
        LDA #>$FAB4
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C13:
        PHP
        PHA
        LDA #<$FABD
        STA X28_CALL+1
        LDA #>$FABD
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_GATE

X28_C14:
        PHP
        PHA
        LDA #<$F007
        STA X28_CALL+1
        LDA #>$F007
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_TAIL

X28_C15:
        PHP
        PHA
        LDA #<$E80E
        STA X28_CALL+1
        LDA #>$E80E
        STA X28_CALL+2
        LDA #3
        STA X28_CALL_BANK
        PLA
        PLP
        JMP X28_TAIL

X28_R0:
        PHP
        PHA

        LDA #<$EE92
        STA X28_PTR
        LDA #>$EE92
        STA X28_PTR+1

        TXA
        CLC
        ADC X28_PTR
        STA X28_PTR
        BCC X28_R0_PTR
        INC X28_PTR+1
X28_R0_PTR:

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R1:
        PHP
        PHA

        LDA MM_SRC
        STA X28_PTR
        LDA MM_SRC+1
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R2:
        PHP
        PHA

        LDA MM_DST
        STA X28_PTR
        LDA MM_DST+1
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R3:
        PHP
        PHA

        LDA MM_SRC
        STA X28_PTR
        LDA MM_SRC+1
        STA X28_PTR+1

        PLA
        PLP
        JMP X28_READ

X28_R4:
        PHP
        PHA

        LDA V2_PTR
        STA X28_PTR
        LDA V2_PTR+1
        STA X28_PTR+1

        PLA
        PLP
        JMP X28_READ

X28_R5:
        PHP
        PHA

        LDA MM_TZ_PTR
        STA X28_PTR
        LDA MM_TZ_PTR+1
        STA X28_PTR+1

        PLA
        PLP
        JMP X28_READ

X28_R6:
        PHP
        PHA

        LDA #<$F0C1
        STA X28_PTR
        LDA #>$F0C1
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R7:
        PHP
        PHA

        LDA #<$F0C2
        STA X28_PTR
        LDA #>$F0C2
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R8:
        PHP
        PHA

        LDA #<$F0C3
        STA X28_PTR
        LDA #>$F0C3
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R9:
        PHP
        PHA

        LDA #<$F684
        STA X28_PTR
        LDA #>$F684
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R10:
        PHP
        PHA

        LDA #<$F685
        STA X28_PTR
        LDA #>$F685
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R11:
        PHP
        PHA

        LDA #<$F686
        STA X28_PTR
        LDA #>$F686
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R12:
        PHP
        PHA

        LDA #<$F687
        STA X28_PTR
        LDA #>$F687
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R13:
        PHP
        PHA

        LDA #<$FFFD
        STA X28_PTR
        LDA #>$FFFD
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R14:
        PHP
        PHA

        LDA #<$FFFC
        STA X28_PTR
        LDA #>$FFFC
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R15:
        PHP
        PHA

        LDA #<$E000
        STA X28_PTR
        LDA #>$E000
        STA X28_PTR+1

        TXA
        CLC
        ADC X28_PTR
        STA X28_PTR
        BCC X28_R15_PTR
        INC X28_PTR+1
X28_R15_PTR:

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R16:
        PHP
        PHA

        LDA #<$E6E0
        STA X28_PTR
        LDA #>$E6E0
        STA X28_PTR+1

        TXA
        CLC
        ADC X28_PTR
        STA X28_PTR
        BCC X28_R16_PTR
        INC X28_PTR+1
X28_R16_PTR:

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R17:
        PHP
        PHA

        LDA #<$E6F0
        STA X28_PTR
        LDA #>$E6F0
        STA X28_PTR+1

        TXA
        CLC
        ADC X28_PTR
        STA X28_PTR
        BCC X28_R17_PTR
        INC X28_PTR+1
X28_R17_PTR:

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R18:
        PHP
        PHA

        LDA #<$E011
        STA X28_PTR
        LDA #>$E011
        STA X28_PTR+1

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS

X28_R19:
        PHP
        PHA

        LDA #<$9000
        STA X28_PTR
        LDA #>$9000
        STA X28_PTR+1

        TXA
        CLC
        ADC X28_PTR
        STA X28_PTR
        BCC X28_R19_PTR
        INC X28_PTR+1
X28_R19_PTR:

        PLA
        PLP
        PHY
        LDY #0
        JSR X28_READ
        PLY
        ORA #0
        RTS
