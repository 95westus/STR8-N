; Example command body, linked into resident B3:C flash at C900.
; The registered target is a three-byte RAM JMP stub at 7403.
; No persistent state: only foreground monitor scratch E0-E4.
                        MODULE B2_COMMAND_X
                        XDEF X_ENTRY
                        XDEF X_END
                        INCLUDE "str8n-v2-public.inc"
TEXT_PTR                EQU $E0
TOKEN_PTR               EQU $E2
ARG_START               EQU $E4
                        CODE
X_ENTRY:                LDX #$01
                        JSR SKIP_SPACES
                        BEQ SHOW_USAGE
                        STX ARG_START
                        LDA #<HELLO_TOKEN
                        LDY #>HELLO_TOKEN
                        JSR MATCH_TOKEN
                        BCC TRY_ECHO
                        JSR SKIP_SPACES
                        BNE SHOW_USAGE
                        LDX #<HELLO_TEXT
                        LDY #>HELLO_TEXT
                        JSR PRINT
                        BRA HANDLED
TRY_ECHO:               LDX ARG_START
                        LDA #<ECHO_TOKEN
                        LDY #>ECHO_TOKEN
                        JSR MATCH_TOKEN
                        BCC SHOW_USAGE
                        JSR SKIP_SPACES
ECHO_ENTRY:
ECHO_BYTE:              LDA STR8V2_LINE,X
                        BEQ ECHO_DONE
                        JSR EMIT
                        INX
                        BRA ECHO_BYTE
ECHO_DONE:              JSR STR8V2_RAM_NEWLINE
                        BRA HANDLED
SHOW_USAGE:             LDX #<USAGE_TEXT
                        LDY #>USAGE_TEXT
                        JSR PRINT
HANDLED:                LDA #$01
                        RTS
HELLO_ENTRY:            LDA STR8V2_LINE,X
                        BNE SHOW_USAGE
                        LDX #<HELLO_TEXT
                        LDY #>HELLO_TEXT
                        JSR PRINT
                        BRA HANDLED
; X indexes the original NUL-terminated line; tabs were normalized by core.
SKIP_SPACES:            LDA STR8V2_LINE,X
                        CMP #' '
                        BNE SKIP_DONE
                        INX
                        BRA SKIP_SPACES
SKIP_DONE:              CMP #$00
                        RTS
; A/Y=keyword low/high, X=line offset. On success X points after keyword.
; Matching includes the token boundary, so HELLOX is not HELLO.
MATCH_TOKEN:            STA TOKEN_PTR
                        STY TOKEN_PTR+1
                        LDY #$00
MATCH_BYTE:             LDA (TOKEN_PTR),Y
                        BEQ MATCH_BOUNDARY
                        CMP STR8V2_LINE,X
                        BNE MATCH_FAIL
                        INX
                        INY
                        BRA MATCH_BYTE
MATCH_BOUNDARY:         LDA STR8V2_LINE,X
                        BEQ MATCH_OK
                        CMP #' '
                        BNE MATCH_FAIL
MATCH_OK:               SEC
                        RTS
MATCH_FAIL:             CLC
                        RTS
; Preserve our loop registers across the public console call.
EMIT:                   PHX
                        PHY
                        JSR STR8V2_RAM_PUTC
                        PLY
                        PLX
                        RTS
PRINT:                  STX TEXT_PTR
                        STY TEXT_PTR+1
                        LDY #$00
PRINT_BYTE:             LDA (TEXT_PTR),Y
                        BEQ PRINT_DONE
                        JSR EMIT
                        INC TEXT_PTR
                        BNE PRINT_BYTE
                        INC TEXT_PTR+1
                        BRA PRINT_BYTE
PRINT_DONE:             RTS
HELLO_TOKEN:            DB "HELLO",0
ECHO_TOKEN:             DB "ECHO",0
HELLO_TEXT:             DB "HELLO FROM X",$0D,$0A,0
USAGE_TEXT:             DB "Use X HELLO or X ECHO text",$0D,$0A,0
X_END:
                        ENDMOD
                        END
