; Bounded typeahead keeps polling for Ctrl-C from eating the next command.
; An overflowing line is discarded through its delimiter and reported as
; Bad input, never executed as a truncated prefix/suffix. X/Y are preserved.
V2_RX_RESET:           STZ     V2_RX_HEAD
                        STZ     V2_RX_TAIL
                        STZ     V2_RX_COUNT
                        STZ     V2_RX_DROP
                        STZ     V2_RX_BAD
                        STZ     V2_CANCEL_REQUEST
                        RTS

V2_RX_SERVICE:         JSR     V2_RAW_POLL
                        BCC     V2_RX_RETURN
                        PHX
                        STA     V2_RX_CHAR
                        CMP     #$03
                        BEQ     V2_RX_CANCEL
                        LDA     V2_RX_DROP
                        BEQ     V2_RX_QUEUE_BYTE
V2_RX_DELIMITER:       LDA     V2_RX_CHAR
                        CMP     #$0D
                        BEQ     V2_RX_LINE_END
                        CMP     #$0A
                        BNE     V2_RX_CONSUMED
V2_RX_LINE_END:        STZ     V2_RX_DROP
                        LDA     #$0D
                        STA     V2_RX_CHAR
V2_RX_QUEUE_BYTE:      LDA     V2_RX_COUNT
                        CMP     #V2_RX_SIZE
                        BCS     V2_RX_OVERFLOW
                        LDA     V2_RX_TAIL
                        AND     #(V2_RX_SIZE-1)
                        TAX
                        LDA     V2_RX_CHAR
                        STA     V2_RX_QUEUE,X
                        INC     V2_RX_TAIL
                        INC     V2_RX_COUNT
V2_RX_CONSUMED:        PLX
                        SEC
V2_RX_RETURN:          RTS
V2_RX_OVERFLOW:        STZ     V2_RX_HEAD
                        STZ     V2_RX_TAIL
                        STZ     V2_RX_COUNT
                        LDA     #$01
                        STA     V2_RX_DROP
                        STA     V2_RX_BAD
                        BRA     V2_RX_DELIMITER
V2_RX_CANCEL:          JSR     V2_RX_RESET
                        INC     V2_CANCEL_REQUEST
                        BRA     V2_RX_CONSUMED

V2_GETC:               PHX
; Consume the boolean cancel latch; an absent request remains zero.
V2_GETC_WAIT:          LSR     V2_CANCEL_REQUEST
                        BCC     V2_GETC_QUEUE
                        LDA     #$03
                        PLX
                        RTS
V2_GETC_QUEUE:         LDA     V2_RX_COUNT
                        BNE     V2_GETC_POP
                        JSR     V2_RX_SERVICE
                        BRA     V2_GETC_WAIT
V2_GETC_POP:           LDA     V2_RX_HEAD
                        AND     #(V2_RX_SIZE-1)
                        TAX
                        LDA     V2_RX_QUEUE,X
                        INC     V2_RX_HEAD
                        DEC     V2_RX_COUNT
                        PLX
                        RTS

; Safe-point poll: at most 64 physical bytes, preserving command typeahead.
; C=1 means cancel requested; the caller completes/unwinds any atomic work.
V2_CHECK_CANCEL:       PHX
                        LDX     #V2_RX_SIZE
V2_CANCEL_POLL:        LDA     V2_CANCEL_REQUEST
                        BNE     V2_CANCEL_POLL_DONE
                        JSR     V2_RX_SERVICE
                        BCC     V2_CANCEL_POLL_DONE
                        DEX
                        BNE     V2_CANCEL_POLL
V2_CANCEL_POLL_DONE:   LDA     V2_CANCEL_REQUEST
                        LSR     A
                        PLX
                        RTS
