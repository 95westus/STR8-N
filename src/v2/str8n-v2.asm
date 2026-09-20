; v2-alpha1: independent, common-instruction-subset boot milestone.
; Only help and J0-J3 are implemented. No automatic execution or flash writes.
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
                        BRA     V2_ENTER

V2_REENTER:
                        SEI
                        CLD
                        LDX     #$FF
                        TXS
; No reset initialization of RAM vectors on software prompt entry.
                        JSR     V2_CAPTURE_BANK
V2_ENTER:
                        STZ     V2_SKIP_LF
                        LDX     #$00
V2_COPY_WORKER:        LDA     V2_WORKER_IMAGE,X
                        STA     V2_WORKER,X
                        INX
                        CPX     #V2_WORKER_SIZE
                        BNE     V2_COPY_WORKER
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
V2_PROMPT:
                        LDX     #<V2_PROMPT_TEXT
                        LDY     #>V2_PROMPT_TEXT
                        JSR     V2_PRINT
                        JSR     V2_READ_LINE
                        BCC     V2_LINE_LONG
                        LDA     V2_LINE
                        BEQ     V2_PROMPT
                        CMP     #'?'
                        BNE     V2_COMMAND_J
                        LDA     V2_LINE+1
                        BNE     V2_UNKNOWN
                        LDX     #<V2_HELP
                        LDY     #>V2_HELP
                        BRA     V2_MESSAGE
V2_COMMAND_J:
                        CMP     #'J'
                        BNE     V2_UNKNOWN
                        LDA     V2_LINE+1
                        CMP     #'0'
                        BCC     V2_BAD_BANK
                        CMP     #'4'
                        BCS     V2_BAD_BANK
                        AND     #$03
                        STA     V2_TARGET
                        LDA     V2_LINE+2
                        BNE     V2_UNKNOWN
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
V2_UNKNOWN:            LDX     #<V2_UNKNOWN_TEXT
                        LDY     #>V2_UNKNOWN_TEXT
V2_MESSAGE:            JSR     V2_PRINT
                        BRA     V2_PROMPT

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
; X counts accepted bytes; Y is sticky overflow. CR/LF pairs are one line.
V2_READ_LINE:
                        LDX     #$00
                        LDY     #$00
V2_LINE_BYTE:          JSR     V2_GETC
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
                        CMP     #$20
                        BCC     V2_LINE_BYTE
                        CMP     #$7F
                        BCS     V2_LINE_BYTE
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
                        LDY     #$00
V2_LINE_END:           STZ     V2_LINE,X
; Clear stale suffixes so J with a missing argument cannot reuse an old bank.
                        INX
                        STZ     V2_LINE,X
                        LDA     #$0D
                        JSR     V2_PUTC
                        LDA     #$0A
                        JSR     V2_PUTC
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
V2_GETC:               STZ     V2_DDRA
                        LDA     #$02
                        BIT     V2_CTRL
                        BNE     V2_GETC
                        LDA     #$08
                        TRB     V2_CTRL
                        NOP
                        NOP
                        LDA     V2_DATA
                        PHA
                        LDA     #$08
                        TSB     V2_CTRL
                        PLA
                        RTS
V2_PUTC:               PHA
                        STZ     V2_DDRA
                        STA     V2_DATA
                        NOP
                        NOP
                        LDA     #$01
V2_TX_WAIT:            BIT     V2_CTRL
                        BNE     V2_TX_WAIT
                        LDA     #$04
                        TSB     V2_CTRL
                        DEC     V2_DDRA
                        NOP
                        NOP
                        LDA     #$04
                        TRB     V2_CTRL
                        STZ     V2_DDRA
                        PLA
                        RTS

V2_BANNER:             DB      $0D,$0A,"STR8-N 2.0a1 B",$00
V2_PROMPT_TEXT:        DB      $0D,$0A,"> ",$00
V2_HELP:               DB      "J0-J3 ?",$00
V2_BAD_BANK_TEXT:      DB      "Bad bank",$00
V2_BAD_VECTOR_TEXT:    DB      "Bad vector",$00
V2_LONG_TEXT:          DB      "Line too long",$00
V2_UNKNOWN_TEXT:       DB      "Unknown command",$00
V2_WORKER_IMAGE:
                        INCLUDE "worker-image.inc"
V2_VECTOR_IMAGE:
                        INCLUDE "vectors-image.inc"
V2_END:
                        ENDMOD
                        END
