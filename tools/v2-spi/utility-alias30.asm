; Exact monitor aliases share the existing native-name table.
; Only called for provider zero. Do not intercept utility subcommands.
B30_ALIAS:
        LDX #0
B30_LEADING:
        LDA $7C00,X
        CMP #' '
        BNE B30_FIRST
        INX
        BRA B30_LEADING
B30_FIRST:
        STX B29_LIMIT
        LDY #0
B30_NAME:
        STY B29_LENGTH
        LDX B29_LIMIT
B30_MATCH:
        LDA B29_NATIVE_NAMES,Y
        BEQ B30_TAIL
        CMP #$FF
        BEQ B30_RETURN
        CMP $7C00,X
        BNE B30_NEXT
        INX
        INY
        BRA B30_MATCH
B30_TAIL:
        LDA $7C00,X
        BEQ B30_EXPAND
        CMP #' '
        BNE B30_NEXT
        INX
        BRA B30_TAIL
B30_NEXT:
        LDA B29_NATIVE_NAMES,Y
        CMP #$FF
        BEQ B30_RETURN
        INY
        CMP #0
        BNE B30_NEXT
        BRA B30_NAME
B30_EXPAND:
        LDY B29_LENGTH
        LDX #2
B30_COPY:
        LDA B29_NATIVE_NAMES,Y
        STA $7C00,X
        BEQ B30_PREFIX
        INX
        INY
        BRA B30_COPY
B30_PREFIX:
        STX B29_N
        LDA #'R'
        STA $7C00
        LDA #' '
        STA $7C01
B30_RETURN:
        RTS
