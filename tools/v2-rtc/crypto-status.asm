; ATECC608A/B status engine. Standalone build has refusing hardware hooks.
; Foreground 65C02 / 816 emulation only; not reentrant.
; HAL slots below deliberately refuse hardware use. See crypto-status README.
        MODULE CRYPTO_STATUS
        XDEF START
        XDEF APP_END
        XDEF RESULT
        XDEF CLEANUP_ERROR
        XDEF VALID
        XDEF REVISION
        XDEF SERIAL
        XDEF LOCKS
        XDEF FIELD_ERRORS
        XDEF DEVICE_STATUS
        XDEF TXBUF
        XDEF RXBUF
        XDEF RXLEN
        XDEF HAL_CHECK
        XDEF HAL_CLAIM
        XDEF HAL_WAKE
        XDEF HAL_SEND
        XDEF HAL_RECEIVE
        XDEF HAL_WAIT
        XDEF HAL_SLEEP
        XDEF HAL_RELEASE
        CODE
START:  PHP
        SEI
        CLD
        STZ RESULT
        STZ CLEANUP_ERROR
        STZ VALID
        STZ DEVICE_STATUS
        STZ COMMAND_INDEX
        STZ SERIAL_FAILED
        LDX #12
CLEAR_ID:
        STZ REVISION,X
        DEX
        BPL CLEAR_ID
        LDA #$FF
        STA LOCKS
        STA LOCKS+1
        LDX #3
CLEAR_ERRORS:
        STA FIELD_ERRORS,X
        DEX
        BPL CLEAR_ERRORS
        JSR HAL_CHECK
        CMP #0
        BNE EARLY_ERROR
        JSR HAL_CLAIM
        CMP #0
        BNE EARLY_ERROR
        ; Claim succeeds before any wake or cleanup is attempted.
        JSR HAL_WAKE
        CMP #0
        BNE OWNED_ERROR
        ; HAL_WAKE includes recovery delay; receive wake packet only once.
        STZ RXLEN
        JSR HAL_RECEIVE
        CMP #0
        BNE OWNED_ERROR
        JSR CHECK_PACKET
        CMP #0
        BNE OWNED_ERROR
        LDA RXLEN
        CMP #4
        BNE INVALID_WAKE
        LDA RXBUF+1
        CMP #$11
        BNE INVALID_WAKE
        BRA COMMAND_LOOP
INVALID_WAKE:
        LDA #6
        BRA OWNED_ERROR
EARLY_ERROR:
        STA RESULT
        JMP RETURN
OWNED_ERROR:
        STA RESULT
        JMP CLEANUP
COMMAND_LOOP:
        ; Five immutable commands: Info, three serial words, lock word.
        LDA COMMAND_INDEX
        ASL A
        ASL A
        ASL A
        TAY
        LDX #0
COPY_COMMAND:
        LDA COMMANDS,Y
        STA TXBUF,X
        INY
        INX
        CPX #8
        BNE COPY_COMMAND
        JSR HAL_SEND
        CMP #0
        BNE COMMAND_ERROR
        LDA #8
        STA POLLS
POLL:   JSR HAL_WAIT
        CMP #0
        BNE COMMAND_ERROR
        STZ RXLEN
        JSR HAL_RECEIVE
        CMP #4
        BNE RECEIVED
        DEC POLLS
        BNE POLL
        LDA #4
RECEIVED:
        CMP #0
        BNE COMMAND_ERROR
        JSR CHECK_PACKET
        CMP #0
        BNE COMMAND_ERROR
        LDA RXLEN
        CMP #7
        BEQ COMMAND_DATA
        ; A CRC-valid four-byte command response is a device status packet,
        ; never successful Info/Read data, even if the status byte is zero.
        LDA RXBUF+1
        STA DEVICE_STATUS
        LDA #7
        BRA COMMAND_ERROR
COMMAND_DATA:
        LDA COMMAND_INDEX
        BNE PUBLIC_FIELD
        LDX #3
COPY_REVISION:
        LDA RXBUF+1,X
        STA REVISION,X
        CPX #3
        BNE COMPARE_REVISION
        CMP #3
        BEQ REVISION_BYTE_OK
COMPARE_REVISION:
        CMP EXPECT_REV,X
        BNE UNKNOWN_REVISION
REVISION_BYTE_OK:
        DEX
        BPL COPY_REVISION
        LDA #1
        STA VALID
        BRA NEXT_COMMAND
UNKNOWN_REVISION:
        ; Retain all raw revision bytes, including an unsupported revision.
        LDX #3
COPY_UNKNOWN:
        LDA RXBUF+1,X
        STA REVISION,X
        DEX
        BPL COPY_UNKNOWN
        LDA #8
        JMP OWNED_ERROR
PUBLIC_FIELD:
        DEC A
        TAX
        STZ FIELD_ERRORS,X
        LDA COMMAND_INDEX
        CMP #4
        BEQ COPY_LOCKS
        CMP #3
        BEQ SERIAL_LAST
        CMP #2
        BEQ SERIAL_MIDDLE
        LDY #0
        BRA SERIAL_COPY
SERIAL_MIDDLE:
        LDY #4
SERIAL_COPY:
        LDX #0
SERIAL_BYTE:
        LDA RXBUF+1,X
        STA SERIAL,Y
        INY
        INX
        CPX #4
        BNE SERIAL_BYTE
        BRA NEXT_COMMAND
SERIAL_LAST:
        LDA RXBUF+1
        STA SERIAL+8
        BRA NEXT_COMMAND
COPY_LOCKS:
        LDA RXBUF+3
        STA LOCKS
        JSR LOCK_VALID
        BNE BAD_LOCKS
        LDA RXBUF+4
        STA LOCKS+1
        JSR LOCK_VALID
        BNE BAD_LOCKS
        LDA VALID
        ORA #4
        STA VALID
        BRA NEXT_COMMAND
BAD_LOCKS:
        LDA #6
COMMAND_ERROR:
        LDX COMMAND_INDEX
        BEQ INFO_ERROR
        DEX
        STA FIELD_ERRORS,X
        CPX #3
        BEQ NEXT_COMMAND
        INC SERIAL_FAILED
NEXT_COMMAND:
        INC COMMAND_INDEX
        LDA COMMAND_INDEX
        CMP #5
        BNE COMMAND_LOOP
        LDA SERIAL_FAILED
        BNE CLEAR_SERIAL
        LDA VALID
        ORA #2
        STA VALID
        BRA CLEANUP
CLEAR_SERIAL:
        LDX #8
CLEAR_PARTIAL:
        STZ SERIAL,X
        DEX
        BPL CLEAR_PARTIAL
        BRA CLEANUP
INFO_ERROR:
        JMP OWNED_ERROR
CLEANUP:
        JSR HAL_SLEEP
        STA CLEANUP_ERROR
        JSR HAL_RELEASE
RETURN: PLP
        LDA RESULT
        RTS
LOCK_VALID:
        CMP #0
        BEQ LOCK_OK
        CMP #$55
LOCK_OK:
        RTS
; Reject lengths before indexing. CRC-16/0x8005, input bits LSB first,
; register shifts left; packet CRC stored low byte first.
CHECK_PACKET:
        LDA RXLEN
        CMP #4
        BEQ LENGTH_OK
        CMP #7
        BNE PACKET_BAD
LENGTH_OK:
        CMP RXBUF
        BNE PACKET_BAD
        SEC
        SBC #2
        STA CRC_COUNT
        STZ CRC_LO
        STZ CRC_HI
        LDY #0
CRC_BYTE:
        LDA RXBUF,Y
        STA CRC_INPUT
        LDX #8
CRC_BIT:
        ; Need input bit0 XOR register bit15.
        LDA CRC_HI
        ASL A
        LDA #0
        ROL A
        EOR CRC_INPUT
        AND #1
        STA CRC_MIX
        ASL CRC_LO
        ROL CRC_HI
        LDA CRC_MIX
        BEQ CRC_NO_XOR
        LDA CRC_LO
        EOR #5
        STA CRC_LO
        LDA CRC_HI
        EOR #$80
        STA CRC_HI
CRC_NO_XOR:
        LSR CRC_INPUT
        DEX
        BNE CRC_BIT
        INY
        CPY CRC_COUNT
        BNE CRC_BYTE
        LDA RXBUF,Y
        CMP CRC_LO
        BNE PACKET_BAD
        INY
        LDA RXBUF,Y
        CMP CRC_HI
        BNE PACKET_BAD
        LDA #0
        RTS
PACKET_BAD:
        LDA #6
        RTS
; Fail-closed slots. A future qualified adapter replaces these routines.
HAL_CHECK:
        LDA #2
        RTS
HAL_CLAIM:
        LDA #5
        RTS
HAL_WAKE:
        LDA #5
        RTS
HAL_SEND:
        LDA #5
        RTS
HAL_RECEIVE:
        LDA #5
        RTS
HAL_WAIT:
        LDA #5
        RTS
HAL_SLEEP:
        LDA #5
        RTS
HAL_RELEASE:
        RTS
EXPECT_REV DB $00,$00,$60,$02
        INCLUDE "crypto-commands.inc"
RESULT DB 0
CLEANUP_ERROR DB 0
VALID DB 0
DEVICE_STATUS DB 0
REVISION DS 4
SERIAL DS 9
LOCKS DS 2
FIELD_ERRORS DS 4
COMMAND_INDEX DB 0
SERIAL_FAILED DB 0
POLLS DB 0
CRC_LO DB 0
CRC_HI DB 0
CRC_COUNT DB 0
CRC_INPUT DB 0
CRC_MIX DB 0
TXBUF DS 8
RXLEN DB 0
RXBUF DS 7
APP_END:
        ENDMOD
        END
