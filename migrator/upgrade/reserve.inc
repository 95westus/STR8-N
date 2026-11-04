; NFU1 extension to NFM1: append one immutable, host-sealed SNBT frame,
; verify/commit it before the single F erase. Never erase C/D.
U_FRAME EQU $3100
U_INFO EQU $3300
U_PAGE EQU $6013
U_CHECK:
        LDA PLAN+5
        CMP #1
        BNE U_BAD
        LDX #3
U_MAGIC_LOOP:
        LDA U_INFO,X
        CMP U_MAGIC,X
        BNE U_BAD
        DEX
        BPL U_MAGIC_LOOP
        LDA U_INFO+4
        CMP #$C0
        BCC U_BAD
        CMP #$E0
        BCS U_BAD
        LDA U_INFO+5
        ORA U_INFO+6
        ORA U_INFO+7
        BNE U_BAD
        LDA U_FRAME+$FF
        CMP #$FF
        BNE U_BAD
        LDX #3
U_AFTER_HASH:
        LDA U_INFO+8,X
        CMP PLAN+$24,X
        BNE U_BAD
        DEX
        BPL U_AFTER_HASH
        SEC
        RTS
U_BAD:
        CLC
        RTS
U_APPEND:
        JSR CHECK_SELF
        BCC U_BAD
        JSR GUARD_INITIAL_ALL
        BCC U_BAD
        LDA #3
        JSR SELECT_BANK
        LDA U_INFO+4
        STA U_PAGE
        STA PTR+1
        STZ PTR
U_BLANK:
        LDA (PTR)
        CMP #$FF
        BNE U_BAD
        INC PTR
        BNE U_BLANK
        LDX #<U_BEGIN
        LDY #>U_BEGIN
        JSR PRINT
U_PROGRAM:
        LDY PTR
        LDA U_FRAME,Y
        CMP #$FF
        BEQ U_PROGRAM_NEXT
        STA FLASH_DATA
        JSR PROGRAM_RAW
        BCC U_BAD
U_PROGRAM_NEXT:
        INC PTR
        BNE U_PROGRAM
U_COMPARE:
        LDY PTR
        LDA (PTR)
        CMP U_FRAME,Y
        BNE U_BAD
        INC PTR
        BNE U_COMPARE
        ; Only this commit makes the new reservation authoritative.
        LDA #$FF
        STA PTR
        STZ FLASH_DATA
        JSR PROGRAM_RAW
        BCC U_BAD
        LDA (PTR)
        BNE U_BAD
        JSR HASH_VISIBLE_BANK
        LDA #<(U_INFO+8)
        STA EXPECT
        LDA #>(U_INFO+8)
        STA EXPECT+1
        JSR COMPARE_HASH
        BCC U_BAD
        LDX #<U_DONE
        LDY #>U_DONE
        JSR PRINT
        SEC
        RTS
U_MAGIC: DB "JFR1"
U_BEGIN: DB "JOURNAL: append F erase reservation; no C/D erase",13,10,0
U_DONE: DB "JOURNAL: F reservation committed and full B3 verified",13,10,0
