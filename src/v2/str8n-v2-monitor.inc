; Monitor commands share hex parsing and bank-safe reads. M preflights the
; complete command before changing any application byte. No flash writes.
V2_BAD_HEX:            LDX     #V2_BAD_HEX_TEXT
                        BRA     V2_MESSAGE
V2_BAD_RANGE:          LDX     #V2_BAD_RANGE_TEXT
                        BRA     V2_MESSAGE
V2_PROTECTED:          LDX     #V2_PROTECTED_TEXT
                        BRA     V2_MESSAGE

V2_GET_ADDRESS:        LDX     #$01
                        JSR     V2_HEX_WORD
                        BCC     V2_ADDRESS_DONE
                        LDA     V2_VALUE
                        STA     V2_ADDR
                        STA     V2_VECTOR
                        LDA     V2_VALUE+1
                        STA     V2_ADDR+1
                        STA     V2_VECTOR+1
V2_ADDRESS_DONE:       RTS

V2_COMMAND_G:          JSR     V2_GET_ADDRESS
                        BCC     V2_BAD_HEX
                        JSR     V2_SKIP_SPACES
                        BNE     V2_BAD_HEX
                        LDA     V2_ADDR+1
                        BMI     V2_G_GO
                        JSR     V2_APPLICATION_ADDRESS
                        BCC     V2_PROTECTED
V2_G_GO:               JSR     V2_CHECK_CANCEL
                        BCS     V2_CANCELLED
V2_G_READY:            JMP     V2W_EXECUTE

V2_COMMAND_D:          JSR     V2_GET_ADDRESS
                        BCC     V2_BAD_HEX
                        JSR     V2_SKIP_SPACES
                        BEQ     V2_D_DEFAULT
                        JSR     V2_HEX_WORD
                        BCC     V2_BAD_HEX
                        JSR     V2_SKIP_SPACES
                        BNE     V2_BAD_HEX
                        BRA     V2_D_END
V2_D_DEFAULT:          LDA     V2_ADDR
                        CLC
                        ADC     #$0F
                        STA     V2_VALUE
                        LDA     V2_ADDR+1
                        ADC     #$00
                        STA     V2_VALUE+1
                        BCS     V2_BAD_RANGE
V2_D_END:              LDA     V2_VALUE
                        CMP     V2_ADDR
                        LDA     V2_VALUE+1
                        SBC     V2_ADDR+1
                        BCC     V2_BAD_RANGE
; Reject the whole request before any target read if it intersects I/O.
                        LDA     V2_ADDR+1
                        BMI     V2_D_ROW
                        CMP     #$7F
                        BEQ     V2_PROTECTED
                        LDA     V2_LAST+1
                        CMP     #$7F
                        BCS     V2_PROTECTED
V2_D_ROW:              JSR     V2_CHECK_CANCEL
                        BCC     V2_D_CONTINUE
                        JMP     V2_CANCELLED
V2_D_CONTINUE:         LDA     #$10
                        STA     V2_COUNT
; Compute remaining distance; a same-page distance <15 needs a short row.
                        LDA     V2_LAST
                        SEC
                        SBC     V2_ADDR
                        PHA
                        LDA     V2_LAST+1
                        SBC     V2_ADDR+1
                        BNE     V2_D_FULL
                        PLA
                        CMP     #$0F
                        BCS     V2_D_READ
                        INC     A
                        STA     V2_COUNT
                        BRA     V2_D_READ
V2_D_FULL:             PLA
; RAM reads do not need a snapshot or a bank switch. In particular, copying
; a RAM range that overlaps BYTES would corrupt the very data being displayed.
V2_D_READ:             LDA     V2_ADDR+1
                        BPL     V2_D_HEADER
                        JSR     V2W_READ
V2_D_HEADER:           JSR     V2_PRINT_ADDR
                        LDA     #':'
                        JSR     V2_PUTC
                        LDX     #$00
V2_D_PRINT:            LDA     #' '
                        JSR     V2_PUTC
                        LDA     V2_ADDR+1
                        BMI     V2_D_FLASH_BYTE
                        TXA
                        TAY
                        LDA     (V2_ADDR),Y
                        BRA     V2_D_OUTPUT
V2_D_FLASH_BYTE:
                        LDA     V2_BYTES,X
V2_D_OUTPUT:
                        JSR     V2_HEX_OUT
                        INX
                        CPX     V2_COUNT
                        BNE     V2_D_PRINT
                        JSR     V2_NEWLINE
                        LDA     V2_CANCEL_REQUEST
                        BEQ     V2_D_ADVANCE
                        JMP     V2_CANCELLED
V2_D_ADVANCE:
                        LDA     V2_ADDR
                        CLC
                        ADC     V2_COUNT
                        STA     V2_ADDR
                        BCC     V2_D_COMPARE
                        INC     V2_ADDR+1
                        BEQ     V2_D_DONE
V2_D_COMPARE:          LDA     V2_LAST
                        CMP     V2_ADDR
                        LDA     V2_LAST+1
                        SBC     V2_ADDR+1
                        BCS     V2_D_ROW
V2_D_DONE:             JMP     V2_PROMPT

V2_COMMAND_M:          JSR     V2_GET_ADDRESS
                        BCS     V2_M_BEGIN
                        JMP     V2_BAD_HEX
V2_M_BEGIN:            STZ     V2_EDIT_FLASH
V2_EDIT_BEGIN:         STZ     V2_COUNT
V2_M_PARSE:            JSR     V2_HEX_BYTE
                        BCS     V2_M_BYTE
                        JMP     V2_BAD_HEX
V2_M_BYTE:             LDA     V2_EDIT_FLASH
                        BEQ     V2_EDIT_RAM
                        LDA     V2_ADDR+1
                        AND     #$F0
                        CMP     V2_SECTOR
                        BEQ     V2_M_ALLOWED
                        JMP     V2_F_CROSS
V2_EDIT_RAM:           JSR     V2_MODIFIABLE_ADDRESS
                        BCS     V2_M_ALLOWED
                        JMP     V2_PROTECTED
V2_M_ALLOWED:          LDY     V2_COUNT
                        LDA     V2_VALUE
                        STA     V2_BYTES,Y
                        INC     V2_COUNT
                        INC     V2_ADDR
                        BNE     V2_M_NEXT
                        INC     V2_ADDR+1
V2_M_NEXT:             JSR     V2_SKIP_SPACES
                        BNE     V2_M_PARSE
; All bytes and addresses are now valid. Keep NMI from following a partially
; written pointer during the short commit loop; IRQ is already disabled.
                        JSR     V2_CHECK_CANCEL
                        BCC     V2_EDIT_READY
                        JMP     V2_CANCELLED
V2_EDIT_READY:         LDA     V2_EDIT_FLASH
                        BEQ     V2_M_COMMIT
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
V2_COPY_BYTES:         LDA     #$01
                        STA     V2_NMI_HOLD
                        LDY     #$00
V2_M_WRITE:
V2_LOAD_COPY:          LDA     V2_LINE,X
                        STA     (V2_ADDR),Y
                        INX
                        INY
                        CPY     V2_COUNT
                        BNE     V2_LOAD_COPY
                        STZ     V2_NMI_HOLD
                        RTS

; IN address in V2_ADDR; C=1 only for ordinary application RAM.
V2_APPLICATION_ADDRESS:
                        LDA     V2_ADDR+1
                        BEQ     V2_APP_ZP
                        CMP     #$02
                        BCC     V2_ADDRESS_NO
                        CMP     #$69
                        BCC     V2_ADDRESS_YES
V2_ADDRESS_NO:         CLC
                        RTS
V2_APP_ZP:             LDA     V2_ADDR
                        CMP     #$E0
                        BCS     V2_ADDRESS_NO
V2_ADDRESS_YES:        SEC
                        RTS

; M's deliberate exception: ten emulation/native pointer bytes in each slot
; group. Monitor entry code and unassigned vector-page bytes stay protected.
V2_MODIFIABLE_ADDRESS:
                        JSR     V2_APPLICATION_ADDRESS
                        BCS     V2_MOD_DONE
                        LDA     V2_ADDR+1
                        CMP     #$7E
                        BNE     V2_ADDRESS_NO
                        LDA     V2_ADDR
                        AND     #$EF
                        CMP     #$0A
                        BCC     V2_ADDRESS_YES
                        CLC
V2_MOD_DONE:            RTS

V2_SKIP_SPACES:        LDA     V2_LINE,X
                        CMP     #' '
                        BNE     V2_SKIP_DONE
                        INX
                        BRA     V2_SKIP_SPACES
V2_SKIP_DONE:          CMP     #$00
                        RTS

; IN X=line offset. OUT word in VALUE, X at space/NUL, C=valid.
; Addresses accept 1-4 digits; byte values 1-2. A token must end at space/NUL.
V2_HEX_WORD:           LDA     #$04
                        BRA     V2_HEX_PARSE
V2_HEX_BYTE:           LDA     #$02
V2_HEX_PARSE:          STA     V2_DIGIT_LIMIT
                        STZ     V2_VALUE
                        STZ     V2_VALUE+1
                        JSR     V2_SKIP_SPACES
                        LDY     #$00
V2_HEX_NEXT:           LDA     V2_LINE,X
                        BEQ     V2_HEX_END
                        CMP     #' '
                        BEQ     V2_HEX_END
                        CPY     V2_DIGIT_LIMIT
                        BCS     V2_HEX_FAIL
                        JSR     V2_HEX_NIBBLE
                        BCC     V2_HEX_FAIL
V2_HEX_DIGIT:          PHA
                        PHX
                        LDX     #$04
V2_HEX_SHIFT:         ASL     V2_VALUE
                        ROL     V2_VALUE+1
                        DEX
                        BNE     V2_HEX_SHIFT
                        PLX
                        PLA
                        ORA     V2_VALUE
                        STA     V2_VALUE
                        INX
                        INY
                        BRA     V2_HEX_NEXT
V2_HEX_END:            CPY     #$01
                        RTS
V2_HEX_FAIL:           CLC
                        RTS

; Shared by command tokens and streaming S19. Accept either case; C=valid.
V2_HEX_NIBBLE:         SEC
                        SBC     #'0'
                        BCC     V2_HEX_FAIL
                        CMP     #$0A
                        BCC     V2_HEX_NIBBLE_OK
; After subtracting '0', A-F/a-f differ only in bit 5. CMP above supplies
; the carry for subtraction; a valid letter leaves carry clear for ADC.
                        ORA     #$20
                        SBC     #('a'-'0')
                        CMP     #$06
                        BCS     V2_HEX_FAIL
                        ADC     #$0A
V2_HEX_NIBBLE_OK:      SEC
                        RTS

V2_HEX_OUT:            PHA
                        LSR     A
                        LSR     A
                        LSR     A
                        LSR     A
                        JSR     V2_NIBBLE_OUT
                        PLA
                        AND     #$0F
V2_NIBBLE_OUT:         CMP     #$0A
                        BCC     V2_NIBBLE_ASCII
                        ADC     #$06
V2_NIBBLE_ASCII:       ADC     #'0'
                        JMP     V2_PUTC
