; Read-only all-bank archive helper; FT245 USB only, no vendor ROM calls.
; Only I/O writes: FT245 control/data/directions and bank-select PCR.
; No flash command/ID/probe, SPI, RTC, EEPROM, LED/PIA or EDU operation.
; Two complete passes; each bank stream has its own FNV32 trailer.
; Physical RESET is required to re-enter WDC; no native-context RTS trick.
        MODULE NF_ARCHIVE
        XDEF ARCHIVE_END
PTR EQU $E0
TEXT EQU $E4
EXPECT EQU $E8
HASH EQU $6000
TERM EQU $6004
STOP_HI EQU $6008
BANK EQU $600A
TIMER EQU $600C
TXBYTE EQU $600D
STOP_LO EQU $6010
PASS EQU $6011
SELF_HASH EQU $3FFC
FT_CTRL EQU $7FE0
FT_DATA EQU $7FE1
FT_DDRB EQU $7FE2
FT_DDRA EQU $7FE3
PCR EQU $7FEC
        CODE
ENTRY_65C02:
        JMP ARCHIVE_START
        DS 13,$EA
ENTRY_65C816:
        SEC
        DB $FB
        SEI
        CLD
        LDX #$FF
        TXS
        DB $F4,$00,$00,$2B
        DB $4B,$AB
        JMP ARCHIVE_START
ARCHIVE_START:
        SEI
        CLD
        LDX #$FF
        TXS
        LDA #$0C
        STA FT_CTRL
        STA FT_DDRB
        STZ FT_DDRA
        LDX #<TITLE
        LDY #>TITLE
        JSR PRINT
        JSR CHECK_SELF
        BCC FAIL_SELF
        LDX #<READY
        LDY #>READY
        JSR PRINT
        JSR GET_BYTE
        BCC FAIL_INPUT
        CMP #'G'
        BNE FAIL_INPUT
        JSR GET_BYTE
        BCC FAIL_INPUT
        CMP #13
        BNE FAIL_INPUT
        STZ PASS
ARCHIVE_PASS:
        STZ BANK
ARCHIVE_BANK:
        LDA BANK
        JSR SELECT_BANK
        LDX #<BANK_PREFIX
        LDY #>BANK_PREFIX
        JSR PRINT
        LDA BANK
        CLC
        ADC #'0'
        JSR PUT_BYTE
        LDX #<PASS_PREFIX
        LDY #>PASS_PREFIX
        JSR PRINT
        LDA PASS
        CLC
        ADC #'1'
        JSR PUT_BYTE
        JSR NEWLINE
        LDX #3
ARCHIVE_HASH_INIT:
        LDA FNV_OFFSET,X
        STA HASH,X
        DEX
        BPL ARCHIVE_HASH_INIT
        STZ PTR
        LDA #$80
        STA PTR+1
ARCHIVE_BYTE:
        LDA (PTR)
        PHA
        JSR FNV_BYTE
        PLA
        JSR PUT_BYTE
        INC PTR
        BNE ARCHIVE_BYTE
        INC PTR+1
        BNE ARCHIVE_BYTE
        LDX #0
ARCHIVE_TRAILER:
        LDA HASH,X
        JSR PUT_BYTE
        INX
        CPX #4
        BNE ARCHIVE_TRAILER
        LDA #3
        JSR SELECT_BANK
        INC BANK
        LDA BANK
        CMP #4
        BNE ARCHIVE_BANK
        INC PASS
        LDA PASS
        CMP #2
        BNE ARCHIVE_PASS
        LDX #<DONE
        LDY #>DONE
        JSR PRINT
HALT:   JMP HALT
FAIL_SELF:
        LDX #<SELF_BAD
        LDY #>SELF_BAD
        JSR PRINT
        JMP HALT
FAIL_INPUT:
        LDX #<INPUT_BAD
        LDY #>INPUT_BAD
        JSR PRINT
        JMP HALT
FAIL_TX:
        STZ FT_DDRA
        LDA #3
        JSR SELECT_BANK
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
        LDX #3
SELF_COMPARE:
        LDA SELF_HASH,X
        CMP HASH,X
        BNE SELF_MISMATCH
        DEX
        BPL SELF_COMPARE
        SEC
        RTS
SELF_MISMATCH:
        CLC
        RTS
        INCLUDE "archive-fnv.inc"
        INCLUDE "archive-ft245.inc"
SELECT_BANK:
        TAX
        LDA PCR
        AND #$11
        ORA BANK_BITS,X
        STA PCR
        RTS
NEWLINE:
        LDA #13
        JSR PUT_BYTE
        LDA #10
        JMP PUT_BYTE
BANK_BITS: DB $CC,$CE,$EC,$EE
FNV_OFFSET: DB $C5,$9D,$1C,$81
TITLE: DB 13,10,"STR8N-F READ-ONLY RAM ARCHIVER / NFA1 / USB",13,10,"Two passes of B0-B3, 32768 bytes plus FNV per bank. No flash commands.",13,10,0
READY: DB "ARCHIVER READY; G then Enter> ",0
BANK_PREFIX: DB "ARCHIVE B",0
PASS_PREFIX: DB " PASS ",0
DONE: DB 13,10,"ARCHIVE COMPLETE; PRESS PHYSICAL RESET",13,10,0
SELF_BAD: DB "REFUSED: archive RAM self-image hash mismatch; halted",13,10,0
INPUT_BAD: DB "CANCELLED/REFUSED: expected G then CR; no flash writes; halted",13,10,0
ARCHIVE_END:
        ENDMOD
        END
