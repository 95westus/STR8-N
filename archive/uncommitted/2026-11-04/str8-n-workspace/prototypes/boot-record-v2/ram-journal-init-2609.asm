; Exact-preimage, USB-only first SNBT initializer. Runs from b15 F raw L.
; No MON, F, B0/B1/B2, RTC or EEPROM mutation. Host reserves both erases.
        MODULE RAM_JOURNAL_INIT_2609
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
        BCC JI_BAD_COMMAND
        LDA JI_LINE+1
        BNE JI_BAD_COMMAND
        LDA JI_LINE
        CMP #'?'
        BEQ JI_HELP
        CMP #'W'
        BEQ JI_WEAR
        CMP #'V'
        BEQ JI_VERIFY
        CMP #'Q'
        BEQ JI_QUIT
        CMP #'I'
        BNE JI_BAD_COMMAND
        LDA JI_DONE
        BNE JI_BAD_COMMAND
        LDX #<JI_CONFIRM
        LDY #>JI_CONFIRM
        JSR JI_PRINT
        JSR JI_READLINE
        BCC JI_BAD_COMMAND
        LDX #0
JI_CONFIRM_BYTE:
        LDA JI_LINE,X
        CMP JI_CONFIRM_WORD,X
        BNE JI_BAD_COMMAND
        INX
        CPX #9
        BNE JI_CONFIRM_BYTE
        JSR JI_PREFLIGHT
        BCC JI_HALT_BAD
        STZ JI_PHASE
JI_INSTALL_NEXT:
        LDX JI_PHASE
        LDA JI_PAGES,X
        STA JI_SECTOR
        LDA JI_ROW_LO,X
        STA V2_BUF_PTR
        LDA JI_ROW_HI,X
        STA V2_BUF_PTR+1
        LDA JI_SECTOR
        JSR JI_HEX
        LDX #<JI_ERASING
        LDY #>JI_ERASING
        JSR JI_PRINT
        STZ V2_FLASH_PTR
        LDA JI_SECTOR
        STA V2_FLASH_PTR+1
        JSR V2W_ERASE_RAW+2
        BCC JI_HALT_BAD
        JSR JI_VERIFY_BLANK
        BCC JI_HALT_BAD
        LDX #<JI_PROGRAMMING
        LDY #>JI_PROGRAMMING
        JSR JI_PRINT
        STZ JI_INDEX
        STZ V2_FLASH_PTR
        LDA JI_SECTOR
        STA V2_FLASH_PTR+1
JI_PROGRAM_BYTE:
        LDY JI_INDEX
        LDA (V2_BUF_PTR),Y
        CMP #$FF
        BEQ JI_PROGRAM_SKIP
        STA V2_FLASH_DATA
        JSR V2W_BYTE+2
        BCC JI_HALT_BAD
JI_PROGRAM_SKIP:
        INC V2_FLASH_PTR
        INC JI_INDEX
        LDA JI_INDEX
        CMP #$FF
        BNE JI_PROGRAM_BYTE
        ; Verify the entire uncommitted page before its last byte is written.
        STZ V2_FLASH_PTR
        LDY #0
JI_CHECK_BODY:
        LDA (V2_BUF_PTR),Y
        CMP (V2_FLASH_PTR),Y
        BNE JI_HALT_BAD
        INY
        CPY #$FF
        BNE JI_CHECK_BODY
        LDA (V2_FLASH_PTR),Y
        CMP #$FF
        BNE JI_HALT_BAD
        LDA #$FF
        STA V2_FLASH_PTR
        STZ V2_FLASH_DATA
        JSR V2W_BYTE+2
        BCC JI_HALT_BAD
        JSR JI_VERIFY_SECTOR
        BCC JI_HALT_BAD
        LDX #<JI_COMMITTED
        LDY #>JI_COMMITTED
        JSR JI_PRINT
        INC JI_PHASE
        LDA JI_PHASE
        CMP #2
        BNE JI_INSTALL_NEXT
        INC JI_DONE
        LDX #<JI_SUCCESS
        LDY #>JI_SUCCESS
        JSR JI_PRINT
        JMP JI_MENU
JI_BAD_COMMAND:
        LDX #<JI_BAD_COMMAND_TEXT
        LDY #>JI_BAD_COMMAND_TEXT
        JSR JI_PRINT
        JMP JI_MENU
JI_HELP:
        LDX #<JI_HELP_TEXT
        LDY #>JI_HELP_TEXT
        JSR JI_PRINT
        JMP JI_MENU
JI_WEAR:
        LDX #<JI_WEAR_TEXT
        LDY #>JI_WEAR_TEXT
        JSR JI_PRINT
        JMP JI_MENU
JI_VERIFY:
        LDA JI_DONE
        BNE JI_VERIFY_AFTER
        JSR JI_PREFLIGHT
        BCC JI_HALT_BAD
        JMP JI_MENU
JI_VERIFY_AFTER:
        STZ JI_PHASE
JI_VERIFY_NEXT:
        LDX JI_PHASE
        LDA JI_PAGES,X
        STA JI_SECTOR
        LDA JI_ROW_LO,X
        STA V2_BUF_PTR
        LDA JI_ROW_HI,X
        STA V2_BUF_PTR+1
        JSR JI_VERIFY_SECTOR
        BCC JI_HALT_BAD
        INC JI_PHASE
        LDA JI_PHASE
        CMP #2
        BNE JI_VERIFY_NEXT
        LDX #<JI_VERIFIED_TEXT
        LDY #>JI_VERIFIED_TEXT
        JSR JI_PRINT
        JMP JI_MENU
JI_QUIT:
        ; RESET selects B3 and F. HOLD requires a MON and is not used.
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

; Own RAM-only USB console and hashing allow refusal without trusting the ABI.
; Checks cover every loaded byte except the final checksum field, both resident
; RAM routines, and all four physical banks (including the exact F image).
JI_PREFLIGHT:
        LDX #<JI_CHECKING
        LDY #>JI_CHECKING
        JSR JI_PRINT
        LDA #<JI_START
        STA V2_PTR
        LDA #>JI_START
        STA V2_PTR+1
        LDA #<JI_SELF_HASH
        STA JI_STOP
        LDA #>JI_SELF_HASH
        STA JI_STOP+1
        JSR JI_HASH_RANGE
        LDX #0
JI_SELF_COMPARE:
        LDA JI_HASH,X
        CMP JI_SELF_HASH,X
        BNE JI_GUARD_BAD
        INX
        CPX #4
        BNE JI_SELF_COMPARE
        STZ JI_TABLE
JI_RAM_GUARD:
        LDX JI_TABLE
        LDA JI_RAM_RANGES,X
        STA V2_PTR
        LDA JI_RAM_RANGES+1,X
        STA V2_PTR+1
        LDA JI_RAM_RANGES+2,X
        STA JI_STOP
        LDA JI_RAM_RANGES+3,X
        STA JI_STOP+1
        JSR JI_HASH_RANGE
        LDX JI_TABLE
        LDY #0
JI_RAM_COMPARE:
        LDA JI_HASH,Y
        CMP JI_RAM_HASHES,X
        BNE JI_GUARD_BAD
        INX
        INY
        CPY #4
        BNE JI_RAM_COMPARE
        STX JI_TABLE
        CPX #8
        BNE JI_RAM_GUARD
        STZ JI_BANK
        STZ JI_TABLE
JI_BANK_GUARD:
        LDA JI_BANK
        JSR JI_SELECT
        STZ V2_PTR
        LDA #$80
        STA V2_PTR+1
        STZ JI_STOP
        STZ JI_STOP+1
        JSR JI_HASH_RANGE
        LDX JI_TABLE
        LDY #0
JI_BANK_COMPARE:
        LDA JI_HASH,Y
        CMP JI_BANK_HASHES,X
        BNE JI_GUARD_BAD
        INX
        INY
        CPY #4
        BNE JI_BANK_COMPARE
        STX JI_TABLE
        LDA #'B'
        JSR JI_PUTC
        LDA JI_BANK
        ORA #'0'
        JSR JI_PUTC
        LDX #<JI_OK
        LDY #>JI_OK
        JSR JI_PRINT
        INC JI_BANK
        LDA JI_BANK
        CMP #4
        BNE JI_BANK_GUARD
        LDA #3
        JSR JI_SELECT
        SEC
        RTS
JI_GUARD_BAD:
        LDA #3
        JSR JI_SELECT
        CLC
        RTS
JI_SELECT:
        TAX
        LDA V2_PCR
        AND #$11
        ORA JI_BANK_BITS,X
        STA V2_PCR
        RTS

JI_VERIFY_BLANK:
        STZ V2_FLASH_PTR
        LDA JI_SECTOR
        STA V2_FLASH_PTR+1
        CLC
        ADC #$10
        STA JI_ENDPAGE
JI_BLANK_BYTE:
        LDA (V2_FLASH_PTR)
        CMP #$FF
        BNE JI_CHECK_BAD
        INC V2_FLASH_PTR
        BNE JI_BLANK_BYTE
        INC V2_FLASH_PTR+1
        LDA V2_FLASH_PTR+1
        CMP JI_ENDPAGE
        BNE JI_BLANK_BYTE
        SEC
        RTS
JI_VERIFY_SECTOR:
        STZ V2_FLASH_PTR
        LDA JI_SECTOR
        STA V2_FLASH_PTR+1
        LDY #0
JI_PAGE_BYTE:
        LDA (V2_BUF_PTR),Y
        CMP (V2_FLASH_PTR),Y
        BNE JI_CHECK_BAD
        INY
        BNE JI_PAGE_BYTE
        INC V2_FLASH_PTR+1
        LDA JI_SECTOR
        CLC
        ADC #$10
        STA JI_ENDPAGE
        JMP JI_BLANK_BYTE
JI_CHECK_BAD:
        CLC
        RTS

; FNV-1a, byte order/multiply identical to the qualified RAM migrator.
JI_HASH_RANGE:
        LDX #3
JI_HASH_INIT:
        LDA JI_OFFSET,X
        STA JI_HASH,X
        DEX
        BPL JI_HASH_INIT
JI_HASH_BYTE:
        LDA (V2_PTR)
        JSR JI_FNV_BYTE
        INC V2_PTR
        BNE JI_HASH_TEST
        INC V2_PTR+1
JI_HASH_TEST:
        LDA V2_PTR
        CMP JI_STOP
        BNE JI_HASH_BYTE
        LDA V2_PTR+1
        CMP JI_STOP+1
        BNE JI_HASH_BYTE
        RTS
JI_FNV_BYTE:
        EOR JI_HASH
        STA JI_HASH
        LDX #3
JI_FNV_COPY:
        LDA JI_HASH,X
        STA JI_TERM,X
        DEX
        BPL JI_FNV_COPY
        LDX #1
        JSR JI_SHIFT_ADD
        LDX #3
        JSR JI_SHIFT_ADD
        LDX #3
        JSR JI_SHIFT_ADD
        LDX #1
        JSR JI_SHIFT_ADD
        LDA JI_HASH+3
        CLC
        ADC JI_TERM+1
        STA JI_HASH+3
        RTS
JI_SHIFT_ADD:
        ASL JI_TERM
        ROL JI_TERM+1
        ROL JI_TERM+2
        ROL JI_TERM+3
        DEX
        BNE JI_SHIFT_ADD
        CLC
        LDA JI_HASH
        ADC JI_TERM
        STA JI_HASH
        LDA JI_HASH+1
        ADC JI_TERM+1
        STA JI_HASH+1
        LDA JI_HASH+2
        ADC JI_TERM+2
        STA JI_HASH+2
        LDA JI_HASH+3
        ADC JI_TERM+3
        STA JI_HASH+3
        RTS

JI_PUTC:
        PHA
JI_TX_WAIT:
        LDA #1
        BIT V2_CTRL
        BNE JI_TX_WAIT
        PLA
        STA V2_DATA
        NOP
        NOP
        LDA #4
        TSB V2_CTRL
        DEC V2_DDRA
        NOP
        NOP
        LDA #4
        TRB V2_CTRL
        STZ V2_DDRA
        RTS
JI_GETC:
        STZ V2_DDRA
        LDA #2
        BIT V2_CTRL
        BNE JI_GETC
        LDA #8
        TRB V2_CTRL
        NOP
        NOP
        LDA V2_DATA
        PHA
        LDA #8
        TSB V2_CTRL
        PLA
        RTS
JI_PRINT:
        STX V2_ADDR
        STY V2_ADDR+1
        LDY #0
JI_PRINT_BYTE:
        LDA (V2_ADDR),Y
        BEQ JI_PRINT_END
        JSR JI_PUTC
        INY
        BNE JI_PRINT_BYTE
        INC V2_ADDR+1
        BRA JI_PRINT_BYTE
JI_PRINT_END:
        RTS
JI_HEX:
        PHA
        LSR A
        LSR A
        LSR A
        LSR A
        JSR JI_NIBBLE
        PLA
        AND #15
JI_NIBBLE:
        TAX
        LDA JI_HEX_DIGITS,X
        JMP JI_PUTC
JI_READLINE:
        STZ JI_LENGTH
        STZ JI_BADLINE
JI_READ_CHAR:
        JSR JI_GETC
        PHA
        LDA JI_SKIP
        BEQ JI_READ_KEEP
        STZ JI_SKIP
        PLA
        CMP #10
        BEQ JI_READ_CHAR
        PHA
JI_READ_KEEP:
        PLA
        CMP #3
        BEQ JI_LINE_CANCEL
        CMP #13
        BEQ JI_LINE_CR
        CMP #10
        BEQ JI_LINE_END
        LDX JI_LENGTH
        CPX #15
        BCS JI_LINE_LONG
        STA JI_LINE,X
        INC JI_LENGTH
        JSR JI_PUTC
        BRA JI_READ_CHAR
JI_LINE_LONG:
        INC JI_BADLINE
        BRA JI_READ_CHAR
JI_LINE_CANCEL:
        LDX #0
        STZ JI_LINE
        CLC
        RTS
JI_LINE_CR:
        INC JI_SKIP
JI_LINE_END:
        LDX JI_LENGTH
        STZ JI_LINE,X
        LDX #<JI_NEWLINE
        LDY #>JI_NEWLINE
        JSR JI_PRINT
        LDA JI_BADLINE
        BNE JI_LINE_REFUSE
        SEC
        RTS
JI_LINE_REFUSE:
        CLC
        RTS

JI_TITLE: DB "2609 RAM JOURNAL INIT / b15 F / USB only",13,10,0
JI_PROMPT: DB "RAM JINIT ? V W I Q> ",0
JI_CHECKING: DB "Checking RAM image, RAM ABI and four-bank preimages",13,10,0
JI_OK: DB " OK",13,10,0
JI_NEWLINE: DB 13,10,0
JI_CONFIRM: DB "Erase B3:D then C only; type INIT C/D then Enter> ",0
JI_CONFIRM_WORD: DB "INIT C/D",0
JI_BAD_COMMAND_TEXT: DB "REFUSED: command/cancel; ? for help",13,10,0
JI_HELP_TEXT:
        DB "V Verify preimages (or completed C/D); W Show imported/reserved wear",13,10
        DB "I Initialize exact bound C/D; requires INIT C/D; Q Reset to F",13,10
        DB "No MON installation. Partial failure requires a new host recovery plan.",13,10,0
JI_ERASING: DB ": erase and verify blank",13,10,0
JI_PROGRAMMING: DB "  program and verify body; commit last",13,10,0
JI_COMMITTED: DB "  committed; all 4096 bytes verified",13,10,0
JI_SUCCESS: DB "C/D VERIFIED; recovery default; MON A/B absent; no other sector written",13,10,0
JI_VERIFIED_TEXT: DB "C/D postimages VERIFIED",13,10,0
JI_FAILED: DB "REFUSED/FAILED; HALTED IN RAM; do not retry without host review",13,10,0
JI_HEX_DIGITS: DB "0123456789ABCDEF"
JI_BANK_BITS: DB $CC,$CE,$EC,$EE
JI_OFFSET: DB $C5,$9D,$1C,$81
JI_PAGES: DB $D0,$C0
JI_ROW_LO: DB <JI_ROW_D,<JI_ROW_C
JI_ROW_HI: DB >JI_ROW_D,>JI_ROW_C
        INCLUDE "journal-init-params.inc"
JI_SELF_HASH: DS 4
JI_END:
        ENDS
        END
