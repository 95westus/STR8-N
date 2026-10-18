; Load-only S0/S1/S9. Each complete, checked S1 commits atomically to
; application RAM $0200-$66FF. Earlier records survive errors/cancellation.
V2_COMMAND_L:          LDX     #$01
                        JSR     V2_SKIP_SPACES
                        BNE str8n_v2_load_LONG_4
                        JMP V2_LOAD_BEGIN
str8n_v2_load_LONG_4:
                        JMP     V2_BAD_HEX
V2_LOAD_BEGIN:         LDX     #V2_S19_TEXT
                        JSR     V2_PRINT
V2_LOAD_NEXT:          JSR     V2_SREC
                        BCS str8n_v2_load_LONG_9
                        JMP V2_LOAD_ERROR
str8n_v2_load_LONG_9:
                        LDA     V2_REC_TYPE
                        BNE str8n_v2_load_LONG_11
                        JMP V2_LOAD_NEXT
str8n_v2_load_LONG_11:
                        CMP     #$09
                        BNE str8n_v2_load_LONG_13
                        JMP V2_LOAD_DONE
str8n_v2_load_LONG_13:
                        LDA     V2_ADDR+1
                        CMP     #$02
                        BCS str8n_v2_load_LONG_16
                        JMP V2_LOAD_RANGE
str8n_v2_load_LONG_16:
                        JSR     V2_RECORD_END
                        BCC str8n_v2_load_LONG_18
                        JMP V2_LOAD_RANGE
str8n_v2_load_LONG_18:
                        CMP     #$67
                        BCC str8n_v2_load_LONG_20
                        JMP V2_LOAD_RANGE
str8n_v2_load_LONG_20:
                        CMP     #$65
                        BCS str8n_v2_load_LONG_22
                        JMP SVC_LOAD_OK
str8n_v2_load_LONG_22:
                        BIT SVC_ACTIVE
                        BEQ str8n_v2_load_LONG_24
                        JMP V2_LOAD_RANGE
str8n_v2_load_LONG_24:
SVC_LOAD_OK:
                        LDX     #$00
                        JSR     V2_COPY_BYTES
                        JMP V2_LOAD_NEXT
V2_LOAD_DONE:          LDX     #V2_LOADED_TEXT
                        JSR     V2_PRINT
                        JSR     V2_PRINT_ADDR
                        JMP     V2_PROMPT
V2_LOAD_RANGE:         LDA     #$04
V2_LOAD_ERROR:         PHA
                        JSR     V2_LOAD_DRAIN
                        PLA
                        CMP     #$03
                        BEQ str8n_v2_load_LONG_38
                        JMP V2_LOAD_NOT_CANCEL
str8n_v2_load_LONG_38:
                        JMP     V2_CANCELLED
V2_LOAD_NOT_CANCEL:    TAY
                        LDX     V2_LOAD_ERROR_TEXTS-1,Y
                        JMP     V2_MESSAGE

; Discard transfer tail until 8192 consecutive empty hardware polls.
; Host must stop sending before resuming commands. No partial rollback.
V2_LOAD_DRAIN:         JSR     V2_RX_RESET
                        STZ     V2_SKIP_LF
V2_DRAIN_RESTART:      LDY     #$20
                        LDX     #$00
V2_DRAIN_POLL:         JSR     V2_RAW_POLL
                        BCC str8n_v2_load_LONG_51
                        JMP V2_DRAIN_RESTART
str8n_v2_load_LONG_51:
                        DEX
                        BEQ str8n_v2_load_LONG_53
                        JMP V2_DRAIN_POLL
str8n_v2_load_LONG_53:
                        DEY
                        BEQ str8n_v2_load_LONG_55
                        JMP V2_DRAIN_POLL
str8n_v2_load_LONG_55:
                        RTS

; Inclusive record end high byte in A; carry set on 16-bit wrap. COUNT > 0.
V2_RECORD_END:         LDA     V2_COUNT
                        DEC     A
                        CLC
                        ADC     V2_ADDR
                        LDA     V2_ADDR+1
                        ADC     #$00
                        RTS

; C=1 complete record; C=0 A=1 format, 2 checksum, 3 Ctrl-C.
V2_SREC:               STZ     V2_REC_SUM
V2_SREC_START:         JSR     V2_SREC_CHAR
                        BCC str8n_v2_load_LONG_70
                        JMP V2_SREC_FIRST
str8n_v2_load_LONG_70:
                        RTS
V2_SREC_FIRST:
                        CMP     #$0D
                        BNE str8n_v2_load_LONG_74
                        JMP V2_SREC_START
str8n_v2_load_LONG_74:
                        CMP     #$0A
                        BNE str8n_v2_load_LONG_76
                        JMP V2_SREC_START
str8n_v2_load_LONG_76:
                        AND     #$DF
                        CMP     #'S'
                        BEQ str8n_v2_load_LONG_79
                        JMP V2_SREC_BAD
str8n_v2_load_LONG_79:
                        JSR     V2_SREC_CHAR
                        BCS str8n_v2_load_LONG_81
                        JMP V2_SREC_RETURN
str8n_v2_load_LONG_81:
; SREC_CHAR returns carry set on success. Accept types 0/1 together.
                        SBC     #'0'
                        CMP     #$02
                        BCS str8n_v2_load_LONG_85
                        JMP V2_SREC_TYPE_OK
str8n_v2_load_LONG_85:
                        CMP     #$09
                        BEQ str8n_v2_load_LONG_87
                        JMP V2_SREC_BAD
str8n_v2_load_LONG_87:
V2_SREC_TYPE_OK:       STA     V2_REC_TYPE
                        JSR     V2_SREC_BYTE
                        BCS str8n_v2_load_LONG_90
                        JMP V2_SREC_RETURN
str8n_v2_load_LONG_90:
                        CMP     #$03
                        BCS str8n_v2_load_LONG_92
                        JMP V2_SREC_BAD
str8n_v2_load_LONG_92:
                        SBC     #$03
                        STA     V2_COUNT
                        LDA     V2_REC_TYPE
                        BNE str8n_v2_load_LONG_96
                        JMP V2_SREC_ADDRESS
str8n_v2_load_LONG_96:
                        CMP     #$09
                        BNE str8n_v2_load_LONG_98
                        JMP V2_SREC_END_COUNT
str8n_v2_load_LONG_98:
                        LDA     V2_COUNT
                        BNE str8n_v2_load_LONG_100
                        JMP V2_SREC_BAD
str8n_v2_load_LONG_100:
                        JMP V2_SREC_ADDRESS
V2_SREC_END_COUNT:     LDA     V2_COUNT
                        BEQ str8n_v2_load_LONG_103
                        JMP V2_SREC_BAD
str8n_v2_load_LONG_103:
V2_SREC_ADDRESS:       JSR     V2_SREC_BYTE
                        BCS str8n_v2_load_LONG_105
                        JMP V2_SREC_RETURN
str8n_v2_load_LONG_105:
                        STA     V2_ADDR+1
                        JSR     V2_SREC_BYTE
                        BCS str8n_v2_load_LONG_108
                        JMP V2_SREC_RETURN
str8n_v2_load_LONG_108:
                        STA     V2_ADDR
                        LDX     #$00
V2_SREC_DATA:          CPX     V2_COUNT
                        BNE str8n_v2_load_LONG_112
                        JMP V2_SREC_CHECK
str8n_v2_load_LONG_112:
                        JSR     V2_SREC_BYTE
                        BCS str8n_v2_load_LONG_114
                        JMP V2_SREC_RETURN
str8n_v2_load_LONG_114:
                        STA     V2_LINE,X
                        INX
                        JMP V2_SREC_DATA
V2_SREC_CHECK:         JSR     V2_SREC_BYTE
                        BCS str8n_v2_load_LONG_119
                        JMP V2_SREC_RETURN
str8n_v2_load_LONG_119:
                        LDA     V2_REC_SUM
                        CMP     #$FF
                        BEQ str8n_v2_load_LONG_122
                        JMP V2_SREC_SUM_BAD
str8n_v2_load_LONG_122:
                        JSR     V2_SREC_CHAR
                        BCS str8n_v2_load_LONG_124
                        JMP V2_SREC_RETURN
str8n_v2_load_LONG_124:
                        STZ     V2_SKIP_LF
                        CMP     #$0A
                        BNE str8n_v2_load_LONG_127
                        JMP V2_SREC_OK
str8n_v2_load_LONG_127:
                        CMP     #$0D
                        BEQ str8n_v2_load_LONG_129
                        JMP V2_SREC_BAD
str8n_v2_load_LONG_129:
                        INC     V2_SKIP_LF
; Either matching delimiter comparison already set carry; INC preserves it.
V2_SREC_OK:             LDA     V2_LED
                        EOR     #V2_LED_RX
                        STA     V2_LED
V2_SREC_RETURN:        RTS
V2_SREC_SUM_BAD:       LDA     #$02
                        CLC
                        RTS
V2_SREC_BAD:           LDA     #$01
                        CLC
                        RTS

V2_SREC_CHAR:          JSR     V2_GETC
                        CMP     #$03
                        BNE str8n_v2_load_LONG_145
                        JMP V2_SREC_CHAR_FAIL
str8n_v2_load_LONG_145:
; A receive error immediately aborts the record; drain resets all RX state.
                        LSR     V2_RX_BAD
                        BCC str8n_v2_load_LONG_148
                        JMP V2_SREC_BAD
str8n_v2_load_LONG_148:
V2_SREC_CHAR_OK:       SEC
                        RTS
V2_SREC_CHAR_FAIL:     CLC
                        RTS
V2_SREC_BYTE:          JSR     V2_SREC_CHAR
                        BCS str8n_v2_load_LONG_154
                        JMP V2_SREC_RETURN
str8n_v2_load_LONG_154:
                        JSR     V2_HEX_NIBBLE
                        BCS str8n_v2_load_LONG_156
                        JMP V2_SREC_BAD
str8n_v2_load_LONG_156:
                        ASL     A
                        ASL     A
                        ASL     A
                        ASL     A
                        STA     V2_REC_HEX
                        JSR     V2_SREC_CHAR
                        BCS str8n_v2_load_LONG_163
                        JMP V2_SREC_RETURN
str8n_v2_load_LONG_163:
                        JSR     V2_HEX_NIBBLE
                        BCS str8n_v2_load_LONG_165
                        JMP V2_SREC_BAD
str8n_v2_load_LONG_165:
                        ORA     V2_REC_HEX
                        PHA
                        CLC
                        ADC     V2_REC_SUM
                        STA     V2_REC_SUM
                        PLA
                        SEC
                        RTS
