; C [0|1 0-3 address|V delay]. Numeric fields hex; delay $0A-$FF tenths.
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
                        JSR     V2_SKIP_SPACES
                        CMP     #'V'
                        BEQ     V2_C_VECTOR
                        JSR     V2_HEX_WORD
                        BCC     V2_C_HEX
                        LDA     V2_VALUE
                        STA     V2_CONFIG+3
                        LDA     V2_VALUE+1
                        STA     V2_CONFIG+4
                        BRA     V2_C_DELAY
V2_C_VECTOR:            INX
                        LDA     V2_LINE,X
                        CMP     #' '
                        BNE     V2_C_HEX
                        INC     V2_CONFIG+6
V2_C_DELAY:
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
V2_C_VALID:            JSR V2_CONFIG_SHOW
                        JSR V2_CONFIRM
                        BCC V2_C_CANCEL
                        JSR BOOT_API_CFG
                        BCS V2_C_DONE
                        JMP V2_FLASH_FAILED
V2_C_CANCEL:           JMP V2_CANCELLED
V2_C_DONE:             JMP V2_FLASH_COMPLETE

V2_CONFIG_READ:        JSR BOOT_API_READ
                        BCC V2_CONFIG_BAD
V2_CONFIG_CHECK:       LDA     V2_CONFIG
                        DEC     A
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
                        LDA     V2_CONFIG+6
                        CMP     #$02
                        BCS     V2_CONFIG_BAD
                        DEC     A
                        BEQ     V2_CONFIG_ADDRESS
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
                        LDA     V2_CONFIG+6
                        BEQ     V2_CONFIG_ADDRESS_OUT
                        LDA     #'V'
                        JSR     V2_PUTC
                        LDX     #$05
                        BRA     V2_CONFIG_NEXT
V2_CONFIG_ADDRESS_OUT:
                        LDA     V2_CONFIG+4
                        JSR     V2_HEX_OUT
                        LDA     V2_CONFIG+3
                        INX
V2_CONFIG_BYTE:        JSR     V2_HEX_OUT
                        INX
V2_CONFIG_NEXT:
                        CPX     #$06
                        BNE     V2_CONFIG_FIELD
                        JMP     V2_NEWLINE

; Reset-only autostart. Probe FT245 once per tenth, print a dot only if its
; transmit FIFO is ready, and retain the hold window when USB is absent.
V2_AUTO_HEADLESS:
                        LDA     V2_CONFIG+5
                        STA     V2_TICKS
; Nominal tenths at 8 MHz; linked timing is checked by the config suite.
V2_AUTO_TICK:          LDY     #$70
                        LDA     V2_CONSOLE
                        BEQ     V2_AUTO_DOT
                        LDA     #$20
                        BIT     V2_CTRL
                        BNE     V2_AUTO_TICK_READY
                        STZ     V2_CONSOLE
V2_AUTO_DOT:           LDY     #$2B
                        LDA     #$01
                        BIT     V2_CTRL
                        BNE     V2_AUTO_TICK_READY
                        LDA     #'.'
                        JSR     V2W_SEND
V2_AUTO_TICK_READY:
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
                        LDA     V2_CONFIG+6
                        BEQ     V2_AUTO_ADDRESS
                        LDA     V2_CONFIG+2
                        STA     V2_TARGET
                        JMP     V2_J_READY
V2_AUTO_ADDRESS:        LDA     V2_CONFIG+2
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
; FT245 supplies hold input once ready. Headless startup never polls ACIA.
; Overflow holds on the active FT245 path.
V2_AUTO_KEY:           LDA     V2_CONSOLE
                        BNE     V2_AUTO_NO_KEY
                        LDA     V2_CANCEL_REQUEST
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
V2_AUTO_NO_KEY:        CLC
                        RTS
