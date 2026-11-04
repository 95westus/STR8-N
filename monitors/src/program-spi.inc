; Per-byte addressed transfers work in all admitted00/40/80 modes without WRMR.
; READ may inspect the array; WRITE is restricted to PROGRAM payload/directory.
W_SPI_GUARD:
        LDA W_IER
        AND #$18
        BNE SP_BUSY
        LDA W_PCR
        AND #$F0
        BNE SP_BUSY
        LDA W_ACR
        AND #$1E
        BNE SP_BUSY
        LDA W_DDR
        AND #$2F
        BNE SP_BUSY
        SEC
        RTS
SP_BUSY:
        LDA #1
        CLC
        RTS
SP_READ64:
        LDA W_EDU
        STA SP_PROFILE
        LDA W_A0
        STA SP_A0
        LDA W_A1
        STA SP_A1
        LDA W_A2
        STA SP_A2
        LDA #<W_LAYOUT
        STA SP_PTR
        LDA #>W_LAYOUT
        STA SP_PTR+1
        LDA #64
        STA SP_COUNT
        LDA #1
        STA SP_OP
        JSR SP_TRANSFER
        CMP #0
        BNE SP_BUSY_RETURN
        SEC
        RTS
SP_BUSY_RETURN:
        CLC
        RTS
SP_TRANSFER:
        LDA SP_PROFILE
        BEQ SP_NO_PROFILE
        LDA SP_COUNT
        BEQ SP_BAD_RANGE
        CMP #65
        BCS SP_BAD_RANGE
        LDA SP_A2
        CMP #2
        BCS SP_BAD_RANGE
        CMP #1
        BNE SP_OP_CHECK
        CLC
        LDA SP_A0
        ADC SP_COUNT
        STA SP_TEMP
        LDA SP_A1
        ADC #0
        BCC SP_OP_CHECK
        ORA SP_TEMP
        BNE SP_BAD_RANGE
SP_OP_CHECK:
        LDA SP_OP
        CMP #1
        BEQ SP_BEGIN
        CMP #2
        BNE SP_BAD_RANGE
        LDA SP_A2
        BNE SP_BAD_RANGE
        ; Exact allowed partitions: slots0040-023F and payload0800-limit.
        LDA SP_A1
        BNE SP_WRITE_HIGH
        LDA SP_A0
        CMP #$40
        BCC SP_BAD_RANGE
SP_WRITE_HIGH:
        LDA SP_A1
        CMP #8
        BCS SP_CHECK_PAYLOAD
        CLC
        LDA SP_A0
        ADC SP_COUNT
        STA SP_TEMP
        LDA SP_A1
        ADC #0
        CMP #2
        BCC SP_BEGIN
        BNE SP_BAD_RANGE
        LDA SP_TEMP
        CMP #$41
        BCS SP_BAD_RANGE
        BRA SP_BEGIN
SP_CHECK_PAYLOAD:
        CLC
        LDA SP_A0
        ADC SP_COUNT
        STA SP_TEMP
        LDA SP_A1
        ADC #0
        ; Carry denotes the exclusive10000 endpoint, allowed only for64K.
        BCC SP_PAYLOAD_NORMAL
        BNE SP_BAD_RANGE
        LDX LIMIT
        BNE SP_BAD_RANGE
        LDA SP_TEMP
        BNE SP_BAD_RANGE
        BRA SP_BEGIN
SP_PAYLOAD_NORMAL:
        LDX LIMIT
        BEQ SP_BEGIN
        CMP LIMIT
        BCC SP_BEGIN
        BNE SP_BAD_RANGE
        LDA SP_TEMP
        BNE SP_BAD_RANGE
SP_BEGIN:
        JSR W_SPI_GUARD
        BCC SP_STATUS_RETURN
        LDA W_IFR
        AND #$18
        BNE SP_BUSY
        LDA W_DDR
        STA SP_DDR
        LDA W_ORB
        STA SP_ORB
        AND #$FC
        ORA #$0C
        STA SP_PORT
        STA W_ORB
        LDA SP_DDR
        AND #$DF
        ORA #$0F
        STA W_DDR
        LDA #5
        JSR SP_COMMAND
        LDA #$FF
        JSR SP_BYTE
        STA SP_TEMP
        JSR SP_DESELECT
        LDA SP_TEMP
        BEQ SP_MODE_OK
        CMP #$40
        BEQ SP_MODE_OK
        CMP #$80
        BNE SP_MODE_BAD
SP_MODE_OK:
        LDA #3
        LDX SP_OP
        CPX #2
        BNE SP_FRAME
        LDA #2
SP_FRAME:
        JSR SP_COMMAND
        LDA SP_A2
        JSR SP_BYTE
        LDA SP_A1
        JSR SP_BYTE
        LDA SP_A0
        JSR SP_BYTE
        LDY #0
        LDA (SP_PTR),Y
        LDX SP_OP
        CPX #2
        BEQ SP_DATA
        LDA #$FF
SP_DATA:
        JSR SP_BYTE
        LDX SP_OP
        CPX #1
        BNE SP_DATA_DONE
        LDY #0
        STA (SP_PTR),Y
SP_DATA_DONE:
        JSR SP_DESELECT
        INC SP_PTR
        BNE SP_ADDR
        INC SP_PTR+1
SP_ADDR:
        INC SP_A0
        BNE SP_LEFT
        INC SP_A1
        BNE SP_LEFT
        INC SP_A2
SP_LEFT:
        DEC SP_COUNT
        BNE SP_MODE_OK
        STZ SP_ERROR
        BRA SP_RESTORE
SP_MODE_BAD:
        LDA #2
        STA SP_ERROR
SP_RESTORE:
        JSR SP_DESELECT
        LDA SP_DDR
        STA W_DDR
        LDA SP_ORB
        STA W_ORB
        LDA SP_ERROR
SP_STATUS_RETURN:
        RTS
SP_NO_PROFILE:
        LDA #$80
        RTS
SP_BAD_RANGE:
        LDA #$44
        RTS
SP_COMMAND:
        PHA
        LDA SP_PORT
        AND #$FB
        STA SP_PORT
        STA W_ORB
        PLA
        JMP SP_BYTE
SP_DESELECT:
        LDA SP_PORT
        ORA #$0C
        STA SP_PORT
        STA W_ORB
        RTS
SP_BYTE:
        STA SP_TX
        LDX #8
SP_BIT:
        LDA #2
        TRB SP_PORT
        ASL SP_TX
        BCC SP_ZERO
        TSB SP_PORT
SP_ZERO:
        LDA SP_PORT
        STA W_ORB
        INC A
        STA W_ORB
        LDA W_ORB
        ASL A
        ASL A
        ASL A
        ROL SP_RX
        LDA SP_PORT
        STA W_ORB
        DEX
        BNE SP_BIT
        LDA SP_RX
        RTS
