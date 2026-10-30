; Shared transaction engine. RTC adapters and the public bus entry use this
; same code. Low-level INIT/RESTORE/START/STOP/byte routines remain common.
PUBLIC_I2C
        LDA BUSY
        BEQ PUBLIC_FREE
        LDA #RTC_IN_USE
        CLC
        RTS
PUBLIC_FREE INC BUSY
        STZ I2C_WRITTEN
        STZ I2C_READ
        STZ I2C_PHASE
        JSR VALIDATE_I2C
        BCS PUBLIC_READY
        JMP PUBLIC_DONE
PUBLIC_READY
        JSR INIT
        BCC PUBLIC_RESTORE
        JSR TRANSFER
PUBLIC_RESTORE
        STA I_ERROR
        JSR RESTORE
        LDA I_ERROR
PUBLIC_DONE
        STA I2C_RESULT
        STZ BUSY
        CMP #0
        BEQ PUBLIC_SUCCESS
        CLC
        RTS
PUBLIC_SUCCESS SEC
        RTS

VALIDATE_I2C
        LDA I2C_ADDRESS
        CMP #8
        BCS ADDRESS_LOW_OK
        LDA #I2C_BAD_ARGUMENT
        CLC
        RTS
ADDRESS_LOW_OK
        CMP #$78
        BCC ADDRESS_OK
        LDA #I2C_BAD_ARGUMENT
        CLC
        RTS
ADDRESS_OK
        STA I_ADDRESS
        LDA I2C_FLAGS
        AND #$FE
        BNE ARGUMENT_BAD
        LDA I2C_FLAGS
        STA I_FLAGS
        LDA I2C_WRITE_COUNT
        ORA I2C_READ_COUNT
        BEQ ARGUMENT_BAD
        LDA I2C_WRITE_PTR
        LDX I2C_WRITE_PTR+1
        LDY I2C_WRITE_COUNT
        JSR BUFFER_VALID
        BCC ARGUMENT_BAD
        LDA I2C_READ_PTR
        LDX I2C_READ_PTR+1
        LDY I2C_READ_COUNT
        JSR BUFFER_VALID
        BCC ARGUMENT_BAD
        LDA I2C_WRITE_PTR
        STA IO_LOAD+1
        LDA I2C_WRITE_PTR+1
        STA IO_LOAD+2
        LDA I2C_READ_PTR
        STA IO_STORE+1
        LDA I2C_READ_PTR+1
        STA IO_STORE+2
        LDA I2C_WRITE_COUNT
        STA I_TX_LEFT
        LDA I2C_READ_COUNT
        STA I_RX_LEFT
        LDA I_ADDRESS
        CMP #$57
        BEQ MANAGED_DENIED
        CMP #$6F
        BNE REQUEST_VALID
        ; Managed RTC permits pointer+read only; never SRAM or data writes.
        LDA I_TX_LEFT
        CMP #1
        BNE MANAGED_DENIED
        LDA I_RX_LEFT
        BEQ MANAGED_DENIED
        LDA I_FLAGS
        CMP #1
        BNE MANAGED_DENIED
        JSR IO_LOAD
        CMP #$20
        BCS MANAGED_DENIED
        CLC
        ADC I_RX_LEFT
        CMP #$21
        BCS MANAGED_DENIED
REQUEST_VALID SEC
        RTS
ARGUMENT_BAD LDA #I2C_BAD_ARGUMENT
        CLC
        RTS
MANAGED_DENIED LDA #RTC_DENIED
        CLC
        RTS

; A/X=pointer, Y=count. Nonzero buffers are caller RAM, max 64 bytes.
BUFFER_VALID
        CPY #0
        BEQ BUFFER_GOOD
        CPY #I2C_MAX_BYTES+1
        BCS BUFFER_BAD
        STA I_PTR_LO
        CPX #2
        BCC BUFFER_BAD
        CPX #$65
        BCS BUFFER_BAD
        TYA
        SEC
        SBC #1
        CLC
        ADC I_PTR_LO
        TXA
        ADC #0
        CMP #$65
        BCS BUFFER_BAD
BUFFER_GOOD SEC
        RTS
BUFFER_BAD CLC
        RTS

; Internal RTC transfers use private buffers and skip public ownership policy.
; Outer RTC operation owns the gateway/bus lock and saved VIA state.
READ_REGS
        LDA #<REGADDR
        STA IO_LOAD+1
        LDA #>REGADDR
        STA IO_LOAD+2
        LDA #<READBUF
        STA IO_STORE+1
        LDA #>READBUF
        STA IO_STORE+2
        LDA #1
        STA I_TX_LEFT
        STA I_FLAGS
        LDA COUNT
        STA I_RX_LEFT
        BRA RTC_TRANSFER
WRITE_REGS
        LDA REGADDR
        STA I_REG_PACKET
        LDX #0
PACK_REGISTER LDA WRITEBUF,X
        STA I_REG_PACKET+1,X
        INX
        CPX COUNT
        BNE PACK_REGISTER
        LDA #<I_REG_PACKET
        STA IO_LOAD+1
        LDA #>I_REG_PACKET
        STA IO_LOAD+2
        LDA COUNT
        INC A
        STA I_TX_LEFT
        STZ I_RX_LEFT
        STZ I_FLAGS
RTC_TRANSFER LDA #$6F
        STA I_ADDRESS

TRANSFER
        STZ I2C_WRITTEN
        STZ I2C_READ
        LDA #1
        STA I2C_PHASE
        JSR START_BUS
        BCS START_READY
        JMP TRANSFER_END
START_READY
        LDA I_TX_LEFT
        BNE SEND_WRITE_ADDRESS
        JMP SEND_READ_ADDRESS
SEND_WRITE_ADDRESS
        LDA I_ADDRESS
        ASL A
        JSR WRITE_BYTE
        BCS WRITE_PAYLOAD
        JMP TRANSFER_END
WRITE_PAYLOAD
        LDA #2
        STA I2C_PHASE
WRITE_PAYLOAD_LOOP
        JSR IO_LOAD
        JSR WRITE_BYTE
        BCS WROTE_BYTE
        JMP TRANSFER_END
WROTE_BYTE
        INC I2C_WRITTEN
        INC IO_LOAD+1
        BNE WRITE_PTR_READY
        INC IO_LOAD+2
WRITE_PTR_READY
        DEC I_TX_LEFT
        BNE WRITE_PAYLOAD_LOOP
        LDA I_RX_LEFT
        BNE READ_FOLLOWS
        JMP TRANSFER_SUCCESS
READ_FOLLOWS
        LDA I_FLAGS
        AND #1
        BNE REPEATED_START
        LDA #5
        STA I2C_PHASE
        JSR STOP_BUS
        BCS REPEATED_START
        JMP TRANSFER_END
REPEATED_START
        LDA #3
        STA I2C_PHASE
        JSR START_BUS
        BCS SEND_READ_ADDRESS
        JMP TRANSFER_END
SEND_READ_ADDRESS
        LDA #3
        STA I2C_PHASE
        LDA I_ADDRESS
        ASL A
        ORA #1
        JSR WRITE_BYTE
        BCS READ_PAYLOAD
        JMP TRANSFER_END
READ_PAYLOAD
        LDA #4
        STA I2C_PHASE
READ_PAYLOAD_LOOP
        LDY #0
        LDA I_RX_LEFT
        CMP #1
        BNE READ_WITH_ACK
        INY
READ_WITH_ACK
        JSR READ_BYTE
        BCS GOT_BYTE
        JMP TRANSFER_END
GOT_BYTE
        JSR IO_STORE
        INC I2C_READ
        INC IO_STORE+1
        BNE READ_PTR_READY
        INC IO_STORE+2
READ_PTR_READY
        DEC I_RX_LEFT
        BNE READ_PAYLOAD_LOOP
TRANSFER_SUCCESS LDA #0
TRANSFER_END
        STA I_ERROR
        JSR STOP_BUS
        BCS STOP_COMPLETE
        LDA I_ERROR
        BNE STOP_COMPLETE
        LDA #5
        STA I2C_PHASE
        LDA #RTC_TIMEOUT
        STA I_ERROR
STOP_COMPLETE
        LDA I_ERROR
        STA I2C_RESULT
        BEQ TRANSFER_GOOD
        CLC
        RTS
TRANSFER_GOOD SEC
        RTS
