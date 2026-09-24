; STR8-N V2 bank-independent RAM ABI hardware probe.
; Load at $2000 under alpha16 and execute G 2000. No flash is written.
                        MODULE  V2_RAM_ABI_TEST
                        XDEF    START
                        XDEF    PROBE_END
                        INCLUDE "str8n-v2-public.inc"
                        CODE

VIA_PCR                 EQU     $7FEC

START:                  SEI
                        CLD
                        LDA     STR8V2_RAM_SIGNATURE
                        CMP     #'R'
                        BNE     PROBE_FAIL
                        LDA     STR8V2_RAM_SIGNATURE+1
                        CMP     #'A'
                        BNE     PROBE_FAIL
                        LDA     STR8V2_RAM_SIGNATURE+2
                        CMP     #STR8V2_RAM_FORMAT
                        BNE     PROBE_FAIL
                        LDA     STR8V2_RAM_SIGNATURE+3
                        CMP     #STR8V2_RAM_CALLS
                        BNE     PROBE_FAIL

                        LDX     #$00
PROBE_BANK:             LDA     VIA_PCR
                        AND     #$11
                        ORA     PROBE_BITS,X
                        STA     VIA_PCR
                        LDA     #'B'
                        JSR     STR8V2_RAM_PUTC
                        TXA
                        CLC
                        ADC     #'0'
                        JSR     STR8V2_RAM_PUTC
                        LDA     #' '
                        JSR     STR8V2_RAM_PUTC
; A returning RAM call must leave the caller's flash overlay selected.
                        LDA     VIA_PCR
                        AND     #$EE
                        CMP     PROBE_BITS,X
                        BNE     PROBE_FAIL
                        INX
                        CPX     #$04
                        BNE     PROBE_BANK

                        JSR     STR8V2_RAM_CAPS_QUERY
                        BCC     PROBE_FAIL
                        CMP     #STR8V2_CAPS_FORMAT
                        BNE     PROBE_FAIL
                        CPX     #STR8V2_CAPS_FLAGS
                        BNE     PROBE_FAIL
                        CPY     #STR8V2_CAPS_LENGTH
                        BNE     PROBE_FAIL
                        JSR     STR8V2_RAM_BOARD_QUERY
                        BCC     PROBE_FAIL
                        CMP     #STR8V2_BOARD_FORMAT
                        BNE     PROBE_FAIL
                        LDX     #$00
PROBE_PASS:             LDA     PROBE_PASS_TEXT,X
                        BEQ     PROBE_HOLD
                        JSR     STR8V2_RAM_PUTC
                        INX
                        BRA     PROBE_PASS

PROBE_FAIL:             LDX     #$00
PROBE_FAIL_PRINT:       LDA     PROBE_FAIL_TEXT,X
                        BEQ     PROBE_HOLD
                        JSR     STR8V2_RAM_PUTC
                        INX
                        BRA     PROBE_FAIL_PRINT
PROBE_HOLD:             JMP     STR8V2_RAM_HOLD

PROBE_BITS:             DB      $CC,$CE,$EC,$EE
PROBE_PASS_TEXT:        DB      "RAM ABI: PASS",$0D,$0A,0
PROBE_FAIL_TEXT:        DB      "RAM ABI: FAIL",$0D,$0A,0
PROBE_END:
                        ENDMOD
                        END
