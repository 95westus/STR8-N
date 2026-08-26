; ----------------------------------------------------------------------------
; str8-config-eq.inc
; Bank-3 top-sector configuration pocket at $FFF0-$FFF9.
;
; A sector locator packs bank in the high nibble and CPU-visible sector in
; the low nibble. $FF means no sector is assigned. Only Banks 0-2 and sectors
; $8-$F are valid application-sector locators.
; ----------------------------------------------------------------------------

STR8_CONFIG_BASE             EQU             $FFF0
STR8_CONFIG_END              EQU             $FFF9
STR8_CONFIG_NONE             EQU             $FF

STR8_CONFIG_WORK_SECTOR      EQU             $FFF0
STR8_CONFIG_WORK_DEFAULT     EQU             $1E
; Default $1E is Bank 1, sector E.

STR8_CONFIG_TOP_BACKUP_SECTOR EQU            $FFF1
STR8_CONFIG_TOP_BACKUP_DEFAULT EQU           $1F
; Default $1F is Bank 1, sector F: protected raw backup of Bank 3 sector F.

; $FFF2-$FFF9 remain erased and unassigned. A future directory-expansion
; locator may consume one of them without changing these sector roles.
