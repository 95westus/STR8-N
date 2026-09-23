; STR8-N v2 signature followed by public three-byte JMP entries.
; JMP to RESET/HOLD; JSR to returning and reserved entries.
; Returning calls require initialized monitor RAM/worker, the monitor's flash
; bank mapped in, IRQ disabled, and decimal mode clear. On 816: E=1, D=0,
; DBR=0, PBR=0. No native-mode or reentrant calling convention is provided.
STR8V2_SIGNATURE        EQU     $F000
STR8V2_RESET            EQU     $F004
STR8V2_HOLD             EQU     $F007
STR8V2_CON_INIT         EQU     $F00A
STR8V2_PUTC             EQU     $F00D
STR8V2_GETC             EQU     $F010
STR8V2_RAW_POLL         EQU     $F013
STR8V2_CHECK_CANCEL     EQU     $F016
STR8V2_RX_RESET         EQU     $F019
STR8V2_READ_LINE        EQU     $F01C
STR8V2_HEX_OUT          EQU     $F01F
STR8V2_NEWLINE          EQU     $F022
STR8V2_HEX_NIBBLE       EQU     $F025
STR8V2_RESERVED0        EQU     $F028
STR8V2_RESERVED1        EQU     $F02B
STR8V2_RESERVED2        EQU     $F02E
STR8V2_RESERVED3        EQU     $F031

STR8V2_LINE             EQU     $7C00
STR8V2_LINE_LIMIT       EQU     $20
