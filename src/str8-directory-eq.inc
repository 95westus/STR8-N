; ----------------------------------------------------------------------------
; str8-directory-eq.inc
; Frozen STR8-N V1 Bank Directory layout and read-only validator states.
; The directory exists only in Bank 3 at $FFB0-$FFEF.
; ----------------------------------------------------------------------------

STR8_DIR_BASE              EQU             $FFB0
STR8_DIR_END               EQU             $FFEF
STR8_DIR_RECORD_SIZE       EQU             $10
STR8_DIR_RECORD_COUNT      EQU             $04

STR8_DIR_TYPE              EQU             $00
STR8_DIR_RESERVED          EQU             $01
STR8_DIR_RESERVED_LEN      EQU             $03
STR8_DIR_DESCRIPTION       EQU             $04
STR8_DIR_DESCRIPTION_LEN   EQU             $05
STR8_DIR_SEAL              EQU             $09
STR8_DIR_ENTRY_LO          EQU             $0A
STR8_DIR_ENTRY_HI          EQU             $0B
STR8_DIR_JOURNAL           EQU             $0C
STR8_DIR_JOURNAL_LEN       EQU             $04

STR8_DIR_EMPTY_BYTE        EQU             $FF
STR8_DIR_SEAL_VALUE        EQU             $FE
STR8_DIR_NO_ENTRY          EQU             $FFFF
STR8_DIR_BANK3             EQU             $03
STR8_DIR_BANK3_ENTRY_MIN_HI EQU            $80
STR8_DIR_BANK3_ENTRY_MAX_HI EQU            $EF

STR8_DIR_PAIR_COMPLETE     EQU             $00
STR8_DIR_PAIR_ILLEGAL      EQU             $01
STR8_DIR_PAIR_STARTED      EQU             $02
STR8_DIR_PAIR_UNUSED       EQU             $03
STR8_DIR_PAIR_COUNT        EQU             $10
STR8_DIR_PAIR_NONE         EQU             $FF

STR8_DIR_JOURNAL_INVALID   EQU             $00
STR8_DIR_JOURNAL_FRESH     EQU             $01
STR8_DIR_JOURNAL_STARTED   EQU             $02
STR8_DIR_JOURNAL_COMPLETE  EQU             $03
STR8_DIR_JOURNAL_FULL      EQU             $04

STR8_DIR_RECORD_INVALID    EQU             $00
STR8_DIR_RECORD_EMPTY      EQU             $01
STR8_DIR_RECORD_INCOMPLETE EQU             $02
STR8_DIR_RECORD_COMPLETE   EQU             $03

; STR8_DIR_WRITE_BYTES status in A and STR8_REC_STATUS.
STR8_DIR_WRITE_OK          EQU             $00
STR8_DIR_WRITE_BAD_COUNT   EQU             $01
STR8_DIR_WRITE_BAD_RANGE   EQU             $02
STR8_DIR_WRITE_BAD_TRANS   EQU             $03
STR8_DIR_WRITE_WORKER      EQU             $04
STR8_DIR_WRITE_VERIFY      EQU             $05
