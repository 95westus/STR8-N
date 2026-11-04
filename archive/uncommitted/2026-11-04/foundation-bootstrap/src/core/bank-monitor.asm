; FLASH page example for b15. This is the RAM body, linked at $0200.
; The small ROM entry copies this body before changing the flash overlay.
; IRQ stays masked. 65C816 callers use emulation mode, D/DBR/PBR=0.
        MODULE BANK_MONITOR
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "vectors-symbols.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "bank-monitor-layout.inc"
        CODE
OI_PTR EQU V2_PTR
OI_STAGE EQU $6800
BM_START:
        SEI
        CLD
        LDA #3
        JSR V2W_SELECT
        STZ DC_BINARY
        STZ V2_NMI_HOLD
        LDA BM_HOME
        STA BM_BANK
        JSR BM_GUARD
        BCC BM_FATAL
        LDX #<BM_BANNER
        LDY #>BM_BANNER
        JSR BOOT_PRINT
BM_MENU:
        ; Raw erase/program entries set the flash LEDs but bypass the normal
        ; MON worker's finish routine. Every idle return must clear busy F0.
        LDA #V2_LED_RUNNING
        STA V2_LED
        LDX #<BM_PROMPT
        LDY #>BM_PROMPT
        JSR BOOT_PRINT
        JSR BOOT_READ_LINE
        BCC BM_BAD
        LDA V2_LINE
        CMP #'B'
        BEQ BM_SELECT
        CMP #'D'
        BEQ BM_DUMP
        CMP #'M'
        BEQ BM_EDIT
        CMP #'F'
        BEQ BM_EDIT
        CMP #'I'
        BEQ BM_ERASE
        LDA V2_LINE+1
        BNE BM_BAD
        LDA V2_LINE
        CMP #'Q'
        BEQ BM_QUIT
        CMP #'?'
        BNE BM_BAD
        LDX #<BM_HELP
        LDY #>BM_HELP
        JMP BM_MESSAGE
BM_BAD:
        LDX #<BM_BAD_TEXT
        LDY #>BM_BAD_TEXT
        JMP BM_MESSAGE
BM_RANGE:
        LDX #<BM_RANGE_TEXT
        LDY #>BM_RANGE_TEXT
BM_MESSAGE:
        JSR BOOT_PRINT
        JMP BM_MENU

; B selects a data overlay. Instruction fetches and F calls still see B3.
BM_SELECT:
        LDA V2_LINE+2
        BNE BM_BAD
        LDA V2_LINE+1
        CMP #'0'
        BCC BM_BAD
        CMP #'4'
        BCS BM_BAD
        SEC
        SBC #'0'
        STA BM_BANK
        LDX #<BM_BANK_TEXT
        LDY #>BM_BANK_TEXT
        JSR BOOT_PRINT
        LDA BM_BANK
        CLC
        ADC #'0'
        JSR STR8V2_RAM_PUTC
        JSR STR8V2_RAM_NEWLINE
        JMP BM_MENU

; Parse an address into private state; F parsers are called only with B3.
BM_ADDRESS:
        LDA V2_LINE+1
        CMP #' '
        BNE BM_PARSE_BAD
        LDX #2
        JSR BOOT_API_HEX_WORD
        BCC BM_PARSE_BAD
        LDA V2_VALUE
        STA BM_ADDR
        LDA V2_VALUE+1
        STA BM_ADDR+1
        SEC
        RTS
BM_PARSE_BAD:
        CLC
        RTS
BM_END_LINE:
        JSR BOOT_API_SKIP
        BEQ BM_PARSE_OK
        CLC
        RTS
BM_PARSE_OK:
        SEC
        RTS

; D snapshots 16 bytes before printing, avoiding both I/O and pointer wrap.
BM_DUMP:
        JSR BM_ADDRESS
        BCC BM_BAD
        JSR BM_END_LINE
        BCC BM_BAD
        LDA BM_ADDR
        CLC
        ADC #15
        LDA BM_ADDR+1
        ADC #0
        BCS BM_RANGE
        CMP #$65
        BCC BM_DUMP_RAM
        LDA BM_ADDR+1
        CMP #$80
        BCC BM_RANGE
        BRA BM_DUMP_READ
BM_DUMP_RAM:
        LDA BM_ADDR+1
        CMP #$20
        BCC BM_RANGE
BM_DUMP_READ:
        LDA BM_ADDR
        STA V2_PTR
        LDA BM_ADDR+1
        STA V2_PTR+1
        LDA BM_BANK
        JSR V2W_SELECT
        LDY #0
BM_DUMP_COPY:
        LDA (V2_PTR),Y
        STA BM_DUMP_BYTES,Y
        INY
        CPY #16
        BNE BM_DUMP_COPY
        LDA #3
        JSR V2W_SELECT
        LDY #0
BM_DUMP_PRINT:
        LDA BM_DUMP_BYTES,Y
        PHY
        JSR STR8V2_RAM_HEX_OUT
        LDA #' '
        JSR STR8V2_RAM_PUTC
        PLY
        INY
        CPY #16
        BNE BM_DUMP_PRINT
        JSR STR8V2_RAM_NEWLINE
        JMP BM_MENU

; Parse the ENTIRE edit before changing RAM or staging flash. Eight bytes max.
BM_EDIT:
        STA BM_OP
        JSR BM_ADDRESS
        BCC BM_BAD
        STZ BM_COUNT
BM_EDIT_PARSE:
        JSR BOOT_API_SKIP
        BEQ BM_EDIT_PARSED
        LDA BM_COUNT
        CMP #8
        BCS BM_BAD
        JSR BOOT_API_HEX_BYTE
        BCC BM_BAD
        LDY BM_COUNT
        LDA V2_VALUE
        STA BM_VALUES,Y
        INC BM_COUNT
        BRA BM_EDIT_PARSE
BM_EDIT_PARSED:
        LDA BM_COUNT
        BEQ BM_BAD
        DEC A
        CLC
        ADC BM_ADDR
        STA BM_LAST
        LDA BM_ADDR+1
        ADC #0
        BCS BM_RANGE
        STA BM_LAST+1
        LDA BM_OP
        CMP #'F'
        BEQ BM_FLASH_EDIT
        ; M cannot alter this tool, reserved services, staging, ZP or I/O.
        LDA BM_ADDR+1
        CMP #$20
        BCC BM_RANGE
        LDA BM_LAST+1
        CMP #$65
        BCS BM_RANGE
        LDA BM_ADDR
        STA V2_PTR
        LDA BM_ADDR+1
        STA V2_PTR+1
        LDY #0
BM_RAM_WRITE:
        LDA BM_VALUES,Y
        STA (V2_PTR),Y
        INY
        CPY BM_COUNT
        BNE BM_RAM_WRITE
        LDX #<BM_RAM_OK
        LDY #>BM_RAM_OK
        JMP BM_MESSAGE

; Both F and I operate on exactly one sector. F preserves every unedited byte.
BM_ERASE:
        LDA #'I'
        STA BM_OP
        JSR BM_ADDRESS
        BCC BM_BAD
        JSR BM_END_LINE
        BCC BM_BAD
        LDA BM_ADDR
        BNE BM_RANGE
        LDA BM_ADDR+1
        AND #15
        BNE BM_RANGE
        BRA BM_FLASH_PREPARE
BM_FLASH_EDIT:
        LDA BM_ADDR+1
        EOR BM_LAST+1
        AND #$F0
        BNE BM_RANGE
BM_FLASH_PREPARE:
        JSR BM_TARGET_ALLOWED
        BCC BM_RANGE
        JSR BM_GUARD
        BCC BM_FATAL
        JSR OI_TARGET
        STZ V2_BUF_PTR
        LDA #$68
        STA V2_BUF_PTR+1
        LDA #16
        STA OI_PAGES
BM_STAGE_COPY:
        LDA (V2_FLASH_PTR)
        STA (V2_BUF_PTR)
        INC V2_FLASH_PTR
        INC V2_BUF_PTR
        BNE BM_STAGE_COPY
        INC V2_FLASH_PTR+1
        INC V2_BUF_PTR+1
        DEC OI_PAGES
        BNE BM_STAGE_COPY
        JSR BM_STAGE_CRC
        LDA OI_CRC
        STA OI_HEADER+10
        LDA OI_CRC+1
        STA OI_HEADER+11
        LDA #3
        JSR V2W_SELECT
        LDA BM_OP
        CMP #'I'
        BEQ BM_STAGE_ERASE
        LDA BM_ADDR
        STA V2_PTR
        LDA BM_ADDR+1
        AND #15
        CLC
        ADC #$68
        STA V2_PTR+1
        LDY #0
BM_STAGE_EDIT:
        LDA BM_VALUES,Y
        STA (V2_PTR),Y
        INY
        CPY BM_COUNT
        BNE BM_STAGE_EDIT
        BRA BM_STAGE_READY
BM_STAGE_ERASE:
        STZ V2_PTR
        LDA #$68
        STA V2_PTR+1
        LDX #16
        LDY #0
        LDA #$FF
BM_STAGE_FILL:
        STA (V2_PTR),Y
        INY
        BNE BM_STAGE_FILL
        INC V2_PTR+1
        DEX
        BNE BM_STAGE_FILL
BM_STAGE_READY:
        JSR BM_STAGE_CRC
        LDA OI_CRC
        STA OI_HEADER+12
        LDA OI_CRC+1
        STA OI_HEADER+13
        LDX #<BM_CONFIRM
        LDY #>BM_CONFIRM
        JSR BOOT_PRINT
        LDA BM_BANK
        CLC
        ADC #'0'
        JSR STR8V2_RAM_PUTC
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA OI_HEADER+7
        JSR STR8V2_RAM_HEX_OUT
        LDX #<BM_CONFIRM_END
        LDY #>BM_CONFIRM_END
        JSR BOOT_PRINT
        JSR BOOT_READ_LINE
        BCC BM_CANCEL
        LDA V2_LINE
        CMP #'Y'
        BNE BM_CANCEL
        LDA V2_LINE+1
        CMP #'E'
        BNE BM_CANCEL
        LDA V2_LINE+2
        CMP #'S'
        BNE BM_CANCEL
        LDA V2_LINE+3
        BNE BM_CANCEL
        ; Verify code/F, staged bytes and current target again after the pause.
        JSR BM_GUARD
        BCC BM_FATAL
        JSR BM_STAGE_CRC
        LDA OI_CRC
        CMP OI_HEADER+12
        BNE BM_STAGE_BAD
        LDA OI_CRC+1
        CMP OI_HEADER+13
        BNE BM_STAGE_BAD
        JSR OI_TARGET_CRC
        LDA OI_CRC
        CMP OI_HEADER+10
        BNE OI_PREIMAGE_BAD
        LDA OI_CRC+1
        CMP OI_HEADER+11
        BNE OI_PREIMAGE_BAD
        JSR OI_COMPARE
        BCS OI_IDENTICAL
        LDA #3
        JSR V2W_SELECT
        LDA OI_HEADER+6
        ASL A
        ASL A
        ASL A
        STA J_COUNTINDEX
        LDA OI_HEADER+7
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
        BCC OI_JOURNAL_BAD
        JMP OI_APPLY
BM_STAGE_BAD:
        LDX #<BM_STAGE_BAD_TEXT
        LDY #>BM_STAGE_BAD_TEXT
        JMP BM_MESSAGE
BM_CANCEL:
        LDX #<BM_CANCEL_TEXT
        LDY #>BM_CANCEL_TEXT
        JMP BM_MESSAGE

; Exclude B3's protected sectors and the whole allocated source image span.
BM_TARGET_ALLOWED:
        LDA BM_BANK
        CMP #4
        BCS BM_DENY
        STA OI_HEADER+6
        LDA BM_ADDR+1
        AND #$F0
        CMP #$80
        BCC BM_DENY
        STA OI_HEADER+7
        LDA BM_BANK
        CMP #3
        BNE BM_SELF_CHECK
        LDA OI_HEADER+7
        CMP #$80
        BEQ BM_SELF_CHECK
        CMP #$90
        BEQ BM_SELF_CHECK
        CMP #$E0
        BNE BM_DENY
BM_SELF_CHECK:
        LDA BM_BANK
        CMP BM_HOME
        BNE BM_ALLOW
        LDA OI_HEADER+7
        CMP #BM_HOME_FIRST
        BCC BM_ALLOW
        CMP #BM_HOME_AFTER
        BCC BM_DENY
BM_ALLOW:
        SEC
        RTS
BM_DENY:
        CLC
        RTS

; Q explicitly admits a MON. RESET would boot this default image again.
BM_QUIT:
        JSR BM_GUARD
        BCC BM_FATAL
        LDA #3
        STA V2_RESIDENT
        STA V2_SELECTED
        LDA #$B0
        JSR BM_MON_CHECK
        BCS BM_MON_GO
        LDA #$A0
        JSR BM_MON_CHECK
        BCS BM_MON_GO
        JMP BOOT_RECOVERY
BM_MON_CHECK:
        STA BOOT_DEST
        STA V2_PTR+1
        STZ V2_PTR
        JMP BOOT_SLOT_CHECK
BM_MON_GO:
        LDA BOOT_DEST
        STA BOOT_ACTIVE
        JMP STR8V2_RAM_HOLD

; Local CRC works with every bank selected. All immutable code, text and the
; unmodified guarded journal engine are covered; mutable state follows them.
BM_GUARD:
        LDA #3
        JSR V2W_SELECT
        LDA #<BM_START
        STA V2_PTR
        LDA #>BM_START
        STA V2_PTR+1
        LDA #<BM_CODE_END
        STA V2_ADDR
        LDA #>BM_CODE_END
        STA V2_ADDR+1
        JSR BM_SPAN_CRC
        LDA OI_CRC
        CMP BM_CODE_CRC
        BNE BM_GUARD_BAD
        LDA OI_CRC+1
        CMP BM_CODE_CRC+1
        BNE BM_GUARD_BAD
        STZ V2_PTR
        LDA #$F0
        STA V2_PTR+1
        STZ V2_ADDR
        STZ V2_ADDR+1
        JSR BM_SPAN_CRC
        LDA OI_CRC
        CMP #BM_F_CRC_LO
        BNE BM_GUARD_BAD
        LDA OI_CRC+1
        CMP #BM_F_CRC_HI
        BNE BM_GUARD_BAD
        SEC
        RTS
BM_GUARD_BAD:
        CLC
        RTS
BM_STAGE_CRC:
        STZ V2_PTR
        LDA #$68
        STA V2_PTR+1
        STZ V2_ADDR
        LDA #$78
        STA V2_ADDR+1
BM_SPAN_CRC:
        JSR OI_CRC_INIT
BM_SPAN_BYTE:
        LDA (V2_PTR)
        JSR OI_CRC_BYTE
        INC V2_PTR
        BNE BM_SPAN_COMPARE
        INC V2_PTR+1
BM_SPAN_COMPARE:
        LDA V2_PTR
        CMP V2_ADDR
        BNE BM_SPAN_BYTE
        LDA V2_PTR+1
        CMP V2_ADDR+1
        BNE BM_SPAN_BYTE
        RTS
BM_FATAL:
        LDX #<BM_FATAL_TEXT
        LDY #>BM_FATAL_TEXT
        JSR OI_PRINT
BM_HALT:
        JMP BM_HALT

; These includes are extracted unchanged from the qualified OIP1 source.
        INCLUDE "bank-monitor-apply.inc"
OI_FINISH:
        PHX
        LDA #3
        JSR V2W_SELECT
        PLX
        STZ V2_NMI_HOLD
        STZ DC_BINARY
        JSR V2W_RX_RESET
        JMP BM_MESSAGE
        INCLUDE "bank-monitor-target.inc"
        INCLUDE "bank-monitor-crc.inc"
        INCLUDE "prototype-engine.inc"

BM_BANNER: DB 13,10,"FLASH / MAINT - b15 example",13,10,"? help; Q returns to MON",13,10,0
BM_PROMPT: DB "FLASH> ",0
BM_BANK_TEXT: DB "Data bank B",0
BM_HELP: DB "B0..B3 data bank; D addr (16 bytes)",13,10
        DB "M addr byte... RAM 2000-64FF",13,10
        DB "F addr byte... flash edit (1-8 bytes)",13,10
        DB "I sectoraddr erase 4K; YES confirms F/I",13,10
        DB "Q MON B/A; B3:A/B/C/D/F + own image protected",13,10,0
BM_BAD_TEXT: DB "REFUSED: syntax (use ?)",13,10,0
BM_RANGE_TEXT: DB "REFUSED: range/protected image",13,10,0
BM_RAM_OK: DB "OK: RAM",13,10,0
BM_CONFIRM: DB "REWRITE SECTOR B",0
BM_CONFIRM_END: DB "00; type YES> ",0
BM_CANCEL_TEXT: DB "Cancelled; no flash change",13,10,0
BM_STAGE_BAD_TEXT: DB "REFUSED: staging CRC",13,10,0
BM_FATAL_TEXT: DB "STOP: code/F CRC mismatch; reset required",13,10,0
OI_OK_TEXT: DB "OK: verified sector",13,10,0
OI_SAME_TEXT: DB "OK: identical; no erase",13,10,0
OI_PREIMAGE_TEXT: DB "REFUSED: preimage CRC",13,10,0
OI_JOURNAL_TEXT: DB "REFUSED: durable wear reservation",13,10,0
OI_FLASH_TEXT: DB "FAILED: flash/readback; target may be torn",13,10,0
BM_CODE_END:

; Builder patches this CRC after linking. No mutable byte is in its coverage.
BM_CODE_CRC: DB 0,0
BM_HOME: DB 0
BM_BANK: DB 0
BM_OP: DB 0
BM_COUNT: DB 0
BM_ADDR: DB 0,0
BM_LAST: DB 0,0
BM_VALUES: DB 0,0,0,0,0,0,0,0
BM_DUMP_BYTES: DB 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
OI_HEADER: DB 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
OI_CRC: DB 0,0
OI_PAGES: DB 0
BM_END:
        ENDMOD
        END
