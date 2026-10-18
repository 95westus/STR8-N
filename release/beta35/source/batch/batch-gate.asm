        MODULE BATCH_GATE
        XDEF B29_GATE_END
        CODE
B29_MON: JMP B29_MON_VERIFY
        NOP
B29_CLOCK: LDA #5
        BRA B29_COMMON
B29_ERROR: LDA #1
        STA $7EE7
        RTS
B29_APP: RTS
B29_COMMON:
        STA $7EE8
        LDA $7FEC
        STA $7EE9
        LDA #2
        JSR $7848
        LDA $7EE8
        JSR $D0EA
        BCS B29_RETURN
        LDA $7EE9
        STA $7FEC
        JSR B29_ORIGINAL
        BCC B29_RAW_RETURN
        PHX
        PHY
        LDA #2
        JSR $7848
        LDA $7EE8
        ORA #$80
        JSR $D0EA
        PLY
        PLX
B29_RETURN:
        PHP
        LDA $7EE9
        STA $7FEC
        PLP
B29_RAW_RETURN:
        RTS
B29_ORIGINAL: JMP ($7EEA)
B29_MON_VERIFY:
        LDA $7EF4
        CMP #$B9
        BEQ B29_MON_ENABLED
        JMP ($7EEA)
B29_MON_ENABLED:
        LDA #0
        JMP B29_COMMON
B29_GATE_END:
        ENDMOD
