; RAM-only foreground status client. Launch at $2800 under the STR8-N RAM ABI.
; Adapter is separately linked at $2000; target/clock are explicitly configured.
        MODULE CRYPTO_DISPLAY
        XDEF CLIENT_START
        XDEF CLIENT_END
        INCLUDE "crypto-symbols.inc"
        CODE
CLIENT_START:
        CLD
        ; Validate discovery before touching service RAM or calling RTC STATUS.
        LDA $7D27
        BEQ RUN_ENGINE
        CMP #1
        BNE CLIENT_UNAVAILABLE
        LDX #2
CHECK_DESC:
        LDA $7D04,X
        CMP DESC_MAGIC,X
        BNE CLIENT_UNAVAILABLE
        DEX
        BPL CHECK_DESC
        LDA $7D07
        AND #3
        CMP #3
        BNE CLIENT_UNAVAILABLE
        LDA $7D08
        BNE CLIENT_UNAVAILABLE
        LDA $7D09
        CMP #$65
        BNE CLIENT_UNAVAILABLE
        LDA $7D0A
        CMP #$FF
        BNE CLIENT_UNAVAILABLE
        LDA $7D0B
        CMP #$64
        BNE CLIENT_UNAVAILABLE
        LDX #3
CHECK_SIGNATURES:
        LDA $6500,X
        CMP CLOCK_MAGIC,X
        BNE CLIENT_UNAVAILABLE
        LDA $6510,X
        CMP BUS_MAGIC,X
        BNE CLIENT_UNAVAILABLE
        DEX
        BPL CHECK_SIGNATURES
        ; HOLD clears verification. A normal, read-only RTC STATUS call
        ; revalidates the shared component; crypto itself needs no RTC device.
        JSR $6507
RUN_ENGINE:
        JSR START
        BRA DISPLAY
CLIENT_UNAVAILABLE:
        LDA #2
        STA RESULT
        STZ VALID
        STZ CLEANUP_ERROR
DISPLAY:
        LDX #<TITLE
        LDY #>TITLE
        JSR PUTS
        LDX #<STATUS_LABEL
        LDY #>STATUS_LABEL
        JSR PUTS
        LDA RESULT
        JSR STATUS_TEXT
        JSR NEWLINE
        LDX #<DEVICE_LABEL
        LDY #>DEVICE_LABEL
        JSR PUTS
        LDA VALID
        AND #1
        BEQ DEVICE_UNKNOWN
        LDX #<PART_A
        LDY #>PART_A
        LDA REVISION+3
        CMP #2
        BEQ DEVICE_PRINT
        LDX #<PART_B
        LDY #>PART_B
        BRA DEVICE_PRINT
DEVICE_UNKNOWN:
        LDX #<UNKNOWN
        LDY #>UNKNOWN
DEVICE_PRINT:
        JSR PUTS
        JSR NEWLINE
        LDX #<ADDRESS_LABEL
        LDY #>ADDRESS_LABEL
        JSR PUTS
        LDA CA_ADDRESS
        JSR HEX
        JSR NEWLINE
        LDX #<REVISION_LABEL
        LDY #>REVISION_LABEL
        JSR PUTS
        LDA VALID
        AND #1
        BNE REVISION_PRINT
        LDA RESULT
        CMP #8
        BNE REVISION_UNKNOWN
REVISION_PRINT:
        STZ INDEX
REVISION_NEXT:
        LDX INDEX
        LDA REVISION,X
        JSR HEX
        LDA #' '
        JSR OUT
        INC INDEX
        LDA INDEX
        CMP #4
        BNE REVISION_NEXT
        BRA REVISION_DONE
REVISION_UNKNOWN:
        JSR PRINT_UNKNOWN
REVISION_DONE:
        JSR NEWLINE
        LDX #<SERIAL_LABEL
        LDY #>SERIAL_LABEL
        JSR PUTS
        LDA VALID
        AND #2
        BEQ SERIAL_UNKNOWN
        STZ INDEX
SERIAL_NEXT:
        LDX INDEX
        LDA SERIAL,X
        JSR HEX
        INC INDEX
        LDA INDEX
        CMP #9
        BNE SERIAL_NEXT
        BRA SERIAL_DONE
SERIAL_UNKNOWN:
        JSR PRINT_UNKNOWN
SERIAL_DONE:
        JSR NEWLINE
        LDX #<CONFIG_LABEL
        LDY #>CONFIG_LABEL
        JSR PUTS
        LDA LOCKS+1
        JSR LOCK_TEXT
        JSR NEWLINE
        LDX #<DATA_LABEL
        LDY #>DATA_LABEL
        JSR PUTS
        LDA LOCKS
        JSR LOCK_TEXT
        JSR NEWLINE
        LDA VALID
        AND #1
        BEQ NO_FIELD_ERRORS
        LDA FIELD_ERRORS
        ORA FIELD_ERRORS+1
        ORA FIELD_ERRORS+2
        ORA FIELD_ERRORS+3
        BEQ NO_FIELD_ERRORS
        LDX #<FIELD_LABEL
        LDY #>FIELD_LABEL
        JSR PUTS
        STZ INDEX
FIELD_NEXT:
        LDX INDEX
        LDA FIELD_ERRORS,X
        JSR HEX
        LDA #' '
        JSR OUT
        INC INDEX
        LDA INDEX
        CMP #4
        BNE FIELD_NEXT
        JSR NEWLINE
NO_FIELD_ERRORS:
        LDX #<CLEANUP_LABEL
        LDY #>CLEANUP_LABEL
        JSR PUTS
        LDA CLEANUP_ERROR
        BNE CLEANUP_BAD
        LDX #<OK_TEXT
        LDY #>OK_TEXT
        JSR PUTS
        BRA FINISH
CLEANUP_BAD:
        JSR STATUS_TEXT
FINISH:
        JSR NEWLINE
        JMP $7E67
LOCK_TEXT:
        PHA
        LDA VALID
        AND #4
        BEQ LOCK_UNKNOWN
        PLA
        BEQ LOCKED
        CMP #$55
        BNE PRINT_UNKNOWN
        LDX #<UNLOCKED_TEXT
        LDY #>UNLOCKED_TEXT
        BRA PUTS
LOCKED:
        LDX #<LOCKED_TEXT
        LDY #>LOCKED_TEXT
        BRA PUTS
LOCK_UNKNOWN:
        PLA
PRINT_UNKNOWN:
        LDX #<UNKNOWN
        LDY #>UNKNOWN
        BRA PUTS
STATUS_TEXT:
        CMP #9
        BCC STATUS_VALID
        LDA #9
STATUS_VALID:
        TAX
        LDA STATUS_HIGH,X
        TAY
        LDA STATUS_LOW,X
        TAX
PUTS:
        STX PRINT_LOAD+1
        STY PRINT_LOAD+2
PRINT_LOAD:
        LDA $FFFF
        BEQ PRINT_DONE
        JSR OUT
        INC PRINT_LOAD+1
        BNE PRINT_LOAD
        INC PRINT_LOAD+2
        BRA PRINT_LOAD
PRINT_DONE:
        RTS
HEX:
        PHA
        LSR A
        LSR A
        LSR A
        LSR A
        JSR NIBBLE
        PLA
        AND #$0F
NIBBLE:
        CMP #10
        BCC DIGIT
        ADC #6
DIGIT:
        ADC #'0'
OUT:
        JMP $7E6D
NEWLINE:
        LDA #13
        JSR OUT
        LDA #10
        JMP OUT
DESC_MAGIC DB "SV",1
CLOCK_MAGIC DB "RG",1,4
BUS_MAGIC DB "I2",1,1
INDEX DB 0
TITLE DB 13,10,"CRYPTO STATUS (RAM)",13,10,0
STATUS_LABEL DB "Status:        ",0
DEVICE_LABEL DB "Device:        ",0
ADDRESS_LABEL DB "I2C address:   $",0
REVISION_LABEL DB "Revision:      ",0
SERIAL_LABEL DB "Serial:        ",0
CONFIG_LABEL DB "Configuration: ",0
DATA_LABEL DB "Data/OTP:      ",0
FIELD_LABEL DB "Field errors:  ",0
CLEANUP_LABEL DB "Cleanup:       ",0
PART_A DB "ATECC608A",0
PART_B DB "ATECC608B",0
UNKNOWN DB "unknown",0
LOCKED_TEXT DB "LOCKED",0
UNLOCKED_TEXT DB "UNLOCKED",0
OK_TEXT DB "OK",0
STATUS_LOW DB <S0,<S1,<S2,<S3,<S4,<S5,<S6,<S7,<S8,<S9
STATUS_HIGH DB >S0,>S1,>S2,>S3,>S4,>S5,>S6,>S7,>S8,>S9
S0 DB "Present",0
S1 DB "Disabled (EDU OFF)",0
S2 DB "Service unavailable",0
S3 DB "Busy",0
S4 DB "Not responding",0
S5 DB "Bus error",0
S6 DB "Invalid response",0
S7 DB "Device error",0
S8 DB "Unrecognized device",0
S9 DB "Unknown error",0
CLIENT_END:
        ENDMOD
        END
