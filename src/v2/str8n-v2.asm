; v2-alpha5: required monitor commands, configuration and held autostart.
; 816 software entry requires E=1, D=0, DBR=0, PBR=0. Reset supplies this state.
                        MODULE  V2_MONITOR
                        XDEF    START
                        XDEF    V2_PROMPT_ENTRY
                        XDEF    V2_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "vectors-symbols.inc"
                        CODE
START:                 JMP     V2_RESET
V2_PROMPT_ENTRY:        JMP     V2_REENTER

V2_RESET:
                        SEI
                        CLD
                        LDX     #$FF
                        TXS
; Capture the visible bank before touching peripherals. Manual-low CA2/CB2
; selects zero; manual-high or reset input with board pull-up selects one.
                        JSR     V2_CAPTURE_BANK
                        LDX     #$00
V2_CLEAR_STATE:        STZ     V2_RESIDENT+3,X
                        INX
                        CPX     #$FD
                        BNE     V2_CLEAR_STATE
                        LDX     #$00
V2_COPY_VECTORS:       LDA     V2_VECTOR_IMAGE,X
                        STA     V2_VECTOR_CODE,X
                        INX
                        CPX     #V2_VECTOR_SIZE
                        BNE     V2_COPY_VECTORS
                        LDX     #$00
V2_INIT_POINTERS:      LDA     #<V2V_DEFAULT
                        STA     V2_POINTERS,X
                        STA     V2_NATIVE_POINTERS,X
                        LDA     #>V2V_DEFAULT
                        STA     V2_POINTERS+1,X
                        STA     V2_NATIVE_POINTERS+1,X
                        INX
                        INX
                        CPX     #$0A
                        BNE     V2_INIT_POINTERS
                        INC     V2_AUTO
                        BRA     V2_ENTER

V2_REENTER:
                        SEI
                        CLD
                        STZ     V2_AUTO
                        LDX     #$FF
                        TXS
; No reset initialization of RAM vectors on software prompt entry.
                        JSR     V2_CAPTURE_BANK
V2_ENTER:
                        STZ     V2_SKIP_LF
                        STZ     V2_NMI_HOLD
                        JSR     V2_RX_RESET
                        LDA     #<V2_WORKER_IMAGE
                        STA     V2_PTR
                        LDA     #>V2_WORKER_IMAGE
                        STA     V2_PTR+1
                        STZ     V2_ADDR
                        LDA     #>V2_WORKER
                        STA     V2_ADDR+1
                        LDX     #>V2_WORKER_SIZE
                        LDY     #$00
V2_COPY_WORKER:        CPX     #$00
                        BNE     V2_COPY_WORKER_BYTE
                        CPY     #<V2_WORKER_SIZE
                        BEQ     V2_WORKER_COPIED
V2_COPY_WORKER_BYTE:   LDA     (V2_PTR),Y
                        STA     (V2_ADDR),Y
                        INY
                        BNE     V2_COPY_WORKER
                        INC     V2_PTR+1
                        INC     V2_ADDR+1
                        DEX
                        BRA     V2_COPY_WORKER
V2_WORKER_COPIED:
; Quiet the EDU buzzer and assert its running LED. No PCR write here.
                        LDA     #$30
                        STA     V2_PIA_CRA
                        LDA     #$FF
                        STA     V2_LED
                        LDA     #$34
                        STA     V2_PIA_CRA
                        LDA     #$01
                        STA     V2_LED
                        JSR     V2_CON_INIT
                        LDX     #<V2_BANNER
                        LDY     #>V2_BANNER
                        JSR     V2_PRINT
                        LDA     V2_RESIDENT
                        ORA     #'0'
                        JSR     V2_PUTC
                        LDA     V2_AUTO
                        BEQ     V2_PROMPT
                        JSR     V2_AUTOSTART
V2_PROMPT:
                        LDX     #<V2_PROMPT_TEXT
                        LDY     #>V2_PROMPT_TEXT
                        JSR     V2_PRINT
                        JSR     V2_READ_LINE
                        BCS     V2_DISPATCH
                        CPY     #$03
                        BNE     V2_LINE_NOT_CANCEL
                        JMP     V2_CANCELLED
V2_LINE_NOT_CANCEL:
                        CPY     #$02
                        BNE     V2_LINE_OVERFLOW
                        JMP     V2_BAD_INPUT
V2_LINE_OVERFLOW:
                        JMP     V2_LINE_LONG
V2_DISPATCH:
                        LDA     V2_LINE
                        BEQ     V2_PROMPT
                        CMP     #'?'
                        BNE     V2_DISPATCH_COMMAND
                        LDA     V2_LINE+1
                        BEQ     V2_SHOW_HELP
                        JMP     V2_UNKNOWN
V2_SHOW_HELP:
                        LDX     #<V2_HELP
                        LDY     #>V2_HELP
                        JMP     V2_MESSAGE
V2_DISPATCH_COMMAND:
                        CMP     #'B'
                        BEQ     V2_COMMAND_B
                        CMP     #'D'
                        BNE     V2_TRY_M
                        JMP     V2_COMMAND_D
V2_TRY_M:              CMP     #'M'
                        BNE     V2_TRY_G
                        JMP     V2_COMMAND_M
V2_TRY_G:              CMP     #'G'
                        BNE     V2_TRY_L
                        JMP     V2_COMMAND_G
V2_TRY_L:              CMP     #'L'
                        BNE     V2_TRY_F
                        JMP     V2_COMMAND_L
V2_TRY_F:              CMP     #'F'
                        BNE     V2_TRY_I
                        JMP     V2_COMMAND_F
V2_TRY_I:              CMP     #'I'
                        BNE     V2_TRY_C
                        JMP     V2_COMMAND_I
V2_TRY_C:              CMP     #'C'
                        BNE     V2_COMMAND_J
                        JMP     V2_COMMAND_C
V2_COMMAND_B:          JSR     V2_PARSE_BANK
                        BCC     V2_BAD_BANK
                        PHA
                        JSR     V2_CHECK_CANCEL
                        BCC     V2_B_READY
                        PLA
                        JMP     V2_CANCELLED
V2_B_READY:            PLA
                        STA     V2_SELECTED
                        LDA     #'B'
                        JSR     V2_PUTC
                        LDA     V2_SELECTED
                        ORA     #'0'
                        JSR     V2_PUTC
                        JMP     V2_PROMPT
V2_COMMAND_J:
                        CMP     #'J'
                        BNE     V2_UNKNOWN
                        JSR     V2_PARSE_BANK
                        BCC     V2_BAD_BANK
                        STA     V2_TARGET
                        JSR     V2_CHECK_CANCEL
                        BCC     V2_J_READY
                        JMP     V2_CANCELLED
V2_J_READY:
                        JSR     V2_WORKER
                        LDX     #<V2_BAD_VECTOR_TEXT
                        LDY     #>V2_BAD_VECTOR_TEXT
                        BRA     V2_MESSAGE
V2_BAD_BANK:           LDX     #<V2_BAD_BANK_TEXT
                        LDY     #>V2_BAD_BANK_TEXT
                        BRA     V2_MESSAGE
V2_LINE_LONG:          LDX     #<V2_LONG_TEXT
                        LDY     #>V2_LONG_TEXT
                        BRA     V2_MESSAGE
V2_BAD_INPUT:          LDX     #<V2_BAD_INPUT_TEXT
                        LDY     #>V2_BAD_INPUT_TEXT
                        BRA     V2_MESSAGE
V2_UNKNOWN:            LDX     #<V2_UNKNOWN_TEXT
                        LDY     #>V2_UNKNOWN_TEXT
V2_MESSAGE:            JSR     V2_PRINT
                        JMP     V2_PROMPT
V2_CANCELLED:          STZ     V2_CANCEL_REQUEST
                        JSR     V2_NEWLINE
                        LDX     #<V2_CANCEL_TEXT
                        LDY     #>V2_CANCEL_TEXT
                        JMP     V2_MESSAGE

V2_PARSE_BANK:         LDA     V2_LINE+2
                        BNE     V2_BANK_FAIL
                        LDA     V2_LINE+1
                        CMP     #'0'
                        BCC     V2_BANK_FAIL
                        CMP     #'4'
                        BCS     V2_BANK_FAIL
                        AND     #$03
                        SEC
                        RTS
V2_BANK_FAIL:          CLC
                        RTS

                        INCLUDE "str8n-v2-monitor.inc"
                        INCLUDE "str8n-v2-load.inc"
                        INCLUDE "str8n-v2-input.inc"
                        INCLUDE "str8n-v2-flash.inc"
                        INCLUDE "str8n-v2-config.inc"

V2_CAPTURE_BANK:
                        LDX     #$00
                        LDA     V2_PCR
                        AND     #$0E
                        CMP     #$0C
                        BEQ     V2_CAPTURE_CB2
                        INX
V2_CAPTURE_CB2:        LDA     V2_PCR
                        AND     #$E0
                        CMP     #$C0
                        BEQ     V2_CAPTURE_DONE
                        INX
                        INX
V2_CAPTURE_DONE:       STX     V2_RESIDENT
                        STX     V2_SELECTED
                        STX     V2_TARGET
                        RTS

; Short line reader. Overflow drains the whole line; never executes a prefix.
; X counts accepted bytes; Y=1 overflow, Y=2 invalid input (sticky). CR/LF
; pairs are one line. Tab is whitespace; other unexpected bytes reject the
; whole line rather than silently joining tokens into a destructive command.
V2_READ_LINE:
                        LDX     #$00
                        LDY     #$00
                        LDA     V2_RX_BAD
                        BEQ     V2_LINE_BYTE
                        STZ     V2_RX_BAD
                        LDY     #$02
V2_LINE_BYTE:          JSR     V2_GETC
                        PHA
                        LDA     V2_RX_BAD
                        BEQ     V2_LINE_INPUT_OK
                        STZ     V2_RX_BAD
                        LDY     #$02
V2_LINE_INPUT_OK:      PLA
                        CMP     #$0A
                        BNE     V2_NOT_LF
                        LDA     V2_SKIP_LF
                        BEQ     V2_LINE_END
                        STZ     V2_SKIP_LF
                        BRA     V2_LINE_BYTE
V2_NOT_LF:             STZ     V2_SKIP_LF
                        CMP     #$0D
                        BNE     V2_NOT_CR
                        INC     V2_SKIP_LF
                        BRA     V2_LINE_END
V2_NOT_CR:             CMP     #$03
                        BEQ     V2_CANCEL
                        CPY     #$00
                        BNE     V2_LINE_BYTE
                        CMP     #$08
                        BEQ     V2_BACKSPACE
                        CMP     #$7F
                        BEQ     V2_BACKSPACE
                        CMP     #$09
                        BNE     V2_NOT_TAB
                        LDA     #' '
V2_NOT_TAB:
                        CMP     #$20
                        BCC     V2_INVALID_BYTE
                        CMP     #$7F
                        BCS     V2_INVALID_BYTE
                        CMP     #'a'
                        BCC     V2_STORE_CHAR
                        CMP     #'z'+1
                        BCS     V2_STORE_CHAR
                        AND     #$DF
V2_STORE_CHAR:         CPX     #V2_LINE_LIMIT
                        BCS     V2_OVERFLOW
                        STA     V2_LINE,X
                        INX
                        JSR     V2_PUTC
                        BRA     V2_LINE_BYTE
V2_OVERFLOW:           INY
                        BRA     V2_LINE_BYTE
V2_INVALID_BYTE:       LDY     #$02
                        BRA     V2_LINE_BYTE
V2_BACKSPACE:          CPX     #$00
                        BEQ     V2_LINE_BYTE
                        DEX
                        LDA     #$08
                        JSR     V2_PUTC
                        LDA     #' '
                        JSR     V2_PUTC
                        LDA     #$08
                        JSR     V2_PUTC
                        BRA     V2_LINE_BYTE
V2_CANCEL:             LDX     #$00
                        LDY     #$03
V2_LINE_END:           STZ     V2_LINE,X
; Clear stale suffixes so J with a missing argument cannot reuse an old bank.
                        INX
                        STZ     V2_LINE,X
                        JSR     V2_NEWLINE
                        CPY     #$01
                        BCS     V2_LINE_FAIL
                        SEC
                        RTS
V2_LINE_FAIL:          CLC
                        RTS

V2_PRINT:              STX     V2_PTR
                        STY     V2_PTR+1
                        LDY     #$00
V2_PRINT_NEXT:         LDA     (V2_PTR),Y
                        BEQ     V2_PRINT_END
                        JSR     V2_PUTC
                        INY
                        BRA     V2_PRINT_NEXT
V2_PRINT_END:          RTS

; Direct FT245/VIA routines derived from the v1.35 board-tested sequences.
; Preserve X/Y; initialization never changes bank-select PCR bits.
V2_CON_INIT:           LDA     #$0C
                        STA     V2_CTRL
                        STA     V2_DDRB
                        STZ     V2_DDRA
                        RTS
V2_RAW_POLL:           STZ     V2_DDRA
                        LDA     #$02
                        BIT     V2_CTRL
                        BNE     V2_RAW_EMPTY
                        LDA     #$08
                        TRB     V2_CTRL
                        NOP
                        NOP
                        LDA     V2_DATA
                        PHA
                        LDA     #$08
                        TSB     V2_CTRL
                        PLA
                        SEC
                        RTS
V2_RAW_EMPTY:          CLC
                        RTS
V2_PUTC:               PHA
                        LDA     V2_CANCEL_REQUEST
                        BNE     V2_TX_CANCEL
                        STZ     V2_DDRA
                        LDA     #$01
V2_TX_WAIT:            BIT     V2_CTRL
                        BEQ     V2_TX_READY
; Poll input while output is blocked. Drop this byte on cancel; the caller
; unwinds normally and stops at its next safe boundary.
                        JSR     V2_RX_SERVICE
                        LDA     V2_CANCEL_REQUEST
                        BNE     V2_TX_CANCEL
                        LDA     #$01
                        BRA     V2_TX_WAIT
V2_TX_READY:           PLA
                        PHA
                        STA     V2_DATA
                        NOP
                        NOP
                        LDA     #$04
                        TSB     V2_CTRL
                        DEC     V2_DDRA
                        NOP
                        NOP
                        LDA     #$04
                        TRB     V2_CTRL
                        STZ     V2_DDRA
V2_TX_CANCEL:
                        PLA
                        RTS

V2_BANNER:             DB      $0D,$0A,"STR8-N 2.0a5 B",$00
V2_PROMPT_TEXT:        DB      $0D,$0A,"> ",$00
V2_HELP:               DB      "B0-B3 D addr [end] M/F addr bytes G addr L I start end C [on bank addr delay] J0-J3 ?",$00
V2_BAD_BANK_TEXT:      DB      "Bad bank",$00
V2_BAD_VECTOR_TEXT:    DB      "Bad vector",$00
V2_LONG_TEXT:          DB      "Line too long",$00
V2_UNKNOWN_TEXT:       DB      "Unknown command",$00
V2_BAD_INPUT_TEXT:     DB      "Bad input",$00
V2_BAD_HEX_TEXT:       DB      "Bad hex",$00
V2_BAD_RANGE_TEXT:     DB      "Bad range",$00
V2_PROTECTED_TEXT:     DB      "Protected address",$00
V2_CANCEL_TEXT:        DB      "Cancelled",$00
V2_S19_TEXT:           DB      "S19",$0D,$0A,$00
V2_S19_BAD_TEXT:       DB      "Bad S19 record",$00
V2_S19_SUM_TEXT:       DB      "Bad S19 checksum",$00
V2_LOADED_TEXT:        DB      "Loaded; entry ",$00
                        INCLUDE "str8n-v2-flash-text.inc"
V2_NO_CONFIG_TEXT:     DB      "No config",$00
V2_HOLD_TEXT:          DB      "S/Ctrl-C hold",$0D,$0A,$00
V2_WORKER_IMAGE:
                        INCLUDE "worker-image.inc"
V2_VECTOR_IMAGE:
                        INCLUDE "vectors-image.inc"
V2_END:
                        ENDMOD
                        END
