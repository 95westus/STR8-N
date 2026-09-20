; Load-only S0/S1/S9. Each complete, checked S1 commits atomically to
; application RAM $0200-$68FF. Earlier records survive errors/cancellation.
V2_COMMAND_L:          LDX     #$01
                        JSR     V2_SKIP_SPACES
                        BEQ     V2_LOAD_BEGIN
                        JMP     V2_BAD_HEX
V2_LOAD_BEGIN:         STZ     V2_LOAD_HAVE_DATA
                        LDX     #V2_S19_TEXT
                        JSR     V2_PRINT
V2_LOAD_NEXT:          JSR     V2_SREC
                        BCC     V2_LOAD_ERROR
                        LDA     V2_REC_TYPE
                        BEQ     V2_LOAD_NEXT
                        CMP     #$09
                        BEQ     V2_LOAD_DONE
                        LDA     V2_ADDR+1
                        CMP     #$02
                        BCC     V2_LOAD_RANGE
                        LDA     V2_COUNT
                        DEC     A
                        CLC
                        ADC     V2_ADDR
                        LDA     V2_ADDR+1
                        ADC     #$00
                        BCS     V2_LOAD_RANGE
                        CMP     #$69
                        BCS     V2_LOAD_RANGE
; Do not poll inside a validated record's copy. Finish it before cancelling.
                        LDA     #$01
                        STA     V2_NMI_HOLD
                        LDY     #$00
V2_LOAD_COPY:          LDA     V2_LINE,Y
                        STA     (V2_ADDR),Y
                        INY
                        CPY     V2_COUNT
                        BNE     V2_LOAD_COPY
                        STZ     V2_NMI_HOLD
                        LDA     #$01
                        STA     V2_LOAD_HAVE_DATA
                        BRA     V2_LOAD_NEXT
V2_LOAD_DONE:          LDA     V2_LOAD_HAVE_DATA
                        BEQ     V2_LOAD_FORMAT
                        LDX     #V2_LOADED_TEXT
                        JSR     V2_PRINT
                        LDA     V2_ADDR+1
                        JSR     V2_HEX_OUT
                        LDA     V2_ADDR
                        JSR     V2_HEX_OUT
                        JMP     V2_PROMPT
V2_LOAD_RANGE:         LDA     #$04
                        BRA     V2_LOAD_ERROR
V2_LOAD_FORMAT:        LDA     #$01
V2_LOAD_ERROR:         PHA
                        JSR     V2_LOAD_DRAIN
                        PLA
                        CMP     #$03
                        BNE     V2_LOAD_NOT_CANCEL
                        JMP     V2_CANCELLED
V2_LOAD_NOT_CANCEL:    CMP     #$04
                        BNE     V2_LOAD_NOT_RANGE
                        JMP     V2_PROTECTED
V2_LOAD_NOT_RANGE:     CMP     #$02
                        BEQ     V2_LOAD_CHECKSUM
                        LDX     #V2_S19_BAD_TEXT
                        JMP     V2_MESSAGE
V2_LOAD_CHECKSUM:      LDX     #V2_S19_SUM_TEXT
                        JMP     V2_MESSAGE

; Discard transfer tail until 8192 consecutive empty hardware polls.
; Host must stop sending before resuming commands. No partial rollback.
V2_LOAD_DRAIN:         JSR     V2_RX_RESET
                        STZ     V2_SKIP_LF
V2_DRAIN_RESTART:      LDY     #$20
                        LDX     #$00
V2_DRAIN_POLL:         JSR     V2_RAW_POLL
                        BCS     V2_DRAIN_RESTART
                        DEX
                        BNE     V2_DRAIN_POLL
                        DEY
                        BNE     V2_DRAIN_POLL
                        RTS

; C=1 complete record; C=0 A=1 format, 2 checksum, 3 Ctrl-C.
V2_SREC:               STZ     V2_REC_SUM
V2_SREC_START:         JSR     V2_SREC_CHAR
                        BCS     V2_SREC_FIRST
                        RTS
V2_SREC_FIRST:
                        CMP     #$0D
                        BEQ     V2_SREC_START
                        CMP     #$0A
                        BEQ     V2_SREC_START
                        AND     #$DF
                        CMP     #'S'
                        BNE     V2_SREC_BAD
                        JSR     V2_SREC_CHAR
                        BCC     V2_SREC_RETURN
                        SEC
                        SBC     #'0'
                        CMP     #$00
                        BEQ     V2_SREC_TYPE_OK
                        CMP     #$01
                        BEQ     V2_SREC_TYPE_OK
                        CMP     #$09
                        BNE     V2_SREC_BAD
V2_SREC_TYPE_OK:       STA     V2_REC_TYPE
                        JSR     V2_SREC_BYTE
                        BCC     V2_SREC_RETURN
                        CMP     #$03
                        BCC     V2_SREC_BAD
                        SBC     #$03
                        STA     V2_COUNT
                        LDA     V2_REC_TYPE
                        BEQ     V2_SREC_ADDRESS
                        CMP     #$09
                        BEQ     V2_SREC_END_COUNT
                        LDA     V2_COUNT
                        BEQ     V2_SREC_BAD
                        BRA     V2_SREC_ADDRESS
V2_SREC_END_COUNT:     LDA     V2_COUNT
                        BNE     V2_SREC_BAD
V2_SREC_ADDRESS:       JSR     V2_SREC_BYTE
                        BCC     V2_SREC_RETURN
                        STA     V2_ADDR+1
                        JSR     V2_SREC_BYTE
                        BCC     V2_SREC_RETURN
                        STA     V2_ADDR
                        LDX     #$00
V2_SREC_DATA:          CPX     V2_COUNT
                        BEQ     V2_SREC_CHECK
                        JSR     V2_SREC_BYTE
                        BCC     V2_SREC_RETURN
                        STA     V2_LINE,X
                        INX
                        BRA     V2_SREC_DATA
V2_SREC_CHECK:         JSR     V2_SREC_BYTE
                        BCC     V2_SREC_RETURN
                        LDA     V2_REC_SUM
                        CMP     #$FF
                        BNE     V2_SREC_SUM_BAD
                        JSR     V2_SREC_CHAR
                        BCC     V2_SREC_RETURN
                        STZ     V2_SKIP_LF
                        CMP     #$0A
                        BEQ     V2_SREC_OK
                        CMP     #$0D
                        BNE     V2_SREC_BAD
                        INC     V2_SKIP_LF
V2_SREC_OK:            SEC
V2_SREC_RETURN:        RTS
V2_SREC_SUM_BAD:       LDA     #$02
                        CLC
                        RTS
V2_SREC_BAD:           LDA     #$01
                        CLC
                        RTS

V2_SREC_CHAR:          JSR     V2_GETC
                        CMP     #$03
                        BEQ     V2_SREC_CHAR_FAIL
                        PHA
                        LDA     V2_RX_BAD
                        BEQ     V2_SREC_CHAR_OK
                        PLA
                        BRA     V2_SREC_BAD
V2_SREC_CHAR_OK:       PLA
                        SEC
                        RTS
V2_SREC_CHAR_FAIL:     CLC
                        RTS
V2_SREC_BYTE:          JSR     V2_SREC_CHAR
                        BCC     V2_SREC_RETURN
                        JSR     V2_HEX_NIBBLE
                        BCC     V2_SREC_BAD
                        ASL     A
                        ASL     A
                        ASL     A
                        ASL     A
                        STA     V2_REC_HEX
                        JSR     V2_SREC_CHAR
                        BCC     V2_SREC_RETURN
                        JSR     V2_HEX_NIBBLE
                        BCC     V2_SREC_BAD
                        ORA     V2_REC_HEX
                        PHA
                        CLC
                        ADC     V2_REC_SUM
                        STA     V2_REC_SUM
                        PLA
                        SEC
                        RTS
