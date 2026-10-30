; RAM FLASH / MAINT. Frozen PR05, common 65C02 / 816 emulation source.
; $2000 code, $5C00-$5FFF admitted overlay context, $6800-$77FF sector buffer.
; CONFIG and OIP1 bodies are generated from their preserved existing sources.
        MODULE BOARD_TOOL
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "vectors-symbols.inc"
        INCLUDE "boot-symbols.inc"
OI_PTR EQU V2_PTR
OI_STAGE EQU $6800
        CODE
FT_START:
        SEI
        CLD
        LDX #$FF
        TXS
        LDA #3
        JSR V2W_SELECT
        STZ FT_VALID
        STZ FT_DIRTY
        STZ FT_HOST_MODE
        LDA $5D00
        AND #3
        STA FT_BANK
        JMP CONFIG_START
FT_MENU:
        LDX #<FT_PROMPT
        LDY #>FT_PROMPT
        JSR CONFIG_PRINT
        JSR BOOT_READ_LINE
        BCC FT_BAD
        LDX #<FT_HELP_WORD
        LDY #>FT_HELP_WORD
        JSR FT_MATCH
        BCS FT_HELP
        LDX #<FT_BANK_WORD
        LDY #>FT_BANK_WORD
        JSR FT_MATCH
        BCS FT_BANK_COMMAND
        LDX #<FT_READ_WORD
        LDY #>FT_READ_WORD
        JSR FT_MATCH
        BCS FT_READ_COMMAND
        LDX #<FT_VIEW_WORD
        LDY #>FT_VIEW_WORD
        JSR FT_MATCH
        BCS FT_VIEW_COMMAND
        LDX #<FT_EDIT_WORD
        LDY #>FT_EDIT_WORD
        JSR FT_MATCH
        BCS FT_EDIT_COMMAND
        LDX #<FT_BYTE_WORD
        LDY #>FT_BYTE_WORD
        JSR FT_MATCH
        BCS FT_BYTE_COMMAND
        LDX #<FT_ERASE_WORD
        LDY #>FT_ERASE_WORD
        JSR FT_MATCH
        BCS FT_ERASE_COMMAND
        LDX #<FT_WRITE_WORD
        LDY #>FT_WRITE_WORD
        JSR FT_MATCH
        BCS FT_WRITE_COMMAND
        LDX #<FT_HOST_WORD
        LDY #>FT_HOST_WORD
        JSR FT_MATCH
        BCS FT_HOST_COMMAND
        LDX #<FT_BOOT_WORD
        LDY #>FT_BOOT_WORD
        JSR FT_MATCH
        BCS FT_BOOT_COMMAND
        LDX #<FT_VERSION_WORD
        LDY #>FT_VERSION_WORD
        JSR FT_MATCH
        BCS FT_VERSION_COMMAND
        JMP CONFIG_DISPATCH
FT_BAD:
        LDX #<FT_BAD_TEXT
        LDY #>FT_BAD_TEXT
        JSR CONFIG_PRINT
        JMP FT_MENU
FT_HELP:
        JSR FT_END
        BCC FT_BAD
        LDX #<FT_HELP_TEXT
        LDY #>FT_HELP_TEXT
        JSR CONFIG_PRINT
        JMP FT_MENU
FT_VERSION_COMMAND:
        JSR FT_END
        BCC FT_BAD
        LDX #<FT_VERSION_TEXT
        LDY #>FT_VERSION_TEXT
        JSR CONFIG_PRINT
        LDA V2_CPU
        CMP #$16
        BEQ FT_SXB816
        LDX #<FT_SXB02_TEXT
        LDY #>FT_SXB02_TEXT
        BRA FT_PROFILE
FT_SXB816:
        LDX #<FT_SXB816_TEXT
        LDY #>FT_SXB816_TEXT
FT_PROFILE:
        JSR CONFIG_PRINT
        LDX #<FT_EDU_TEXT
        LDY #>FT_EDU_TEXT
        JSR CONFIG_PRINT
        JMP FT_MENU
FT_BANK_COMMAND:
        JSR BOOT_API_SKIP
        SEC
        SBC #'0'
        CMP #4
        BCS FT_BAD
        STA FT_PENDING_BANK
        INX
        JSR FT_END
        BCC FT_BAD
        LDA FT_PENDING_BANK
        STA FT_BANK
        JMP FT_OK
FT_READ_COMMAND:
        JSR FT_ADDRESS
        BCC FT_BAD
        JSR FT_END
        BCC FT_BAD
        JSR FT_READ
        BCC FT_BAD
        JMP FT_OK
FT_ERASE_COMMAND:
        JSR FT_ADDRESS
        BCC FT_BAD
        JSR FT_END
        BCC FT_BAD
        JSR FT_READ
        BCC FT_BAD
        STZ V2_BUF_PTR
        LDA #$68
        STA V2_BUF_PTR+1
        LDA #16
        STA FT_PAGES
        LDA #$FF
FT_FILL:
        STA (V2_BUF_PTR)
        INC V2_BUF_PTR
        BNE FT_FILL
        INC V2_BUF_PTR+1
        DEC FT_PAGES
        BNE FT_FILL
        INC FT_DIRTY
        JMP FT_WRITE
FT_ADDRESS:
        JSR BOOT_API_HEX_WORD
        BCC FT_NO
        LDA V2_VALUE
        STA FT_ADDRESS_VALUE
        LDA V2_VALUE+1
        STA FT_ADDRESS_VALUE+1
        CMP #$80
        BCC FT_NO
        ; Byte/sector entry accepts every flash address; sector is rounded down.
        LDA FT_BANK
        CMP #3
        BNE FT_YES
        LDA FT_ADDRESS_VALUE+1
        AND #$F0
        CMP #$C0
        BEQ FT_NO
        CMP #$D0
        BEQ FT_NO
        CMP #$F0
        BEQ FT_NO
FT_YES:
        SEC
        RTS
FT_NO:
        CLC
        RTS
FT_READ:
        ; A new read deliberately replaces only this tool's RAM edit buffer.
        LDA FT_BANK
        STA OI_HEADER+6
        STA FT_BUFFER_BANK
        LDA FT_ADDRESS_VALUE+1
        AND #$F0
        STA OI_HEADER+7
        STA FT_BUFFER_PAGE
        JSR OI_TARGET_CRC
        LDA OI_CRC
        STA FT_PREIMAGE
        LDA OI_CRC+1
        STA FT_PREIMAGE+1
        JSR OI_TARGET
        STZ V2_BUF_PTR
        LDA #$68
        STA V2_BUF_PTR+1
        LDA #16
        STA FT_PAGES
FT_READ_BYTE:
        LDA (V2_FLASH_PTR)
        STA (V2_BUF_PTR)
        INC V2_FLASH_PTR
        INC V2_BUF_PTR
        BNE FT_READ_BYTE
        INC V2_FLASH_PTR+1
        INC V2_BUF_PTR+1
        DEC FT_PAGES
        BNE FT_READ_BYTE
        LDA #3
        JSR V2W_SELECT
        LDA #1
        STA FT_VALID
        STZ FT_DIRTY
        SEC
        RTS
FT_VIEW_COMMAND:
        JSR FT_OFFSET
        BCC FT_BAD
        JSR FT_END
        BCC FT_BAD
        LDA FT_ADDRESS_VALUE
        BNE FT_BAD
        STZ FT_ROW
        LDX #<FT_COLUMNS
        LDY #>FT_COLUMNS
        JSR CONFIG_PRINT
FT_VIEW_ROW:
        LDA FT_ADDRESS_VALUE+1
        JSR V2V_RAM_HEX_OUT
        LDA FT_ROW
        JSR V2V_RAM_HEX_OUT
        LDA #' '
        JSR V2W_PUTC
        LDA FT_ROW
        STA V2_BUF_PTR
        LDA FT_ADDRESS_VALUE+1
        CLC
        ADC #$68
        STA V2_BUF_PTR+1
        STZ FT_COL
FT_VIEW_BYTE:
        LDA #' '
        JSR V2W_PUTC
        LDA (V2_BUF_PTR)
        JSR V2V_RAM_HEX_OUT
        INC V2_BUF_PTR
        INC FT_COL
        LDA FT_COL
        CMP #16
        BCC FT_VIEW_BYTE
        JSR V2V_RAM_NEWLINE
        CLC
        LDA FT_ROW
        ADC #16
        STA FT_ROW
        BNE FT_VIEW_ROW
        JMP FT_MENU
FT_OFFSET:
        LDA FT_VALID
        BEQ FT_NO
        JSR BOOT_API_HEX_WORD
        BCC FT_NO
        LDA V2_VALUE+1
        CMP #$10
        BCS FT_NO
        STA FT_ADDRESS_VALUE+1
        LDA V2_VALUE
        STA FT_ADDRESS_VALUE
        SEC
        RTS
FT_EDIT_COMMAND:
        JSR FT_OFFSET
        BCC FT_BAD
        STZ FT_BYTE_COUNT
FT_EDIT_PARSE:
        JSR BOOT_API_HEX_WORD
        BCC FT_BAD
        LDA V2_VALUE+1
        BNE FT_BAD
        LDY FT_BYTE_COUNT
        CPY #8
        BCS FT_BAD
        LDA V2_VALUE
        STA FT_BYTES,Y
        INC FT_BYTE_COUNT
        JSR BOOT_API_SKIP
        BNE FT_EDIT_PARSE
        CLC
        LDA FT_ADDRESS_VALUE
        ADC FT_BYTE_COUNT
        LDA FT_ADDRESS_VALUE+1
        ADC #0
        CMP #$10
        BCC FT_EDIT_FITS
        BNE FT_BAD
        LDA FT_ADDRESS_VALUE
        CLC
        ADC FT_BYTE_COUNT
        BNE FT_BAD
FT_EDIT_FITS:
        LDA FT_ADDRESS_VALUE
        STA V2_BUF_PTR
        LDA FT_ADDRESS_VALUE+1
        CLC
        ADC #$68
        STA V2_BUF_PTR+1
        LDY #0
FT_EDIT_APPLY:
        LDA FT_BYTES,Y
        STA (V2_BUF_PTR),Y
        INY
        CPY FT_BYTE_COUNT
        BCC FT_EDIT_APPLY
        INC FT_DIRTY
        JMP FT_OK
FT_BYTE_COMMAND:
        JSR FT_ADDRESS
        BCC FT_BAD
        JSR BOOT_API_HEX_WORD
        BCC FT_BAD
        LDA V2_VALUE+1
        BNE FT_BAD
        LDA V2_VALUE
        STA FT_BYTE
        JSR FT_END
        BCC FT_BAD
        LDA FT_BANK
        JSR V2W_SELECT
        LDA FT_ADDRESS_VALUE
        STA V2_FLASH_PTR
        LDA FT_ADDRESS_VALUE+1
        STA V2_FLASH_PTR+1
        LDA (V2_FLASH_PTR)
        STA FT_OLD_BYTE
        AND FT_BYTE
        CMP FT_BYTE
        PHP
        LDA #3
        JSR V2W_SELECT
        PLP
        BNE FT_BAD
        JSR FT_CONFIRM_BYTE
        BCC FT_CANCEL
        LDA FT_BANK
        JSR V2W_SELECT
        LDA FT_ADDRESS_VALUE
        STA V2_FLASH_PTR
        LDA FT_ADDRESS_VALUE+1
        STA V2_FLASH_PTR+1
        LDA (V2_FLASH_PTR)
        CMP FT_OLD_BYTE
        BNE FT_BYTE_STALE
        LDA FT_BYTE
        CMP FT_OLD_BYTE
        BEQ FT_BYTE_OK
        STA V2_FLASH_DATA
        LDA #1
        STA V2_NMI_HOLD
        JSR V2W_BYTE+2
        BCC FT_FATAL
        LDA (V2_FLASH_PTR)
        CMP FT_BYTE
        BNE FT_FATAL
FT_BYTE_OK:
        LDA #3
        JSR V2W_SELECT
        STZ V2_NMI_HOLD
        LDA #1
        STA V2_LED
        JMP FT_OK
FT_BYTE_STALE:
        LDA #3
        JSR V2W_SELECT
        JMP FT_BAD
FT_FATAL:
        ; A worker failure cannot safely return into flash-backed recovery.
        LDA #1
        STA V2_LED
        LDA #'!'
        JSR V2W_PUTC
FT_HALT:
        BRA FT_HALT
FT_WRITE_COMMAND:
        JSR FT_END
        BCC FT_BAD
FT_WRITE:
        LDA FT_VALID
        BEQ FT_BAD
        ; Confirm the actual buffered target, independent of current BANK.
        LDA FT_BUFFER_BANK
        STA OI_HEADER+6
        LDA FT_BUFFER_PAGE
        STA OI_HEADER+7
        LDX #<FT_REWRITE_TEXT
        LDY #>FT_REWRITE_TEXT
        JSR CONFIG_PRINT
        LDA FT_BUFFER_BANK
        ORA #'0'
        JSR V2W_PUTC
        LDA #':'
        JSR V2W_PUTC
        LDA FT_BUFFER_PAGE
        JSR V2V_RAM_HEX_OUT
        LDA #0
        JSR V2V_RAM_HEX_OUT
        JSR FT_CONFIRM
        BCC FT_CANCEL
        JSR OI_TARGET_CRC
        LDA OI_CRC
        CMP FT_PREIMAGE
        BNE FT_STALE
        LDA OI_CRC+1
        CMP FT_PREIMAGE+1
        BNE FT_STALE
        JSR OI_COMPARE
        BCS FT_WRITE_IDENTICAL
        STZ OI_PTR
        LDA #$68
        STA OI_PTR+1
        LDA #16
        STA FT_PAGES
        JSR OI_CRC_INIT
FT_STAGE_CRC:
        LDA (OI_PTR)
        JSR OI_CRC_BYTE
        INC OI_PTR
        BNE FT_STAGE_CRC
        INC OI_PTR+1
        DEC FT_PAGES
        BNE FT_STAGE_CRC
        LDA OI_CRC
        STA OI_HEADER+12
        LDA OI_CRC+1
        STA OI_HEADER+13
        LDA #3
        JSR V2W_SELECT
        LDA FT_BUFFER_BANK
        ASL A
        ASL A
        ASL A
        STA J_COUNTINDEX
        LDA FT_BUFFER_PAGE
        LSR A
        LSR A
        LSR A
        LSR A
        SEC
        SBC #8
        ORA J_COUNTINDEX
        STA J_COUNTINDEX
        LDA #2
        JSR JE_ENTER
        BCC FT_JOURNAL_BAD
        ; Invalidate before mutation: a failed rewrite must require READ again.
        STZ FT_VALID
        JMP OI_APPLY
FT_WRITE_IDENTICAL:
        LDA #3
        JSR V2W_SELECT
        STZ FT_DIRTY
        JMP FT_OK
FT_STALE:
        LDA #3
        JSR V2W_SELECT
        JMP FT_BAD
FT_JOURNAL_BAD:
        LDX #<OI_JOURNAL_TEXT
        LDY #>OI_JOURNAL_TEXT
        JSR CONFIG_PRINT
        JMP FT_MENU
FT_CANCEL:
        LDX #<FT_CANCEL_TEXT
        LDY #>FT_CANCEL_TEXT
        JSR CONFIG_PRINT
        JMP FT_MENU
FT_CONFIRM_BYTE:
        LDX #<FT_BYTE_TEXT
        LDY #>FT_BYTE_TEXT
        JSR CONFIG_PRINT
        LDA FT_BANK
        ORA #'0'
        JSR V2W_PUTC
        LDA #':'
        JSR V2W_PUTC
        LDA FT_ADDRESS_VALUE+1
        JSR V2V_RAM_HEX_OUT
        LDA FT_ADDRESS_VALUE
        JSR V2V_RAM_HEX_OUT
        LDA #'='
        JSR V2W_PUTC
        LDA FT_BYTE
        JSR V2V_RAM_HEX_OUT
FT_CONFIRM:
        LDX #<FT_CONFIRM_TEXT
        LDY #>FT_CONFIRM_TEXT
        JSR CONFIG_PRINT
        JSR BOOT_READ_LINE
        BCC FT_NO
        LDX #<FT_YES_WORD
        LDY #>FT_YES_WORD
        JSR FT_MATCH
        BCC FT_NO
        JMP FT_END
FT_HOST_COMMAND:
        JSR FT_END
        BCC FT_BAD
        STZ FT_VALID
        LDA #1
        STA FT_HOST_MODE
        JMP INSTALLER_START
FT_OIP_FINISH:
        LDA FT_HOST_MODE
        BEQ FT_OIP_MENU
        JMP INSTALLER_MENU
FT_HOST_QUIT:
        STZ FT_HOST_MODE
        STZ FT_VALID
FT_OIP_MENU:
        JMP FT_MENU
FT_BOOT_COMMAND:
        JSR BOOT_API_SKIP
        BEQ FT_BOOT_SHOW
        STX FT_ARG
        LDX #<FT_OFF_WORD
        LDY #>FT_OFF_WORD
        JSR FT_MATCH
        BCS FT_BOOT_OFF
        LDX #<FT_DELAY_WORD
        LDY #>FT_DELAY_WORD
        JSR FT_MATCH
        BCS FT_BOOT_DELAY
        LDX #<FT_RUN_WORD
        LDY #>FT_RUN_WORD
        JSR FT_MATCH
        BCS FT_BOOT_RUN
        LDX FT_ARG
        ; BOOT B/C ... use the existing checked CONFIG grammar and writer.
        LDY #0
FT_BOOT_MOVE:
        LDA V2_LINE,X
        STA V2_LINE,Y
        BEQ FT_BOOT_DISPATCH
        INX
        INY
        BRA FT_BOOT_MOVE
FT_BOOT_DISPATCH:
        JMP CONFIG_DISPATCH
FT_BOOT_SHOW:
        JMP CONFIG_SHOW
FT_BOOT_OFF:
        JSR BOOT_API_SKIP
        SEC
        SBC #'0'
        CMP #4
        BCS FT_BAD
        STA CONFIG_BANK_NUMBER
        INX
        JSR FT_END
        BCC FT_BAD
        LDA #1
        STA FT_BOOT_ACTION
        LDA #7
        JMP CONFIG_CALL
FT_BOOT_DELAY:
        JSR BOOT_API_HEX_WORD
        BCC FT_BAD
        LDA V2_VALUE+1
        BNE FT_BAD
        LDA V2_VALUE
        STA FT_DELAY
        JSR FT_END
        BCC FT_BAD
        LDA #2
        STA FT_BOOT_ACTION
        LDA #7
        JMP CONFIG_CALL
FT_BOOT_RUN:
        JSR BOOT_API_SKIP
        SEC
        SBC #'0'
        CMP #4
        BCS FT_BAD
        STA CONFIG_BANK_NUMBER
        INX
        JSR FT_END
        BCC FT_BAD
        LDA #0
        JSR JE_ENTER
        BCC FT_BAD
        LDX CONFIG_BANK_NUMBER
        JSR CONFIG_BANK_MASK
        AND JE_FRAME+13
        BEQ FT_BAD
        LDX CONFIG_BANK_NUMBER
        LDA JE_FRAME+14,X
        ASL A
        ASL A
        ASL A
        ASL A
        STA V2_VECTOR+1
        STZ V2_VECTOR
        LDA CONFIG_BANK_NUMBER
        STA V2_SELECTED
        JMP V2W_EXECUTE
FT_BOOT_APPLY:
        LDA FT_BOOT_ACTION
        CMP #1
        BNE FT_APPLY_DELAY
        LDX CONFIG_BANK_NUMBER
        JSR CONFIG_BANK_MASK
        EOR #$FF
        AND JE_FRAME+13
        STA JE_FRAME+13
        BRA FT_APPLY_FIELDS
FT_APPLY_DELAY:
        LDA FT_DELAY
        STA JE_FRAME+12
FT_APPLY_FIELDS:
        JSR BOOT_CHECK_FIELDS
        BCC FT_APPLY_REFUSED
        JMP JE_APPEND
FT_APPLY_REFUSED:
        JMP JE_FAIL
FT_END:
        JSR BOOT_API_SKIP
        BNE FT_NO
        SEC
        RTS
FT_MATCH:
        STX V2_PTR
        STY V2_PTR+1
        LDX #0
        LDY #0
FT_MATCH_BYTE:
        LDA (V2_PTR),Y
        BEQ FT_MATCH_END
        CMP V2_LINE,X
        BNE FT_NO
        INX
        INY
        BRA FT_MATCH_BYTE
FT_MATCH_END:
        LDA V2_LINE,X
        BEQ FT_YES
        CMP #' '
        BEQ FT_YES
        CLC
        RTS
FT_OK:
        LDX #<CONFIG_OK
        LDY #>CONFIG_OK
        JSR CONFIG_PRINT
        JMP FT_MENU
FT_PROMPT: DB "FLASH/MAINT> ",0
FT_HELP_WORD: DB "?",0
FT_BANK_WORD: DB "BANK",0
FT_READ_WORD: DB "READ",0
FT_VIEW_WORD: DB "VIEW",0
FT_EDIT_WORD: DB "EDIT",0
FT_BYTE_WORD: DB "BYTE",0
FT_ERASE_WORD: DB "ERASE",0
FT_WRITE_WORD: DB "WRITE",0
FT_HOST_WORD: DB "HOST",0
FT_BOOT_WORD: DB "BOOT",0
FT_OFF_WORD: DB "BOOT OFF",0
FT_DELAY_WORD: DB "BOOT DELAY",0
FT_RUN_WORD: DB "BOOT RUN",0
FT_VERSION_WORD: DB "VERSION",0
FT_YES_WORD: DB "YES",0
FT_BAD_TEXT: DB "REFUSED: syntax/range/protected/stale; ? help",13,10,0
FT_CANCEL_TEXT: DB "Canceled; flash unchanged.",13,10,0
FT_CONFIRM_TEXT: DB "; type YES> ",0
FT_REWRITE_TEXT: DB "REWRITE 4K B",0
FT_BYTE_TEXT: DB "PROGRAM byte B",0
FT_VERSION_TEXT: DB "STR8-N FLASH/MAINT g00000001; N-F 0.3.0 BASE1/PR05",13,10,0
FT_SXB02_TEXT: DB "SXB: W65C02SXB / 65C02",13,10,0
FT_SXB816_TEXT: DB "SXB: W65C816SXB / emulation",13,10,0
FT_EDU_TEXT: DB "EDU profile: Rev D; revision/presence not electrically identified.",13,10,0
FT_COLUMNS: DB "offset 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F",13,10,0
FT_HELP_TEXT:
        DB "BANK 0-3; READ addr (4K -> RAM buffer); VIEW 000..F00",13,10
        DB "EDIT offset byte... (1-8); WRITE (buffer -> sector; YES)",13,10
        DB "BYTE addr value (flash 1->0; YES); ERASE addr (4K; YES)",13,10
        DB "BOOT shows settings; BOOT B bank entry; BOOT C S|A|B|0-3",13,10
        DB "BOOT OFF bank; BOOT RUN bank; BOOT DELAY hex-ticks (0.1s)",13,10
        DB "B/C/W/? also use CONFIG; HOST enters OIP1 opaque transfer",13,10
        DB "VERSION: tool/SXB/EDU profile; Q: monitor",13,10
        DB "B3:C/D/F protected. READ discards pending buffer edits.",13,10,0
FT_VALID: DB 0
FT_DIRTY: DB 0
FT_BANK: DB 3
FT_PENDING_BANK: DB 0
FT_BUFFER_BANK: DB 0
FT_BUFFER_PAGE: DB 0
FT_ADDRESS_VALUE: DB 0,0
FT_PREIMAGE: DB 0,0
FT_BYTE: DB 0
FT_OLD_BYTE: DB 0
FT_BYTES: DS 8
FT_BYTE_COUNT: DB 0
FT_ROW: DB 0
FT_COL: DB 0
FT_PAGES: DB 0
FT_ARG: DB 0
FT_BOOT_ACTION: DB 0
FT_DELAY: DB 0
FT_HOST_MODE: DB 0
        INCLUDE "board-config.inc"
        INCLUDE "board-opaque.inc"
        INCLUDE "config-engine.inc"
BOARD_END:
        ENDMOD
        END
