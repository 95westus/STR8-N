; Borrowed monitor staging only. No application RAM, RTC or storage I/O.
        MODULE VERSION
        XDEF START
        XDEF APP_END
        INCLUDE "version-links.inc"
VPTR EQU $D0
TZ_PTR EQU $D6
        CODE
START:  DB "BS",1,3
        JMP DISPLAY_VERSION
DISPLAY_VERSION:
        LDA BOOT_ACTIVE
        STA RUNNING_SLOT
        CMP #$A0
        BEQ CHECK_RUNNING
        CMP #$B0
        BNE RUNNING_BAD
CHECK_RUNNING:
        STA BOOT_DEST
        STA $E1
        STZ $E0
        JSR BOOT_SLOT_CHECK
        BCC RUNNING_BAD
        LDY #$3E
        LDA ($E0),Y
        STA MON_CALL
        INY
        LDA ($E0),Y
        STA MON_CALL+1
        LDX #10
        JSR MON_PRINT
        LDA $7D00
        ORA #'0'
        JSR $7E6D
        LDX #11
        LDA $7D01
        CMP #$16
        BNE CPU_READY
        INX
CPU_READY:
        JSR MON_PRINT
        LDX #13
        JSR MON_PRINT
        JSR $7E7F
        JSR $7E7F
        JSR BN_READ
        LDA BN_LENGTH
        BEQ BOARD_UNNAMED
        JSR BN_SHOW
        BRA RUNNING_LINE
BOARD_UNNAMED:
        LDX #<UNNAMED_TEXT
        LDY #>UNNAMED_TEXT
        JSR PRINT
RUNNING_LINE:
        LDX #<RUNNING_TEXT
        LDY #>RUNNING_TEXT
        JSR PRINT
        LDA RUNNING_SLOT
        JSR SLOT_LETTER
        LDX #<GEN_TEXT
        LDY #>GEN_TEXT
        JSR PRINT
        LDA RUNNING_SLOT
        STA VPTR+1
        STZ VPTR
        LDY #11
RUNNING_GEN:
        LDA (VPTR),Y
        JSR $7E7C
        DEY
        CPY #7
        BNE RUNNING_GEN
        JSR $7E7F
        BRA SLOT_LIST
RUNNING_BAD:
        LDX #<BAD_RUNNING_TEXT
        LDY #>BAD_RUNNING_TEXT
        JSR PRINT
SLOT_LIST:
        ; Recompute default using the bootstrap's actual preference/validity
        ; rules. Its startup formatter labels BOOT_ACTIVE as the default.
        JSR BOOT_SELECT
        LDA BOOT_BEST
        STA BOOT_ACTIVE
        LDA #$A0
        JSR BOOT_CHOICE_SLOT
        LDA #$B0
        JSR BOOT_CHOICE_SLOT
        LDA RUNNING_SLOT
        STA BOOT_ACTIVE
        JSR $7E7F
        SEC
        RTS
SLOT_LETTER:
        CMP #$B0
        LDA #'A'
        BCC SLOT_CHAR
        LDA #'B'
SLOT_CHAR:
        JMP $7E6D
MON_PRINT:
        JMP (MON_CALL)
PRINT:  STX VPTR
        STY VPTR+1
        LDY #0
PRINT_NEXT:
        LDA (VPTR),Y
        BEQ PRINT_DONE
        JSR $7E6D
        INY
        BNE PRINT_NEXT
        INC VPTR+1
        BRA PRINT_NEXT
PRINT_DONE:
        RTS
UNNAMED_TEXT DB "Board: unnamed",13,10,0
RUNNING_TEXT DB "Running: MONITOR ",0
GEN_TEXT DB ", gen ",0
BAD_RUNNING_TEXT DB 13,10,"Running monitor: INVALID",13,10,0
RUNNING_SLOT DB 0
MON_CALL DS 2
TZ_SUM DS 2
        INCLUDE "version-board.inc"
APP_END:
        ENDMOD
