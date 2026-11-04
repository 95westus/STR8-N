; Standalone b15 CONFIG. F/MON and the on-flash record format stay unchanged.
; The builder adds mode 6 to this app's private copy of the guarded writer.
        MODULE RAM_CONFIG_B15
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "vectors-symbols.inc"
        INCLUDE "boot-symbols.inc"
        CODE
CONFIG_START:
        SEI
        CLD
        LDX #<CONFIG_BANNER
        LDY #>CONFIG_BANNER
        JSR CONFIG_PRINT
        LDA #<JE_ENTER
        STA $7C60
        LDA #>JE_ENTER
        STA $7C61
CONFIG_MENU:
        LDX #<CONFIG_TEXT
        LDY #>CONFIG_TEXT
        JSR CONFIG_PRINT
        JSR BOOT_READ_LINE
        BCS CF_LONG_1
        JMP CONFIG_BAD
CF_LONG_1:
        LDA V2_LINE
        CMP #'B'
        BNE CF_LONG_2
        JMP CONFIG_BANK
CF_LONG_2:
        CMP #'C'
        BNE CF_LONG_3
        JMP CONFIG_C
CF_LONG_3:
        LDA V2_LINE+1
        BEQ CF_LONG_4
        JMP CONFIG_BAD
CF_LONG_4:
        LDA V2_LINE
        CMP #'?'
        BNE CF_LONG_5
        JMP CONFIG_HELP
CF_LONG_5:
        CMP #'I'
        BNE CF_LONG_6
        JMP CONFIG_INIT
CF_LONG_6:
        CMP #'W'
        BNE CF_LONG_7
        JMP CONFIG_W
CF_LONG_7:
        CMP #'Q'
        BNE CF_LONG_8
        JMP CONFIG_QUIT
CF_LONG_8:
CONFIG_BAD:
        LDX #<CONFIG_BAD_TEXT
        LDY #>CONFIG_BAD_TEXT
        JMP CONFIG_MESSAGE
CONFIG_HELP:
        LDX #<CONFIG_HELP_TEXT
        LDY #>CONFIG_HELP_TEXT
        JMP CONFIG_MESSAGE
CONFIG_INIT:
        LDA #5
        JMP CONFIG_CALL
CONFIG_W:
        LDA #4
        JMP CONFIG_CALL
CONFIG_C:
        LDA V2_LINE+1
        BNE CF_LONG_9
        JMP CONFIG_SHOW
CF_LONG_9:
        CMP #' '
        BEQ CF_LONG_10
        JMP CONFIG_BAD
CF_LONG_10:
        LDA V2_LINE+3
        BEQ CF_LONG_11
        JMP CONFIG_BAD
CF_LONG_11:
        LDA V2_LINE+2
        STA JE_REQUEST
        LDA #1
        JMP CONFIG_CALL
CONFIG_BANK:
        LDA V2_LINE+1
        BNE CF_LONG_12
        JMP CONFIG_SHOW
CF_LONG_12:
        CMP #' '
        BEQ CF_LONG_13
        JMP CONFIG_BAD
CF_LONG_13:
        LDA V2_LINE+2
        CMP #'0'
        BCS CF_LONG_14
        JMP CONFIG_RANGE
CF_LONG_14:
        CMP #'4'
        BCC CF_LONG_15
        JMP CONFIG_RANGE
CF_LONG_15:
        SEC
        SBC #'0'
        STA CONFIG_BANK_NUMBER
        LDA V2_LINE+3
        CMP #' '
        BEQ CF_LONG_16
        JMP CONFIG_BAD
CF_LONG_16:
        LDX #4
        JSR BOOT_API_HEX_WORD
        BCS CF_LONG_17
        JMP CONFIG_RANGE
CF_LONG_17:
        CPX #8
        BEQ CF_LONG_18
        JMP CONFIG_RANGE
CF_LONG_18:
        LDA V2_LINE,X
        BEQ CF_LONG_19
        JMP CONFIG_BAD
CF_LONG_19:
        LDA V2_VALUE
        BEQ CF_LONG_20
        JMP CONFIG_RANGE
CF_LONG_20:
        LDA V2_VALUE+1
        AND #$0F
        BEQ CF_LONG_21
        JMP CONFIG_RANGE
CF_LONG_21:
        LDA V2_VALUE+1
        LSR A
        LSR A
        LSR A
        LSR A
        STA CONFIG_ENTRY_PAGE
        JSR CONFIG_CHECK_BANK
        BCS CF_LONG_22
        JMP CONFIG_RANGE
CF_LONG_22:
        LDA #6
CONFIG_CALL:
        JSR JE_ENTER
        BCS CF_LONG_23
        JMP CONFIG_FAILED
CF_LONG_23:
        LDX #<CONFIG_OK
        LDY #>CONFIG_OK
        JMP CONFIG_MESSAGE
CONFIG_FAILED:
        LDX #<CONFIG_FAIL_TEXT
        LDY #>CONFIG_FAIL_TEXT
        JMP CONFIG_MESSAGE
CONFIG_RANGE:
        LDX #<CONFIG_RANGE_TEXT
        LDY #>CONFIG_RANGE_TEXT
CONFIG_MESSAGE:
        JSR CONFIG_PRINT
        JMP CONFIG_MENU
CONFIG_QUIT:
        JMP $F004

; Display a fully admitted snapshot. This operation never appends a page.
CONFIG_SHOW:
        LDA #0
        JSR JE_ENTER
        BCS CF_LONG_24
        JMP CONFIG_FAILED
CF_LONG_24:
        LDX #<CONFIG_DEFAULT_TEXT
        LDY #>CONFIG_DEFAULT_TEXT
        JSR CONFIG_PRINT
        LDA JE_FRAME+7
        JSR V2W_PUTC
        JSR V2V_RAM_NEWLINE
        STZ CONFIG_ROW
CONFIG_SHOW_ROW:
        LDA #'B'
        JSR V2W_PUTC
        LDA CONFIG_ROW
        ORA #'0'
        JSR V2W_PUTC
        LDX CONFIG_ROW
        JSR CONFIG_BANK_MASK
        AND JE_FRAME+13
        BNE CF_LONG_25
        JMP CONFIG_SHOW_OFF
CF_LONG_25:
        LDX #<CONFIG_ON_TEXT
        LDY #>CONFIG_ON_TEXT
        JMP CONFIG_SHOW_STATE
CONFIG_SHOW_OFF:
        LDX #<CONFIG_OFF_TEXT
        LDY #>CONFIG_OFF_TEXT
CONFIG_SHOW_STATE:
        JSR CONFIG_PRINT
        LDX CONFIG_ROW
        LDA JE_FRAME+14,X
        JSR V2V_RAM_NIBBLE_OUT
        LDX #<CONFIG_ZEROS_TEXT
        LDY #>CONFIG_ZEROS_TEXT
        JSR CONFIG_PRINT
        INC CONFIG_ROW
        LDA CONFIG_ROW
        CMP #4
        BEQ CF_LONG_26
        JMP CONFIG_SHOW_ROW
CF_LONG_26:
        JMP CONFIG_MENU

; Entered only after JE_ENTER has saved scratch and admitted the full journal.
; Use exactly the existing append/reserve/verify/commit-last/exit machinery.
CONFIG_BANK_APPLY:
        JSR CONFIG_CHECK_BANK
        BCS CF_LONG_27
        JMP CONFIG_APPLY_BAD
CF_LONG_27:
        LDX CONFIG_BANK_NUMBER
        JSR CONFIG_BANK_MASK
        AND JE_FRAME+13
        BNE CF_LONG_28
        JMP CONFIG_APPLY_CHANGE
CF_LONG_28:
        LDX CONFIG_BANK_NUMBER
        LDA CONFIG_ENTRY_PAGE
        CMP JE_FRAME+14,X
        BEQ CF_LONG_29
        JMP CONFIG_APPLY_CHANGE
CF_LONG_29:
        JMP JE_OK
CONFIG_APPLY_CHANGE:
        LDX CONFIG_BANK_NUMBER
        LDA CONFIG_ENTRY_PAGE
        STA JE_FRAME+14,X
        JSR CONFIG_BANK_MASK
        ORA JE_FRAME+13
        STA JE_FRAME+13
        JSR BOOT_CHECK_FIELDS
        BCS CF_LONG_30
        JMP CONFIG_APPLY_BAD
CF_LONG_30:
        JMP JE_APPEND
CONFIG_APPLY_BAD:
        JMP JE_FAIL

CONFIG_CHECK_BANK:
        LDA CONFIG_BANK_NUMBER
        CMP #4
        BCC CF_LONG_31
        JMP CONFIG_CHECK_BAD
CF_LONG_31:
        LDA CONFIG_ENTRY_PAGE
        CMP #8
        BCS CF_LONG_32
        JMP CONFIG_CHECK_BAD
CF_LONG_32:
        CMP #15
        BCC CF_LONG_33
        JMP CONFIG_CHECK_BAD
CF_LONG_33:
        LDX CONFIG_BANK_NUMBER
        CPX #3
        BEQ CF_LONG_34
        JMP CONFIG_CHECK_OK
CF_LONG_34:
        CMP #12
        BNE CF_LONG_35
        JMP CONFIG_CHECK_BAD
CF_LONG_35:
        CMP #13
        BNE CF_LONG_36
        JMP CONFIG_CHECK_BAD
CF_LONG_36:
CONFIG_CHECK_OK:
        SEC
        RTS
CONFIG_CHECK_BAD:
        CLC
        RTS
; X=bank, A=mask; X is consumed.
CONFIG_BANK_MASK:
        LDA #1
CONFIG_MASK_SHIFT:
        CPX #0
        BNE CF_LONG_37
        JMP CONFIG_MASK_DONE
CF_LONG_37:
        ASL A
        DEX
        JMP CONFIG_MASK_SHIFT
CONFIG_MASK_DONE:
        RTS

; F's short-string printer wraps at 256 bytes. Help can span whole pages.
CONFIG_PRINT:
        STX V2_PTR
        STY V2_PTR+1
        LDY #0
CONFIG_PRINT_BYTE:
        LDA (V2_PTR),Y
        BNE CF_LONG_38
        JMP CONFIG_PRINT_DONE
CF_LONG_38:
        JSR V2W_PUTC
        INY
        BEQ CF_LONG_39
        JMP CONFIG_PRINT_BYTE
CF_LONG_39:
        INC V2_PTR+1
        JMP CONFIG_PRINT_BYTE
CONFIG_PRINT_DONE:
        RTS
CONFIG_BANNER:
        DB "STR8N-F CONFIG 0.3.0 / BASE1 / PR05 / settings writes are immediate",13,10
        DB "Inspect only: ? B C W Q; B/C with arguments and I may write",13,10,0
CONFIG_TEXT: DB "RAM CONFIG ? B C I W Q> ",0
CONFIG_OK: DB "OK",13,10,0
CONFIG_BAD_TEXT: DB "REFUSED: command; ? for help",13,10,0
CONFIG_FAIL_TEXT: DB "REFUSED: journal/target",13,10,0
CONFIG_RANGE_TEXT: DB "REFUSED: bank/entry; use 0-3 and 8000-E000 step 1000; B3 excludes C000/D000",13,10,0
CONFIG_DEFAULT_TEXT: DB "DEFAULT=",0
CONFIG_ON_TEXT: DB " ON  ENTRY=",0
CONFIG_OFF_TEXT: DB " OFF ENTRY=",0
CONFIG_ZEROS_TEXT: DB "000",13,10,0
CONFIG_HELP_TEXT:
        DB "B             Show saved default, enabled banks and entries",13,10
        DB "B bank entry  Enable bank 0-3 and save its hex entry address",13,10
        DB "              Entries: 8000-E000 in steps of 1000; B3 excludes C000/D000",13,10
        DB "C target      Save default: S recovery, A/B monitor, enabled bank 0-3",13,10
        DB "C             Show saved settings",13,10
        DB "I             Initialize only an entirely blank C/D journal",13,10
        DB "W             Show erase counts and unknown history",13,10
        DB "Q             Restart through F using the saved default",13,10
        DB "Example: B 0 8000, then C 0, then Q (each followed by Enter)",13,10
        DB "Install the opaque image separately. B/C only save boot settings.",13,10,0
; Private request/display bytes belong to this disposable app.
CONFIG_BANK_NUMBER: DB 0
CONFIG_ENTRY_PAGE: DB 0
CONFIG_ROW: DB 0
        INCLUDE "config-engine.inc"
CONFIG_END:
        ENDMOD
        END
