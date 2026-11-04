; STR8N-F minimal release RAM migrator, USB FT245 only.
; Project-authored RAM bank/flash/FT245/FNV patterns; no vendor firmware/code.
; Code/data $2000-$3FFF, payload $4000-$4FFF, scratch $6000-$601F, ZP $E0-$E9.
; All executing code, strings and flash polling stay in RAM. No F/MON calls.
; Host must escrow RAM before loading, read back this image, render NFM1 plan
; and durably reserve every actual erase before EXEC/confirmation.
        MODULE NF_MIGRATE
        XDEF MIG_END
PTR EQU $E0
BUF EQU $E2
TEXT EQU $E4
ROW EQU $E6
EXPECT EQU $E8
HASH EQU $6000
TERM EQU $6004
STOP_HI EQU $6008
INDEX EQU $6009
BANK EQU $600A
SECTOR EQU $600B
TIMER EQU $600C
TXBYTE EQU $600D
FLASH_DATA EQU $600E
FLASH_ERROR EQU $600F
STOP_LO EQU $6010
PLAN EQU $3000
SELF_HASH EQU $3FFC
FT_CTRL EQU $7FE0
FT_DATA EQU $7FE1
FT_DDRB EQU $7FE2
FT_DDRA EQU $7FE3
PCR EQU $7FEC
LED EQU $7FA0
PIA_CRA EQU $7FA1
        CODE
; Host selects entry from the WDC debugger's detected CPU family.
ENTRY_65C02:
        JMP MIG_START
        DS 13,$EA
ENTRY_65C816:
        SEC
        DB $FB                 ; XCE: enter emulation, independent of M/X widths.
        SEI
        CLD
        LDX #$FF
        TXS
        DB $F4,$00,$00,$2B     ; PEA 0000 / PLD: D=0.
        DB $4B,$AB             ; PHK / PLB: DBR=bank-zero RAM code.
        JMP MIG_START
MIG_START:
        SEI
        CLD
        LDX #$FF
        TXS
        LDA #$0C
        STA FT_CTRL
        STA FT_DDRB
        STZ FT_DDRA
        LDA #$30
        STA PIA_CRA
        LDA #$FF
        STA LED
        LDA #$34
        STA PIA_CRA
        LDA #1
        STA LED
        STZ INDEX
        LDX #<TITLE
        LDY #>TITLE
        JSR PRINT
        JSR CHECK_SELF
        BCC FAIL_SELF
        JSR CHECK_PLAN
        BCC FAIL_PLAN
        LDX #<SELF_OK
        LDY #>SELF_OK
        JSR PRINT
        JSR GUARD_INITIAL_ALL
        BCC FAIL_SOURCE
        LDA #3
        JSR SELECT_BANK
        JSR IDENTIFY_FLASH
        BCC FAIL_CHIP
        LDX #<SOURCE_OK
        LDY #>SOURCE_OK
        JSR PRINT
        LDX #<CONFIRM
        LDY #>CONFIRM
        JSR PRINT
        JSR GET_BYTE
        BCC FAIL_TIMEOUT
        CMP #3
        BEQ CANCELLED
        CMP #'Y'
        BNE FAIL_CONFIRM
        JSR GET_BYTE
        BCC FAIL_TIMEOUT
        CMP #13
        BNE FAIL_CONFIRM
        ; Discard one already queued LF from a terminal's CR/LF pair.
        JSR POLL_BYTE
        BCC MIG_NEXT
        CMP #10
        BNE FAIL_CONFIRM
MIG_NEXT:
        JSR SET_ROW
        LDY #0
        LDA (ROW),Y
        STA SECTOR
        LDX #<PHASE_TARGET
        LDY #>PHASE_TARGET
        JSR PRINT
        LDA INDEX
        CLC
        ADC #'1'
        JSR PUT_BYTE
        LDA #'/'
        JSR PUT_BYTE
        LDA PLAN+5
        CLC
        ADC #'0'
        JSR PUT_BYTE
        LDA #' '
        JSR PUT_BYTE
        JSR PRINT_DEST
        JSR NEWLINE
        JSR CHECK_SELF
        BCC FAIL_SELF
        JSR GUARD_ROW_BEFORE
        BCC FAIL_SOURCE
        LDX #<SEND
        LDY #>SEND
        JSR PRINT
        JSR PRINT_DEST
        JSR NEWLINE
        STZ BUF
        LDA #$40
        STA BUF+1
RECEIVE:
        JSR GET_BYTE
        BCC FAIL_TIMEOUT
        STA (BUF)
        INC BUF
        BNE RECEIVE
        INC BUF+1
        LDA BUF+1
        CMP #$50
        BNE RECEIVE
        STZ PTR
        LDA #$40
        STA PTR+1
        STZ STOP_LO
        LDA #$50
        STA STOP_HI
        JSR HASH_RANGE
        LDA ROW
        CLC
        ADC #8
        STA EXPECT
        LDA ROW+1
        STA EXPECT+1
        JSR COMPARE_HASH
        BCC FAIL_PAYLOAD
        ; Commit-last journal transfers carry FF at their final commit byte.
        LDY #1
        LDA (ROW),Y
        BEQ RECEIVE_VALID
        LDA $40FF
        CMP #$FF
        BNE FAIL_PAYLOAD
RECEIVE_VALID:
        LDX #<PAYLOAD_OK
        LDY #>PAYLOAD_OK
        JSR PRINT
        JSR CHECK_SELF
        BCC FAIL_SELF
        JSR GUARD_ROW_BEFORE
        BCC FAIL_SOURCE
        LDX #<ERASING
        LDY #>ERASING
        JSR PRINT
        JSR SET_DEST_PTR
        JSR ERASE_RAW
        BCC FAIL_FLASH
        JSR VERIFY_BLANK
        BCC FAIL_FLASH
        LDX #<ERASE_OK
        LDY #>ERASE_OK
        JSR PRINT
        STZ BUF
        LDA #$40
        STA BUF+1
        JSR SET_DEST_PTR
PROGRAM_BYTE:
        LDA (BUF)
        CMP #$FF
        BEQ PROGRAM_NEXT
        STA FLASH_DATA
        JSR PROGRAM_RAW
        BCC FAIL_FLASH
PROGRAM_NEXT:
        INC BUF
        INC PTR
        BNE PROGRAM_BYTE
        INC BUF+1
        INC PTR+1
        LDA BUF+1
        CMP #$50
        BNE PROGRAM_BYTE
        JSR VERIFY_STAGED
        BCC FAIL_FLASH
        LDX #<PROGRAM_OK
        LDY #>PROGRAM_OK
        JSR PRINT
        LDY #1
        LDA (ROW),Y
        BEQ COMMIT_DONE
        LDX #<COMMITTING
        LDY #>COMMITTING
        JSR PRINT
        LDA #$FF
        STA PTR
        LDA SECTOR
        STA PTR+1
        STZ FLASH_DATA
        JSR PROGRAM_RAW
        BCC FAIL_FLASH
        LDA (PTR)
        BNE FAIL_FLASH
        ; Match staging to final committed data for the second full comparison.
        STZ $40FF
        JSR VERIFY_STAGED
        BCC FAIL_FLASH
COMMIT_DONE:
        JSR HASH_B3
        LDA ROW
        CLC
        ADC #12
        STA EXPECT
        LDA ROW+1
        STA EXPECT+1
        JSR COMPARE_HASH
        BCC FAIL_POSTIMAGE
        LDA #1
        STA LED
        LDX #<ROW_OK
        LDY #>ROW_OK
        JSR PRINT
        INC INDEX
        LDA INDEX
        CMP PLAN+5
        BNE MIG_NEXT
        JSR GUARD_FINAL_ALL
        BCC FAIL_POSTIMAGE
        LDX #<DONE
        LDY #>DONE
        JSR PRINT
HALT:   JMP HALT

CANCELLED:
        LDX #<CANCEL_TEXT
        LDY #>CANCEL_TEXT
        JMP STOP_TEXT
FAIL_SELF:
        LDX #<SELF_BAD
        LDY #>SELF_BAD
        JMP STOP_TEXT
FAIL_PLAN:
        LDX #<PLAN_BAD
        LDY #>PLAN_BAD
        JMP STOP_TEXT
FAIL_SOURCE:
        LDX #<SOURCE_BAD
        LDY #>SOURCE_BAD
        JMP STOP_TEXT
FAIL_CHIP:
        LDX #<CHIP_BAD
        LDY #>CHIP_BAD
        JMP STOP_TEXT
FAIL_CONFIRM:
        LDX #<CONFIRM_BAD
        LDY #>CONFIRM_BAD
        JMP STOP_TEXT
FAIL_TIMEOUT:
        LDX #<TIMEOUT_BAD
        LDY #>TIMEOUT_BAD
        JMP STOP_TEXT
FAIL_PAYLOAD:
        LDX #<PAYLOAD_BAD
        LDY #>PAYLOAD_BAD
        JMP STOP_TEXT
FAIL_FLASH:
        LDX #<FLASH_BAD
        LDY #>FLASH_BAD
        JMP STOP_TEXT
FAIL_POSTIMAGE:
        LDX #<POSTIMAGE_BAD
        LDY #>POSTIMAGE_BAD
STOP_TEXT:
        JSR PRINT
        LDX #<STOPPED
        LDY #>STOPPED
        JSR PRINT
        JMP HALT
FAIL_TX:
        STZ FT_DDRA
        JMP HALT

CHECK_SELF:
        STZ PTR
        LDA #$20
        STA PTR+1
        LDA #$FC
        STA STOP_LO
        LDA #$3F
        STA STOP_HI
        JSR HASH_RANGE
        LDA #<SELF_HASH
        STA EXPECT
        LDA #>SELF_HASH
        STA EXPECT+1
        JMP COMPARE_HASH
CHECK_PLAN:
        LDX #3
PLAN_MAGIC_LOOP:
        LDA PLAN,X
        CMP MAGIC,X
        BNE CHECK_BAD
        DEX
        BPL PLAN_MAGIC_LOOP
        LDA PLAN+4
        CMP #1
        BNE CHECK_BAD
        LDA PLAN+5
        BEQ CHECK_BAD
        CMP #4
        BCS CHECK_BAD
        LDA PLAN+6
        ORA PLAN+7
        BNE CHECK_BAD
        LDX #7
PLAN_RESERVED_LOOP:
        LDA PLAN+$18,X
        BNE CHECK_BAD
        DEX
        BPL PLAN_RESERVED_LOOP
        STZ INDEX
PLAN_ROW_LOOP:
        JSR SET_ROW
        LDA INDEX
        BEQ PLAN_FIRST
        CMP #1
        BNE PLAN_C
        LDA PLAN+5
        CMP #3
        BNE PLAN_C
        BRA PLAN_D
PLAN_FIRST:
        LDA PLAN+5
        CMP #2
        BEQ PLAN_D
        LDA #$F0
        LDX #0
        BRA PLAN_EXPECT
PLAN_D:
        LDA #$D0
        LDX #1
        BRA PLAN_EXPECT
PLAN_C:
        LDA #$C0
        LDX #1
PLAN_EXPECT:
        LDY #0
        CMP (ROW),Y
        BNE CHECK_BAD
        TXA
        INY
        CMP (ROW),Y
        BNE CHECK_BAD
        INY
        LDA (ROW),Y
        INY
        ORA (ROW),Y
        BNE CHECK_BAD
        INC INDEX
        LDA INDEX
        CMP PLAN+5
        BNE PLAN_ROW_LOOP
        STZ INDEX
        SEC
        RTS
CHECK_BAD:
        CLC
        RTS
SET_ROW:
        LDA INDEX
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #$20
        STA ROW
        LDA #$30
        STA ROW+1
        RTS
GUARD_INITIAL_ALL:
        STZ BANK
INITIAL_BANK:
        LDA BANK
        JSR SELECT_BANK
        JSR HASH_VISIBLE_BANK
        LDX #<SOURCE_BANK
        LDY #>SOURCE_BANK
        JSR PRINT
        JSR PRINT_BANK_HASH
        LDA BANK
        ASL A
        ASL A
        CLC
        ADC #8
        STA EXPECT
        LDA #$30
        STA EXPECT+1
        JSR COMPARE_HASH
        BCC GUARD_BAD
        INC BANK
        LDA BANK
        CMP #4
        BNE INITIAL_BANK
        SEC
        RTS
GUARD_FINAL_ALL:
        STZ BANK
FINAL_BANK:
        LDA BANK
        JSR SELECT_BANK
        JSR HASH_VISIBLE_BANK
        LDX #<FINAL_BANK_TEXT
        LDY #>FINAL_BANK_TEXT
        JSR PRINT
        JSR PRINT_BANK_HASH
        LDA BANK
        CMP #3
        BEQ FINAL_B3
        ASL A
        ASL A
        CLC
        ADC #8
        BRA FINAL_EXPECT
FINAL_B3:
        LDA PLAN+5
        DEC A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #$2C
FINAL_EXPECT:
        STA EXPECT
        LDA #$30
        STA EXPECT+1
        JSR COMPARE_HASH
        BCC GUARD_BAD
        INC BANK
        LDA BANK
        CMP #4
        BNE FINAL_BANK
        SEC
        RTS
GUARD_ROW_BEFORE:
        JSR HASH_B3
        LDA ROW
        CLC
        ADC #4
        STA EXPECT
        LDA ROW+1
        STA EXPECT+1
        JMP COMPARE_HASH
GUARD_BAD:
        CLC
        RTS
HASH_B3:
        LDA #3
        JSR SELECT_BANK
HASH_VISIBLE_BANK:
        STZ PTR
        LDA #$80
        STA PTR+1
        STZ STOP_LO
        STZ STOP_HI
        JMP HASH_RANGE
COMPARE_HASH:
        LDY #0
HASH_COMPARE_LOOP:
        LDA (EXPECT),Y
        CMP HASH,Y
        BNE GUARD_BAD
        INY
        CPY #4
        BNE HASH_COMPARE_LOOP
        SEC
        RTS

; FNV-1a code follows the project's previously used 32-bit multiply pattern.
HASH_RANGE:
        LDX #3
HASH_INIT:
        LDA FNV_OFFSET,X
        STA HASH,X
        DEX
        BPL HASH_INIT
HASH_NEXT:
        LDA (PTR)
        JSR FNV_BYTE
        INC PTR
        BNE HASH_TEST
        INC PTR+1
HASH_TEST:
        LDA PTR
        CMP STOP_LO
        BNE HASH_NEXT
        LDA PTR+1
        CMP STOP_HI
        BNE HASH_NEXT
        RTS
FNV_BYTE:
        EOR HASH
        STA HASH
        LDX #3
FNV_COPY:
        LDA HASH,X
        STA TERM,X
        DEX
        BPL FNV_COPY
        LDX #1
        JSR FNV_SHIFT_ADD
        LDX #3
        JSR FNV_SHIFT_ADD
        LDX #3
        JSR FNV_SHIFT_ADD
        LDX #1
        JSR FNV_SHIFT_ADD
        LDA HASH+3
        CLC
        ADC TERM+1
        STA HASH+3
        RTS
FNV_SHIFT_ADD:
        ASL TERM
        ROL TERM+1
        ROL TERM+2
        ROL TERM+3
        DEX
        BNE FNV_SHIFT_ADD
        CLC
        LDA HASH
        ADC TERM
        STA HASH
        LDA HASH+1
        ADC TERM+1
        STA HASH+1
        LDA HASH+2
        ADC TERM+2
        STA HASH+2
        LDA HASH+3
        ADC TERM+3
        STA HASH+3
        RTS

SELECT_BANK:
        TAX
        LDA PCR
        AND #$11
        ORA BANK_BITS,X
        STA PCR
        RTS
IDENTIFY_FLASH:
        JSR UNLOCK
        LDA #$90
        STA $D555
        LDA $8000
        STA $6011
        LDA $8001
        STA $6012
        LDA #$F0
        STA $8000
        LDX #<FLASH_ID_TEXT
        LDY #>FLASH_ID_TEXT
        JSR PRINT
        LDA $6011
        JSR HEX_BYTE
        LDA #'/'
        JSR PUT_BYTE
        LDA $6012
        JSR HEX_BYTE
        JSR NEWLINE
        LDA $6011
        CMP #$BF
        BNE GUARD_BAD
        LDA $6012
        CMP #$B5
        BNE GUARD_BAD
        SEC
        RTS
SET_DEST_PTR:
        STZ PTR
        LDA SECTOR
        STA PTR+1
        RTS
UNLOCK:
        LDA #$F0
        STA LED
        LDA #$AA
        STA $D555
        LDA #$55
        STA $AAAA
        RTS
ERASE_RAW:
        JSR UNLOCK
        LDA #$80
        STA $D555
        JSR UNLOCK
        LDA #$30
        STA (PTR)
        LDA #$FF
        STA FLASH_DATA
        LDA #8
        BRA WAIT_FLASH
PROGRAM_RAW:
        JSR UNLOCK
        LDA #$A0
        STA $D555
        LDA FLASH_DATA
        STA (PTR)
        LDA #2
WAIT_FLASH:
        PHA
        LDX #0
        LDY #0
FLASH_POLL:
        LDA (PTR)
        CMP FLASH_DATA
        BEQ FLASH_OK
        BIT FLASH_DATA
        DEX
        BNE FLASH_POLL
        BIT FLASH_DATA
        DEY
        BNE FLASH_POLL
        PLA
        DEC A
        BEQ FLASH_TIMEOUT
        PHA
        BRA FLASH_POLL
FLASH_TIMEOUT:
        LDA #$F0
        STA $D555
        CLC
        RTS
FLASH_OK:
        PLA
        LDA #$F0
        STA $D555
        SEC
        RTS
VERIFY_BLANK:
        JSR SET_DEST_PTR
BLANK_BYTE:
        LDA (PTR)
        CMP #$FF
        BNE GUARD_BAD
        INC PTR
        BNE BLANK_BYTE
        INC PTR+1
        LDA PTR+1
        SEC
        SBC SECTOR
        CMP #$10
        BNE BLANK_BYTE
        SEC
        RTS
VERIFY_STAGED:
        JSR SET_DEST_PTR
        STZ BUF
        LDA #$40
        STA BUF+1
VERIFY_BYTE:
        LDA (BUF)
        CMP (PTR)
        BNE GUARD_BAD
        INC BUF
        INC PTR
        BNE VERIFY_BYTE
        INC BUF+1
        INC PTR+1
        LDA BUF+1
        CMP #$50
        BNE VERIFY_BYTE
        SEC
        RTS

; FT245 handshakes retain the project's proven two-NOP bus setup/hold pattern.
POLL_BYTE:
        STZ FT_DDRA
        LDA #2
        BIT FT_CTRL
        BNE POLL_EMPTY
        LDA #8
        TRB FT_CTRL
        NOP
        NOP
        LDA FT_DATA
        PHA
        LDA #8
        TSB FT_CTRL
        PLA
        SEC
        RTS
POLL_EMPTY:
        CLC
        RTS
GET_BYTE:
        LDX #0
        LDY #0
        LDA #32
        STA TIMER
GET_POLL:
        JSR POLL_BYTE
        BCS GET_DONE
        DEX
        BNE GET_POLL
        DEY
        BNE GET_POLL
        DEC TIMER
        BNE GET_POLL
        CLC
GET_DONE:
        RTS
PUT_BYTE:
        STA TXBYTE
        PHX
        PHY
        LDX #0
        LDY #0
PUT_WAIT:
        LDA #1
        BIT FT_CTRL
        BEQ PUT_READY
        DEX
        BNE PUT_WAIT
        DEY
        BNE PUT_WAIT
        PLY
        PLX
        JMP FAIL_TX
PUT_READY:
        STZ FT_DDRA
        LDA TXBYTE
        STA FT_DATA
        NOP
        NOP
        LDA #4
        TSB FT_CTRL
        DEC FT_DDRA
        NOP
        NOP
        LDA #4
        TRB FT_CTRL
        STZ FT_DDRA
        PLY
        PLX
        RTS
PRINT:
        STX TEXT
        STY TEXT+1
        LDY #0
PRINT_NEXT:
        LDA (TEXT),Y
        BEQ PRINT_DONE
        JSR PUT_BYTE
        INY
        BNE PRINT_NEXT
        INC TEXT+1
        BRA PRINT_NEXT
PRINT_DONE:
        RTS
PRINT_DEST:
        LDA #'B'
        JSR PUT_BYTE
        LDA #'3'
        JSR PUT_BYTE
        LDA #':'
        JSR PUT_BYTE
        LDA SECTOR
        LSR A
        LSR A
        LSR A
        LSR A
        CMP #10
        BCC DEST_DIGIT
        CLC
        ADC #7
DEST_DIGIT:
        CLC
        ADC #'0'
        JMP PUT_BYTE
PRINT_BANK_HASH:
        LDA BANK
        CLC
        ADC #'0'
        JSR PUT_BYTE
        LDA #'='
        JSR PUT_BYTE
        LDX #3
PRINT_HASH_BYTE:
        LDA HASH,X
        JSR HEX_BYTE
        DEX
        BPL PRINT_HASH_BYTE
        JMP NEWLINE
HEX_BYTE:
        PHA
        LSR A
        LSR A
        LSR A
        LSR A
        JSR HEX_NIBBLE
        PLA
        AND #$0F
HEX_NIBBLE:
        CMP #10
        BCC HEX_DIGIT
        CLC
        ADC #7
HEX_DIGIT:
        CLC
        ADC #'0'
        JMP PUT_BYTE
NEWLINE:
        LDA #13
        JSR PUT_BYTE
        LDA #10
        JMP PUT_BYTE
MAGIC: DB "NFM1"
BANK_BITS: DB $CC,$CE,$EC,$EE
FNV_OFFSET: DB $C5,$9D,$1C,$81
TITLE: DB 13,10,"STR8N-F RAM MIGRATOR / NFM1 / USB",13,10,"Only B3:F and declared C/D may change. No B0 copy.",13,10,0
SELF_OK: DB "CHECK: RAM image and plan verified",13,10,0
SOURCE_OK: DB "CHECK: all four bank preimages and SST39SF010A BF/B5 verified",13,10,0
SOURCE_BANK: DB "CHECK source bank FNV B",0
FINAL_BANK_TEXT: DB "CHECK final bank FNV B",0
FLASH_ID_TEXT: DB "FLASH ID: ",0
CONFIRM: DB "Host backup and erase reservations must be durable. Ctrl-C cancels here.",13,10,"Y then Enter> ",0
PHASE_TARGET: DB "STEP ",0
SEND: DB "SEND 4096 BYTES FOR ",0
PAYLOAD_OK: DB "CHECK: staged 4096-byte payload FNV verified; preimage recheck",13,10,0
ERASING: DB "ERASE: issuing one reserved 4K erase; keep power stable",13,10,0
ERASE_OK: DB "ERASE: all 4096 bytes blank; PROGRAM begins",13,10,0
PROGRAM_OK: DB "PROGRAM: all 4096 staged bytes compared",13,10,0
COMMITTING: DB "JOURNAL: program commit byte last; verify final sector",13,10,0
ROW_OK: DB "VERIFY: complete B3 postimage verified; sector finished",13,10,0
DONE: DB "VERIFY: all four final banks match the plan",13,10,"MIGRATION VERIFIED; PRESS PHYSICAL RESET",13,10,0
CANCEL_TEXT: DB "CANCELLED: no flash erase/program was issued",13,10,0
SELF_BAD: DB "REFUSED: RAM self-image hash mismatch",13,10,0
PLAN_BAD: DB "REFUSED: NFM1 plan/order/destination/commit policy",13,10,0
SOURCE_BAD: DB "REFUSED: complete source-bank preimage changed",13,10,0
CHIP_BAD: DB "REFUSED: unsupported flash ID (require BF/B5)",13,10,0
CONFIRM_BAD: DB "REFUSED: expected Y then CR",13,10,0
TIMEOUT_BAD: DB "REFUSED: USB receive timeout; current sector not started",13,10,0
PAYLOAD_BAD: DB "REFUSED: staged payload hash/commit placeholder mismatch",13,10,0
FLASH_BAD: DB "FAILED: flash poll/readback; current destination may be torn",13,10,0
POSTIMAGE_BAD: DB "FAILED: final complete-bank postimage mismatch",13,10,0
STOPPED: DB "HALTED IN RAM. No automatic retry/reset. Keep host backups and phase log.",13,10,0
MIG_END:
        ENDMOD
        END
