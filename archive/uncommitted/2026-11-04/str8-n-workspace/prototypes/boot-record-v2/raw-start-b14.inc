RL_LOAD:
        STZ B14_PENDING
        LDA DC_LAST
        STA DC_BINARY
        ; Consume the optional LF belonging to the command before SEND BIN.
        ; Raw bytes start after that ready message; no control decoding then.
        JSR V2W_BOOT_DELAY
        LDA DC_SKIP
        AND DC_BINARY
        BEQ B14_READY
        JSR V2W_RAW_POLL
        BCC B14_READY
        CMP #10
        BEQ B14_READY
        STA B14_PENDING_BYTE
        INC B14_PENDING
B14_READY:
        ; Preserve a receive error detected during the optional-LF probe.
        LDA V2_RX_BAD
        PHA
        JSR V2W_RX_RESET
        PLA
        STA V2_RX_BAD
        STZ DC_BINARY
        STZ RL_PTR
        LDA #2
        STA RL_PTR+1
        LDX #<RL_SEND
        LDY #>RL_SEND
        JSR BOOT_PRINT
        LDA B14_PENDING
        BEQ B14_FIRST
        LDA B14_PENDING_BYTE
        JMP RL_LOAD_BYTE
B14_FIRST:
        JSR V2W_RAW_POLL
        BCS B14_FIRST_GOT
        LDA V2_RX_BAD
        BNE B14_FIRST_BAD
        BRA B14_FIRST
B14_FIRST_GOT:
        JMP RL_LOAD_BYTE
B14_FIRST_BAD:
        JMP B14_RX_BAD
