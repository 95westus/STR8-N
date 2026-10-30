; Project RAM return for the qualified 65C02 WDC host workflow.
; Link at $2000. 18 code bytes, padded for WdcLink's 8192-byte upload.
; Read back before execution. This does not itself restore owner RAM.
; This is NOT a Foundation raw-L BIN linked at $0200.
        MODULE WDC_RETURN_RESET
        CODE
RETURN_START:
        SEI
        CLD
        LDX #$FF
        TXS
        LDA $7FEC
        AND #$11
        ORA #$EE
        STA $7FEC
        JMP $F004             ; Public Foundation RESET, B3 selected.
        DS 8174,$00
        ENDMOD
        END
