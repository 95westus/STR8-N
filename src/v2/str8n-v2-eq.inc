; Provisional v2 milestone ABI. All addresses are CPU bank zero on the 816.
V2_PTR                  EQU     $E0
V2_ADDR                 EQU     $E2
V2_FLASH_PTR            EQU     $E4
V2_BUF_PTR              EQU     $E6
V2_SECTOR               EQU     $EE
V2_ERASE                EQU     $EF
; Command phases have disjoint lifetimes: edit preflight precedes SELF;
; config checksums precede flash mutation; S19 parsing never parses tokens.
V2_SELF                 EQU     $F5      ; V2_EDIT_FLASH after preflight
V2_FLASH_ERROR          EQU     $F6      ; V2_CFG_SUM during mutation
V2_FLASH_DATA           EQU     $F0
; Flash polling keeps its three counters in X, Y and one stack byte.
; These persistent console/bank bytes therefore remain live during polling.
V2_INSTALL_NEXT         EQU     $FE      ; V2_VECTOR during I
V2_INSTALL_END          EQU     $E9      ; parsed end high byte; low is always FF
V2_INSTALL_DONE         EQU     $E8      ; parsed end low byte after confirmation
V2_EDIT_FLASH           EQU     $F5
V2_RESIDENT             EQU     $7D00
V2_CPU                  EQU     $7D01
V2_CONSOLE              EQU     $7D02
V2_CPU_65C02            EQU     $02
V2_CPU_65C816           EQU     $16
V2_CONSOLE_FT245        EQU     $00
V2_CONSOLE_ACIA         EQU     $01
V2_SELECTED             EQU     $F3
V2_TARGET               EQU     $FB      ; V2_REC_SUM outside S19 transfers
V2_VECTOR               EQU     $FE
V2_SKIP_LF              EQU     $EC      ; boolean 0/1, consumed with LSR
V2_LAST                 EQU     $E8      ; D retains the parsed end in VALUE
V2_VALUE                EQU     $E8
V2_COUNT                EQU     $EA
V2_DIGIT_LIMIT          EQU     $EB
V2_NMI_HOLD             EQU     $F4
V2_RX_HEAD              EQU     $FD
V2_RX_TAIL              EQU     $FA
V2_RX_COUNT             EQU     $F9
V2_CANCEL_REQUEST       EQU     $F8      ; boolean 0/1, consumed by GETC
V2_RX_DROP              EQU     $F2
V2_RX_BAD               EQU     $F1      ; boolean 0/1, consumed by readers
V2_REC_TYPE             EQU     $EB      ; V2_DIGIT_LIMIT during S19 input
V2_REC_SUM              EQU     $FB
V2_REC_HEX              EQU     $FC
V2_RX_CHAR              EQU     $ED
V2_RX_QUEUE             EQU     $7D40
V2_RX_SIZE              EQU     $40
V2_LINE                 EQU     $7C00
V2_LINE_LIMIT           EQU     $20
V2_BYTES                EQU     $7C80
V2_WORKER               EQU     $7900
V2_POINTERS             EQU     $7E00
V2_NATIVE_POINTERS      EQU     $7E10
V2_VECTOR_CODE          EQU     $7E20
V2_PCR                  EQU     $7FEC
V2_CTRL                 EQU     $7FE0
V2_DATA                 EQU     $7FE1
V2_DDRB                 EQU     $7FE2
V2_DDRA                 EQU     $7FE3
V2_ACIA_DATA            EQU     $7F80
V2_ACIA_STATUS          EQU     $7F81
V2_ACIA_COMMAND         EQU     $7F82
V2_ACIA_CONTROL         EQU     $7F83
V2_ACIA_RDRF            EQU     $08
V2_ACIA_COMMAND_19200   EQU     $0B
V2_ACIA_CONTROL_19200   EQU     $1F
V2_LED                  EQU     $7FA0
V2_PIA_CRA              EQU     $7FA1
V2_LED_RUNNING          EQU     $01
V2_LED_RX               EQU     $04
V2_LED_FLASH            EQU     $F0
V2_CFG_SUM              EQU     $F6
V2_CFG_SUM2             EQU     $F7
V2_AUTO                 EQU     $7D26
V2_TICKS                EQU     $F7      ; V2_CFG_SUM2 after config validation
V2_CONFIG               EQU     $7D80
