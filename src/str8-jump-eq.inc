; ----------------------------------------------------------------------------
; str8-jump-eq.inc
; Shared resident/worker constants for non-destructive J0-J3 handoff.
; ----------------------------------------------------------------------------

STR8_COPY_MODE_JUMP_BANK EQU           $08

; Published bank-selector ABI. STR8_BANK_SELECT_SERVICE copies the current
; worker image to RAM, then tail-calls the fixed RAM entry so the selected ROM
; bank cannot replace an executing RTS. The caller and its return address must
; be below $8000.
STR8_BANK_SELECT_SERVICE EQU            $F010
STR8_BANK_SELECT_RAM     EQU            $0203

; Published live bank-latch state byte. Read the raw PCR byte; only bits in
; STR8_BANK_STATE_MASK are controlled by explicit bank selection. Explicit
; B0/B1/B2/B3 patterns are $CC/$CE/$EC/$EE. Other states are not bank IDs.
STR8_BANK_STATE_BYTE    EQU             $7FEC
STR8_BANK_STATE_MASK    EQU             $EE

; Published Bank Jump Record at the tail of the STR8 Recovery State Capsule.
; The worker commits this only after bank selection and vector validation,
; immediately before the final jump. HIMON cold clear preserves a valid row.
STR8_BANK_JUMP_SIG0_VALUE EQU           'B'
STR8_BANK_JUMP_SIG1_VALUE EQU           'J'
STR8_BANK_COUNT         EQU             $04
STR8_BANK_NONE          EQU             $FF

STR8_JUMP_STATUS_NONE   EQU             $00
STR8_JUMP_STATUS_BANK   EQU             $01
STR8_JUMP_STATUS_LOW    EQU             $02
STR8_JUMP_STATUS_ERASED EQU             $03
STR8_JUMP_STATUS_GO     EQU             $80
