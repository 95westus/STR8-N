; STR8-N v2 public three-byte JMP entries. JMP to RESET/HOLD; JSR to others.
; Returning calls require initialized monitor RAM/worker, the monitor's flash
; bank mapped in, IRQ disabled, and decimal mode clear. On 816: E=1, D=0,
; DBR=0, PBR=0. No native-mode or reentrant calling convention is provided.
STR8V2_RESET            EQU     $F000
STR8V2_HOLD             EQU     $F003
STR8V2_CON_INIT         EQU     $F006
STR8V2_PUTC             EQU     $F009
STR8V2_GETC             EQU     $F00C
STR8V2_RAW_POLL         EQU     $F00F
STR8V2_CHECK_CANCEL     EQU     $F012
STR8V2_RX_RESET         EQU     $F015
STR8V2_READ_LINE        EQU     $F018
STR8V2_HEX_OUT          EQU     $F01B
STR8V2_NEWLINE          EQU     $F01E
STR8V2_HEX_NIBBLE       EQU     $F021

STR8V2_LINE             EQU     $7C00
STR8V2_LINE_LIMIT       EQU     $20
