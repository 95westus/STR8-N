; v2-alpha24: optional, guarded S/R/T extension in the resident E sector.
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
                        XDEF    V2_CAPS_QUERY_ENTRY
                        XDEF    V2_BOARD_QUERY_ENTRY
                        XDEF    V2_RESERVED2_ENTRY
                        XDEF    V2_RESERVED3_ENTRY
                        XDEF    V2_CAPS_DATA
                        XDEF    V2_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "vectors-symbols.inc"
                        INCLUDE "text-ids.inc"
                        INCLUDE "boot-symbols.inc"
V2_IMAGE_PAGE EQU $B0
; Internal monitor calls and the resident compatibility facade share the
; exact RAM implementations exposed to applications in every flash bank.
V2_CON_INIT             EQU     V2W_CON_INIT
V2_PUTC                 EQU     V2W_PUTC
V2_TX_WAIT              EQU     V2W_TX_WAIT
V2_GETC                 EQU     V2W_GETC
V2_GETC_WAIT            EQU     V2W_GETC_WAIT
V2_RAW_POLL             EQU     V2W_RAW_POLL
V2_CHECK_CANCEL         EQU     V2W_CHECK_CANCEL
V2_RX_RESET             EQU     V2W_RX_RESET
V2_HEX_OUT              EQU     V2V_RAM_HEX_OUT
V2_NEWLINE              EQU     V2V_RAM_NEWLINE
V2_HEX_NIBBLE           EQU     V2V_RAM_HEX_NIBBLE
V2_CAPS_QUERY           EQU     V2V_RAM_CAPS_QUERY
V2_BOARD_QUERY          EQU     V2V_RAM_BOARD_QUERY
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
V2_READ_LINE_ENTRY:     JMP     V2_RESERVED
V2_HEX_OUT_ENTRY:       JMP     V2_HEX_OUT
V2_NEWLINE_ENTRY:       JMP     V2_NEWLINE
V2_HEX_NIBBLE_ENTRY:    JMP     V2_HEX_NIBBLE
V2_CAPS_QUERY_ENTRY:    JMP     V2_CAPS_QUERY
V2_BOARD_QUERY_ENTRY:   JMP     V2_BOARD_QUERY
V2_RESERVED2_ENTRY:     JMP     V2_RESERVED
V2_RESERVED3_ENTRY:     JMP     V2_RESERVED
V2_RESERVED:            RTS
; Fixed, ROM-readable descriptor: magic, format, capability flags.
V2_CAPS_DATA:           DB      "CA",STR8V2_CAPS_FORMAT,STR8V2_CAPS_FLAGS

V2_RESET:
                        STZ $7EE4
                        STZ $7EE7
                        INC V2_AUTO
                        JMP V2_ENTER

V2_REENTER:
                        SEI
                        CLD
                        STZ     V2_AUTO
                        LDX     #$FF
                        TXS
; No reset initialization of RAM vectors on software prompt entry.
                        JSR     V2_CAPTURE_BANK
V2_ENTER:
                        LDX #B29_GATE_END-B29_GATE_IMAGE-1
B29_INSTALL:
                        LDA B29_GATE_IMAGE,X
                        STA $7C90,X
                        DEX
                        BPL B29_INSTALL
                        LDA #<V2_BANK_READ_LINE
                        STA $7EEA
                        LDA #>V2_BANK_READ_LINE
                        STA $7EEB
                        JSR B29_CHECK_PROVIDER
                        LDA     $7D27
                        PHA
                        STZ     V2_SKIP_LF
                        STZ     V2_NMI_HOLD
; Build-sized absolute copies cover the worker exactly. The last 256-byte
; window can overlap the preceding one; no ROM padding or extra RAM is used.
                        LDA #V2_IMAGE_PAGE
                        STA BOOT_ACTIVE
V2_WORKER_COPIED:
                        STZ SVC_DESC
                        STZ $7D19
                        STZ SVC_BANNER_PTR+1
                        JSR AP_CHECK
                        BCC SVC_BOOT_DONE
                        JSR $E014
SVC_BOOT_DONE:
                        JSR     V2_RX_RESET
; Quiet the EDU buzzer and assert its running LED. No PCR write here.
                        LDA     #$30
                        STA     V2_PIA_CRA
                        LDA     #$FF
                        STA     V2_LED
                        LDA     #$34
                        STA     V2_PIA_CRA
                        LDA     #V2_LED_RUNNING
                        STA     V2_LED
; Bootstrap already printed the startup dots before A/B selection. Enabled
; autostart keeps its separate configured hold window even when USB is absent.
                        LDA     #$0C
                        STA     V2_CTRL
                        STA     V2_DDRB
                        STZ     V2_DDRA
                        LDA     V2_AUTO
                        BEQ V2_BOOT_DELAY_DONE
                        JSR     V2_CONFIG_READ
                        BCC V2_BOOT_MONITOR
                        LDA     V2_CONFIG+1
                        BEQ V2_BOOT_MONITOR
                        JSR     V2_AUTO_HEADLESS
V2_BOOT_MONITOR:
V2_BOOT_DELAY_DONE:
                        JSR     V2_CON_INIT
                        PLA
                        BNE V2_PROMPT
                        LDX     #V2_BANNER
                        JSR     V2_PRINT
                        LDA     V2_RESIDENT
                        ORA     #'0'
                        JSR     V2_PUTC
                        LDX     #V2_CPU_02_TEXT
                        LDA     V2_CPU
                        CMP     #V2_CPU_65C816
                        BNE V2_CPU_HEADER
                        LDX     #V2_CPU_816_TEXT
V2_CPU_HEADER:          JSR     V2_PRINT
                        LDX     #V2_ABI_HEADER
                        JSR     V2_PRINT
                        LDA SVC_BANNER_PTR+1
                        BEQ V2_CLOCK_BANNER_DONE
                        JSR V2_CLOCK_BANNER
V2_CLOCK_BANNER_DONE:
V2_PROMPT:              LDA     $7DF9
                        CMP     #$54
                        BNE V2_NORMAL_PROMPT
                        STZ     $7DF9
                        JMP     ($7DFA)
V2_NORMAL_PROMPT:       LDA     #V2_LED_RUNNING
                        STZ     $7DFC
                        STA     V2_LED
                        LDX     #V2_PROMPT_TEXT
                        JSR     V2_PRINT
                        JSR     $7C90
                        BCS V2_DISPATCH
                        CPY     #$03
                        BNE str8n_v2_LONG_154
                        JMP V2_CANCELLED
str8n_v2_LONG_154:
V2_LINE_NOT_CANCEL:
                        CPY     #$02
                        BEQ V2_BAD_INPUT
V2_LINE_OVERFLOW:
                        JMP V2_LINE_LONG
V2_DISPATCH:           LDA SVC_BANNER_PTR+1
                        BEQ TIME_SKIP
                        JSR $EF03
                        BCS V2_PROMPT
TIME_SKIP:              JSR AP_TRY
                        BCS V2_PROMPT
                        LDA     V2_LINE
                        BEQ V2_PROMPT
                        LDX     #$0F
V2_DISPATCH_FIND:      CMP     V2_COMMAND_KEYS,X
                        BEQ V2_DISPATCH_GO
                        DEX
                        BPL V2_DISPATCH_FIND
                        JMP V2_UNKNOWN
V2_DISPATCH_GO:        TXA
                        ASL     A
                        TAX
                        JMP     (V2_COMMAND_TABLE,X)
V2_SHOW_HELP:          LDA     V2_LINE+1
                        BNE V2_UNKNOWN
                        LDX     #V2_HELP
                        JMP V2_MESSAGE
V2_COMMAND_B:          JSR     V2_PARSE_BANK
                        BCC V2_BAD_BANK
                        PHA
                        JSR     V2_CHECK_CANCEL
                        BCC V2_B_READY
                        PLA
                        JMP V2_CANCELLED
V2_B_READY:            PLA
                        STA     V2_SELECTED
                        JMP V2_PROMPT
V2_COMMAND_J:
                        JSR     V2_PARSE_BANK
                        BCC V2_BAD_BANK
                        STA     V2_TARGET
                        JSR     V2_CHECK_CANCEL
                        BCS V2_CANCELLED
V2_J_READY:
                        JSR     V2_WORKER
                        LDX     #V2_BAD_VECTOR_TEXT
                        JMP V2_MESSAGE
V2_BAD_BANK:           LDX     #V2_BAD_BANK_TEXT
                        JMP V2_MESSAGE
V2_LINE_LONG:          LDX     #V2_LONG_TEXT
                        JMP V2_MESSAGE
V2_BAD_INPUT:          LDX     #V2_BAD_INPUT_TEXT
                        JMP V2_MESSAGE
V2_UNKNOWN:            LDX     #V2_UNKNOWN_TEXT
; The leading error ordinals share one stored "Bad " prefix.
V2_MESSAGE:            CPX     #V2_BAD_PREFIX
                        BCS V2_MESSAGE_BODY
                        JSR $7C98
                        PHX
                        LDX     #V2_BAD_PREFIX
                        JSR     V2_PRINT
                        PLX
V2_MESSAGE_BODY:       JSR     V2_PRINT
                        JMP     V2_PROMPT
V2_CANCELLED:          STZ     V2_CANCEL_REQUEST
                        JSR     V2_NEWLINE
                        LDX     #V2_CANCEL_TEXT
                        JMP V2_MESSAGE

V2_PARSE_BANK:         LDA     V2_LINE+1
                        SEC
                        SBC     #'0'
                        CMP     #$04
                        BCS V2_BANK_FAIL
                        LDY     V2_LINE+2
                        BNE V2_BANK_FAIL
                        SEC
                        RTS
V2_BANK_FAIL:          CLC
                        RTS

; The recovery monitor never depends on E code during reset. A missing or
; incompatible extension simply makes these three commands unavailable.
                        INCLUDE "app-fixed-symbols.inc"
; Candidate-only hook. Checked E000-E7FF extension, including its command table.
; Fixed F is unchanged; these private CRC helpers are pinned by its exact hash.
AP_TRY:                LDA V2_LINE
                        BEQ AP_UNHANDLED
                       JSR AP_CHECK
                        BCC AP_UNHANDLED
                       JMP $E008
AP_UNHANDLED:          CLC
                       RTS

AP_CHECK:              LDA $E000
                       CMP #'N'
                        BNE AP_BAD
                       LDA $E001
                       CMP #'A'
                        BNE AP_BAD
                       LDA $E002
                       CMP #$01
                        BNE AP_BAD
                       LDA $E003
                       CMP #$3F
                        BNE AP_BAD
                       JSR AP_CRC_INIT
                       STZ V2_PTR
                       LDA #$E0
                       STA V2_PTR+1
                       LDY #$00
AP_CHECK_LOOP:         LDA (V2_PTR),Y
                       JSR AP_CRC_BYTE
                       INY
                        BNE AP_CHECK_LOOP
                       INC V2_PTR+1
                       LDA V2_PTR+1
                       CMP #$F0
                        BNE AP_CHECK_LOOP
                       LDA J_CRC
                       ORA J_CRC+1
                        BNE AP_BAD
                       SEC
                       RTS
AP_BAD:                CLC
                       RTS

V2_SR_DISPATCH:        JSR AP_CHECK
                        BCC V2_SR_MISSING
                       JMP $E00B
V2_MAP_REQUEST:        JSR AP_CHECK
                        BCC V2_SR_MISSING
                       JMP $E00E
V2_SR_MISSING:         LDX #V2_SR_MISSING_TEXT
                       JMP V2_MESSAGE

                        INCLUDE "str8n-v2-monitor.inc"
                        INCLUDE "str8n-v2-load.inc"
                        INCLUDE "str8n-v2-flash.inc"
                        INCLUDE "str8n-v2-config.inc"

V2_COMMAND_W:          LDA V2_LINE+1
                        BEQ str8n_v2_LONG_296
                        JMP V2_UNKNOWN
str8n_v2_LONG_296:
                        JSR BOOT_API_W
                        JMP V2_PROMPT
V2_COMMAND_U:          LDA V2_LINE+1
                        BNE V2_U_ARGS
                        LDX #V2_UPDATE_USAGE
                        JMP V2_MESSAGE
V2_U_ARGS:             JMP BOOT_API_UPDATE

; P displays or durably promotes one exact valid slot generation. F's journal
; owns the preference and preserves it through legacy C and wear updates.
V2_COMMAND_P:          JSR V2_CONFIG_READ
                        BCS str8n_v2_LONG_308
                        JMP V2_P_NO_CONFIG
str8n_v2_LONG_308:
                        LDX #$01
                        JSR V2_SKIP_SPACES
                        BEQ V2_P_SHOW
                        CMP #'A'
                        BEQ V2_P_A
                        CMP #'B'
                        BNE V2_P_BAD
                        LDA #$B0
                        JMP V2_P_TARGET
V2_P_A:                LDA #$A0
V2_P_TARGET:           STA BOOT_DEST
                        INX
                        JSR V2_SKIP_SPACES
                        BNE V2_P_BAD
                        STZ V2_PTR
                        LDA BOOT_DEST
                        STA V2_PTR+1
                        JSR BOOT_SLOT_CHECK
                        BCC V2_P_BAD
                        LDA #'P'
                        STA V2_CONFIG+7
                        LDA BOOT_DEST
                        STA V2_CONFIG+8
                        LDY #$08
V2_P_GENERATION:       LDA (V2_PTR),Y
                        STA V2_CONFIG+1,Y
                        INY
                        CPY #$0C
                        BNE V2_P_GENERATION
                        JSR V2_CONFIG_SUM
                        LDA V2_CFG_SUM
                        STA V2_CONFIG+14
                        LDA V2_CFG_SUM2
                        STA V2_CONFIG+15
                        JSR BOOT_API_PROMOTE
                        BCC V2_P_FAILED
V2_P_SHOW:             LDA V2_CONFIG+7
                        CMP #'P'
                        BNE V2_P_BAD
                        LDX #V2_PROMOTE_TEXT
                        JSR V2_PRINT
                        LDA V2_CONFIG+8
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        AND #$01
                        CLC
                        ADC #'A'
                        JSR V2_PUTC
                        LDA #' '
                        JSR V2_PUTC
                        LDX #$03
V2_P_GEN_OUT:          LDA V2_CONFIG+9,X
                        JSR V2_HEX_OUT
                        DEX
                        BPL V2_P_GEN_OUT
                        JMP V2_PROMPT
V2_P_BAD:              JMP V2_BAD_RANGE
V2_P_FAILED:           JMP V2_FLASH_FAILED
V2_P_NO_CONFIG:        LDX #V2_NO_CONFIG_TEXT
                        JMP V2_MESSAGE

; M [1|2|3] loads the stored map utility; all other M arguments stay edits.
V2_CAPTURE_BANK:
                        LDX     #$00
                        LDA     V2_PCR
                        AND     #$0E
                        CMP     #$0C
                        BEQ V2_CAPTURE_CB2
                        INX
V2_CAPTURE_CB2:        LDA     V2_PCR
                        AND     #$E0
                        CMP     #$C0
                        BEQ V2_CAPTURE_DONE
                        INX
                        INX
V2_CAPTURE_DONE:       STX     V2_RESIDENT
                        STX     V2_SELECTED
                        STX     V2_TARGET
                        RTS

; Shared selected-bank suffix for the command and flash-risk prompts.
V2_BANK_READ_LINE:     LDA #'B'
                        JSR V2_PUTC
                        LDA V2_SELECTED
                        ORA     #'0'
                        JSR     V2_PUTC
                        LDA     #'>'
                        JSR     V2_PUTC
                        LDA     #' '
                        JSR     V2_PUTC
; Fall through so READ_LINE returns its original status to either caller.
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
                        BCC V2_LINE_INPUT_OK
                        LDY     #$02
V2_LINE_INPUT_OK:      CMP     #$0A
                        BNE V2_NOT_LF
                        LSR     V2_SKIP_LF
                        BCC V2_LINE_END
                        JMP V2_LINE_BYTE
V2_NOT_LF:             STZ     V2_SKIP_LF
                        CMP     #$0D
                        BNE V2_NOT_CR
                        INC     V2_SKIP_LF
                        JMP V2_LINE_END
V2_NOT_CR:             CMP     #$1B
                        BEQ V2_CANCEL
                        CMP     #$03
                        BEQ V2_CANCEL
                        CPY     #$00
                        BNE V2_LINE_BYTE
                        CMP     #$08
                        BEQ V2_BACKSPACE
                        CMP     #$7F
                        BEQ V2_BACKSPACE
                        CMP     #$09
                        BNE V2_NOT_TAB
                        LDA     #' '
V2_NOT_TAB:
                        CMP     #$20
                        BCC V2_INVALID_BYTE
                        CMP     #$7F
                        BCS V2_INVALID_BYTE
                        CMP     #'a'
                        BCC V2_STORE_CHAR
                        CMP     #'z'+1
                        BCS V2_STORE_CHAR
                        AND     #$DF
V2_STORE_CHAR:         CPX     #V2_LINE_LIMIT
                        BCS V2_OVERFLOW
                        STA     V2_LINE,X
                        INX
                        JSR     V2_PUTC
                        JMP V2_LINE_BYTE
V2_OVERFLOW:           INY
                        JMP V2_LINE_BYTE
V2_INVALID_BYTE:       LDY     #$02
                        JMP V2_LINE_BYTE
V2_BACKSPACE:          TXA
                        BEQ V2_LINE_BYTE
                        DEX
                        LDA     #$08
                        JSR     V2_PUTC
                        LDA     #' '
                        JSR     V2_PUTC
                        LDA     #$08
                        JSR     V2_PUTC
                        JMP V2_LINE_BYTE
V2_CANCEL:             LDX     #$00
                        LDY     #$03
V2_LINE_END:           STZ     V2_LINE,X
                        JSR     V2_NEWLINE
                        CPY     #$01
                        BCS V2_LINE_FAIL
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
                        BEQ V2_PRINT_NEXT
V2_PRINT_SCAN:         LDA     (V2_PTR),Y
                        INY
                        BNE V2_PRINT_SCAN_TEST
                        INC     V2_PTR+1
V2_PRINT_SCAN_TEST:    CMP     #$80
                        BCC V2_PRINT_SCAN
                        DEX
                        BNE V2_PRINT_SCAN
V2_PRINT_NEXT:         LDA     (V2_PTR),Y
                        PHA
                        AND     #$7F
                        JSR     V2_PUTC
                        PLA
                        BMI V2_PRINT_END
                        INY
                        BNE V2_PRINT_NEXT
                        INC     V2_PTR+1
                        JMP V2_PRINT_NEXT
V2_PRINT_END:          PLX
                        RTS

V2_COMMAND_KEYS:      DB      "BDMGLFICJ?SRTWUP"
V2_COMMAND_TABLE:     DW      V2_COMMAND_B,V2_COMMAND_D,V2_COMMAND_M,V2_COMMAND_G
                        DW      V2_COMMAND_L,V2_COMMAND_F,V2_COMMAND_I,V2_COMMAND_C
                        DW      V2_COMMAND_J,V2_SHOW_HELP
                        DW      V2_SR_DISPATCH,V2_SR_DISPATCH,V2_SR_DISPATCH
                        DW      V2_COMMAND_W,V2_COMMAND_U,V2_COMMAND_P
; S19 errors 1..4; cancellation uses its existing cleanup path.
V2_LOAD_ERROR_TEXTS:   DB      V2_S19_BAD_TEXT,V2_S19_SUM_TEXT
                        DB      V2_CANCEL_TEXT,V2_PROTECTED_TEXT
                        INCLUDE "text-image.inc"
V2_CLOCK_BANNER: JMP (SVC_BANNER_PTR)
B29_CHECK_PROVIDER:
        STZ $7EF4
        LDA V2_SELECTED
        PHA
        LDA #2
        STA V2_SELECTED
        STZ V2_ADDR
        LDA #$80
        STA V2_ADDR+1
        LDA #16
        STA V2_COUNT
        JSR V2W_READ
        LDX #3
B29_PROVIDER_HEADER:
        LDA V2_BYTES,X
        CMP B29_PROVIDER_MAGIC,X
        BNE B29_PROVIDER_BAD
        DEX
        BPL B29_PROVIDER_HEADER
        JSR $FAB4
B29_PROVIDER_BLOCK:
        LDY #0
B29_PROVIDER_CRC:
        LDA V2_BYTES,Y
        JSR $FABD
        INY
        CPY #16
        BNE B29_PROVIDER_CRC
        CLC
        LDA V2_ADDR
        ADC #16
        STA V2_ADDR
        BCC B29_PROVIDER_READ
        INC V2_ADDR+1
        LDA V2_ADDR+1
        CMP #$D8
        BEQ B29_PROVIDER_SEAL
B29_PROVIDER_READ:
        JSR V2W_READ
        BRA B29_PROVIDER_BLOCK
B29_PROVIDER_SEAL:
        LDA J_CRC
        ORA J_CRC+1
        BNE B29_PROVIDER_BAD
        LDA #$BA
        STA $7EF4
        BRA B29_PROVIDER_RESTORE
B29_PROVIDER_BAD:
        STZ $7EE4
B29_PROVIDER_RESTORE:
        PLA
        STA V2_SELECTED
        RTS
B29_PROVIDER_MAGIC DB "UX",3,42
B29_GATE_IMAGE:
                        INCLUDE "batch-gate.inc"
B29_GATE_END:
V2_END:
                        ENDMOD
                        END
