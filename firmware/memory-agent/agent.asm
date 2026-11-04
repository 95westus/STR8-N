; MEMORY1 RAM service, WDC SXB + EDU Rev D, FT245 only.
; 65C02 / 65C816 E=1, D=DBR=PBR=0. Code and all flash polling in RAM.
; Header: op,bank,addr LE24,count LE16,CRC16 LE (CCITT init FFFF).
; Write header followed by complete payload+CRC, staged BEFORE mutation.
; Reply: status,count LE16,payload,CRC16 LE over status/count/payload.
; No retries, no reset, no calendar/factory EEPROM writes. F is protected.
        MODULE MEMORY_AGENT
        XDEF START
        XDEF AGENT_END
P EQU $E0
B EQU $E2
BUF EQU $2000
CTRL EQU $7FE0
DATA EQU $7FE1
DDRA EQU $7FE3
PCR EQU $7FEC
ORB EQU $7FC0
DDRB EQU $7FC2
VORA EQU $7FCF
VDDR EQU $7FC3
        CODE
START:
        SEI
        CLD
        LDA $F4
        STA OLD_NMI
        LDA #1
        STA $F4
        STZ DDRA
        LDA #$0C
        STA CTRL
        LDX #0
BANNER_LOOP:
        LDA BANNER,X
        BEQ COMMAND
        JSR TX
        INX
        BRA BANNER_LOOP
COMMAND:
        STZ QUIT_FLAG
        STZ STATUS
        STZ OUTLEN
        STZ OUTLEN+1
        JSR CRC_INIT
        LDY #0
HEADER_LOOP:
        JSR RX
        STA HEADER,Y
        JSR CRC_BYTE
        INY
        CPY #7
        BNE HEADER_LOOP
        JSR CHECK_CRC
        BCC HEADER_BAD
        LDA OP
        CMP #$7F
        BNE NORMAL_HEADER
        LDA BANK
        ORA ADDR
        ORA ADDR+1
        ORA ADDR+2
        ORA LEN
        ORA LEN+1
        BNE HEADER_BAD
        INC QUIT_FLAG
        JMP REPLY
NORMAL_HEADER:
        LDA LEN+1
        CMP #$10
        BCC HEADER_SIZE_OK
        BNE HEADER_BAD
        LDA LEN
        BNE HEADER_BAD
HEADER_SIZE_OK:
        LDA LEN
        ORA LEN+1
        BEQ HEADER_BAD
        LDA OP
        BPL EXECUTE
        JSR BUFFER_PTR
        JSR CRC_INIT
        JSR COUNT_INIT
RECEIVE_LOOP:
        JSR RX
        STA (B)
        JSR CRC_BYTE
        INC B
        BNE RECEIVE_NEXT
        INC B+1
RECEIVE_NEXT:
        JSR COUNT_DOWN
        BNE RECEIVE_LOOP
        JSR CHECK_CRC
        BCC HEADER_BAD
EXECUTE:
        LDA OP
        AND #$7F
        CMP #1
        BEQ FLASH
        CMP #2
        BEQ SPI
        CMP #3
        BEQ EEPROM
        CMP #4
        BEQ RAM
        CMP #5
        BEQ ZERO_PAGE
        CMP #6
        BEQ SPI_MODE
HEADER_BAD:
        LDA #1
        STA STATUS
        JMP REPLY
FLASH:
        LDA BANK
        CMP #4
        BCS HEADER_BAD
        LDA ADDR+2
        BNE HEADER_BAD
        LDA ADDR+1
        BMI FLASH_ADDR_OK
        JMP HEADER_BAD
FLASH_ADDR_OK:
        JSR END_ADDRESS
        BCC FLASH_END_OK
        LDA ENDADDR
        ORA ENDADDR+1
        BNE HEADER_BAD
FLASH_END_OK:
        LDA OP
        BPL FLASH_READ
        LDA ADDR
        BNE HEADER_BAD
        LDA ADDR+1
        AND #$0F
        BNE HEADER_BAD
        LDA LEN
        BNE HEADER_BAD
        LDA LEN+1
        CMP #$10
        BNE HEADER_BAD
        LDA BANK
        CMP #3
        BNE FLASH_WRITE_OK
        LDA ADDR+1
        CMP #$F0
        BCS HEADER_BAD
FLASH_WRITE_OK:
        JSR FLASH_WRITE
        JMP REPLY
FLASH_READ:
        LDA BANK
        JSR SELECT_BANK
        JSR ADDRESS_PTR
        JSR BUFFER_PTR
        JSR COUNT_INIT
FLASH_READ_LOOP:
        LDA (P)
        STA (B)
        JSR POINTER_NEXT
        JSR COUNT_DOWN
        BNE FLASH_READ_LOOP
        LDA #3
        JSR SELECT_BANK
        JMP BUFFER_REPLY
RAM:
        LDA ADDR+2
        BNE HEADER_BAD
        LDA ADDR+1
        CMP #2
        BCC HEADER_BAD
        JSR END_ADDRESS
        BCS HEADER_BAD
        LDA ENDADDR+1
        CMP #$67
        BCC RAM_OK
        BNE HEADER_BAD
        LDA ENDADDR
        BNE HEADER_BAD
RAM_OK:
        JSR ADDRESS_PTR
        BRA RAM_COMMON
ZERO_PAGE:
        LDA ADDR
        ORA ADDR+1
        ORA ADDR+2
        ORA LEN+1
        BNE HEADER_BAD
        LDA LEN
        CMP #$E0
        BNE HEADER_BAD
        STZ P
        STZ P+1
RAM_COMMON:
        LDA OP
        BPL DIRECT_REPLY
        JSR BUFFER_PTR
        JSR COUNT_INIT
RAM_WRITE_LOOP:
        LDA (B)
        STA (P)
        JSR POINTER_NEXT
        JSR COUNT_DOWN
        BNE RAM_WRITE_LOOP
        JMP REPLY
DIRECT_REPLY:
        LDA LEN
        STA OUTLEN
        LDA LEN+1
        STA OUTLEN+1
        JMP REPLY_SOURCE
SPI_MODE:
        LDA ADDR
        ORA ADDR+1
        ORA ADDR+2
        ORA LEN+1
        BNE HEADER_BAD
        LDA LEN
        CMP #1
        BNE HEADER_BAD
        LDA OP
        BPL MODE_VALID
        LDA BUF
        AND #$3F
        BNE HEADER_BAD
        LDA BUF
        CMP #$C0
        BEQ HEADER_BAD
MODE_VALID:
        JSR SPI_INIT
        BCC IO_BAD
        LDA #5
        BIT OP
        BPL MODE_COMMAND
        LDA #1
MODE_COMMAND:
        JSR SPI_COMMAND
        LDA BUF
        JSR SPI_BYTE
        STA TEMP
        JSR SPI_RESTORE
        LDA OP
        BMI MODE_WRITE_DONE
        LDA TEMP
        STA BUF
        JMP BUFFER_REPLY
MODE_WRITE_DONE:
        JMP REPLY
SPI:
        ; Byte-addressed transactions preserve byte/page/sequential mode.
        LDA ADDR+2
        CMP #2
        BCS HEADER_BAD
        LDA LEN+1
        CMP #1
        BCC SPI_SIZE_OK
        BNE HEADER_BAD
        LDA LEN
        BNE HEADER_BAD
SPI_SIZE_OK:
        JSR END_ADDRESS
        LDA ADDR+2
        ADC #0
        CMP #2
        BCC SPI_RANGE_OK
        BNE HEADER_BAD
        LDA ENDADDR
        ORA ENDADDR+1
        BNE HEADER_BAD
SPI_RANGE_OK:
        JSR SPI_INIT
        BCC IO_BAD
        JSR BUFFER_PTR
        JSR COUNT_INIT
SPI_LOOP:
        LDA #3
        BIT OP
        BPL SPI_COMMAND_READY
        LDA #2
SPI_COMMAND_READY:
        JSR SPI_COMMAND
        LDA ADDR+2
        JSR SPI_BYTE
        LDA ADDR+1
        JSR SPI_BYTE
        LDA ADDR
        JSR SPI_BYTE
        LDA (B)
        JSR SPI_BYTE
        BIT OP
        BMI SPI_WRITTEN
        STA (B)
SPI_WRITTEN:
        JSR SPI_DESELECT
        INC B
        BNE SPI_ADDR_NEXT
        INC B+1
SPI_ADDR_NEXT:
        INC ADDR
        BNE SPI_COUNT
        INC ADDR+1
        BNE SPI_COUNT
        INC ADDR+2
SPI_COUNT:
        JSR COUNT_DOWN
        BNE SPI_LOOP
        JSR SPI_RESTORE
        LDA OP
        BMI SPI_WRITE_DONE
        JMP BUFFER_REPLY
SPI_WRITE_DONE:
        JMP REPLY
IO_BAD:
        LDA #2
        STA STATUS
        JMP REPLY
EEPROM:
        LDA ADDR+1
        ORA ADDR+2
        ORA LEN+1
        BNE HEADER_BAD
        LDA ADDR
        CMP #$80
        BCS HEADER_BAD
        CLC
        ADC LEN
        BCS HEADER_BAD
        CMP #$81
        BCS HEADER_BAD
        LDA OP
        BPL EE_SIZE_OK
        ; 8-byte physical pages: host never crosses one.
        LDA ADDR
        AND #7
        CLC
        ADC LEN
        CMP #9
        BCS HEADER_BAD
EE_SIZE_OK:
        JSR I2C_INIT
        BCC EE_RESTORE_BAD
        JSR I2C_START
        BCC EE_STOP_BAD
        LDA #$AE
        JSR I2C_WRITE
        BCC EE_STOP_BAD
        LDA ADDR
        JSR I2C_WRITE
        BCC EE_STOP_BAD
        JSR BUFFER_PTR
        JSR COUNT_INIT
        LDA OP
        BMI EE_WRITE_LOOP
        JSR I2C_START
        BCC EE_STOP_BAD
        LDA #$AF
        JSR I2C_WRITE
        BCC EE_STOP_BAD
EE_READ_LOOP:
        LDY #0
        LDA LEFT
        CMP #1
        BNE EE_READ_NEXT
        INY
EE_READ_NEXT:
        JSR I2C_READ
        BCC EE_STOP_BAD
        STA (B)
        INC B
        BNE EE_READ_COUNT
        INC B+1
EE_READ_COUNT:
        JSR COUNT_DOWN
        BNE EE_READ_LOOP
        JSR I2C_STOP
        BCC EE_RESTORE_BAD
        JSR I2C_RESTORE
        JMP BUFFER_REPLY
EE_WRITE_LOOP:
        LDA (B)
        JSR I2C_WRITE
        BCC EE_STOP_BAD
        INC B
        BNE EE_WRITE_COUNT
        INC B+1
EE_WRITE_COUNT:
        JSR COUNT_DOWN
        BNE EE_WRITE_LOOP
        JSR I2C_STOP
        BCC EE_RESTORE_BAD
        ; Bounded ACK polling for the EEPROM write cycle.
        LDA #$FF
        STA RETRIES
EE_POLL:
        JSR I2C_START
        BCC EE_STOP_BAD
        LDA #$AE
        JSR I2C_WRITE
        PHP
        JSR I2C_STOP
        PLP
        BCS EE_WRITE_DONE
        DEC RETRIES
        BNE EE_POLL
        BRA EE_RESTORE_BAD
EE_WRITE_DONE:
        JSR I2C_RESTORE
        JMP REPLY
EE_STOP_BAD:
        JSR I2C_STOP
EE_RESTORE_BAD:
        JSR I2C_RESTORE
        JMP IO_BAD
BUFFER_REPLY:
        STZ P
        LDA #>BUF
        STA P+1
        JMP DIRECT_REPLY
REPLY:
        STZ P
        STZ P+1
REPLY_SOURCE:
        JSR CRC_INIT
        LDA STATUS
        JSR SEND_CRC
        LDA OUTLEN
        JSR SEND_CRC
        LDA OUTLEN+1
        JSR SEND_CRC
        LDA OUTLEN
        STA LEFT
        LDA OUTLEN+1
        STA LEFT+1
        ORA LEFT
        BEQ REPLY_SUM
REPLY_LOOP:
        LDA (P)
        JSR SEND_CRC
        INC P
        BNE REPLY_COUNT
        INC P+1
REPLY_COUNT:
        JSR COUNT_DOWN
        BNE REPLY_LOOP
REPLY_SUM:
        LDA SUM
        JSR TX
        LDA SUM+1
        JSR TX
        LDA QUIT_FLAG
        BEQ REPLY_CONTINUE
        LDA OLD_NMI
        STA $F4
        JMP RECOVERY_ENTRY
REPLY_CONTINUE:
        JMP COMMAND
SEND_CRC:
        PHA
        JSR CRC_BYTE
        PLA
        JMP TX
CRC_INIT:
        LDA #$FF
        STA SUM
        STA SUM+1
        RTS
CRC_BYTE:
        EOR SUM+1
        STA SUM+1
        LDX #8
CRC_BIT:
        ASL SUM
        ROL SUM+1
        BCC CRC_NEXT
        LDA SUM
        EOR #$21
        STA SUM
        LDA SUM+1
        EOR #$10
        STA SUM+1
CRC_NEXT:
        DEX
        BNE CRC_BIT
        RTS
CHECK_CRC:
        JSR RX
        CMP SUM
        BNE CHECK_BAD
        JSR RX
        CMP SUM+1
        BNE CHECK_FAIL
        SEC
        RTS
CHECK_BAD:
        JSR RX
CHECK_FAIL:
        CLC
        RTS
COUNT_INIT:
        LDA LEN
        STA LEFT
        LDA LEN+1
        STA LEFT+1
        RTS
COUNT_DOWN:
        LDA LEFT
        BNE COUNT_LOW
        DEC LEFT+1
COUNT_LOW:
        DEC LEFT
        LDA LEFT
        ORA LEFT+1
        RTS
END_ADDRESS:
        CLC
        LDA ADDR
        ADC LEN
        STA ENDADDR
        LDA ADDR+1
        ADC LEN+1
        STA ENDADDR+1
        RTS
ADDRESS_PTR:
        LDA ADDR
        STA P
        LDA ADDR+1
        STA P+1
        RTS
BUFFER_PTR:
        STZ B
        LDA #>BUF
        STA B+1
        RTS
POINTER_NEXT:
        INC P
        BNE POINTER_BUFFER
        INC P+1
POINTER_BUFFER:
        INC B
        BNE POINTER_DONE
        INC B+1
POINTER_DONE:
        RTS
SELECT_BANK:
        TAX
        LDA PCR
        AND #$11
        ORA BANK_BITS,X
        STA PCR
        RTS
RX:
        LDA #2
        BIT CTRL
        BNE RX
        LDA #8
        TRB CTRL
        NOP
        NOP
        LDA DATA
        PHA
        LDA #8
        TSB CTRL
        PLA
        RTS
TX:
        PHA
TX_WAIT:
        LDA #1
        BIT CTRL
        BNE TX_WAIT
        PLA
        STA DATA
        NOP
        NOP
        LDA #4
        TSB CTRL
        DEC DDRA
        NOP
        NOP
        LDA #4
        TRB CTRL
        STZ DDRA
        RTS
FLASH_WRITE:
        LDA BANK
        JSR SELECT_BANK
        JSR ADDRESS_PTR
        JSR BUFFER_PTR
        JSR COUNT_INIT
FLASH_COMPARE:
        LDA (P)
        CMP (B)
        BNE FLASH_ERASE
        JSR POINTER_NEXT
        JSR COUNT_DOWN
        BNE FLASH_COMPARE
        BRA FLASH_FINISH
FLASH_ERASE:
        JSR ADDRESS_PTR
        JSR UNLOCK
        LDA #$80
        STA $D555
        JSR UNLOCK
        LDA #$30
        STA (P)
        LDA #$FF
        STA EXPECT
        JSR FLASH_WAIT
        BCC FLASH_FAIL
        JSR BUFFER_PTR
        JSR COUNT_INIT
FLASH_PROGRAM:
        LDA (B)
        CMP #$FF
        BEQ FLASH_PROGRAM_NEXT
        STA EXPECT
        JSR UNLOCK
        LDA #$A0
        STA $D555
        LDA EXPECT
        STA (P)
        JSR FLASH_WAIT
        BCC FLASH_FAIL
FLASH_PROGRAM_NEXT:
        JSR POINTER_NEXT
        JSR COUNT_DOWN
        BNE FLASH_PROGRAM
        JSR ADDRESS_PTR
        JSR BUFFER_PTR
        JSR COUNT_INIT
FLASH_VERIFY:
        LDA (P)
        CMP (B)
        BNE FLASH_FAIL
        JSR POINTER_NEXT
        JSR COUNT_DOWN
        BNE FLASH_VERIFY
        BRA FLASH_FINISH
FLASH_FAIL:
        LDA #3
        STA STATUS
FLASH_FINISH:
        LDA #$F0
        STA $D555
        LDA #3
        JMP SELECT_BANK
UNLOCK:
        LDA #$AA
        STA $D555
        LDA #$55
        STA $AAAA
        RTS
FLASH_WAIT:
        LDA #8
        STA RETRIES
        LDX #0
        LDY #0
FLASH_POLL:
        LDA (P)
        CMP EXPECT
        BEQ FLASH_READY
        DEX
        BNE FLASH_POLL
        DEY
        BNE FLASH_POLL
        DEC RETRIES
        BNE FLASH_POLL
        CLC
        RTS
FLASH_READY:
        SEC
        RTS
SPI_INIT:
        ; Refuse active serial/handshake use; no WRMR or format command.
        LDA $7FCB
        AND #$1E
        BNE SPI_INIT_BAD
        LDA $7FCC
        AND #$F0
        BNE SPI_INIT_BAD
        LDA $7FCE
        AND #$18
        BNE SPI_INIT_BAD
        LDA DDRB
        AND #$2F
        BNE SPI_INIT_BAD
        LDA DDRB
        STA OLD_DDR
        LDA ORB
        STA OLD_PORT
        AND #$FC
        ORA #$0C
        STA PORT
        STA ORB
        LDA OLD_DDR
        AND #$DF
        ORA #$0F
        STA DDRB
        SEC
        RTS
SPI_INIT_BAD:
        CLC
        RTS
SPI_COMMAND:
        PHA
        LDA PORT
        AND #$FB
        STA PORT
        STA ORB
        PLA
        JMP SPI_BYTE
SPI_DESELECT:
        LDA PORT
        ORA #$0C
        STA PORT
        STA ORB
        RTS
SPI_RESTORE:
        JSR SPI_DESELECT
        LDA OLD_DDR
        STA DDRB
        LDA OLD_PORT
        STA ORB
        RTS
SPI_BYTE:
        STA SHIFT
        LDX #8
SPI_BIT:
        LDA #2
        TRB PORT
        ASL SHIFT
        BCC SPI_ZERO
        TSB PORT
SPI_ZERO:
        LDA PORT
        STA ORB
        INC A
        STA ORB
        LDA ORB
        ASL A
        ASL A
        ASL A
        ROL RECEIVED
        LDA PORT
        STA ORB
        DEX
        BNE SPI_BIT
        LDA RECEIVED
        RTS
        INCLUDE "i2c.inc"
BANNER: DB "STR8-N UTIL MEMORY 0.1.0",13,10,"Copyright (c) 2026 95west.us/wlp1963; MIT",13,10,"MEMORY1> ",0
BANK_BITS: DB $CC,$CE,$EC,$EE
HEADER:
OP: DB 0
BANK: DB 0
ADDR: DB 0,0,0
LEN: DB 0,0
STATUS: DB 0
OUTLEN: DB 0,0
SUM: DB 0,0
LEFT: DB 0,0
ENDADDR: DB 0,0
OLD_DDR: DB 0
OLD_PORT: DB 0
PORT: DB 0
SHIFT: DB 0
RECEIVED: DB 0
EXPECT: DB 0
RETRIES: DB 0
TEMP: DB 0
SAVEORA: DB 0
SAVEDDR: DB 0
BYTE: DB 0
ACKBIT: DB 0
OLD_NMI: DB 0
QUIT_FLAG: DB 0
AGENT_END:
        ENDMOD
        END
