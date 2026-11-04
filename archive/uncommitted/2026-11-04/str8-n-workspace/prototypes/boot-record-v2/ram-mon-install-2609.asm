; Exact-plan RAM component installer. No flash work occurs on raw-L entry.
; Each action is one prebound page/sector. Journal reservations precede erases.
; Shared guard, USB console and FNV code come from qualified journal initializer.
        MODULE RAM_MON_INSTALL_2609
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "worker-public-symbols.inc"
JI_HASH EQU $6200
JI_TERM EQU $6204
JI_STOP EQU $6208
JI_BANK EQU $620A
JI_TABLE EQU $620B
JI_PHASE EQU $620C
JI_SECTOR EQU $620D
JI_INDEX EQU $620E
JI_DONE EQU $620F
JI_ENDPAGE EQU $6210
JI_SKIP EQU $6211
JI_LENGTH EQU $6212
JI_BADLINE EQU $6213
MI_PAGES EQU $6214
MI_REMAIN EQU $6215
MI_ERASE EQU $6216
MI_MARK EQU $6217
MI_UNCOMMITTED EQU $6218
MI_SOURCE EQU $621A
JI_LINE EQU $6220
        CODE
JI_START:
        SEI
        CLD
        LDX #$FF
        TXS
        STZ JI_DONE
        STZ JI_SKIP
        STZ V2_DDRA
        LDA #$0C
        TSB V2_CTRL
        LDX #<JI_TITLE
        LDY #>JI_TITLE
        JSR JI_PRINT
        JSR JI_PREFLIGHT
        BCC JI_HALT_BAD
JI_MENU:
        LDX #<JI_PROMPT
        LDY #>JI_PROMPT
        JSR JI_PRINT
        JSR JI_READLINE
        BCC MI_BAD_COMMAND
        LDA JI_LINE+1
        BNE MI_BAD_COMMAND
        LDA JI_LINE
        CMP #'?'
        BEQ MI_HELP
        CMP #'W'
        BEQ MI_WEAR
        CMP #'V'
        BEQ MI_VERIFY
        CMP #'Q'
        BEQ MI_QUIT
        CMP #'I'
        BNE MI_BAD_COMMAND
        LDA JI_DONE
        BNE MI_BAD_COMMAND
        LDX #<JI_CONFIRM
        LDY #>JI_CONFIRM
        JSR JI_PRINT
        JSR JI_READLINE
        BCC MI_BAD_COMMAND
        LDX #0
MI_CONFIRM_BYTE:
        LDA JI_LINE,X
        CMP JI_CONFIRM_WORD,X
        BNE MI_BAD_COMMAND
        LDA JI_CONFIRM_WORD,X
        BEQ MI_CONFIRMED
        INX
        BRA MI_CONFIRM_BYTE
MI_CONFIRMED:
        JSR JI_PREFLIGHT
        BCC JI_HALT_BAD
        STZ JI_PHASE
MI_ACTION:
        JSR MI_LOAD_ACTION
        LDA JI_SECTOR
        JSR JI_HEX
        LDX #<MI_ADDRESS_END
        LDY #>MI_ADDRESS_END
        JSR JI_PRINT
        LDA MI_ERASE
        BEQ MI_NO_ERASE
        LDX #<MI_ERASE_TEXT
        LDY #>MI_ERASE_TEXT
        JSR JI_PRINT
        JSR MI_RANGE
        JSR V2W_ERASE_RAW+2
        BCC JI_HALT_BAD
MI_NO_ERASE:
        JSR MI_BLANK
        BCC JI_HALT_BAD
        LDX #<MI_PROGRAM_TEXT
        LDY #>MI_PROGRAM_TEXT
        JSR JI_PRINT
        JSR MI_RANGE
MI_PROGRAM:
        LDA V2_FLASH_PTR+1
        CMP JI_SECTOR
        BNE MI_PROGRAM_DATA
        LDA V2_FLASH_PTR
        CMP MI_MARK
        BEQ MI_PROGRAM_NEXT
MI_PROGRAM_DATA:
        LDA (V2_BUF_PTR)
        CMP #$FF
        BEQ MI_PROGRAM_NEXT
        STA V2_FLASH_DATA
        JSR V2W_BYTE+2
        BCC JI_HALT_BAD
MI_PROGRAM_NEXT:
        JSR MI_ADVANCE
        BCS MI_PROGRAM
        LDA #1
        STA MI_UNCOMMITTED
        JSR MI_COMPARE
        BCC JI_HALT_BAD
        LDA JI_SECTOR
        STA V2_FLASH_PTR+1
        LDA MI_MARK
        STA V2_FLASH_PTR
        STZ V2_FLASH_DATA
        JSR V2W_BYTE+2
        BCC JI_HALT_BAD
        STZ MI_UNCOMMITTED
        JSR MI_COMPARE
        BCC JI_HALT_BAD
        LDX #<MI_VERIFIED_TEXT
        LDY #>MI_VERIFIED_TEXT
        JSR JI_PRINT
        INC JI_PHASE
        LDA JI_PHASE
        CMP #MI_ACTION_COUNT
        BNE MI_ACTION
        INC JI_DONE
        JSR JI_PREFLIGHT
        BCC JI_HALT_BAD
        LDX #<MI_SUCCESS
        LDY #>MI_SUCCESS
        JSR JI_PRINT
        JMP JI_MENU
MI_BAD_COMMAND:
        LDX #<JI_BAD_COMMAND_TEXT
        LDY #>JI_BAD_COMMAND_TEXT
        JSR JI_PRINT
        JMP JI_MENU
MI_HELP:
        LDX #<JI_HELP_TEXT
        LDY #>JI_HELP_TEXT
        JSR JI_PRINT
        JMP JI_MENU
MI_WEAR:
        LDX #<JI_WEAR_TEXT
        LDY #>JI_WEAR_TEXT
        JSR JI_PRINT
        JMP JI_MENU
MI_VERIFY:
        JSR JI_PREFLIGHT
        BCC JI_HALT_BAD
        JMP JI_MENU
MI_QUIT:
        LDA #3
        JSR JI_SELECT
        JMP $F004
JI_HALT_BAD:
        LDA #3
        JSR JI_SELECT
        LDX #<JI_FAILED
        LDY #>JI_FAILED
        JSR JI_PRINT
JI_HALT:
        BRA JI_HALT

; Six-byte action: destination high, pages, erase flag, commit offset, source.
MI_LOAD_ACTION:
        LDA JI_PHASE
        ASL A
        CLC
        ADC JI_PHASE
        ASL A
        TAX
        LDA MI_ACTIONS,X
        STA JI_SECTOR
        LDA MI_ACTIONS+1,X
        STA MI_PAGES
        LDA MI_ACTIONS+2,X
        STA MI_ERASE
        LDA MI_ACTIONS+3,X
        STA MI_MARK
        LDA MI_ACTIONS+4,X
        STA MI_SOURCE
        LDA MI_ACTIONS+5,X
        STA MI_SOURCE+1
        RTS
MI_RANGE:
        STZ V2_FLASH_PTR
        LDA JI_SECTOR
        STA V2_FLASH_PTR+1
        LDA MI_SOURCE
        STA V2_BUF_PTR
        LDA MI_SOURCE+1
        STA V2_BUF_PTR+1
        LDA MI_PAGES
        STA MI_REMAIN
        RTS
; Carry set while bytes remain; source and flash advance in lockstep.
MI_ADVANCE:
        INC V2_BUF_PTR
        BNE MI_ADVANCE_FLASH
        INC V2_BUF_PTR+1
MI_ADVANCE_FLASH:
        INC V2_FLASH_PTR
        BNE MI_MORE
        INC V2_FLASH_PTR+1
        DEC MI_REMAIN
        BEQ MI_END_RANGE
MI_MORE:
        SEC
        RTS
MI_END_RANGE:
        CLC
        RTS
MI_BLANK:
        JSR MI_RANGE
MI_BLANK_BYTE:
        LDA (V2_FLASH_PTR)
        CMP #$FF
        BNE MI_COMPARE_BAD
        JSR MI_ADVANCE
        BCS MI_BLANK_BYTE
        SEC
        RTS
MI_COMPARE:
        JSR MI_RANGE
MI_COMPARE_BYTE:
        LDA MI_UNCOMMITTED
        BEQ MI_COMPARE_DATA
        LDA V2_FLASH_PTR+1
        CMP JI_SECTOR
        BNE MI_COMPARE_DATA
        LDA V2_FLASH_PTR
        CMP MI_MARK
        BNE MI_COMPARE_DATA
        LDA (V2_FLASH_PTR)
        CMP #$FF
        BNE MI_COMPARE_BAD
        BRA MI_COMPARE_NEXT
MI_COMPARE_DATA:
        LDA (V2_FLASH_PTR)
        CMP (V2_BUF_PTR)
        BNE MI_COMPARE_BAD
MI_COMPARE_NEXT:
        JSR MI_ADVANCE
        BCS MI_COMPARE_BYTE
        SEC
        RTS
MI_COMPARE_BAD:
        CLC
        RTS

; The common preflight uses the original hashes before I and final hashes
; after completion. No mutable transaction data is inside the checked image.
MI_COMPARE_BANK:
        PHA
        LDA JI_DONE
        BEQ MI_COMPARE_SOURCE
        PLA
        CMP JI_POST_HASHES,X
        RTS
MI_COMPARE_SOURCE:
        PLA
        CMP JI_BANK_HASHES,X
        RTS
        INCLUDE "component-common.inc"
MI_ADDRESS_END: DB "00",13,10,0
MI_ERASE_TEXT: DB "  erase sector; verify blank",13,10,0
MI_PROGRAM_TEXT: DB "  program; verify body; commit last",13,10,0
MI_VERIFIED_TEXT: DB "  committed; entire action readback VERIFIED",13,10,0
MI_SUCCESS: DB "ALL COMPONENTS VERIFIED; default S recovery; B0 and F preserved",13,10,0
JI_CHECKING: DB "Checking RAM image, RAM ABI and four bank images",13,10,0
JI_OK: DB " OK",13,10,0
JI_NEWLINE: DB 13,10,0
JI_BAD_COMMAND_TEXT: DB "REFUSED: command/cancel/already done",13,10,0
JI_HELP_TEXT:
        DB "V Verify RAM/ABI/all banks; W Show imported and proposed wear",13,10
        DB "I Install exact bound plan; confirmation required; Q Restart F",13,10
        DB "Partial failure: keep host reservation/log; do not blindly retry.",13,10,0
JI_FAILED: DB "REFUSED/FAILED; HALTED IN RAM; host inspection required",13,10,0
JI_HEX_DIGITS: DB "0123456789ABCDEF"
JI_BANK_BITS: DB $CC,$CE,$EC,$EE
JI_OFFSET: DB $C5,$9D,$1C,$81
        INCLUDE "mon-install-params.inc"
JI_SELF_HASH: DS 4
JI_END:
        ENDS
        END
