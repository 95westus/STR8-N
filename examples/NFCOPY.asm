; Eight-byte STORE/RESTORE example, loaded at $3000.
; Same public BASE1/PR05 calls on 65C02 and 65C816 emulation.
; Prints P, then returns through Foundation HOLD to the active monitor.
; Public HOLD performs a cold monitor return; native tools use quiet UI/1.
        MODULE NFCOPY
        INCLUDE "../src/include/str8n-v2-public.inc"
        CODE
NFCOPY_START:
        LDA #'P'
        JSR STR8V2_RAM_PUTC
        JMP STR8V2_RAM_HOLD
        ENDMOD
        END
