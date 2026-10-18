; C [0|1 0-3 address|V delay]. Numeric fields hex; delay $0A-$FF tenths.
; Config belongs to the resident bank, independent of selected target bank.
V2_COMMAND_C:          LDX     #$01
                        JSR     V2_SKIP_SPACES
                        BEQ str8n_v2_config_LONG_4
                        JMP V2_C_SET
str8n_v2_config_LONG_4:
                        JSR     V2_CONFIG_READ
                        BCC str8n_v2_config_LONG_6
                        JMP V2_C_SHOW
str8n_v2_config_LONG_6:
                        LDX     #V2_NO_CONFIG_TEXT
                        JMP     V2_MESSAGE
V2_C_SHOW:             JSR     V2_CONFIG_SHOW
                        JMP     V2_PROMPT
V2_C_SET:              LDX     #$0F
V2_C_CLEAR:            STZ     V2_CONFIG,X
                        DEX
                        BMI str8n_v2_config_LONG_14
                        JMP V2_C_CLEAR
str8n_v2_config_LONG_14:
                        INC     V2_CONFIG
                        LDA $7D28
                        STA V2_CONFIG+13
                        LDX     #$01
                        JSR     V2_HEX_BYTE
                        BCS str8n_v2_config_LONG_20
                        JMP V2_C_HEX
str8n_v2_config_LONG_20:
                        LDA     V2_VALUE
                        STA     V2_CONFIG+1
                        JSR     V2_HEX_BYTE
                        BCS str8n_v2_config_LONG_24
                        JMP V2_C_HEX
str8n_v2_config_LONG_24:
                        LDA     V2_VALUE
                        STA     V2_CONFIG+2
                        JSR     V2_SKIP_SPACES
                        CMP     #'V'
                        BNE str8n_v2_config_LONG_29
                        JMP V2_C_VECTOR
str8n_v2_config_LONG_29:
                        JSR     V2_HEX_WORD
                        BCS str8n_v2_config_LONG_31
                        JMP V2_C_HEX
str8n_v2_config_LONG_31:
                        LDA     V2_VALUE
                        STA     V2_CONFIG+3
                        LDA     V2_VALUE+1
                        STA     V2_CONFIG+4
                        JMP V2_C_DELAY
V2_C_VECTOR:            INX
                        LDA     V2_LINE,X
                        CMP     #' '
                        BEQ str8n_v2_config_LONG_40
                        JMP V2_C_HEX
str8n_v2_config_LONG_40:
                        INC     V2_CONFIG+6
V2_C_DELAY:
                        JSR     V2_HEX_BYTE
                        BCS str8n_v2_config_LONG_44
                        JMP V2_C_HEX
str8n_v2_config_LONG_44:
                        LDA     V2_VALUE
                        STA     V2_CONFIG+5
                        JSR     V2_SKIP_SPACES
                        BEQ str8n_v2_config_LONG_48
                        JMP V2_C_HEX
str8n_v2_config_LONG_48:
                        JSR     V2_CONFIG_SUM
                        LDA     V2_CFG_SUM
                        STA     V2_CONFIG+14
                        LDA     V2_CFG_SUM2
                        STA     V2_CONFIG+15
                        JSR     V2_CONFIG_CHECK
                        BCC str8n_v2_config_LONG_55
                        JMP V2_C_VALID
str8n_v2_config_LONG_55:
                        JMP     V2_BAD_RANGE
V2_C_HEX:              JMP     V2_BAD_HEX
V2_C_VALID:            JSR V2_CONFIG_SHOW
                        JSR V2_CONFIRM
                        BCS str8n_v2_config_LONG_60
                        JMP V2_C_CANCEL
str8n_v2_config_LONG_60:
                        JSR BOOT_API_CFG
                        BCC str8n_v2_config_LONG_62
                        JMP V2_C_DONE
str8n_v2_config_LONG_62:
                        JMP V2_FLASH_FAILED
V2_C_CANCEL:           JMP V2_CANCELLED
V2_C_DONE:             JMP V2_FLASH_COMPLETE

V2_CONFIG_READ:        JSR BOOT_API_READ
                        BCS str8n_v2_config_LONG_68
                        JMP V2_CONFIG_BAD
str8n_v2_config_LONG_68:
V2_CONFIG_CHECK:       LDA     V2_CONFIG
                        DEC     A
                        BEQ str8n_v2_config_LONG_71
                        JMP V2_CONFIG_BAD
str8n_v2_config_LONG_71:
                        LDA     V2_CONFIG+1
                        CMP     #$02
                        BCC str8n_v2_config_LONG_74
                        JMP V2_CONFIG_BAD
str8n_v2_config_LONG_74:
                        LDA     V2_CONFIG+2
                        CMP     #$04
                        BCC str8n_v2_config_LONG_77
                        JMP V2_CONFIG_BAD
str8n_v2_config_LONG_77:
                        LDA     V2_CONFIG+5
                        CMP     #$0A
                        BCS str8n_v2_config_LONG_80
                        JMP V2_CONFIG_BAD
str8n_v2_config_LONG_80:
                        LDA     V2_CONFIG+6
                        CMP     #$02
                        BCC str8n_v2_config_LONG_83
                        JMP V2_CONFIG_BAD
str8n_v2_config_LONG_83:
                        DEC     A
                        BNE str8n_v2_config_LONG_85
                        JMP V2_CONFIG_ADDRESS
str8n_v2_config_LONG_85:
                        LDA     V2_CONFIG+3
                        STA     V2_ADDR
                        LDA     V2_CONFIG+4
                        STA     V2_ADDR+1
                        BPL str8n_v2_config_LONG_90
                        JMP V2_CONFIG_ADDRESS
str8n_v2_config_LONG_90:
                        JSR     V2_APPLICATION_ADDRESS
                        BCS str8n_v2_config_LONG_92
                        JMP V2_CONFIG_BAD
str8n_v2_config_LONG_92:
V2_CONFIG_ADDRESS:     JSR     V2_CONFIG_SUM
                        LDA     V2_CFG_SUM
                        CMP     V2_CONFIG+14
                        BEQ str8n_v2_config_LONG_96
                        JMP V2_CONFIG_BAD
str8n_v2_config_LONG_96:
                        LDA     V2_CFG_SUM2
                        CMP     V2_CONFIG+15
                        BEQ str8n_v2_config_LONG_99
                        JMP V2_CONFIG_BAD
str8n_v2_config_LONG_99:
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
                        BEQ str8n_v2_config_LONG_116
                        JMP V2_CONFIG_SUM_BYTE
str8n_v2_config_LONG_116:
                        RTS
V2_CONFIG_SHOW:        LDA     #'C'
                        JSR     V2_PUTC
                        LDX     #$01
V2_CONFIG_FIELD:       LDA     #' '
                        JSR     V2_PUTC
                        LDA     V2_CONFIG,X
                        CPX     #$03
                        BEQ str8n_v2_config_LONG_125
                        JMP V2_CONFIG_BYTE
str8n_v2_config_LONG_125:
                        LDA     V2_CONFIG+6
                        BNE str8n_v2_config_LONG_127
                        JMP V2_CONFIG_ADDRESS_OUT
str8n_v2_config_LONG_127:
                        LDA     #'V'
                        JSR     V2_PUTC
                        LDX     #$05
                        JMP V2_CONFIG_NEXT
V2_CONFIG_ADDRESS_OUT:
                        LDA     V2_CONFIG+4
                        JSR     V2_HEX_OUT
                        LDA     V2_CONFIG+3
                        INX
V2_CONFIG_BYTE:        JSR     V2_HEX_OUT
                        INX
V2_CONFIG_NEXT:
                        CPX     #$06
                        BEQ str8n_v2_config_LONG_141
                        JMP V2_CONFIG_FIELD
str8n_v2_config_LONG_141:
                        JMP     V2_NEWLINE

; Reset-only autostart. Probe FT245 once per tenth, print a dot only if its
; transmit FIFO is ready, and retain the hold window when USB is absent.
V2_AUTO_HEADLESS:
                        LDA     V2_CONFIG+5
                        STA     V2_TICKS
; Nominal tenths at 8 MHz; linked timing is checked by the config suite.
V2_AUTO_TICK:          LDY     #$70
                        LDA     V2_CONSOLE
                        BNE str8n_v2_config_LONG_152
                        JMP V2_AUTO_DOT
str8n_v2_config_LONG_152:
                        LDA     #$20
                        BIT     V2_CTRL
                        BEQ str8n_v2_config_LONG_155
                        JMP V2_AUTO_TICK_READY
str8n_v2_config_LONG_155:
                        STZ     V2_CONSOLE
V2_AUTO_DOT:           LDY     #$2B
                        LDA     #$01
                        BIT     V2_CTRL
                        BEQ str8n_v2_config_LONG_160
                        JMP V2_AUTO_TICK_READY
str8n_v2_config_LONG_160:
                        LDA     #'.'
                        JSR     V2W_SEND
V2_AUTO_TICK_READY:
                        LDX     #$00
V2_AUTO_POLL:          JSR     V2_AUTO_KEY
                        BCC str8n_v2_config_LONG_166
                        JMP V2_AUTO_STOP
str8n_v2_config_LONG_166:
                        DEX
                        BEQ str8n_v2_config_LONG_168
                        JMP V2_AUTO_POLL
str8n_v2_config_LONG_168:
                        DEY
                        BEQ str8n_v2_config_LONG_170
                        JMP V2_AUTO_POLL
str8n_v2_config_LONG_170:
                        DEC     V2_TICKS
                        BEQ str8n_v2_config_LONG_172
                        JMP V2_AUTO_TICK
str8n_v2_config_LONG_172:
                        JSR     V2_AUTO_KEY
                        BCC str8n_v2_config_LONG_174
                        JMP V2_AUTO_STOP
str8n_v2_config_LONG_174:
                        LDA     V2_CONFIG+6
                        BNE str8n_v2_config_LONG_176
                        JMP V2_AUTO_ADDRESS
str8n_v2_config_LONG_176:
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
                        BEQ str8n_v2_config_LONG_194
                        JMP V2_AUTO_NO_KEY
str8n_v2_config_LONG_194:
                        LDA     V2_CANCEL_REQUEST
                        ORA     V2_RX_BAD
                        BEQ str8n_v2_config_LONG_197
                        JMP V2_AUTO_YES
str8n_v2_config_LONG_197:
                        LDA     V2_RX_COUNT
                        BNE str8n_v2_config_LONG_199
                        JMP V2_AUTO_RAW
str8n_v2_config_LONG_199:
                        JSR     V2_GETC
                        JMP V2_AUTO_CHAR
V2_AUTO_RAW:           JSR     V2_RAW_POLL
                        BCS str8n_v2_config_LONG_203
                        JMP V2_AUTO_RETURN
str8n_v2_config_LONG_203:
V2_AUTO_CHAR:          CMP     #$03
                        BNE str8n_v2_config_LONG_205
                        JMP V2_AUTO_YES
str8n_v2_config_LONG_205:
                        AND     #$DF
                        CMP     #'S'
                        BNE str8n_v2_config_LONG_208
                        JMP V2_AUTO_YES
str8n_v2_config_LONG_208:
                        CLC
                        RTS
V2_AUTO_YES:           SEC
                        RTS
V2_AUTO_NO_KEY:        CLC
                        RTS
