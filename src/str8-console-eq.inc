; ----------------------------------------------------------------------------
; str8-console-eq.inc
; Fixed STR8-N blocking console-service ABI.
; Bank 3 and the reset-initialized FT245R-facing VIA must be visible.
; CHARIN returns A=raw byte and C=1; X/Y are preserved.
; CHAROUT accepts A=raw byte and returns A unchanged and C=1; X/Y are preserved.
; Both services wait without a timeout and perform no echo or translation.
; ----------------------------------------------------------------------------

STR8_CHARIN_SERVICE     EQU             $F013
STR8_CHAROUT_SERVICE    EQU             $F019
