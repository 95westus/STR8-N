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
STR8_CONFIG_WORK_DEFAULT     EQU             $FF
; No flash WORK sector; SPI SRAM allocation is a future hardware contract.

STR8_CONFIG_TOP_BACKUP_SECTOR EQU            $FFF1
STR8_CONFIG_TOP_BACKUP_DEFAULT EQU           $2F
; Default $2F is Bank 2, sector F: protected raw backup of Bank 3 sector F.

; Scoped FNV/AP discovery policy. Fresh images remain disabled ($FF).
; Only $A0-$A7 are valid: low bits enroll B0/B1/B2; invalid values disable.
; The consumer reads this byte in B3 before changing banks. This constant
; does not provision a live board; updates require the guarded B3:F path.
STR8_CONFIG_FNV_POLICY       EQU             $FFF2
STR8_CONFIG_FNV_DEFAULT      EQU             $FF
; $FFF3-$FFF9 remain erased and unassigned.
