; ----------------------------------------------------------------------------
; str8-console-eq.inc
; Fixed STR8-N raw console-service ABI.
; Bank 3 must be visible for every call.
; ABI_QUERY: C=1, A=resident ABI version, X=capabilities; Y preserved.
; CONSOLE_INIT restores the FT245R-facing VIA state; A=$0C and X/Y/C are
; preserved; N/Z reflect A.
; CHARIN returns A=raw byte and C=1; X/Y are preserved.
; CHAROUT accepts A=raw byte and returns A unchanged and C=1; X/Y are preserved.
; CHAR_READY is non-consuming: C=1 when a byte is ready, C=0 when empty;
; A/flags are clobbered except for carry, and X/Y are preserved.
; The services perform no echo or translation.
; ----------------------------------------------------------------------------

STR8_CONSOLE_INIT_SERVICE       EQU     $F003
STR8_ABI_QUERY_SERVICE          EQU     $F006
STR8_CHARIN_SERVICE             EQU     $F013
STR8_CHAROUT_SERVICE            EQU     $F019
STR8_CHAR_READY_SERVICE         EQU     $F03E

STR8_RESIDENT_ABI_VERSION       EQU     $01
STR8_ABI_CAP_RECORD_PARSER      EQU     $01
STR8_ABI_CAP_BANK_SELECT        EQU     $02
STR8_ABI_CAP_CHARIN             EQU     $04
STR8_ABI_CAP_CHAROUT            EQU     $08
STR8_ABI_CAP_CHAR_READY         EQU     $10
STR8_ABI_CAP_CONSOLE_INIT       EQU     $20
STR8_RESIDENT_ABI_CAPS          EQU     $3F
