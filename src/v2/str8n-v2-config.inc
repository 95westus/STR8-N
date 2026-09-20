; C [enable bank address delay]. All fields hex; delay $0A-$FF tenths.
; Config belongs to the resident bank, independent of selected target bank.
V2_COMMAND_C:          LDX     #$01
                        JSR     V2_SKIP_SPACES
                        BNE     V2_C_SET
                        JSR     V2_CONFIG_READ
                        BCS     V2_C_SHOW
                        LDX     #V2_NO_CONFIG_TEXT
                        JMP     V2_MESSAGE
V2_C_SHOW:             JSR     V2_CONFIG_SHOW
                        JMP     V2_PROMPT
V2_C_SET:              LDX     #$0F
V2_C_CLEAR:            STZ     V2_CONFIG,X
                        DEX
                        BPL     V2_C_CLEAR
                        INC     V2_CONFIG
                        LDX     #$01
                        JSR     V2_HEX_BYTE
                        BCC     V2_C_HEX
                        LDA     V2_VALUE
                        STA     V2_CONFIG+1
                        JSR     V2_HEX_BYTE
                        BCC     V2_C_HEX
                        LDA     V2_VALUE
                        STA     V2_CONFIG+2
                        JSR     V2_HEX_WORD
                        BCC     V2_C_HEX
                        LDA     V2_VALUE
                        STA     V2_CONFIG+3
                        LDA     V2_VALUE+1
                        STA     V2_CONFIG+4
                        JSR     V2_HEX_BYTE
                        BCC     V2_C_HEX
                        LDA     V2_VALUE
                        STA     V2_CONFIG+5
                        JSR     V2_SKIP_SPACES
                        BNE     V2_C_HEX
                        JSR     V2_CONFIG_SUM
                        LDA     V2_CFG_SUM
                        STA     V2_CONFIG+14
                        LDA     V2_CFG_SUM2
                        STA     V2_CONFIG+15
                        JSR     V2_CONFIG_CHECK
                        BCS     V2_C_VALID
                        JMP     V2_BAD_RANGE
V2_C_HEX:              JMP     V2_BAD_HEX
V2_C_VALID:            LDA     V2_SELECTED
                        PHA
                        LDA     V2_RESIDENT
                        STA     V2_SELECTED
                        JSR     V2_FLASH_BANK
                        JSR     V2_CONFIG_SHOW
                        LDA     #$E0
                        STA     V2_SECTOR
                        STZ     V2_SELF
                        JSR     V2W_SNAPSHOT
                        LDX     #$0F
V2_C_STAGE:            LDA     V2_CONFIG,X
                        STA     $78F0,X
                        DEX
                        BPL     V2_C_STAGE
                        JSR     V2W_ANALYZE
                        JSR     V2_FLASH_MODE
                        JSR     V2_CONFIRM
                        BCS     V2_C_WRITE
                        PLA
                        STA     V2_SELECTED
                        JMP     V2_CANCELLED
V2_C_WRITE:            JSR     V2W_MUTATE
                        PLA
                        STA     V2_SELECTED
                        BCC     V2_C_DONE
                        JMP     V2_FLASH_FAILED
V2_C_DONE:             JMP     V2_FLASH_COMPLETE

V2_CONFIG_READ:        LDX     #$0F
V2_CONFIG_COPY:        LDA     $EFF0,X
                        STA     V2_CONFIG,X
                        DEX
                        BPL     V2_CONFIG_COPY
V2_CONFIG_CHECK:       LDA     V2_CONFIG
                        CMP     #$01
                        BNE     V2_CONFIG_BAD
                        LDA     V2_CONFIG+1
                        CMP     #$02
                        BCS     V2_CONFIG_BAD
                        LDA     V2_CONFIG+2
                        CMP     #$04
                        BCS     V2_CONFIG_BAD
                        LDA     V2_CONFIG+5
                        CMP     #$0A
                        BCC     V2_CONFIG_BAD
                        LDA     V2_CONFIG+3
                        STA     V2_ADDR
                        LDA     V2_CONFIG+4
                        STA     V2_ADDR+1
                        BMI     V2_CONFIG_ADDRESS
                        JSR     V2_APPLICATION_ADDRESS
                        BCC     V2_CONFIG_BAD
V2_CONFIG_ADDRESS:     JSR     V2_CONFIG_SUM
                        LDA     V2_CFG_SUM
                        CMP     V2_CONFIG+14
                        BNE     V2_CONFIG_BAD
                        LDA     V2_CFG_SUM2
                        CMP     V2_CONFIG+15
                        BNE     V2_CONFIG_BAD
                        SEC
                        RTS
V2_CONFIG_BAD:         CLC
                        RTS
; Two accumulated 8-bit sums (modulo 256), covering bytes 0..13 in order.
V2_CONFIG_SUM:         STZ     V2_CFG_SUM
                        STZ     V2_CFG_SUM2
                        LDX     #$00
V2_CONFIG_SUM_BYTE:    LDA     V2_CONFIG,X
                        CLC
                        ADC     V2_CFG_SUM
                        STA     V2_CFG_SUM
                        CLC
                        ADC     V2_CFG_SUM2
                        STA     V2_CFG_SUM2
                        INX
                        CPX     #$0E
                        BNE     V2_CONFIG_SUM_BYTE
                        RTS
V2_CONFIG_SHOW:        LDA     #'C'
                        JSR     V2_PUTC
                        LDX     #$01
V2_CONFIG_FIELD:       LDA     #' '
                        JSR     V2_PUTC
                        LDA     V2_CONFIG,X
                        CPX     #$03
                        BNE     V2_CONFIG_BYTE
                        LDA     V2_CONFIG+4
                        JSR     V2_HEX_OUT
                        LDA     V2_CONFIG+3
                        INX
V2_CONFIG_BYTE:        JSR     V2_HEX_OUT
                        INX
                        CPX     #$06
                        BNE     V2_CONFIG_FIELD
                        JMP     V2_NEWLINE

; Only reset entry autostarts. F003 always holds and preserves user pointers.
V2_AUTOSTART:          JSR     V2_CONFIG_READ
                        BCC     V2_AUTO_RETURN
                        LDA     V2_CONFIG+1
                        BEQ     V2_AUTO_RETURN
                        JSR     V2_NEWLINE
                        JSR     V2_CONFIG_SHOW
                        LDX     #V2_HOLD_TEXT
                        JSR     V2_PRINT
                        LDA     V2_CONFIG+5
                        STA     V2_TICKS
; Linked 65C02 idle path: about 0.1004 s per tick at 8 MHz. Input extends it.
V2_AUTO_TICK:          LDY     #$31
                        LDX     #$00
V2_AUTO_POLL:          JSR     V2_AUTO_KEY
                        BCS     V2_AUTO_STOP
                        DEX
                        BNE     V2_AUTO_POLL
                        DEY
                        BNE     V2_AUTO_POLL
                        DEC     V2_TICKS
                        BNE     V2_AUTO_TICK
                        JSR     V2_AUTO_KEY
                        BCS     V2_AUTO_STOP
                        LDA     V2_CONFIG+2
                        STA     V2_SELECTED
                        LDA     V2_CONFIG+3
                        STA     V2_VECTOR
                        LDA     V2_CONFIG+4
                        STA     V2_VECTOR+1
                        JMP     V2W_EXECUTE
V2_AUTO_STOP:          JSR     V2_RX_RESET
                        LDX     #V2_CANCEL_TEXT
                        JMP     V2_PRINT
V2_AUTO_RETURN:        RTS
; Consume startup input without blocking; queued S and Ctrl-C are honored.
; Overflow also holds, because it may have discarded a stop key.
V2_AUTO_KEY:           LDA     V2_CANCEL_REQUEST
                        ORA     V2_RX_BAD
                        BNE     V2_AUTO_YES
                        LDA     V2_RX_COUNT
                        BEQ     V2_AUTO_RAW
                        JSR     V2_GETC
                        BRA     V2_AUTO_CHAR
V2_AUTO_RAW:           JSR     V2_RAW_POLL
                        BCC     V2_AUTO_RETURN
V2_AUTO_CHAR:          CMP     #$03
                        BEQ     V2_AUTO_YES
                        AND     #$DF
                        CMP     #'S'
                        BEQ     V2_AUTO_YES
                        CLC
                        RTS
V2_AUTO_YES:           SEC
                        RTS
