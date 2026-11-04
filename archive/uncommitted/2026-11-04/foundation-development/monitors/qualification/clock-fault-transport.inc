; Device-boundary replacement for the real RTC and managed-EEPROM transport.
; INIT/RESTORE do not access VIA registers. All device bytes live in CPU RAM.
INIT:
        LDA #0
        SEC
        RTS
RESTORE:
        RTS
PUBLIC_I2C:
        INC FX_FORBIDDEN
        LDA #6
        CLC
        RTS
READ_REGS:
        LDX REGADDR
        LDY #0
FX_READ_RTC:
        LDA FX_REGS,X
        STA READBUF,Y
        INX
        INY
        CPY COUNT
        BCC FX_READ_RTC
        LDA #0
        SEC
        RTS
WRITE_REGS:
        LDA REGADDR
        STA FX_REG
        LDA COUNT
        STA FX_COUNT
        LDA WRITEBUF
        STA FX_VALUE
        JSR FX_OBSERVE_RTC
        BCC FX_WRITE_RETURN
        LDX REGADDR
        LDY #0
FX_WRITE_RTC:
        LDA WRITEBUF,Y
        JSR FX_CHIP_BYTE
        INX
        INY
        CPY COUNT
        BCC FX_WRITE_RTC
        INC FX_RTC_WRITES
        LDA #0
        SEC
FX_WRITE_RETURN:
        RTS

; Record ordering without enforcing it. A broken caller is allowed to write
; before committing its event, so the host can observe and reject that bug.
FX_OBSERVE_RTC:
        LDA FX_RTC_ATTEMPTS
        BNE FX_OBSERVED
        LDX #127
FX_SNAPSHOT_EE:
        LDA FX_EEPROM,X
        STA FX_BEFORE_RTC,X
        DEX
        BPL FX_SNAPSHOT_EE
        LDA FX_COMMIT_VERIFIED
        STA FX_FIRST_VERIFY
        LDA FX_LOG_N
        STA FX_FIRST_LOG
FX_OBSERVED:
        INC FX_RTC_ATTEMPTS
        LDA #2
        STA FX_KIND
        JSR FX_RECORD
        LDA FX_MODE
        CMP #5
        BNE FX_ACK_FAULT
        LDA FX_REG
        BEQ FX_NACK
FX_ACK_FAULT:
        LDA FX_MODE
        CMP #6
        BNE FX_TRIM_FAULT
        LDA FX_REG
        CMP #3
        BEQ FX_NACK
FX_TRIM_FAULT:
        LDA FX_MODE
        CMP #7
        BNE FX_OBSERVE_OK
        LDA FX_REG
        CMP #8
        BEQ FX_NACK
FX_OBSERVE_OK:
        LDA #0
        SEC
        RTS
FX_NACK:
        LDA #2
        CLC
        RTS

; Deterministic chip model: oscillator-run follows ST. A weekday write clears
; PF and, deliberately, the live stamp window, exercising the worst-case need
; to archive beforehand. This is an injected device response, not a claim
; about every physical chip's post-ACK timestamp contents.
FX_CHIP_BYTE:
        STA FX_REGS,X
        CPX #0
        BNE FX_WEEKDAY
        LDA FX_REGS+3
        AND #$DF
        BIT FX_REGS
        BPL FX_RUN_FLAG
        ORA #$20
FX_RUN_FLAG:
        STA FX_REGS+3
        RTS
FX_WEEKDAY:
        CPX #3
        BNE FX_FINE
        AND #$0F
        BIT FX_REGS
        BPL FX_WEEKDAY_DONE
        ORA #$20
FX_WEEKDAY_DONE:
        STA FX_REGS+3
        PHX
        LDX #7
        LDA #0
FX_ERASE_LIVE_STAMPS:
        STA FX_REGS+$18,X
        DEX
        BPL FX_ERASE_LIVE_STAMPS
        PLX
        RTS
FX_FINE:
        CPX #8
        BNE FX_BYTE_DONE
        INC FX_FINE_WRITES
FX_BYTE_DONE:
        RTS

TRANSFER:
        LDA I_ADDRESS
        CMP #$57
        BEQ FX_EE_TRANSFER
        CMP #$6F
        BEQ FX_TRIM_TRANSFER
        JMP PUBLIC_I2C
FX_TRIM_TRANSFER:
        LDA I_RX_LEFT
        BEQ FX_TRIM_WRITE
        ; Actual TRIM_READ always requests control07 and OSCTRIM08.
        LDA FX_REGS+7
        STA $6BA0
        LDA FX_REGS+8
        LDX FX_MODE
        CPX #8
        BNE FX_TRIM_READ_OK
        LDX FX_FINE_WRITES
        BEQ FX_TRIM_READ_OK
        EOR #1
        INC FX_CORRUPT_READS
FX_TRIM_READ_OK:
        STA $6BA1
        LDA #0
        SEC
        RTS
FX_TRIM_WRITE:
        LDA $6BC0
        STA FX_REG
        LDA #1
        STA FX_COUNT
        LDA $6BC1
        STA FX_VALUE
        JSR FX_OBSERVE_RTC
        BCC FX_TRANSFER_DONE
        LDX FX_REG
        LDA FX_VALUE
        JSR FX_CHIP_BYTE
        INC FX_RTC_WRITES
        LDA #0
        SEC
FX_TRANSFER_DONE:
        RTS

FX_EE_TRANSFER:
        LDA $6BE4
        BNE FX_EE_WRITE
        LDA $6BE0
        STA FX_RAM_STORE+1
        LDA $6BE1
        STA FX_RAM_STORE+2
        LDX $6BE2
        LDY #0
        CPX #$FF
        BEQ FX_EE_STATUS
        CPX #$F2
        BEQ FX_EE_FACTORY
FX_EE_READ:
        LDA FX_EEPROM,X
        JSR FX_RAM_STORE
        INX
        INY
        CPY $6BE3
        BCC FX_EE_READ
        LDA FX_MODE
        CMP #3
        BNE FX_EE_VERIFY
        LDA FX_DATA_WRITES
        BEQ FX_EE_VERIFY
        LDA $6BE2
        CMP #$60
        BNE FX_EE_VERIFY
        LDA $6BE3
        CMP #32
        BNE FX_EE_VERIFY
        LDA $6BE0
        CMP #$A0
        BNE FX_EE_VERIFY
        LDA $6BAC
        EOR #1
        STA $6BAC
        INC FX_CORRUPT_READS
FX_EE_VERIFY:
        LDA $6BE2
        CMP #$60
        BNE FX_TRANSFER_OK
        LDA $6BE3
        CMP #32
        BNE FX_TRANSFER_OK
        LDA FX_EEPROM+127
        CMP #$A5
        BNE FX_TRANSFER_OK
        LDA FX_LOG_N
        STA FX_COMMIT_VERIFIED
FX_TRANSFER_OK:
        LDA #0
        SEC
        RTS
FX_EE_FACTORY:
        LDA FX_EUI,Y
        JSR FX_RAM_STORE
        INY
        CPY #6
        BCC FX_EE_FACTORY
        BRA FX_TRANSFER_OK
FX_EE_STATUS:
        LDA #0
        LDX FX_MODE
        CPX #4
        BNE FX_EE_STATUS_READY
        LDA #$0C
FX_EE_STATUS_READY:
        JSR FX_RAM_STORE
        BRA FX_TRANSFER_OK
FX_RAM_STORE:
        STA $6B00,Y
        RTS

FX_EE_WRITE:
        LDA $6BE2
        STA FX_REG
        LDA $6BE3
        STA FX_COUNT
        LDA $6BC1
        STA FX_VALUE
        LDA #1
        STA FX_KIND
        JSR FX_RECORD
        LDA FX_MODE
        CMP #1
        BNE FX_COMMIT_FAULT
        LDA $6BE3
        CMP #2
        BCS FX_NACK_JUMP
FX_COMMIT_FAULT:
        LDA FX_MODE
        CMP #2
        BNE FX_EE_COPY
        LDA $6BE2
        CMP #$7F
        BNE FX_EE_COPY
        LDA $6BC1
        CMP #$A5
        BEQ FX_NACK_JUMP
FX_EE_COPY:
        INC FX_EE_WRITES
        LDA $6BE3
        CMP #2
        BCC FX_EE_COPY_READY
        INC FX_DATA_WRITES
FX_EE_COPY_READY:
        LDX $6BE2
        LDY #0
FX_EE_COPY_BYTE:
        LDA $6BC1,Y
        STA FX_EEPROM,X
        INX
        INY
        CPY $6BE3
        BCC FX_EE_COPY_BYTE
        BRA FX_TRANSFER_OK
FX_NACK_JUMP:
        JMP FX_NACK

FX_RECORD:
        LDA FX_LOG_N
        CMP #64
        BCC FX_LOG_READY
        INC FX_LOG_OVERFLOW
        RTS
FX_LOG_READY:
        ASL A
        ASL A
        TAX
        LDA FX_KIND
        STA FX_LOG,X
        LDA FX_REG
        STA FX_LOG+1,X
        LDA FX_COUNT
        STA FX_LOG+2,X
        LDA FX_VALUE
        STA FX_LOG+3,X
        INC FX_LOG_N
        RTS
