; ----------------------------------------------------------------------------
; Fixed HIMON image identity and compatible warm-entry ABI.
;
; START remains the callable $C000 entry. Its JMP skips this four-byte marker,
; which lets STR8 prove that the currently visible local payload understands
; the A5/5A/C3/3C warm signature before STR8 writes that signature into RAM.
; ----------------------------------------------------------------------------

HIMON_IMAGE_ENTRY        EQU             $C000
HIMON_IMAGE_ID_ADDR      EQU             $C003
HIMON_IMAGE_ID_SIZE      EQU             $04
HIMON_IMAGE_SIG0_VALUE   EQU             $A5
HIMON_IMAGE_SIG1_VALUE   EQU             $5A
HIMON_IMAGE_SIG2_VALUE   EQU             $C3
HIMON_IMAGE_SIG3_VALUE   EQU             $3C
