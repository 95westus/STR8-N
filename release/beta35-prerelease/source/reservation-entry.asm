; Separate RAM wrapper for the original MIG_NEXT three-byte LDX instruction.
; Call the separately tested reservation helper once, before row zero.
        MODULE RESERVATION_ENTRY
        XDEF T_END
        INCLUDE "transaction-links.inc"
        CODE
T_ENTRY:
        LDA $6200
        BNE T_READY
        JSR $3000
        BCC T_BAD
T_READY:
        LDX $6200
        JMP MIG_NEXT_CONTINUE
T_BAD:  JMP MIG_FAIL
T_END:
        ENDMOD
