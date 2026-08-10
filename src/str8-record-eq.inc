; ----------------------------------------------------------------------------
; str8-record-eq.inc
; Fixed STR8 V1 validated-record service ABI.
; Keep this byte-for-byte aligned with the frozen contract in
; DOC/GUIDES/PLANNING/STR8_MULTIBOOT_BANK_VOLUMES.md.
; ----------------------------------------------------------------------------

STR8_RECORD_SERVICE      EQU             $F009
STR8_REC_SIG0_ADDR       EQU             $F00C
STR8_REC_SIG1_ADDR       EQU             $F00D
STR8_REC_VERSION_ADDR    EQU             $F00E
STR8_REC_CAPS_ADDR       EQU             $F00F

STR8_REC_SIG0_VALUE      EQU             $53
STR8_REC_SIG1_VALUE      EQU             $52
STR8_REC_VERSION_VALUE   EQU             $01
STR8_REC_CAP_BUFFER      EQU             $01
STR8_REC_CAP_CONSOLE     EQU             $02
STR8_REC_CAP_APPLY_LF    EQU             $04
STR8_REC_CAPS_V1         EQU             $07

STR8_REC_OP              EQU             $7E95
STR8_REC_FORMAT          EQU             $7E96
STR8_REC_SOURCE          EQU             $7E97
STR8_REC_STATUS          EQU             $7E98
STR8_REC_SRC_LO          EQU             $7E99
STR8_REC_SRC_HI          EQU             $7E9A
STR8_REC_SRC_LEN         EQU             $7E9B
STR8_REC_KIND            EQU             $7E9C
STR8_REC_FLAGS           EQU             $7E9D
STR8_REC_ADDR_LO         EQU             $7E9E
STR8_REC_ADDR_HI         EQU             $7E9F
STR8_REC_DATA_LEN        EQU             $7EA0
STR8_REC_ENTRY_LO        EQU             $7EA1
STR8_REC_ENTRY_HI        EQU             $7EA2
STR8_REC_DATA_LO         EQU             $7EA3
STR8_REC_DATA_HI         EQU             $7EA4
STR8_REC_FAIL_LO         EQU             $7EA5
STR8_REC_FAIL_HI         EQU             $7EA6
STR8_REC_OBSERVED        EQU             $7EA7
STR8_REC_EXPECTED        EQU             $7EA8

STR8_REC_DATA_BUF        EQU             $7B00
STR8_REC_DATA_BUF_LO     EQU             $00
STR8_REC_DATA_BUF_HI     EQU             $7B
STR8_REC_DATA_MAX        EQU             $FC

STR8_REC_OP_PARSE        EQU             $01
STR8_REC_OP_APPLY_LF     EQU             $02
STR8_REC_FORMAT_S19      EQU             $01
STR8_REC_SOURCE_BUFFER   EQU             $00
STR8_REC_SOURCE_CONSOLE  EQU             $01

STR8_REC_KIND_NONE       EQU             $00
STR8_REC_KIND_METADATA   EQU             $01
STR8_REC_KIND_DATA       EQU             $02
STR8_REC_KIND_END        EQU             $03
STR8_REC_FLAG_ENTRY_VALID EQU            $01

STR8_REC_OK              EQU             $00
STR8_REC_BAD_OP          EQU             $01
STR8_REC_BAD_FORMAT      EQU             $02
STR8_REC_BAD_SOURCE      EQU             $03
STR8_REC_BAD_START       EQU             $04
STR8_REC_BAD_TYPE        EQU             $05
STR8_REC_BAD_HEX         EQU             $06
STR8_REC_BAD_COUNT       EQU             $07
STR8_REC_BAD_CHECKSUM    EQU             $08
STR8_REC_BAD_END         EQU             $09
STR8_REC_LF_PROTECT      EQU             $0A
STR8_REC_LF_NEED_ERASE   EQU             $0B
STR8_REC_LF_WRITE        EQU             $0C
STR8_REC_LF_VERIFY       EQU             $0D
STR8_REC_ABORT           EQU             $0E

; Private worker mode used by STR8_REC_OP_APPLY_LF.
STR8_COPY_MODE_PROGRAM_RECORD EQU        $07
