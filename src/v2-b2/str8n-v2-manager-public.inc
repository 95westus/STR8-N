; Basic pinned-provider manager ABI, format 1. No indexed fast-slot ABI.
; Foreground, IRQ disabled, decimal clear; 816 E=1, DBR=PBR=0.
STR8MGR_INIT             EQU     $7108
STR8MGR_DISPATCH         EQU     $710B
STR8MGR_LOOKUP           EQU     $710E
STR8MGR_NAMED_DISPATCH   EQU     $7111
; COMMAND.REGISTER v2: A/X=four-byte descriptor (name word, target word),
; Y=0. Copies pointers; names/targets stay pinned. Names are 1..15 uppercase
; letters; built-in letters and compact address forms are reserved.
; Same errors as v1. These records are separate from the legacy eight slots.
; Named handlers receive X=first argument offset in the original line.
MG_NAMED_REGISTER_ROM   EQU     $ED00
MG_NAMED_DISPATCH_ROM   EQU     $ED03
MG_NAMED_TABLE          EQU     $7690 ; eight four-byte records
MG_NAMED_COUNT          EQU     $76B0 ; byte count, 0..32
MG_NAMED_ROLLBACK       EQU     $76B1
; DISPATCH: complete NUL-terminated command in STR8V2_LINE, <=40 bytes.
; Returns A=0 unrecognized, A=1 handled. X/Y/flags volatile; stack balanced.
; LOOKUP: A/X=name pointer low/high, Y=exact interface version.
; Names are case-sensitive ASCII, NUL terminated, <=31 bytes.
; C=1: A/X=entry pointer, Y=1 callable or Y=0 data. C=0: A=1 missing,
; A=2 incompatible version. X/Y and monitor scratch are volatile.
; Pinned results are valid until reset/reinitialization or core replacement.
MG_COUNT                EQU     $7DCB
MG_INDEX                EQU     $7DCC
MG_VERSION              EQU     $7DCD
MG_CALL                 EQU     $7DCE
MG_TABLE                EQU     $7DD0
MG_READY                EQU     $7DE8
MG_IMAGE_ID             EQU     $7DE9
MG_CAPACITY             EQU     $08
; SERVICE.REGISTER v1: A/X=descriptor pointer, Y=0. Six-byte descriptor:
; name pointer (word), nonzero version, kind (0=data/1=callable), target (word).
; Descriptor is copied; name/target remain pinned until reset/reinit.
; C=1,A=0 success; C=0,A=1 invalid,2 duplicate,3 full; scratch/AXY volatile.
MG_DYNAMIC_COUNT        EQU     $7DEB ; byte count, 0..48 in steps of six
MG_DYNAMIC_TABLE        EQU     $7600 ; 48 bytes; separate from command table
MG_DYNAMIC_CAPACITY     EQU     $08
; Private build placement, not callable extension ABI; discover via LOOKUP.
MG_SERVICE_LOOKUP_ROM   EQU     $E180
MG_SERVICE_REGISTER_ROM EQU     $E183
; LOOKUP("COMMAND.CORE", version 1): Y=0, A/X points to a read-only
; six-byte descriptor in manager RAM. Its tables are in resident-bank F ROM.
; The targets describe monitor control-flow entries, NOT RTS-callable services.
; Core entries have precedence and do not consume command-registration slots.
MG_CORE_FORMAT_OFFSET   EQU     $00     ; byte: descriptor format, 1
MG_CORE_COUNT_OFFSET    EQU     $01     ; byte: number of built-in commands
MG_CORE_KEYS_OFFSET     EQU     $02     ; word: packed one-byte command keys
MG_CORE_TARGETS_OFFSET  EQU     $04     ; word: corresponding handler addresses
MG_CORE_DESCRIPTOR_SIZE EQU     $06
