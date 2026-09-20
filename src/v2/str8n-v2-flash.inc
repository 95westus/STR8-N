; F preflights one sector, snapshots it, prints old/new bytes, then confirms.
V2_COMMAND_F:          JSR     V2_GET_ADDRESS
                        BCS     V2_F_ADDRESS
V2_F_HEX:              JMP     V2_BAD_HEX
V2_F_ADDRESS:          LDA     V2_ADDR+1
                        BMI     V2_F_BEGIN
V2_F_PROTECTED:        JMP     V2_PROTECTED
V2_F_BEGIN:            AND     #$F0
                        STA     V2_SECTOR
; A flash sector base is already nonzero, which marks the F preflight.
                        STA     V2_EDIT_FLASH
                        JMP     V2_EDIT_BEGIN
V2_F_CROSS:            LDX     #V2_CROSS_TEXT
                        JMP     V2_MESSAGE
V2_F_SNAPSHOT:         JSR     V2W_SNAPSHOT
                        JSR     V2_FLASH_BANK
                        STZ     V2_SELF
                        LDA     V2_SECTOR
                        CMP     #$F0
                        BNE     V2_F_PREVIEW
                        LDA     V2_SELECTED
                        CMP     V2_RESIDENT
                        BNE     V2_F_RECOVERY
                        INC     V2_SELF
                        LDX     #V2_SELF_TEXT
                        JSR     V2_PRINT
V2_F_RECOVERY:         LDA     V2_SELECTED
                        CMP     #$03
                        BNE     V2_F_PREVIEW
                        LDX     #V2_RECOVERY_TEXT
                        JSR     V2_PRINT
V2_F_PREVIEW:          LDA     V2_VECTOR
                        STA     V2_ADDR
                        STA     V2_BUF_PTR
                        LDA     V2_VECTOR+1
                        STA     V2_ADDR+1
                        AND     #$0F
                        CLC
                        ADC     #$69
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
                        BNE     V2_F_PREVIEW_NEXT
                        INC     V2_ADDR+1
                        INC     V2_BUF_PTR+1
V2_F_PREVIEW_NEXT:     INX
                        CPX     V2_COUNT
                        BNE     V2_F_PREVIEW_BYTE
                        JSR     V2W_ANALYZE
                        JSR     V2_FLASH_MODE
                        JSR     V2_CONFIRM
                        BCS     V2_F_COMMIT
                        JMP     V2_CANCELLED
V2_F_COMMIT:           JSR     V2W_MUTATE
                        BCS     V2_FLASH_FAILED
V2_FLASH_COMPLETE:
                        JSR     V2_CHECK_CANCEL
                        BCC     V2_FLASH_DONE
                        JMP     V2_CANCELLED
V2_FLASH_DONE:         LDX     #V2_DONE_TEXT
                        JMP     V2_MESSAGE
V2_FLASH_FAILED:       LDX     #V2_VERIFY_TEXT
                        LDA     V2_FLASH_ERROR
                        DEC     A
                        BNE     V2_FLASH_MESSAGE
                        LDX     #V2_TIMEOUT_TEXT
V2_FLASH_MESSAGE:      JMP     V2_MESSAGE

V2_FLASH_BANK:         LDA     #'B'
                        JSR     V2_PUTC
                        LDA     V2_SELECTED
                        ORA     #'0'
                        JSR     V2_PUTC
                        BRA     V2_NEWLINE
V2_PRINT_ADDR:         LDA     V2_ADDR+1
                        JSR     V2_HEX_OUT
                        LDA     V2_ADDR
                        JMP     V2_HEX_OUT
V2_NEWLINE:            LDA     #$0D
                        JSR     V2_PUTC
                        LDA     #$0A
                        JMP     V2_PUTC
V2_CONFIRM:            LDX     #V2_CONFIRM_TEXT
                        JSR     V2_PRINT
                        JSR     V2_READ_LINE
                        BCC     V2_CONFIRM_NO
                        LDA     V2_LINE
                        CMP     #'Y'
                        BNE     V2_CONFIRM_NO
                        LDA     V2_LINE+1
                        BNE     V2_CONFIRM_NO
                        JSR     V2_CHECK_CANCEL
                        BCS     V2_CONFIRM_NO
                        SEC
                        RTS
V2_CONFIRM_NO:         CLC
                        RTS

; I start end: complete aligned sectors, dense ascending S1 stream. S9 ends.
; Validate a whole record before staging any bytes. Commit only full sectors.
V2_COMMAND_I:          JSR     V2_GET_ADDRESS
                        BCC     V2_I_HEX
                        JSR     V2_HEX_WORD
                        BCC     V2_I_HEX
                        JSR     V2_SKIP_SPACES
                        BNE     V2_I_HEX
                        LDA     V2_ADDR
                        BNE     V2_I_RANGE
                        LDA     V2_ADDR+1
                        BPL     V2_I_RANGE
                        AND     #$0F
                        BNE     V2_I_RANGE
                        LDA     V2_VALUE
                        INC     A
                        BNE     V2_I_RANGE
                        LDA     V2_VALUE+1
                        INC     A
                        AND     #$0F
                        BNE     V2_I_RANGE
                        LDA     V2_VALUE+1
                        CMP     V2_ADDR+1
                        BCC     V2_I_RANGE
                        INC     A
                        BNE     V2_I_ALLOWED
                        LDA     V2_SELECTED
                        CMP     #$03
                        BEQ     V2_I_PROTECTED
                        CMP     V2_RESIDENT
                        BEQ     V2_I_PROTECTED
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
                        BCS     V2_I_BEGIN
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
                        BCS     V2_I_TYPE
V2_I_ERROR:            JMP     V2_LOAD_ERROR
V2_I_FORMAT:           LDA     #$01
                        BRA     V2_I_ERROR
V2_I_TYPE:             LDA     V2_REC_TYPE
                        BEQ     V2_I_RECORD
                        CMP     #$09
                        BNE     V2_I_DATA
                        LDA     V2_INSTALL_DONE
                        BEQ     V2_I_FORMAT
                        JMP     V2_FLASH_DONE
V2_I_DATA:             LDA     V2_INSTALL_DONE
                        BNE     V2_I_FORMAT
                        LDA     V2_ADDR
                        CMP     V2_INSTALL_NEXT
                        BNE     V2_I_FORMAT
                        LDA     V2_ADDR+1
                        CMP     V2_INSTALL_NEXT+1
                        BNE     V2_I_FORMAT
                        JSR     V2_RECORD_END
                        BCS     V2_I_FORMAT
                        CMP     V2_INSTALL_END
                        BCC     V2_I_STAGE
                        BNE     V2_I_FORMAT
V2_I_STAGE:            LDY     #$00
V2_I_BYTE:             LDA     V2_INSTALL_NEXT+1
                        CMP     #$EF
                        BNE     V2_I_STORE
                        LDA     V2_INSTALL_NEXT
                        CMP     #$F0
                        BCC     V2_I_STORE
                        LDA     V2_SELECTED
                        CMP     V2_RESIDENT
                        BEQ     V2_I_ADVANCE
V2_I_STORE:            LDA     V2_LINE,Y
                        STA     (V2_BUF_PTR)
V2_I_ADVANCE:          INC     V2_INSTALL_NEXT
                        BNE     V2_I_BUF_NEXT
                        INC     V2_INSTALL_NEXT+1
V2_I_BUF_NEXT:         INC     V2_BUF_PTR
                        BNE     V2_I_NEXT_BYTE
                        INC     V2_BUF_PTR+1
                        LDA     V2_BUF_PTR+1
                        CMP     #$79
                        BNE     V2_I_NEXT_BYTE
; Once mutation starts, no cancellation until the full sector is verified.
                        PHY
                        JSR     V2_I_CANCEL_POLL
                        BCC     V2_I_MUTATE
                        PLY
                        LDA     #$03
                        JMP     V2_LOAD_ERROR
V2_I_MUTATE:
                        JSR     V2W_ANALYZE
                        JSR     V2W_MUTATE
                        PLY
                        BCC     V2_I_COMMITTED
                        JSR     V2_LOAD_DRAIN
                        JMP     V2_FLASH_FAILED
V2_I_COMMITTED:        PHY
                        JSR     V2_I_CANCEL_POLL
                        PLY
                        BCC     V2_I_CONTINUE
                        LDA     #$03
                        JMP     V2_LOAD_ERROR
V2_I_CONTINUE:         LDA     V2_SECTOR
                        ORA     #$0F
                        CMP     V2_INSTALL_END
                        BEQ     V2_I_COMPLETE
; A nonfinal sector is below the checked end, so CMP left carry clear.
                        LDA     V2_SECTOR
                        ADC     #$10
                        STA     V2_SECTOR
                        PHY
                        JSR     V2_I_BUFFER
                        PLY
                        BRA     V2_I_NEXT_BYTE
V2_I_COMPLETE:         INC     V2_INSTALL_DONE
V2_I_NEXT_BYTE:        INY
                        CPY     V2_COUNT
                        BNE     V2_I_BYTE
                        JMP     V2_I_RECORD
V2_I_BUFFER:           JSR     V2W_SNAPSHOT
                        STZ     V2_BUF_PTR
                        LDA     #$69
                        STA     V2_BUF_PTR+1
                        RTS

; Keep pending S19 typeahead intact while a complete sector is committed.
V2_I_CANCEL_POLL:      LDA     V2_RX_COUNT
                        BNE     V2_I_CANCEL_PENDING
                        JMP     V2_CHECK_CANCEL
V2_I_CANCEL_PENDING:   LDA     V2_CANCEL_REQUEST
                        LSR     A
                        RTS

V2_FLASH_MODE:
                        LDX     #V2_PROGRAM_TEXT
                        LDA     V2_ERASE
                        BEQ     V2_MODE_PRINT
                        LDX     #V2_ERASE_TEXT
V2_MODE_PRINT:         JMP     V2_PRINT
