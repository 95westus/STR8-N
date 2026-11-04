; Stored in F; all instructions below execute in RAM with any bank visible.
V2W_RX_RESET:
        STZ V2_RX_HEAD
        STZ V2_RX_TAIL
        STZ V2_RX_COUNT
        STZ V2_RX_BAD
        STZ V2_CANCEL_REQUEST
        STZ DC_OWNER
        STZ DC_DROP
        STZ DC_SKIP
        RTS

V2W_RX_SERVICE:
        JSR V2W_RAW_POLL
        BCC DC_RX_RETURN
        PHX
        STA V2_RX_CHAR
        CMP #3
        BEQ DC_RX_CANCEL
DC_RX_OWN:
        LDA DC_LAST
        AND DC_DROP
        BNE DC_RX_DROP
        LDA DC_OWNER
        BEQ DC_RX_CLAIM
        CMP DC_LAST
        BEQ DC_RX_QUEUE
        LDA DC_LAST
        TSB DC_DROP
DC_RX_DROP:
        LDA V2_RX_CHAR
        CMP #13
        BEQ DC_RX_DROPPED_END
        CMP #10
        BNE DC_RX_CONSUMED
DC_RX_DROPPED_END:
        LDA DC_LAST
        TRB DC_DROP
        CMP DC_OWNER
        BEQ DC_RX_STORE
        JMP DC_RX_CONSUMED
DC_RX_CLAIM:
        LDA DC_LAST
        STA DC_OWNER
DC_RX_QUEUE:
DC_RX_STORE:
        LDA V2_RX_COUNT
        CMP #V2_RX_SIZE
        BCS DC_RX_OVERFLOW
        LDA V2_RX_TAIL
        AND #(V2_RX_SIZE-1)
        TAX
        LDA V2_RX_CHAR
        STA V2_RX_QUEUE,X
        INC V2_RX_TAIL
        INC V2_RX_COUNT
DC_RX_CONSUMED:
        PLX
        SEC
DC_RX_RETURN:
        RTS
DC_RX_OVERFLOW:
        JSR V2W_RX_RESET
        LDA #1
        STA V2_RX_BAD
        LDA DC_LAST
        STA DC_OWNER
        TSB DC_DROP
        JMP DC_RX_DROP
DC_RX_CANCEL:
        JSR V2W_RX_RESET
        INC V2_CANCEL_REQUEST
        JMP DC_RX_CONSUMED

; CHKC services one hardware byte but never consumes a queued byte.
V2W_CHKC:
        JSR V2W_RX_SERVICE
        LDA V2_CANCEL_REQUEST
        ORA V2_RX_COUNT
        CMP #1
        RTS
V2W_GETC:
V2W_GETC_WAIT:
        JSR V2W_CON_POLL
        BCC V2W_GETC
        RTS
V2W_CON_POLL:
        JSR V2W_CHKC
        BCC DC_POLL_RETURN
        LSR V2_CANCEL_REQUEST
        BCC DC_POLL_QUEUE
        LDA #3
        RTS
DC_POLL_QUEUE:
        PHX
        LDA V2_RX_HEAD
        AND #(V2_RX_SIZE-1)
        TAX
        LDA V2_RX_QUEUE,X
        INC V2_RX_HEAD
        DEC V2_RX_COUNT
        PHA
        LDA DC_OWNER
        STA DC_LAST
        LDA V2_RX_COUNT
        BNE DC_POLL_KEEP_OWNER
        PLA
        CMP #13
        BEQ DC_POLL_RELEASE
        CMP #10
        BNE DC_POLL_FINISH
DC_POLL_RELEASE:
        STZ DC_OWNER
DC_POLL_FINISH:
        PLX
        SEC
DC_POLL_RETURN:
        RTS
DC_POLL_KEEP_OWNER:
        PLA
        JMP DC_POLL_FINISH
V2W_CHECK_CANCEL:
        PHX
        LDX #V2_RX_SIZE
DC_CANCEL_POLL:
        LDA V2_CANCEL_REQUEST
        BNE DC_CANCEL_DONE
        JSR V2W_RX_SERVICE
        BCC DC_CANCEL_DONE
        DEX
        BNE DC_CANCEL_POLL
DC_CANCEL_DONE:
        LDA V2_CANCEL_REQUEST
        LSR A
        PLX
        RTS

V2W_CON_INIT:
        LDA #$0C
        STA V2_CTRL
        STA V2_DDRB
        STZ V2_DDRA
        STZ V2_ACIA_STATUS
        LDA #V2_ACIA_CONTROL_19200
        STA V2_ACIA_CONTROL
        LDA #V2_ACIA_COMMAND_19200
        STA V2_ACIA_COMMAND
        STZ DC_BINARY
        STZ DC_NEXT
        STZ DC_TX_LOST
        LDA #3
        STA V2_CONSOLE
        JMP V2W_RX_RESET

; Try both enabled sources fairly. Binary ownership overrides text mode.
V2W_RAW_POLL:
        PHX
        LDA DC_BINARY
        BNE DC_RAW_MASK
        LDA V2_CONSOLE
DC_RAW_MASK:
        TAX
        LDA DC_NEXT
        LSR A
        BCC DC_RAW_FT_FIRST
        JSR DC_RAW_ACIA
        BCS DC_RAW_GOT
        JSR DC_RAW_FT
        JMP DC_RAW_FINISH
DC_RAW_FT_FIRST:
        JSR DC_RAW_FT
        BCS DC_RAW_GOT
        JSR DC_RAW_ACIA
DC_RAW_FINISH:
        BCC DC_RAW_DONE
DC_RAW_GOT:
        PHA
        LDA DC_LAST
        STA DC_NEXT
        PLA
        SEC
DC_RAW_DONE:
        PLX
        RTS
DC_RAW_FT:
        TXA
        LSR A
        BCC DC_RAW_EMPTY
        STZ V2_DDRA
        LDA #2
        BIT V2_CTRL
        BNE DC_RAW_EMPTY
        LDA #8
        TRB V2_CTRL
        NOP
        NOP
        LDA V2_DATA
        PHA
        LDA #8
        TSB V2_CTRL
        LDA #1
        STA DC_LAST
        PLA
        SEC
        RTS
DC_RAW_ACIA:
        TXA
        AND #2
        BEQ DC_RAW_EMPTY
        LDA V2_ACIA_STATUS
        PHA
        AND #7
        BEQ DC_RAW_ACIA_OK
        LDA #1
        STA V2_RX_BAD
DC_RAW_ACIA_OK:
        PLA
        AND #V2_ACIA_RDRF
        BEQ DC_RAW_EMPTY
        LDA #2
        STA DC_LAST
        LDA V2_ACIA_DATA
        SEC
        RTS
DC_RAW_EMPTY:
        CLC
        RTS

; Text is best effort per port; lost FT245 bytes set a sticky bit.
; Binary output reports C=0 on blocked FT245 so its caller can abort.
V2W_PUTC:
V2W_TX_WAIT:
        STA DC_TX_CHAR
        PHA
        LDA DC_BINARY
        BNE DC_TX_MASK
        LDA V2_CANCEL_REQUEST
        BNE DC_TX_OK
        LDA V2_CONSOLE
DC_TX_MASK:
        LSR A
        BCC DC_TX_ACIA
        LDA #1
        BIT V2_CTRL
        BNE DC_TX_BLOCKED
        STZ V2_DDRA
        LDA DC_TX_CHAR
        JSR V2W_SEND
        JMP DC_TX_ACIA
DC_TX_BLOCKED:
        TSB DC_TX_LOST
        LDA DC_BINARY
        BNE DC_TX_FAIL
DC_TX_ACIA:
        LDA DC_BINARY
        BNE DC_TX_ACIA_MASK
        LDA V2_CONSOLE
DC_TX_ACIA_MASK:
        AND #2
        BEQ DC_TX_OK
        LDA DC_TX_CHAR
        JSR V2W_ACIA_SEND
DC_TX_OK:
        SEC
        JMP DC_TX_RETURN
DC_TX_FAIL:
        CLC
DC_TX_RETURN:
        PLA
        RTS
