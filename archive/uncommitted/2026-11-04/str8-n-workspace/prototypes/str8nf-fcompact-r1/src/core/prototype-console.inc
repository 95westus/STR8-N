FC_READ_LINE:
        LDA V2_RX_BAD
        ORA V2_RX_COUNT
        BNE FC_KEEP_OWNER
        STZ DC_OWNER
FC_KEEP_OWNER:
                        LDX     #$00
                        LDY     #$00
FC_LINE_BYTE:          JSR     V2W_GETC
; RX_BAD is boolean: shift it into carry and clear it without changing A.
                        LSR     V2_RX_BAD
                        BCC FC_LINE_INPUT_OK
                        LDY     #$02
FC_LINE_INPUT_OK:      CMP     #$0A
                        BNE FC_NOT_LF
        PHA
        LDA DC_LAST
        AND DC_SKIP
        BEQ FC_LF_END
        LDA DC_LAST
        TRB DC_SKIP
        PLA
        JMP FC_LINE_BYTE
FC_LF_END:
        PLA
        JMP FC_LINE_END
FC_NOT_LF:
        PHA
        LDA DC_LAST
        TRB DC_SKIP
        PLA
                        CMP     #$0D
                        BNE FC_NOT_CR
        PHA
        LDA DC_LAST
        TSB DC_SKIP
        PLA
                        JMP FC_LINE_END
FC_NOT_CR:             CMP     #$1B
                        BEQ FC_CANCEL
                        CMP     #$03
                        BEQ FC_CANCEL
                        CPY     #$00
                        BNE FC_LINE_BYTE
                        CMP     #$08
                        BEQ FC_BACKSPACE
                        CMP     #$7F
                        BEQ FC_BACKSPACE
                        CMP     #$09
                        BNE FC_NOT_TAB
                        LDA     #' '
FC_NOT_TAB:
                        CMP     #$20
                        BCC FC_INVALID_BYTE
                        CMP     #$7F
                        BCS FC_INVALID_BYTE
                        CPX     #V2_LINE_LIMIT
                        BCS FC_OVERFLOW
                        PHA
                        CMP     #'a'
                        BCC FC_STORE_CHAR
                        CMP     #'z'+1
                        BCS FC_STORE_CHAR
                        AND     #$DF
FC_STORE_CHAR:         STA     V2_LINE,X
                        INX
                        PLA
                        JSR     V2W_PUTC
                        JMP FC_LINE_BYTE
FC_OVERFLOW:           INY
                        JMP FC_LINE_BYTE
FC_INVALID_BYTE:       LDY     #$02
                        JMP FC_LINE_BYTE
FC_BACKSPACE:          TXA
        BNE FC_ERASE_BACKSPACE
        JMP FC_LINE_BYTE
FC_ERASE_BACKSPACE:
                        DEX
                        LDA     #$08
                        JSR     V2W_PUTC
                        LDA     #' '
                        JSR     V2W_PUTC
                        LDA     #$08
                        JSR     V2W_PUTC
                        JMP FC_LINE_BYTE
FC_CANCEL:             LDX     #$00
                        LDY     #$03
FC_LINE_END:           STZ     V2_LINE,X
                        JSR     V2V_RAM_NEWLINE
                        CPY     #$01
                        BCS FC_LINE_FAIL
                        SEC
                        RTS
FC_LINE_FAIL:          CLC
                        RTS

FC_EDITOR_END:
FC_SKIP_SPACES:        LDA     V2_LINE,X
                        CMP     #' '
                        BNE FC_SKIP_DONE
FC_str8n_v2_monitor_LONG_214:
                        INX
                        JMP FC_SKIP_SPACES
FC_SKIP_DONE:          CMP     #$00
                        RTS

; IN X=line offset. OUT word in VALUE, X at space/NUL, C=valid.
; Addresses accept 1-4 digits; byte values 1-2. A token must end at space/NUL.
FC_HEX_WORD:           LDA     #$04
                        JMP FC_HEX_PARSE
FC_HEX_BYTE:           LDA     #$02
FC_HEX_PARSE:          STA     V2_DIGIT_LIMIT
                        STZ     V2_VALUE
                        STZ     V2_VALUE+1
                        JSR     FC_SKIP_SPACES
                        BEQ FC_HEX_FAIL
FC_str8n_v2_monitor_LONG_229:
FC_HEX_NEXT:           LDA     V2_LINE,X
                        BEQ FC_HEX_END
FC_str8n_v2_monitor_LONG_231:
                        CMP     #' '
                        BEQ FC_HEX_END
FC_str8n_v2_monitor_LONG_233:
                        DEC     V2_DIGIT_LIMIT
                        BMI FC_HEX_FAIL
FC_str8n_v2_monitor_LONG_235:
                        JSR     V2V_RAM_HEX_NIBBLE
                        BCC FC_HEX_FAIL
FC_str8n_v2_monitor_LONG_237:
; Remaining digits live in DIGIT_LIMIT. Y shifts the value, leaving both
; the decoded nibble in A and the line position in X intact.
FC_HEX_DIGIT:          LDY     #$04
FC_HEX_SHIFT:         ASL     V2_VALUE
                        ROL     V2_VALUE+1
                        DEY
                        BNE FC_HEX_SHIFT
FC_str8n_v2_monitor_LONG_244:
                        ORA     V2_VALUE
                        STA     V2_VALUE
                        INX
                        JMP FC_HEX_NEXT
; Empty tokens were rejected before the loop; reaching here means success.
FC_HEX_END:            SEC
                        RTS
FC_HEX_FAIL:           CLC
                        RTS
FC_PARSERS_END:
