; Raw BIN receiver. Empty polls count nominal CPU cycles; no frame/CRC/length.
; Main fits the tail of the old 302-byte RLP1 region after relocated vectors.
RL_LOAD_BYTE:
        PHA
        LDA V2_RX_BAD
        BNE B14_RX_BAD_POP
        LDA RL_PTR+1
        CMP #$65
        BCS B14_RANGE_POP
        PLA
        STA (RL_PTR)
        INC RL_PTR
        BNE B14_RELOAD
        INC RL_PTR+1
B14_RELOAD:
        LDA DC_LAST
        STA DC_BINARY
        ; DC_NEXT always equals the selected port after a successful poll.
        CMP #1
        BNE B14_ACIA_TIMER
        LDX #B14_FT_LO
        LDY #B14_FT_MID
        LDA #B14_FT_HI
        BRA B14_TIMER_SET
B14_ACIA_TIMER:
        LDX #B14_AC_LO
        LDY #B14_AC_MID
        LDA #B14_AC_HI
B14_TIMER_SET:
        STA B14_TICKS
B14_IDLE:
        JSR V2W_RAW_POLL
        BCS RL_LOAD_BYTE
        LDA V2_RX_BAD
        BNE B14_RX_BAD
        DEX
        BNE B14_IDLE
        DEY
        BNE B14_IDLE
        DEC B14_TICKS
        BNE B14_IDLE
B14_RUN:
        STZ DC_BINARY
        JSR V2W_RX_RESET
        JMP $0200
B14_RX_BAD_POP:
        PLA
B14_RX_BAD:
        LDX #<B14_RX_TEXT
        LDY #>B14_RX_TEXT
        JMP BR_MESSAGE
B14_RANGE_POP:
        PLA
        LDX #<BR_REFUSED
        LDY #>BR_REFUSED
        JMP BR_MESSAGE
