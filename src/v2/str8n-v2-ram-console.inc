; Bank-independent public console core. Linked into the RAM worker so no
; returning ABI call changes the visible flash bank.
V2W_RX_RESET:          STZ     V2_RX_HEAD
                        STZ     V2_RX_TAIL
                        STZ     V2_RX_COUNT
                        STZ     V2_RX_DROP
                        STZ     V2_RX_BAD
                        STZ     V2_CANCEL_REQUEST
                        RTS

V2W_RX_SERVICE:        JSR     V2W_RAW_POLL
                        BCC     V2W_RX_RETURN
                        PHX
                        STA     V2_RX_CHAR
                        CMP     #$03
                        BEQ     V2W_RX_CANCEL
                        LDA     V2_RX_DROP
                        BEQ     V2W_RX_QUEUE_BYTE
V2W_RX_DELIMITER:      LDA     V2_RX_CHAR
                        CMP     #$0D
                        BEQ     V2W_RX_LINE_END
                        CMP     #$0A
                        BNE     V2W_RX_CONSUMED
V2W_RX_LINE_END:       STZ     V2_RX_DROP
                        LDA     #$0D
                        STA     V2_RX_CHAR
V2W_RX_QUEUE_BYTE:     LDA     V2_RX_COUNT
                        CMP     #V2_RX_SIZE
                        BCS     V2W_RX_OVERFLOW
                        LDA     V2_RX_TAIL
                        AND     #(V2_RX_SIZE-1)
                        TAX
                        LDA     V2_RX_CHAR
                        STA     V2_RX_QUEUE,X
                        INC     V2_RX_TAIL
                        INC     V2_RX_COUNT
V2W_RX_CONSUMED:       PLX
                        SEC
V2W_RX_RETURN:         RTS
V2W_RX_OVERFLOW:       STZ     V2_RX_HEAD
                        STZ     V2_RX_TAIL
                        STZ     V2_RX_COUNT
                        LDA     #$01
                        STA     V2_RX_DROP
                        STA     V2_RX_BAD
                        BRA     V2W_RX_DELIMITER
V2W_RX_CANCEL:         JSR     V2W_RX_RESET
                        INC     V2_CANCEL_REQUEST
                        BRA     V2W_RX_CONSUMED

V2W_GETC:              PHX
V2W_GETC_WAIT:         LSR     V2_CANCEL_REQUEST
                        BCC     V2W_GETC_QUEUE
                        LDA     #$03
                        PLX
                        RTS
V2W_GETC_QUEUE:        LDA     V2_RX_COUNT
                        BNE     V2W_GETC_POP
                        JSR     V2W_RX_SERVICE
                        BRA     V2W_GETC_WAIT
V2W_GETC_POP:          LDA     V2_RX_HEAD
                        AND     #(V2_RX_SIZE-1)
                        TAX
                        LDA     V2_RX_QUEUE,X
                        INC     V2_RX_HEAD
                        DEC     V2_RX_COUNT
                        PLX
                        RTS

V2W_CHECK_CANCEL:      PHX
                        LDX     #V2_RX_SIZE
V2W_CANCEL_POLL:       LDA     V2_CANCEL_REQUEST
                        BNE     V2W_CANCEL_POLL_DONE
                        JSR     V2W_RX_SERVICE
                        BCC     V2W_CANCEL_POLL_DONE
                        DEX
                        BNE     V2W_CANCEL_POLL
V2W_CANCEL_POLL_DONE:  LDA     V2_CANCEL_REQUEST
                        LSR     A
                        PLX
                        RTS

V2W_CON_INIT:          LDA     #$0C
                        STA     V2_CTRL
                        STA     V2_DDRB
                        STZ     V2_DDRA
                        LDA     V2_CTRL
                        AND     #$20
                        BEQ     V2W_CON_FT245
                        LDA     #V2_CONSOLE_ACIA
                        BRA     V2W_CON_SELECTED
V2W_CON_FT245:         LDA     #V2_CONSOLE_FT245
V2W_CON_SELECTED:      CMP     V2_CONSOLE
                        BEQ     V2W_CON_INITIALIZE
                        STA     V2_CONSOLE
                        JSR     V2W_RX_RESET
; Selection is exactly 0/1 and RX_RESET preserves A.
V2W_CON_INITIALIZE:    LSR     A
                        BCC     V2W_CON_READY
                        STZ     V2_ACIA_STATUS
                        LDA     #V2_ACIA_CONTROL_19200
                        STA     V2_ACIA_CONTROL
                        LDA     #V2_ACIA_COMMAND_19200
                        STA     V2_ACIA_COMMAND
V2W_CON_READY:         RTS

V2W_RAW_POLL:          LDA     V2_CONSOLE
                        BNE     V2W_ACIA_RAW_POLL
                        STZ     V2_DDRA
                        LDA     #$02
                        BIT     V2_CTRL
                        BNE     V2W_RAW_EMPTY
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
V2W_RAW_EMPTY:         CLC
                        RTS
V2W_ACIA_RAW_POLL:     LDA     #V2_ACIA_RDRF
                        BIT     V2_ACIA_STATUS
                        BEQ     V2W_RAW_EMPTY
                        LDA     V2_ACIA_DATA
                        SEC
                        RTS

V2W_PUTC:              PHA
                        LDA     V2_CANCEL_REQUEST
                        BNE     V2W_TX_CANCEL
                        LDA     V2_CONSOLE
                        BNE     V2W_TX_ACIA
                        STZ     V2_DDRA
                        LDA     #$01
V2W_TX_WAIT:           BIT     V2_CTRL
                        BEQ     V2W_TX_READY
                        JSR     V2W_RX_SERVICE
                        LDA     V2_CANCEL_REQUEST
                        BNE     V2W_TX_CANCEL
                        LDA     #$01
                        BRA     V2W_TX_WAIT
V2W_TX_READY:          PLA
                        PHA
                        JSR     V2W_SEND
                        BRA     V2W_TX_CANCEL
V2W_TX_ACIA:           PLA
                        PHA
                        JSR     V2W_ACIA_SEND
V2W_TX_CANCEL:         PLA
                        RTS
