; STR8-N V1.21 MENU BANK MAINTENANCE + PROTECTED TOP UPDATE.
;
; This host/WDC source selects the menu variant in the maintained Bank
; Maintenance body. U embeds the current guarded Bank-3 F-to-F updater at
; $3700-$3FFF and its exact verified STR8-N top image at $4000-$4FFF.
; Build with `make bank-maint-menu`; load the resulting S19 with STR8-N L.
; If P is needed, stage its AP envelope at $5000 before loading this image.

STR8_BANK_MAINT_TOP     EQU 1
STR8_TOP_EMBED          EQU 1
STR8_DIRECTORY_REFRESH  EQU 0

        INCLUDE "str8n-v1.21-bank-maint-2000.asm"
