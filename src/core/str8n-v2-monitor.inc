; Monitor commands share hex parsing and bank-safe reads. M preflights the
; complete command before changing any application byte. No flash writes.
V2_BAD_HEX:            LDX     #V2_BAD_HEX_TEXT
                        JMP V2_MESSAGE
V2_BAD_RANGE:          LDX     #V2_BAD_RANGE_TEXT
                        JMP V2_MESSAGE
V2_PROTECTED:          LDX     #V2_PROTECTED_TEXT
                        JMP V2_MESSAGE

V2_GET_ADDRESS:        LDX     #$01
                        JSR     V2_HEX_WORD
                        BCC V2_ADDRESS_DONE
str8n_v2_monitor_LONG_11:
                        LDA     V2_VALUE
                        STA     V2_ADDR
                        STA     V2_VECTOR
                        LDA     V2_VALUE+1
                        STA     V2_ADDR+1
                        STA     V2_VECTOR+1
V2_ADDRESS_DONE:       RTS

V2_COMMAND_G:          JSR     V2_GET_ADDRESS
                        BCS str8n_v2_monitor_LONG_21
                        JMP V2_BAD_HEX
str8n_v2_monitor_LONG_21:
                        JSR     V2_SKIP_SPACES
                        BEQ str8n_v2_monitor_LONG_23
                        JMP V2_BAD_HEX
str8n_v2_monitor_LONG_23:
                        LDA     V2_ADDR+1
                        BPL str8n_v2_monitor_LONG_25
                        JMP V2_G_GO
str8n_v2_monitor_LONG_25:
                        JSR     V2_APPLICATION_ADDRESS
                        BCS str8n_v2_monitor_LONG_27
                        JMP V2_PROTECTED
str8n_v2_monitor_LONG_27:
V2_G_GO:               JSR     V2_CHECK_CANCEL
                        BCS str8n_v2_monitor_LONG_29
                        JMP V2_G_READY
str8n_v2_monitor_LONG_29:
                        JMP     V2_CANCELLED
V2_G_READY:            JMP     V2W_EXECUTE

V2_COMMAND_D:          JSR     V2_GET_ADDRESS
                        BCC V2_BAD_HEX
str8n_v2_monitor_LONG_34:
                        JSR     V2_SKIP_SPACES
; VALUE still contains the start address: an omitted end displays one byte.
                        BEQ V2_D_END
str8n_v2_monitor_LONG_37:
                        JSR     V2_HEX_WORD
                        BCC V2_BAD_HEX
str8n_v2_monitor_LONG_39:
                        JSR     V2_SKIP_SPACES
                        BNE V2_BAD_HEX
str8n_v2_monitor_LONG_41:
V2_D_END:              LDA     V2_VALUE
                        CMP     V2_ADDR
                        LDA     V2_VALUE+1
                        SBC     V2_ADDR+1
                        BCC V2_BAD_RANGE
str8n_v2_monitor_LONG_46:
; Reject the whole request before any target read if it intersects I/O.
                        LDA     V2_ADDR+1
                        BMI V2_D_ROW
str8n_v2_monitor_LONG_49:
                        CMP     #$7F
                        BEQ V2_PROTECTED
str8n_v2_monitor_LONG_51:
                        LDA     V2_LAST+1
                        CMP     #$7F
                        BCS V2_PROTECTED
str8n_v2_monitor_LONG_54:
V2_D_ROW:              JSR     V2_CHECK_CANCEL
                        BCC V2_D_CONTINUE
str8n_v2_monitor_LONG_56:
                        JMP     V2_CANCELLED
V2_D_CONTINUE:         LDA     #$10
                        STA     V2_COUNT
; Compute remaining distance; a same-page distance <15 needs a short row.
                        LDA     V2_LAST
                        SEC
                        SBC     V2_ADDR
                        TAX
                        LDA     V2_LAST+1
                        SBC     V2_ADDR+1
                        BNE V2_D_READ
str8n_v2_monitor_LONG_67:
                        TXA
                        CMP     #$0F
                        BCS V2_D_READ
str8n_v2_monitor_LONG_70:
                        INC     A
                        STA     V2_COUNT
; RAM reads do not need a snapshot or a bank switch. In particular, copying
; a RAM range that overlaps BYTES would corrupt the very data being displayed.
V2_D_READ:             LDA     V2_ADDR+1
                        BPL V2_D_HEADER
str8n_v2_monitor_LONG_76:
                        JSR     V2W_READ
V2_D_HEADER:           JSR     V2_PRINT_ADDR
                        LDA     #':'
                        JSR     V2_PUTC
                        LDX     #$00
V2_D_PRINT:            LDA     #' '
                        JSR     V2_PUTC
                        LDA     V2_ADDR+1
                        BMI V2_D_FLASH_BYTE
str8n_v2_monitor_LONG_85:
                        TXA
                        TAY
                        LDA     (V2_ADDR),Y
                        JMP V2_D_OUTPUT
V2_D_FLASH_BYTE:
                        LDA     V2_BYTES,X
V2_D_OUTPUT:
                        JSR     V2_HEX_OUT
                        INX
                        CPX     V2_COUNT
                        BNE V2_D_PRINT
str8n_v2_monitor_LONG_96:
                        JSR     V2_NEWLINE
                        LDA     V2_CANCEL_REQUEST
                        BEQ V2_D_ADVANCE
str8n_v2_monitor_LONG_99:
                        JMP     V2_CANCELLED
V2_D_ADVANCE:
                        LDA     V2_ADDR
                        CLC
                        ADC     V2_COUNT
                        STA     V2_ADDR
                        BCC V2_D_COMPARE
str8n_v2_monitor_LONG_106:
                        INC     V2_ADDR+1
                        BEQ V2_D_DONE
str8n_v2_monitor_LONG_108:
V2_D_COMPARE:          LDA     V2_LAST
                        CMP     V2_ADDR
                        LDA     V2_LAST+1
                        SBC     V2_ADDR+1
                        BCS V2_D_ROW
str8n_v2_monitor_LONG_113:
V2_D_DONE:             JMP     V2_PROMPT

V2_COMMAND_M:          JMP     V2_MAP_REQUEST
V2_M_EDIT:             JSR     V2_GET_ADDRESS
                        BCS V2_M_BEGIN
str8n_v2_monitor_LONG_118:
                        JMP     V2_BAD_HEX
V2_M_BEGIN:            STZ     V2_EDIT_FLASH
V2_EDIT_BEGIN:         STZ     V2_COUNT
V2_M_PARSE:            JSR     V2_HEX_BYTE
                        BCS V2_M_BYTE
str8n_v2_monitor_LONG_123:
                        JMP     V2_BAD_HEX
V2_M_BYTE:             LDA     V2_EDIT_FLASH
                        BEQ V2_EDIT_RAM
str8n_v2_monitor_LONG_126:
                        LDA     V2_ADDR+1
                        AND     #$F0
                        CMP     V2_SECTOR
                        BEQ V2_M_ALLOWED
str8n_v2_monitor_LONG_130:
                        JMP     V2_F_CROSS
V2_EDIT_RAM:           JSR     V2_MODIFIABLE_ADDRESS
                        BCS V2_M_ALLOWED
str8n_v2_monitor_LONG_133:
                        JMP     V2_PROTECTED
V2_M_ALLOWED:          LDY     V2_COUNT
                        LDA     V2_VALUE
                        STA     V2_BYTES,Y
                        INC     V2_COUNT
                        INC     V2_ADDR
                        BNE V2_M_NEXT
str8n_v2_monitor_LONG_140:
                        INC     V2_ADDR+1
V2_M_NEXT:             JSR     V2_SKIP_SPACES
                        BNE V2_M_PARSE
str8n_v2_monitor_LONG_143:
; All bytes and addresses are now valid. Keep NMI from following a partially
; written pointer during the short commit loop; IRQ is already disabled.
                        JSR     V2_CHECK_CANCEL
                        BCC V2_EDIT_READY
str8n_v2_monitor_LONG_147:
                        JMP     V2_CANCELLED
V2_EDIT_READY:         LDA     V2_EDIT_FLASH
                        BEQ V2_M_COMMIT
str8n_v2_monitor_LONG_150:
                        JMP     V2_F_SNAPSHOT
V2_M_COMMIT:
                        LDA     V2_VECTOR
                        STA     V2_ADDR
                        LDA     V2_VECTOR+1
                        STA     V2_ADDR+1
                        LDX     #$80
                        JSR     V2_COPY_BYTES
                        JMP     V2_PROMPT
; M/L share the gated, non-cancellable copy of a fully checked unit.
; IN X=source offset in LINE, ADDR=destination, COUNT=length (nonzero).
; Set the gate with Y, then decrement Y to the first destination offset.
V2_COPY_BYTES:         LDY     #$01
                        STY     V2_NMI_HOLD
                        DEY
V2_M_WRITE:
V2_LOAD_COPY:          LDA     V2_LINE,X
                        STA     (V2_ADDR),Y
                        INX
                        INY
                        CPY     V2_COUNT
                        BNE V2_LOAD_COPY
str8n_v2_monitor_LONG_172:
                        STZ     V2_NMI_HOLD
                        RTS

; IN address in V2_ADDR; C=1 only for ordinary application RAM.
V2_APPLICATION_ADDRESS:
                        LDA     V2_ADDR+1
                        BEQ V2_APP_ZP
str8n_v2_monitor_LONG_179:
                        CMP     #$02
                        BCC V2_ADDRESS_NO
str8n_v2_monitor_LONG_181:
                        CMP     #$67
                        BCS V2_ADDRESS_NO
str8n_v2_monitor_LONG_183:
                        CMP     #$65
                        BCC V2_ADDRESS_YES
str8n_v2_monitor_LONG_185:
                        BIT SVC_ACTIVE
                        BNE V2_ADDRESS_NO
str8n_v2_monitor_LONG_187:
                        JMP V2_ADDRESS_YES
V2_ADDRESS_NO:         CLC
                        RTS
V2_APP_ZP:             LDA     V2_ADDR
                        CMP     #$E0
                        BCS V2_ADDRESS_NO
str8n_v2_monitor_LONG_193:
V2_ADDRESS_YES:        SEC
                        RTS

; M's deliberate exception: ten emulation/native pointer bytes in each slot
; group. Monitor entry code and unassigned vector-page bytes stay protected.
V2_MODIFIABLE_ADDRESS:
                        JSR     V2_APPLICATION_ADDRESS
                        BCS V2_MOD_DONE
str8n_v2_monitor_LONG_201:
                        LDA     V2_ADDR+1
                        CMP     #$7E
                        BNE V2_ADDRESS_NO
str8n_v2_monitor_LONG_204:
                        LDA     V2_ADDR
                        AND     #$EF
                        CMP     #$0A
                        BCC V2_ADDRESS_YES
str8n_v2_monitor_LONG_208:
                        CLC
V2_MOD_DONE:            RTS

V2_SKIP_SPACES: JMP BOOT_API_SKIP
V2_HEX_WORD: JMP BOOT_API_HEX_WORD
V2_HEX_BYTE: JMP BOOT_API_HEX_BYTE
