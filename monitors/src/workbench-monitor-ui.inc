; Shared MON identity, RTC and warm return. No duplicate peripheral driver.
; A=MU operation; A=result, C=call admitted. MI CRC covers descriptor/vectors.
W_UI_EXPECTED EQU $6630
W_UI_PAGE EQU $6632
W_UI_OP EQU $6633
W_UI_TARGET EQU $6634
W_UI_END EQU $6636
W_UI_VALID EQU $6638

W_UI_CALL:
        JSR W_UI_CHECK
        BCC W_UI_ERROR
        JSR W_UI_JUMP
        SEC
        RTS
W_UI_JUMP:
        JMP (W_UI_TARGET)
W_UI_CHECK:
        STZ W_UI_VALID
        CMP #MU_VECTOR_COUNT
        BCS W_UI_BAD
        STA W_UI_OP
        LDA MU_ACTIVE
        CMP #$A0
        BEQ W_UI_SLOT
        CMP #$B0
        BNE W_UI_BAD
W_UI_SLOT:
        STA W_UI_PAGE
        STA W_PTR+1
        STZ W_PTR
        LDY #7
W_UI_MI:
        CPY #3
        BEQ W_UI_MI_SLOT
        LDA (W_PTR),Y
        CMP W_UI_MI_MAGIC,Y
        BNE W_UI_BAD
        BRA W_UI_MI_NEXT
W_UI_MI_SLOT:
        LDA (W_PTR),Y
        CMP W_UI_PAGE
        BNE W_UI_BAD
W_UI_MI_NEXT:
        DEY
        BPL W_UI_MI
        LDY #23
        LDX #3
W_UI_PR05:
        LDA (W_PTR),Y
        CMP W_UI_MAGIC+4,X
        BNE W_UI_BAD
        DEY
        DEX
        BPL W_UI_PR05
        LDY #13
        LDA (W_PTR),Y
        CMP #$0F
        BCC W_UI_LENGTH
        BNE W_UI_BAD
        DEY
        LDA (W_PTR),Y
        CMP #$81
        BCS W_UI_BAD
W_UI_LENGTH:
        LDY #12
        LDA (W_PTR),Y
        CLC
        ADC #$80
        STA W_UI_END
        INY
        LDA (W_PTR),Y
        ADC W_UI_PAGE
        STA W_UI_END+1
        LDY #18
        LDA (W_PTR),Y
        STA W_UI_EXPECTED
        INY
        LDA (W_PTR),Y
        STA W_UI_EXPECTED+1
        JSR W_CRC_START
        LDY #0
W_UI_HEADER_CRC:
        LDA (W_PTR),Y
        JSR W_CRC_BYTE
        INY
        CPY #18
        BCC W_UI_HEADER_CRC
        LDY #32
        LDX #16
W_UI_PAYLOAD_CRC:
        LDA (W_PTR),Y
        JSR W_CRC_BYTE
        INY
        BNE W_UI_PAYLOAD_CRC
        INC W_PTR+1
        DEX
        BNE W_UI_PAYLOAD_CRC
        LDA W_CRC
        CMP W_UI_EXPECTED
        BNE W_UI_BAD
        LDA W_CRC+1
        CMP W_UI_EXPECTED+1
        BNE W_UI_BAD
        LDA W_UI_PAGE
        STA W_PTR+1
        INC W_UI_VALID
        LDY #MU_DESCRIPTOR
        LDX #0
W_UI_DESCRIPTOR:
        CPX #3
        BNE W_UI_DESCRIPTOR_BYTE
        LDA (W_PTR),Y
        CMP #MU_VECTOR_COUNT
        BCC W_UI_BAD
        BRA W_UI_DESCRIPTOR_NEXT
W_UI_DESCRIPTOR_BYTE:
        LDA (W_PTR),Y
        CMP W_UI_MAGIC,X
        BNE W_UI_BAD
W_UI_DESCRIPTOR_NEXT:
        INY
        INX
        CPX #8
        BCC W_UI_DESCRIPTOR
        LDA W_UI_OP
        ASL A
        CLC
        ADC #MU_VECTOR_BASE
        TAY
        LDA (W_PTR),Y
        STA W_UI_TARGET
        INY
        LDA (W_PTR),Y
        STA W_UI_TARGET+1
        CMP W_UI_PAGE
        BCC W_UI_BAD
        BNE W_UI_UPPER
        LDA W_UI_TARGET
        CMP #$80
        BCC W_UI_BAD
W_UI_UPPER:
        LDA W_UI_TARGET
        CMP W_UI_END
        LDA W_UI_TARGET+1
        SBC W_UI_END+1
        BCS W_UI_BAD
        SEC
        RTS
W_UI_BAD:
        CLC
        RTS
W_UI_ERROR:
        LDX #<W_UI_ERROR_TEXT
        LDY #>W_UI_ERROR_TEXT
        JSR W_PUTS
        LDA #WB_REFUSED
        STA W_RESULT
        LDA #$80
        CLC
        RTS

W_VERSION_NAME:
        LDA W_LINE+1,X
        BEQ W_VERSION_SHORT
        CMP #' '
        BEQ W_VERSION_SHORT
        LDX #<W_VERSION_WORD
        LDY #>W_VERSION_WORD
        JSR W_MATCH
        BCC W_UNHANDLED
        BRA W_VERSION_ARGS
W_VERSION_SHORT:
        INX
W_VERSION_ARGS:
        JSR W_END_ARGS
        BCC W_UNHANDLED
        JSR W_SHOW_VERSION
        JMP W_HANDLED
W_SHOW_VERSION:
        LDA #MU_VERSION
        JSR W_UI_CALL
        BCC W_SHOW_VERSION_END
        LDX #<W_VERSION_TEXT
        LDY #>W_VERSION_TEXT
        JSR W_PUTS
W_SHOW_VERSION_END:
        RTS
W_TIME_NAME:
        LDX #<WC_TIME_WORD
        LDY #>WC_TIME_WORD
        JSR W_MATCH
        BCC W_UNHANDLED
        JSR W_END_ARGS
        BCC W_UNHANDLED
        LDA #MU_TIME
        JSR W_UI_CALL
        BCC W_TIME_DONE
        CMP #0
        BEQ W_TIME_DONE
        LDA #WB_REFUSED
        STA W_RESULT
W_TIME_DONE:
        JMP W_HANDLED
WC_SAMPLE:
        LDA #MU_SAMPLE
        JMP W_UI_CALL
WC_DISPLAY:
        LDA #MU_DISPLAY
        JMP W_UI_CALL
W_VERSION_WORD: DB "VERSION",0
W_UI_MI_MAGIC: DB "MI",1,0,3,1,0,0
W_UI_MAGIC: DB "UI",1,MU_VECTOR_COUNT,"PR05"
W_UI_ERROR_TEXT: DB "MON UI/1 unavailable; load matching MON/tools.",13,10,0
