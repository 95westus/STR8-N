; STR8-N v2 signature followed by the resident compatibility facade.
; Fetching these ROM entries requires the resident flash bank to be visible;
; their returning targets are the same RAM implementations published below.
; Applications in any flash bank call the fixed STR8V2_RAM_* entries after
; checking STR8V2_RAM_SIGNATURE. IRQ must be disabled and decimal mode clear.
; On 816: E=1, D=0, DBR=0, PBR=0. Calls are neither native nor reentrant.
STR8V2_SIGNATURE        EQU     $F000
STR8V2_RESET            EQU     $F004
STR8V2_HOLD             EQU     $F007
STR8V2_CON_INIT         EQU     $F00A
STR8V2_PUTC             EQU     $F00D
STR8V2_GETC             EQU     $F010
STR8V2_RAW_POLL         EQU     $F013
STR8V2_CHECK_CANCEL     EQU     $F016
STR8V2_RX_RESET         EQU     $F019
; $F01C is retained as a reserved ROM-table slot. Line editing is monitor
; policy, not part of the bank-independent application ABI.
STR8V2_RESERVED_LINE    EQU     $F01C
STR8V2_HEX_OUT          EQU     $F01F
STR8V2_NEWLINE          EQU     $F022
STR8V2_HEX_NIBBLE       EQU     $F025
STR8V2_CAPS_QUERY       EQU     $F028
STR8V2_BOARD_QUERY      EQU     $F02B
; Source-compatible name for the slot that BOARD_QUERY now occupies.
STR8V2_RESERVED1        EQU     STR8V2_BOARD_QUERY
STR8V2_RESERVED2        EQU     $F02E
STR8V2_RESERVED3        EQU     $F031
STR8V2_CAPS_DATA        EQU     $F035

; CAPS_QUERY returns A=format, X=flags, Y=descriptor length, C=1.
; The fixed descriptor is "CA", format, flags. Native vectors are supported;
; native-mode calls into monitor services are deliberately not advertised.
STR8V2_CAPS_FORMAT      EQU     $01
STR8V2_CAP_65C02        EQU     $01
STR8V2_CAP_816_EMULATION EQU    $02
STR8V2_CAP_816_NATIVE_VECTORS EQU $04
STR8V2_CAP_816_NATIVE_CALLS EQU $08
STR8V2_CAP_BANK_INDEPENDENT EQU $10
STR8V2_CAPS_FLAGS       EQU     $17
STR8V2_CAPS_LENGTH      EQU     $04

; BOARD_QUERY returns A=format, X=detected CPU, Y=board/console flags, C=1.
STR8V2_BOARD_FORMAT     EQU     $01
STR8V2_CPU_65C02        EQU     $02
STR8V2_CPU_65C816       EQU     $16
STR8V2_BOARD_FT245      EQU     $01
STR8V2_BOARD_ACIA       EQU     $02
STR8V2_BOARD_ACIA_TIMED EQU     $04
STR8V2_BOARD_SELECTED_ACIA EQU  $08
STR8V2_BOARD_FT245_PRESENT EQU  $10

STR8V2_LINE             EQU     $7C00
STR8V2_LINE_LIMIT       EQU     $20

; RAM interrupt handler pointers. Each is a 16-bit bank-$00 address.
STR8V2_EMU_NMI_PTR      EQU     $7E00
STR8V2_EMU_BRK_PTR      EQU     $7E02
STR8V2_EMU_IRQ_PTR      EQU     $7E04
STR8V2_EMU_COP_PTR      EQU     $7E06
STR8V2_EMU_ABORT_PTR    EQU     $7E08
STR8V2_NATIVE_COP_PTR   EQU     $7E10
STR8V2_NATIVE_BRK_PTR   EQU     $7E12
STR8V2_NATIVE_ABORT_PTR EQU     $7E14
STR8V2_NATIVE_NMI_PTR   EQU     $7E16
STR8V2_NATIVE_IRQ_PTR   EQU     $7E18

; Publish native NMI pointers while E=1: increment this gate, write both
; pointer bytes, then clear it. Native handlers own their register widths,
; direct page/data bank requirements, interrupt source, frame, and RTI.
STR8V2_NMI_GATE         EQU     $00F4

; Initialized RAM ABI. Applications launched through STR8-N may call these
; entries with any flash bank visible. The RA descriptor is format, count.
STR8V2_RAM_SIGNATURE    EQU     $7E60
STR8V2_RAM_RESET        EQU     $7E64
STR8V2_RAM_HOLD         EQU     $7E67
STR8V2_RAM_CON_INIT     EQU     $7E6A
STR8V2_RAM_PUTC         EQU     $7E6D
STR8V2_RAM_GETC         EQU     $7E70
STR8V2_RAM_RAW_POLL     EQU     $7E73
STR8V2_RAM_CHECK_CANCEL EQU     $7E76
STR8V2_RAM_RX_RESET     EQU     $7E79
STR8V2_RAM_HEX_OUT      EQU     $7E7C
STR8V2_RAM_NEWLINE      EQU     $7E7F
STR8V2_RAM_HEX_NIBBLE   EQU     $7E82
STR8V2_RAM_CAPS_QUERY   EQU     $7E85
STR8V2_RAM_BOARD_QUERY  EQU     $7E88
STR8V2_RAM_FORMAT       EQU     $01
STR8V2_RAM_CALLS        EQU     $0D
