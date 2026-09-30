; Copied once on reset. Native entries contain only indirect JMP, preserving
; native widths, registers and the hardware interrupt frame for user code.
                        MODULE  V2_VECTORS
                        XDEF    START
                        XDEF    V2V_NMI
                        XDEF    V2V_IRQ_BRK
                        XDEF    V2V_COP
                        XDEF    V2V_ABORT
                        XDEF    V2V_NATIVE_COP
                        XDEF    V2V_NATIVE_BRK
                        XDEF    V2V_NATIVE_ABORT
                        XDEF    V2V_NATIVE_NMI
                        XDEF    V2V_NATIVE_IRQ
                        XDEF    V2V_DEFAULT
                        XDEF    V2V_RAM_SIGNATURE
                        XDEF    V2V_RAM_RESET_ENTRY
                        XDEF    V2V_RAM_HOLD_ENTRY
                        XDEF    V2V_RAM_CON_INIT_ENTRY
                        XDEF    V2V_RAM_PUTC_ENTRY
                        XDEF    V2V_RAM_GETC_ENTRY
                        XDEF    V2V_RAM_RAW_POLL_ENTRY
                        XDEF    V2V_RAM_CHECK_CANCEL_ENTRY
                        XDEF    V2V_RAM_RX_RESET_ENTRY
                        XDEF    V2V_RAM_HEX_OUT_ENTRY
                        XDEF    V2V_RAM_NEWLINE_ENTRY
                        XDEF    V2V_RAM_HEX_NIBBLE_ENTRY
                        XDEF    V2V_RAM_CAPS_QUERY_ENTRY
                        XDEF    V2V_RAM_BOARD_QUERY_ENTRY
                        XDEF    V2V_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "worker-public-symbols.inc"
                        CODE
START:
; M briefly gates NMI dispatch while publishing a complete RAM edit, including
; a possible two-byte NMI pointer. An NMI in that window is acknowledged by RTI.
V2V_NMI:               PHA
                        LDA     V2_NMI_HOLD
                        BNE     V2V_NMI_HELD
                        PLA
                        JMP     (V2_POINTERS)
V2V_NMI_HELD:          PLA
                        RTI
V2V_COP:               JMP     (V2_POINTERS+6)
V2V_ABORT:             JMP     (V2_POINTERS+8)
V2V_IRQ_BRK:
                        PHA
                        PHX
                        TSX
; Increment X before indexing so the page-one stack wraps correctly.
                        INX
                        INX
                        INX
                        LDA     $0100,X
                        AND     #$10
                        BNE     V2V_BRK
                        PLX
                        PLA
                        JMP     (V2_POINTERS+4)
V2V_BRK:               PLX
                        PLA
                        JMP     (V2_POINTERS+2)
V2V_NATIVE_COP:        JMP     (V2_NATIVE_POINTERS)
V2V_NATIVE_BRK:        JMP     (V2_NATIVE_POINTERS+2)
V2V_NATIVE_ABORT:      JMP     (V2_NATIVE_POINTERS+4)
V2V_NATIVE_NMI:        JMP     (V2_NATIVE_POINTERS+6)
V2V_NATIVE_IRQ:        JMP     (V2_NATIVE_POINTERS+8)
; RTI itself is valid in either mode and consumes that mode's hardware frame.
; This is a default, not an IRQ source acknowledgement or a native dispatcher.
V2V_DEFAULT:           RTI
; This eight-byte query exactly fills the alignment gap before the fixed ABI.
V2V_RAM_CAPS_QUERY:    LDA     #STR8V2_CAPS_FORMAT
                        LDX     #STR8V2_CAPS_FLAGS
                        LDY     #STR8V2_CAPS_LENGTH
                        SEC
                        RTS
; Keep the public RAM descriptor fixed even if private interrupt code changes.
V2V_RAM_SIGNATURE:     DB      "RA",STR8V2_RAM_FORMAT,STR8V2_RAM_CALLS
V2V_RAM_RESET_ENTRY:   JMP     V2V_RAM_RESET
V2V_RAM_HOLD_ENTRY:    JMP     V2V_RAM_HOLD
V2V_RAM_CON_INIT_ENTRY:JMP     V2W_CON_INIT
V2V_RAM_PUTC_ENTRY:    JMP     V2W_PUTC
V2V_RAM_GETC_ENTRY:    JMP     V2W_GETC
V2V_RAM_RAW_POLL_ENTRY:JMP     V2W_RAW_POLL
V2V_RAM_CHECK_CANCEL_ENTRY:
                        JMP     V2W_CHECK_CANCEL
V2V_RAM_RX_RESET_ENTRY:JMP     V2W_RX_RESET
V2V_RAM_HEX_OUT_ENTRY: JMP     V2V_RAM_HEX_OUT
V2V_RAM_NEWLINE_ENTRY: JMP     V2V_RAM_NEWLINE
V2V_RAM_HEX_NIBBLE_ENTRY:
                        JMP     V2V_RAM_HEX_NIBBLE
V2V_RAM_CAPS_QUERY_ENTRY:
                        JMP     V2V_RAM_CAPS_QUERY
V2V_RAM_BOARD_QUERY_ENTRY:
                        JMP     V2V_RAM_BOARD_QUERY

V2V_RAM_RESET:         LDA     V2_RESIDENT
                        JSR     V2W_SELECT
                        JMP     STR8V2_RESET
V2V_RAM_HOLD:          LDA     V2_RESIDENT
                        JSR     V2W_SELECT
                        JMP     STR8V2_HOLD

V2V_RAM_HEX_NIBBLE:    SEC
                        SBC     #'0'
                        BCC     V2V_RAM_HEX_FAIL
                        CMP     #$0A
                        BCC     V2V_RAM_HEX_OK
                        ORA     #$20
                        SBC     #('a'-'0')
                        CMP     #$06
                        BCS     V2V_RAM_HEX_FAIL
                        ADC     #$0A
V2V_RAM_HEX_OK:        SEC
                        RTS
V2V_RAM_HEX_FAIL:      CLC
                        RTS

V2V_RAM_HEX_OUT:       PHA
                        LSR     A
                        LSR     A
                        LSR     A
                        LSR     A
                        JSR     V2V_RAM_NIBBLE_OUT
                        PLA
                        AND     #$0F
V2V_RAM_NIBBLE_OUT:    CMP     #$0A
                        BCC     V2V_RAM_NIBBLE_ASCII
                        ADC     #$06
V2V_RAM_NIBBLE_ASCII:  ADC     #'0'
                        JMP     V2W_PUTC
V2V_RAM_NEWLINE:       LDA     #$0D
                        JSR     V2W_PUTC
                        LDA     #$0A
                        JMP     V2W_PUTC

V2V_RAM_BOARD_QUERY:   LDX     V2_CPU
                        LDY     #(STR8V2_BOARD_FT245|STR8V2_BOARD_ACIA|STR8V2_BOARD_ACIA_TIMED|STR8V2_BOARD_FT245_PRESENT)
                        LDA     V2_CONSOLE
                        BEQ     V2V_RAM_BOARD_DONE
                        LDY     #(STR8V2_BOARD_FT245|STR8V2_BOARD_ACIA|STR8V2_BOARD_ACIA_TIMED|STR8V2_BOARD_SELECTED_ACIA)
V2V_RAM_BOARD_DONE:    LDA     #STR8V2_BOARD_FORMAT
                        SEC
                        RTS
V2V_END:
                        ENDMOD
                        END
