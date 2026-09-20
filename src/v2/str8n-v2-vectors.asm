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
                        XDEF    V2V_END
                        INCLUDE "str8n-v2-eq.inc"
                        CODE
START:
V2V_NMI:               JMP     (V2_POINTERS)
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
V2V_END:
                        ENDMOD
                        END
