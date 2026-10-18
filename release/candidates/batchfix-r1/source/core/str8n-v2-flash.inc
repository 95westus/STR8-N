; F preflights one sector, snapshots it, prints old/new bytes, then confirms.
V2_COMMAND_F:          JSR     V2_GET_ADDRESS
                        BCC str8n_v2_flash_LONG_2
                        JMP V2_F_ADDRESS
str8n_v2_flash_LONG_2:
V2_F_HEX:              JMP     V2_BAD_HEX
V2_F_ADDRESS:          LDA     V2_ADDR+1
                        BPL str8n_v2_flash_LONG_5
                        JMP V2_F_BEGIN
str8n_v2_flash_LONG_5:
V2_F_PROTECTED:        JMP     V2_PROTECTED
V2_F_BEGIN:            AND #$F0
                        STA V2_SECTOR
                        LDA V2_SELECTED
                        CMP #$03
                        BEQ str8n_v2_flash_LONG_11
                        JMP V2_F_UNPROTECTED_E
str8n_v2_flash_LONG_11:
                        LDA V2_SECTOR
                        CMP #$80
                        BCC str8n_v2_flash_LONG_14
                        JMP V2_F_PROTECTED
str8n_v2_flash_LONG_14:
V2_F_UNPROTECTED_E:
; A flash sector base is already nonzero, which marks the F preflight.
                        LDA     V2_SECTOR
                        STA     V2_EDIT_FLASH
                        JMP     V2_EDIT_BEGIN
V2_F_CROSS:            LDX     #V2_CROSS_TEXT
                        JMP     V2_MESSAGE
V2_F_SNAPSHOT:         JSR     V2W_SNAPSHOT
                        JSR     V2_FLASH_BANK
                        STZ     V2_SELF
                        LDA     V2_SECTOR
                        CMP     #$F0
                        BEQ str8n_v2_flash_LONG_27
                        JMP V2_F_PREVIEW
str8n_v2_flash_LONG_27:
                        LDA     V2_SELECTED
                        CMP     V2_RESIDENT
                        BEQ str8n_v2_flash_LONG_30
                        JMP V2_F_RECOVERY
str8n_v2_flash_LONG_30:
                        INC     V2_SELF
                        LDX     #V2_SELF_TEXT
                        JSR     V2_PRINT
V2_F_RECOVERY:         LDA     V2_SELECTED
                        CMP     #$03
                        BEQ str8n_v2_flash_LONG_36
                        JMP V2_F_PREVIEW
str8n_v2_flash_LONG_36:
                        LDX     #V2_RECOVERY_TEXT
                        JSR     V2_PRINT
V2_F_PREVIEW:          LDA     V2_VECTOR
                        STA     V2_ADDR
                        STA     V2_BUF_PTR
                        LDA     V2_VECTOR+1
                        STA     V2_ADDR+1
                        AND     #$0F
                        CLC
                        ADC     #$68
                        STA     V2_BUF_PTR+1
                        LDX     #$00
V2_F_PREVIEW_BYTE:     JSR     V2_PRINT_ADDR
                        LDA     #' '
                        JSR     V2_PUTC
                        LDA     (V2_BUF_PTR)
                        JSR     V2_HEX_OUT
                        LDA     #'>'
                        JSR     V2_PUTC
                        LDA     V2_BYTES,X
                        STA     (V2_BUF_PTR)
                        JSR     V2_HEX_OUT
                        JSR     V2_NEWLINE
                        INC     V2_ADDR
                        INC     V2_BUF_PTR
                        BEQ str8n_v2_flash_LONG_62
                        JMP V2_F_PREVIEW_NEXT
str8n_v2_flash_LONG_62:
                        INC     V2_ADDR+1
                        INC     V2_BUF_PTR+1
V2_F_PREVIEW_NEXT:     INX
                        CPX     V2_COUNT
                        BEQ str8n_v2_flash_LONG_67
                        JMP V2_F_PREVIEW_BYTE
str8n_v2_flash_LONG_67:
                        JSR     V2W_ANALYZE
                        JSR     V2_FLASH_MODE
                        JSR     V2_CONFIRM
                        BCS str8n_v2_flash_LONG_71
                        JMP V2_F_CANCEL
str8n_v2_flash_LONG_71:
                        JSR     V2_F_RISK_CONFIRM
                        BCC str8n_v2_flash_LONG_73
                        JMP V2_F_COMMIT
str8n_v2_flash_LONG_73:
V2_F_CANCEL:
                        JMP     V2_CANCELLED
V2_F_COMMIT:           JSR     V2W_MUTATE
                        BCC str8n_v2_flash_LONG_77
                        JMP V2_FLASH_FAILED
str8n_v2_flash_LONG_77:
V2_FLASH_COMPLETE:
                        JSR     V2_CHECK_CANCEL
                        BCS str8n_v2_flash_LONG_80
                        JMP V2_FLASH_DONE
str8n_v2_flash_LONG_80:
                        JMP     V2_CANCELLED
V2_FLASH_DONE:         LDX     #V2_DONE_TEXT
                        JMP     V2_MESSAGE
V2_FLASH_FAILED:       LDX     #V2_VERIFY_TEXT
                        LDA     V2_FLASH_ERROR
                        DEC     A
                        BEQ str8n_v2_flash_LONG_87
                        JMP V2_FLASH_MESSAGE
str8n_v2_flash_LONG_87:
                        LDX     #V2_TIMEOUT_TEXT
V2_FLASH_MESSAGE:      JMP     V2_MESSAGE

V2_FLASH_BANK:         LDA     #'B'
                        JSR     V2_PUTC
                        LDA     V2_SELECTED
                        ORA     #'0'
                        JSR     V2_PUTC
                        JMP     V2_NEWLINE
V2_PRINT_ADDR:         LDA     V2_ADDR+1
                        JSR     V2_HEX_OUT
                        LDA     V2_ADDR
                        JMP     V2_HEX_OUT
V2_CONFIRM:            LDX     #V2_CONFIRM_TEXT
                        JSR     V2_PRINT
                        JSR     V2_READ_LINE
                        BCS str8n_v2_flash_LONG_104
                        JMP V2_CONFIRM_NO
str8n_v2_flash_LONG_104:
                        LDA     V2_LINE
                        CMP     #'Y'
                        BEQ str8n_v2_flash_LONG_107
                        JMP V2_CONFIRM_NO
str8n_v2_flash_LONG_107:
                        LDA     V2_LINE+1
                        BEQ str8n_v2_flash_LONG_109
                        JMP V2_CONFIRM_NO
str8n_v2_flash_LONG_109:
                        JSR     V2_CHECK_CANCEL
                        BCC str8n_v2_flash_LONG_111
                        JMP V2_CONFIRM_NO
str8n_v2_flash_LONG_111:
                        SEC
                        RTS
V2_CONFIRM_NO:         CLC
                        RTS

; Sector F in any bank can destroy that bank's boot path. Any Bank 3 edit can
; damage the board's recovery/application image. After the ordinary Y, require
; the operator to type the exact selected bank (for example B3).
V2_F_RISK_CONFIRM:     LDA     V2_SECTOR
                        CMP     #$F0
                        BNE str8n_v2_flash_LONG_122
                        JMP V2_F_RISK
str8n_v2_flash_LONG_122:
                        LDA     V2_SELECTED
                        CMP     #$03
                        BEQ str8n_v2_flash_LONG_125
                        JMP V2_F_RISK_OK
str8n_v2_flash_LONG_125:
V2_F_RISK:             LDX     #V2_RISK_TEXT
                        JSR     V2_PRINT
                        JSR     V2_BANK_READ_LINE
                        BCS str8n_v2_flash_LONG_129
                        JMP V2_F_RISK_NO
str8n_v2_flash_LONG_129:
                        LDA     V2_LINE
                        CMP     #'B'
                        BEQ str8n_v2_flash_LONG_132
                        JMP V2_F_RISK_NO
str8n_v2_flash_LONG_132:
                        LDA     V2_LINE+1
                        SEC
                        SBC     #'0'
                        CMP     V2_SELECTED
                        BEQ str8n_v2_flash_LONG_137
                        JMP V2_F_RISK_NO
str8n_v2_flash_LONG_137:
                        LDA     V2_LINE+2
                        BEQ str8n_v2_flash_LONG_139
                        JMP V2_F_RISK_NO
str8n_v2_flash_LONG_139:
V2_F_RISK_OK:          SEC
                        RTS
V2_F_RISK_NO:          CLC
                        RTS

; I start end: complete aligned sectors, dense ascending S1 stream. S9 ends.
; Validate a whole record before staging any bytes. Commit only full sectors.
V2_COMMAND_I:          JSR     V2_GET_ADDRESS
                        BCS str8n_v2_flash_LONG_148
                        JMP V2_I_HEX
str8n_v2_flash_LONG_148:
                        JSR     V2_HEX_WORD
                        BCS str8n_v2_flash_LONG_150
                        JMP V2_I_HEX
str8n_v2_flash_LONG_150:
                        JSR     V2_SKIP_SPACES
                        BEQ str8n_v2_flash_LONG_152
                        JMP V2_I_HEX
str8n_v2_flash_LONG_152:
                        LDA     V2_ADDR
                        BEQ str8n_v2_flash_LONG_154
                        JMP V2_I_RANGE
str8n_v2_flash_LONG_154:
                        LDA     V2_ADDR+1
                        BMI str8n_v2_flash_LONG_156
                        JMP V2_I_RANGE
str8n_v2_flash_LONG_156:
                        AND     #$0F
                        BEQ str8n_v2_flash_LONG_158
                        JMP V2_I_RANGE
str8n_v2_flash_LONG_158:
                        LDA     V2_VALUE
                        INC     A
                        BEQ str8n_v2_flash_LONG_161
                        JMP V2_I_RANGE
str8n_v2_flash_LONG_161:
                        LDA     V2_VALUE+1
                        INC     A
                        AND     #$0F
                        BEQ str8n_v2_flash_LONG_165
                        JMP V2_I_RANGE
str8n_v2_flash_LONG_165:
                        LDA     V2_VALUE+1
                        CMP     V2_ADDR+1
                        BCS str8n_v2_flash_LONG_168
                        JMP V2_I_RANGE
str8n_v2_flash_LONG_168:
                        LDA     V2_SELECTED
                        CMP     #$03
                        BEQ str8n_v2_flash_LONG_171
                        JMP V2_I_CHECK_F
str8n_v2_flash_LONG_171:
                        LDA     V2_VALUE+1
                        CMP     #$80
                        BCC str8n_v2_flash_LONG_174
                        JMP V2_I_PROTECTED
str8n_v2_flash_LONG_174:
V2_I_CHECK_F:
                        LDA     V2_VALUE+1
                        INC     A
                        BEQ str8n_v2_flash_LONG_178
                        JMP V2_I_ALLOWED
str8n_v2_flash_LONG_178:
                        LDA     V2_SELECTED
                        CMP     #$03
                        BNE str8n_v2_flash_LONG_181
                        JMP V2_I_PROTECTED
str8n_v2_flash_LONG_181:
                        CMP     V2_RESIDENT
                        BNE str8n_v2_flash_LONG_183
                        JMP V2_I_PROTECTED
str8n_v2_flash_LONG_183:
V2_I_ALLOWED:          LDA     V2_ADDR+1
                        STA     V2_SECTOR
                        STA     V2_INSTALL_NEXT+1
                        STZ     V2_INSTALL_NEXT
; INSTALL_END aliases the parsed VALUE high byte and survives confirmation.
                        JSR     V2_FLASH_BANK
                        JSR     V2_PRINT_ADDR
                        LDA     #'-'
                        JSR     V2_PUTC
                        LDA     V2_INSTALL_END
                        JSR     V2_HEX_OUT
                        LDA     #$FF
                        JSR     V2_HEX_OUT
                        LDX     #V2_INSTALL_TEXT
                        JSR     V2_PRINT
                        JSR     V2_CONFIRM
                        BCC str8n_v2_flash_LONG_200
                        JMP V2_I_BEGIN
str8n_v2_flash_LONG_200:
                        JMP     V2_CANCELLED
V2_I_HEX:              JMP     V2_BAD_HEX
V2_I_RANGE:            JMP     V2_BAD_RANGE
V2_I_PROTECTED:        JMP     V2_PROTECTED
V2_I_BEGIN:            STZ     V2_SELF
                        STZ     V2_INSTALL_DONE
                        JSR     V2_I_BUFFER
                        LDX     #V2_S19_TEXT
                        JSR     V2_PRINT
V2_I_RECORD:           JSR     V2_SREC
                        BCC str8n_v2_flash_LONG_211
                        JMP V2_I_TYPE
str8n_v2_flash_LONG_211:
V2_I_ERROR:            JMP     V2_LOAD_ERROR
V2_I_FORMAT:           LDA     #$01
                        JMP V2_I_ERROR
V2_I_TYPE:             LDA     V2_REC_TYPE
                        BNE str8n_v2_flash_LONG_216
                        JMP V2_I_RECORD
str8n_v2_flash_LONG_216:
                        CMP     #$09
                        BEQ str8n_v2_flash_LONG_218
                        JMP V2_I_DATA
str8n_v2_flash_LONG_218:
                        LDA     V2_INSTALL_DONE
                        BNE str8n_v2_flash_LONG_220
                        JMP V2_I_FORMAT
str8n_v2_flash_LONG_220:
                        JMP     V2_FLASH_DONE
V2_I_DATA:             LDA     V2_INSTALL_DONE
                        BEQ str8n_v2_flash_LONG_223
                        JMP V2_I_FORMAT
str8n_v2_flash_LONG_223:
                        LDA     V2_ADDR
                        CMP     V2_INSTALL_NEXT
                        BEQ str8n_v2_flash_LONG_226
                        JMP V2_I_FORMAT
str8n_v2_flash_LONG_226:
                        LDA     V2_ADDR+1
                        CMP     V2_INSTALL_NEXT+1
                        BEQ str8n_v2_flash_LONG_229
                        JMP V2_I_FORMAT
str8n_v2_flash_LONG_229:
                        JSR     V2_RECORD_END
                        BCC str8n_v2_flash_LONG_231
                        JMP V2_I_FORMAT
str8n_v2_flash_LONG_231:
                        CMP     V2_INSTALL_END
                        BCS str8n_v2_flash_LONG_233
                        JMP V2_I_STAGE
str8n_v2_flash_LONG_233:
                        BEQ str8n_v2_flash_LONG_234
                        JMP V2_I_FORMAT
str8n_v2_flash_LONG_234:
V2_I_STAGE:            LDY     #$00
V2_I_BYTE:
V2_I_STORE:            LDA     V2_LINE,Y
                        STA     (V2_BUF_PTR)
V2_I_ADVANCE:          INC     V2_INSTALL_NEXT
                        BEQ str8n_v2_flash_LONG_240
                        JMP V2_I_BUF_NEXT
str8n_v2_flash_LONG_240:
                        INC     V2_INSTALL_NEXT+1
V2_I_BUF_NEXT:         INC     V2_BUF_PTR
                        BEQ str8n_v2_flash_LONG_243
                        JMP V2_I_NEXT_BYTE
str8n_v2_flash_LONG_243:
                        INC     V2_BUF_PTR+1
                        LDA     V2_BUF_PTR+1
                        CMP     #$78
                        BEQ str8n_v2_flash_LONG_247
                        JMP V2_I_NEXT_BYTE
str8n_v2_flash_LONG_247:
; Once mutation starts, no cancellation until the full sector is verified.
                        PHY
                        JSR     V2_I_CANCEL_POLL
                        BCS str8n_v2_flash_LONG_251
                        JMP V2_I_MUTATE
str8n_v2_flash_LONG_251:
                        PLY
                        LDA     #$03
                        JMP     V2_LOAD_ERROR
V2_I_MUTATE:
                        JSR     V2W_ANALYZE
                        JSR     V2W_MUTATE
                        PLY
                        BCS str8n_v2_flash_LONG_259
                        JMP V2_I_COMMITTED
str8n_v2_flash_LONG_259:
                        JSR     V2_LOAD_DRAIN
                        JMP     V2_FLASH_FAILED
V2_I_COMMITTED:        PHY
                        JSR     V2_I_CANCEL_POLL
                        PLY
                        BCS str8n_v2_flash_LONG_265
                        JMP V2_I_CONTINUE
str8n_v2_flash_LONG_265:
                        LDA     #$03
                        JMP     V2_LOAD_ERROR
V2_I_CONTINUE:         LDA     V2_SECTOR
                        ORA     #$0F
                        CMP     V2_INSTALL_END
                        BNE str8n_v2_flash_LONG_271
                        JMP V2_I_COMPLETE
str8n_v2_flash_LONG_271:
; A nonfinal sector is below the checked end, so CMP left carry clear.
                        LDA     V2_SECTOR
                        ADC     #$10
                        STA     V2_SECTOR
                        PHY
                        JSR     V2_I_BUFFER
                        PLY
                        JMP V2_I_NEXT_BYTE
V2_I_COMPLETE:         INC     V2_INSTALL_DONE
V2_I_NEXT_BYTE:        INY
                        CPY     V2_COUNT
                        BEQ str8n_v2_flash_LONG_283
                        JMP V2_I_BYTE
str8n_v2_flash_LONG_283:
                        JMP     V2_I_RECORD
V2_I_BUFFER:           JSR     V2W_SNAPSHOT
                        STZ     V2_BUF_PTR
                        LDA     #$68
                        STA     V2_BUF_PTR+1
                        RTS

; Keep pending S19 typeahead intact while a complete sector is committed.
V2_I_CANCEL_POLL:      LDA     V2_RX_COUNT
                        BEQ str8n_v2_flash_LONG_293
                        JMP V2_I_CANCEL_PENDING
str8n_v2_flash_LONG_293:
                        JMP     V2_CHECK_CANCEL
V2_I_CANCEL_PENDING:   LDA     V2_CANCEL_REQUEST
                        LSR     A
                        RTS

V2_FLASH_MODE:
                        LDX     #V2_PROGRAM_TEXT
                        LDA     V2_ERASE
                        BNE str8n_v2_flash_LONG_302
                        JMP V2_MODE_PRINT
str8n_v2_flash_LONG_302:
                        LDX     #V2_ERASE_TEXT
V2_MODE_PRINT:         JMP     V2_PRINT
