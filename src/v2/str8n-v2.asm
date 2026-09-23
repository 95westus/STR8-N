; v2-alpha10: signature at F000, public RESET at F004, erased tail to vectors.
; 816 software entry requires E=1, D=0, DBR=0, PBR=0. Reset supplies this state.
                        MODULE  V2_MONITOR
                        XDEF    V2_SIGNATURE
                        XDEF    START
                        XDEF    V2_PROMPT_ENTRY
                        XDEF    V2_CON_INIT_ENTRY
                        XDEF    V2_PUTC_ENTRY
                        XDEF    V2_GETC_ENTRY
                        XDEF    V2_RAW_POLL_ENTRY
                        XDEF    V2_CHECK_CANCEL_ENTRY
                        XDEF    V2_RX_RESET_ENTRY
                        XDEF    V2_READ_LINE_ENTRY
                        XDEF    V2_HEX_OUT_ENTRY
                        XDEF    V2_NEWLINE_ENTRY
                        XDEF    V2_HEX_NIBBLE_ENTRY
                        XDEF    V2_RESERVED0_ENTRY
                        XDEF    V2_RESERVED1_ENTRY
                        XDEF    V2_RESERVED2_ENTRY
                        XDEF    V2_RESERVED3_ENTRY
                        XDEF    V2_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "vectors-symbols.inc"
                        INCLUDE "text-ids.inc"
                        CODE
; Product signature, major ABI and signature-format revision. This deliberately
; differs from v1's SR/02/03 parser-service signature.
V2_SIGNATURE:          DB      "SN",$02,$00
START:                 JMP     V2_RESET
V2_PROMPT_ENTRY:        JMP     V2_REENTER
V2_CON_INIT_ENTRY:      JMP     V2_CON_INIT
V2_PUTC_ENTRY:          JMP     V2_PUTC
V2_GETC_ENTRY:          JMP     V2_GETC
V2_RAW_POLL_ENTRY:      JMP     V2_RAW_POLL
V2_CHECK_CANCEL_ENTRY:  JMP     V2_CHECK_CANCEL
V2_RX_RESET_ENTRY:      JMP     V2_RX_RESET
V2_READ_LINE_ENTRY:     JMP     V2_READ_LINE
V2_HEX_OUT_ENTRY:       JMP     V2_HEX_OUT
V2_NEWLINE_ENTRY:       JMP     V2_NEWLINE
V2_HEX_NIBBLE_ENTRY:    JMP     V2_HEX_NIBBLE
V2_RESERVED0_ENTRY:     JMP     V2_RESERVED
V2_RESERVED1_ENTRY:     JMP     V2_RESERVED
V2_RESERVED2_ENTRY:     JMP     V2_RESERVED
V2_RESERVED3_ENTRY:     JMP     V2_RESERVED
V2_RESERVED:            RTS

V2_RESET:
                        SEI
                        CLD
                        LDX     #$FF
                        TXS
; Capture the visible bank before touching peripherals. Manual-low CA2/CB2
; selects zero; manual-high or reset input with board pull-up selects one.
                        JSR     V2_CAPTURE_BANK
                        LDX     #$03
V2_CLEAR_STATE:        STZ     V2_RESIDENT,X
                        INX
                        BNE     V2_CLEAR_STATE
V2_COPY_VECTORS:       LDA     V2_VECTOR_IMAGE,X
                        STA     V2_VECTOR_CODE,X
                        INX
                        CPX     #V2_VECTOR_SIZE
                        BNE     V2_COPY_VECTORS
                        LDX     #$08
V2_INIT_POINTERS:      LDA     #<V2V_DEFAULT
                        STA     V2_POINTERS,X
                        STA     V2_NATIVE_POINTERS,X
                        LDA     #>V2V_DEFAULT
                        STA     V2_POINTERS+1,X
                        STA     V2_NATIVE_POINTERS+1,X
                        DEX
                        DEX
                        BPL     V2_INIT_POINTERS
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
; Build-sized absolute copies cover the worker exactly. The last 256-byte
; window can overlap the preceding one; no ROM padding or extra RAM is used.
                        INCLUDE "worker-copy.inc"
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
                        LDX     #V2_BANNER
                        JSR     V2_PRINT
                        LDA     V2_RESIDENT
                        ORA     #'0'
                        JSR     V2_PUTC
                        LDA     V2_AUTO
                        BEQ     V2_PROMPT
                        JSR     V2_AUTOSTART
V2_PROMPT:
                        LDX     #V2_PROMPT_TEXT
                        JSR     V2_PRINT
                        LDA     V2_SELECTED
                        ORA     #'0'
                        JSR     V2_PUTC
                        LDA     #'>'
                        JSR     V2_PUTC
                        LDA     #' '
                        JSR     V2_PUTC
                        JSR     V2_READ_LINE
                        BCS     V2_DISPATCH
                        CPY     #$03
                        BEQ     V2_CANCELLED
V2_LINE_NOT_CANCEL:
                        CPY     #$02
                        BEQ     V2_BAD_INPUT
V2_LINE_OVERFLOW:
                        BRA     V2_LINE_LONG
V2_DISPATCH:           LDA     V2_LINE
                        BEQ     V2_PROMPT
                        LDX     #$09
V2_DISPATCH_FIND:      CMP     V2_COMMAND_KEYS,X
                        BEQ     V2_DISPATCH_GO
                        DEX
                        BPL     V2_DISPATCH_FIND
                        BRA     V2_UNKNOWN
V2_DISPATCH_GO:        TXA
                        ASL     A
                        TAX
                        JMP     (V2_COMMAND_TABLE,X)
V2_SHOW_HELP:          LDA     V2_LINE+1
                        BNE     V2_UNKNOWN
                        LDX     #V2_HELP
                        BRA     V2_MESSAGE
V2_COMMAND_B:          JSR     V2_PARSE_BANK
                        BCC     V2_BAD_BANK
                        PHA
                        JSR     V2_CHECK_CANCEL
                        BCC     V2_B_READY
                        PLA
                        BRA     V2_CANCELLED
V2_B_READY:            PLA
                        STA     V2_SELECTED
                        BRA     V2_PROMPT
V2_COMMAND_J:
                        JSR     V2_PARSE_BANK
                        BCC     V2_BAD_BANK
                        STA     V2_TARGET
                        JSR     V2_CHECK_CANCEL
                        BCS     V2_CANCELLED
V2_J_READY:
                        JSR     V2_WORKER
                        LDX     #V2_BAD_VECTOR_TEXT
                        BRA     V2_MESSAGE
V2_BAD_BANK:           LDX     #V2_BAD_BANK_TEXT
                        BRA     V2_MESSAGE
V2_LINE_LONG:          LDX     #V2_LONG_TEXT
                        BRA     V2_MESSAGE
V2_BAD_INPUT:          LDX     #V2_BAD_INPUT_TEXT
                        BRA     V2_MESSAGE
V2_UNKNOWN:            LDX     #V2_UNKNOWN_TEXT
; The leading error ordinals share one stored "Bad " prefix.
V2_MESSAGE:            CPX     #V2_BAD_PREFIX
                        BCS     V2_MESSAGE_BODY
                        PHX
                        LDX     #V2_BAD_PREFIX
                        JSR     V2_PRINT
                        PLX
V2_MESSAGE_BODY:       JSR     V2_PRINT
                        JMP     V2_PROMPT
V2_CANCELLED:          STZ     V2_CANCEL_REQUEST
                        JSR     V2_NEWLINE
                        LDX     #V2_CANCEL_TEXT
                        BRA     V2_MESSAGE

V2_PARSE_BANK:         LDA     V2_LINE+1
                        SEC
                        SBC     #'0'
                        CMP     #$04
                        BCS     V2_BANK_FAIL
                        LDY     V2_LINE+2
                        BNE     V2_BANK_FAIL
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
V2_LINE_BYTE:          JSR     V2_GETC
; RX_BAD is boolean: shift it into carry and clear it without changing A.
                        LSR     V2_RX_BAD
                        BCC     V2_LINE_INPUT_OK
                        LDY     #$02
V2_LINE_INPUT_OK:      CMP     #$0A
                        BNE     V2_NOT_LF
                        LSR     V2_SKIP_LF
                        BCC     V2_LINE_END
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
V2_BACKSPACE:          TXA
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
                        JSR     V2_NEWLINE
                        CPY     #$01
                        BCS     V2_LINE_FAIL
                        SEC
                        RTS
V2_LINE_FAIL:          CLC
                        RTS

 ; IN X=message ordinal. Preserve X; speed is secondary to ROM space.
V2_PRINT:              PHX
                        LDA     #<V2_TEXT
                        STA     V2_PTR
                        LDA     #>V2_TEXT
                        STA     V2_PTR+1
                        LDY     #$00
                        TXA
                        BEQ     V2_PRINT_NEXT
V2_PRINT_SCAN:         LDA     (V2_PTR),Y
                        INY
                        BNE     V2_PRINT_SCAN_TEST
                        INC     V2_PTR+1
V2_PRINT_SCAN_TEST:    CMP     #$80
                        BCC     V2_PRINT_SCAN
                        DEX
                        BNE     V2_PRINT_SCAN
V2_PRINT_NEXT:         LDA     (V2_PTR),Y
                        PHA
                        AND     #$7F
                        JSR     V2_PUTC
                        PLA
                        BMI     V2_PRINT_END
                        INY
                        BNE     V2_PRINT_NEXT
                        INC     V2_PTR+1
                        BRA     V2_PRINT_NEXT
V2_PRINT_END:          PLX
                        RTS

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
; Input polling/cancellation stays here; the identical hardware transaction
; is shared with the RAM-only self-edit reporter. Preserve A on the stack.
                        JSR     V2W_SEND
V2_TX_CANCEL:
                        PLA
                        RTS

V2_COMMAND_KEYS:      DB      "BDMGLFICJ?"
V2_COMMAND_TABLE:     DW      V2_COMMAND_B,V2_COMMAND_D,V2_COMMAND_M,V2_COMMAND_G
                        DW      V2_COMMAND_L,V2_COMMAND_F,V2_COMMAND_I,V2_COMMAND_C
                        DW      V2_COMMAND_J,V2_SHOW_HELP
; S19 errors 1..4; cancellation uses its existing cleanup path.
V2_LOAD_ERROR_TEXTS:   DB      V2_S19_BAD_TEXT,V2_S19_SUM_TEXT
                        DB      V2_CANCEL_TEXT,V2_PROTECTED_TEXT
                        INCLUDE "text-image.inc"
V2_WORKER_IMAGE:
                        INCLUDE "worker-image.inc"
V2_VECTOR_IMAGE:
                        INCLUDE "vectors-image.inc"
V2_END:
                        ENDMOD
                        END
