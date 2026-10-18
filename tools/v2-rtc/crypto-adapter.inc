; Private offline RAM adapter, pinned to the current shared-service layout.
; PA0=SCL, PA7=SDA. No calls through the public gateway while owning its lock.
VORA EQU $7FCF
VDDR EQU $7FC3
RTC_BUS_BUSY EQU 1
RTC_NACK EQU 2
RTC_TIMEOUT EQU 3
        INCLUDE "crypto-service-eq.inc"
HAL_CHECK:
        STZ CA_BROKEN
        STZ CA_FAULT_CODE
        STZ CA_FAULT_PHASE
        STZ CA_STOP_ERROR
        STZ CA_PHASE
        LDA $7D27
        BEQ CA_DISABLED
        CMP #1
        BNE CA_UNAVAILABLE
        LDX #2
CA_DESC:
        LDA $7D04,X
        CMP CA_EXPECT_DESC,X
        BNE CA_UNAVAILABLE
        DEX
        BPL CA_DESC
        LDA $7D07
        AND #2
        BEQ CA_UNAVAILABLE
        LDA $7D08
        BNE CA_UNAVAILABLE
        LDA $7D09
        CMP #$65
        BNE CA_UNAVAILABLE
        LDA $7D0A
        CMP #$FF
        BNE CA_UNAVAILABLE
        LDA $7D0B
        CMP #$64
        BNE CA_UNAVAILABLE
        LDA SVC_ACTIVE
        CMP #$FF
        BNE CA_UNAVAILABLE
        LDX #3
CA_SIGNATURE:
        LDA $6510,X
        CMP CA_EXPECT_I2,X
        BNE CA_UNAVAILABLE
        DEX
        BPL CA_SIGNATURE
        LDA SVC_READY
        AND #1
        BEQ CA_UNAVAILABLE
        ; Configuration defaults to unavailable; no probing arbitrary addresses.
        LDA CA_ENABLE
        CMP #$A5
        BNE CA_UNAVAILABLE
        LDA CA_ADDRESS
        CMP #8
        BCC CA_UNAVAILABLE
        CMP #$78
        BCS CA_UNAVAILABLE
        ; Never allow the managed EEPROM or RTC as the crypto target.
        CMP #$57
        BEQ CA_UNAVAILABLE
        CMP #$6F
        BEQ CA_UNAVAILABLE
        LDA CA_MHZ
        CMP #1
        BEQ CA_CLOCK_OK
        CMP #2
        BEQ CA_CLOCK_OK
        CMP #4
        BEQ CA_CLOCK_OK
        CMP #8
        BNE CA_UNAVAILABLE
CA_CLOCK_OK:
        ASL A
        ASL A
        ASL A
        ASL A
        STA CA_TICKS
        LDA #0
        RTS
CA_DISABLED:
        LDA #1
        RTS
CA_UNAVAILABLE:
        LDA #2
        RTS
HAL_CLAIM:
        LDA SVC_BUSY
        ORA SVC_DRIVER_BUSY
        BNE CA_BUSY
        INC SVC_BUSY
        STZ CA_INITIALIZED
        ; Refuse externally driven pins before changing direction or latch.
        LDA VDDR
        AND #$81
        BNE CA_IDLE_BAD
        LDA VORA
        AND #$81
        CMP #$81
        BNE CA_IDLE_BAD
        LDA #0
        RTS
CA_IDLE_BAD:
        LDA #1
        STA CA_FAULT_CODE
        STZ SVC_BUSY
        LDA #5
        RTS
CA_BUSY:
        LDA #3
        RTS
HAL_WAKE:
        JSR INIT
        INC CA_INITIALIZED
        BCC CA_WAKE_BAD
        LDA #6
        STA CA_PHASE
        JSR SDA_LOW
        JSR CA_DELAY
        JSR SDA_RELEASE
        LDA #200
        JSR CA_DELAY_UNITS
        LDA VORA
        AND #$81
        CMP #$81
        BNE CA_WAKE_BAD
        LDA #0
        RTS
CA_WAKE_BAD:
        LDA #1
        STA CA_RAW
        JSR CA_RECORD
        INC CA_BROKEN
        LDA #5
        RTS
HAL_SEND:
        LDA CA_BROKEN
        BNE CA_REFUSE
        JSR CA_BEGIN_WRITE
        BCC CA_FINISH
        STZ CA_INDEX
CA_SEND_BYTE:
        LDA #2
        STA CA_PHASE
        LDX CA_INDEX
        LDA TXBUF,X
        JSR WRITE_BYTE
        BCC CA_FINISH
        INC CA_INDEX
        LDA CA_INDEX
        CMP #8
        BNE CA_SEND_BYTE
        LDA #0
        BRA CA_FINISH
CA_REFUSE:
        LDA #5
        RTS
HAL_RECEIVE:
        LDA CA_BROKEN
        BNE CA_REFUSE
        STZ RXLEN
        LDA #3
        STA CA_PHASE
        JSR START_BUS
        BCC CA_FINISH
        LDA CA_ADDRESS
        ASL A
        ORA #1
        JSR WRITE_BYTE
        BCC CA_FINISH
        LDA #4
        STA CA_PHASE
        LDY #0
        JSR READ_BYTE
        BCC CA_FINISH
        STA RXLEN
        STA RXBUF
        CMP #4
        BEQ CA_RX_OK
        CMP #7
        BNE CA_BAD_COUNT
CA_RX_OK:
        LDA #1
        STA CA_INDEX
CA_RX_BYTE:
        LDY #0
        LDA CA_INDEX
        INC A
        CMP RXLEN
        BNE CA_RX_MORE
        INY
CA_RX_MORE:
        JSR READ_BYTE
        BCC CA_FINISH
        LDX CA_INDEX
        STA RXBUF,X
        INC CA_INDEX
        LDA CA_INDEX
        CMP RXLEN
        BNE CA_RX_BYTE
        LDA #0
        BRA CA_FINISH
CA_BAD_COUNT:
        ; Count was ACKed before its value was known. Receive one discard
        ; byte with NACK to terminate cleanly without indexing the RX buffer.
        LDY #1
        JSR READ_BYTE
        BCC CA_FINISH
        LDA #9
CA_FINISH:
        STA CA_RAW
        JSR CA_RECORD
        JSR STOP_BUS
        BCS CA_STOPPED
        LDA #3
        STA CA_STOP_ERROR
        LDA #5
        STA CA_PHASE
        LDA #3
        STA CA_RAW
        JSR CA_RECORD
        INC CA_BROKEN
CA_STOPPED:
        LDA CA_RAW
        BEQ CA_SUCCESS
        CMP #2
        BNE CA_OTHER_ERROR
        ; Only an address NACK with a successful STOP is retryable.
        LDA CA_PHASE
        CMP #1
        BEQ CA_NO_RESPONSE
        CMP #3
        BEQ CA_NO_RESPONSE
CA_OTHER_ERROR:
        INC CA_BROKEN
        LDA CA_RAW
        CMP #9
        BEQ CA_INVALID
        LDA #5
        RTS
CA_INVALID:
        LDA #6
        RTS
CA_NO_RESPONSE:
        LDA #4
        RTS
CA_SUCCESS:
        LDA #0
        RTS
CA_RECORD:
        LDA CA_RAW
        BEQ CA_RECORD_DONE
        LDX CA_FAULT_CODE
        BNE CA_RECORD_DONE
        STA CA_FAULT_CODE
        LDA CA_PHASE
        STA CA_FAULT_PHASE
CA_RECORD_DONE:
        RTS
CA_BEGIN_WRITE:
        LDA #1
        STA CA_PHASE
        JSR START_BUS
        BCC CA_BEGIN_DONE
        LDA CA_ADDRESS
        ASL A
        JSR WRITE_BYTE
CA_BEGIN_DONE:
        RTS
HAL_WAIT:
        LDA CA_BROKEN
        BNE CA_REFUSE
        LDA #50
        JSR CA_DELAY_UNITS
        LDA #0
        RTS
HAL_SLEEP:
        LDA CA_INITIALIZED
        BEQ CA_SUCCESS
        ; Attempt only Sleep, never another command, even after a bus fault.
        JSR CA_BEGIN_WRITE
        BCC CA_SLEEP_END
        LDA #2
        STA CA_PHASE
        LDA #1
        JSR WRITE_BYTE
CA_SLEEP_END:
        JSR CA_FINISH
        PHA
        ; A failed STOP may leave SDA driven low. Release both bus pins
        ; before restoring the observed latch, avoiding a driven-high glitch.
        LDA VDDR
        AND #$7E
        STA VDDR
        JSR RESTORE
        STZ CA_INITIALIZED
        PLA
        RTS
HAL_RELEASE:
        STZ SVC_BUSY
        RTS
; Generated long branches make the inner delay loop seven cycles/iteration
; except its final iteration. Timings are checked using linked CPU cycles.
CA_DELAY_UNITS:
        STA CA_WAIT_LEFT
CA_DELAY_NEXT:
        JSR CA_DELAY
        DEC CA_WAIT_LEFT
        BNE CA_DELAY_NEXT
        RTS
CA_DELAY:
        LDX CA_TICKS
CA_DELAY_LOOP:
        DEX
        BNE CA_DELAY_LOOP
        RTS
CA_EXPECT_DESC DB "SV",1
CA_EXPECT_I2 DB "I2",1,1
CA_ENABLE DB 0
CA_ADDRESS DB 0
CA_MHZ DB 0
CA_TICKS DB 0
CA_INITIALIZED DB 0
CA_BROKEN DB 0
CA_PHASE DB 0
CA_RAW DB 0
CA_FAULT_CODE DB 0
CA_FAULT_PHASE DB 0
CA_STOP_ERROR DB 0
CA_INDEX DB 0
CA_WAIT_LEFT DB 0
SAVEORA DB 0
SAVEDDR DB 0
BYTE DB 0
ACKBIT DB 0
        INCLUDE "crypto-wire.inc"
