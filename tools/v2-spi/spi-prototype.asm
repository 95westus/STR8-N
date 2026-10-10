; W65C02S RAM prototype. No flash/PCR access; shared foreground bus lock.
        MODULE SPI_PROTO
        XDEF START
        XDEF CORE_END
        XDEF CORE_BEGIN
        XDEF PUBLIC_SPI
        XDEF PUBLIC_SRAM
        INCLUDE "provider-private.inc"
        CODE
R EQU $6650
GBUSY EQU $6660
BUSY EQU $6669
OP EQU $666A
ODDR EQU $666B
OORB EQU $666C
PORT EQU $666D
TX EQU $666E
RX EQU $666F
LEFT EQU $6670
MASK EQU $6671
OLDMODE EQU $6672
ERR EQU $6673
A0 EQU $6674
A1 EQU $6675
A2 EQU $6676
COUNT EQU $6677
CHANGED EQU $6678
READY EQU $6679
T0 EQU $667A
KIND EQU $667B
SAVED_PCR EQU $667C
LO EQU $66B0
HI EQU $66B4
DDR EQU $7FC2
ORB EQU $7FC0
IFR EQU $7FCD
PCR EQU $7FCC
MANAGED EQU $3DF0
BACKUP EQU $6B80
START DB "SP",1,1
        JMP PUBLIC_SPI
        DB "SM",1,1
        JMP PUBLIC_SRAM
PUBLIC_SPI:
        LDA #0
        BRA ENTER
PUBLIC_SRAM:
        LDA #1
ENTER:  PHP
        SEI
        CLD
        PHA
        LDA GBUSY
        ORA BUSY
        BEQ FREE
        PLA
        PLP
        LDA #8
        CLC
        RTS
FREE:   INC GBUSY
        INC BUSY
        PLA
        STA OP
        STA KIND
        STZ R+9
        STZ R+10
        STZ R+11
        STZ CHANGED
        STZ READY
        STZ ERR
        LDA $7FEC
        STA SAVED_PCR
        AND #$EE
        CMP #$EE
        BEQ MAP_PROVIDER
        LDA $7E01
        BPL MAP_PROVIDER
        LDA #$82
        STA ERR
        BRA DONE
MAP_PROVIDER:
        LDA SAVED_PCR
        AND #$11
        ORA #$EE
        STA $7FEC
        JSR DISPATCH
        STA ERR
        LDA READY
        BEQ DONE
        LDA KIND
        BEQ GPIO_DONE
        LDA CHANGED
        BEQ GPIO_DONE
        LDA OLDMODE
        JSR WRITE_MODE
        JSR READ_MODE
        CMP OLDMODE
        BEQ GPIO_DONE
        LDA #7
        STA ERR
GPIO_DONE:
        JSR RESTORE
DONE:   LDA ERR
        STA R+8
        LDA KIND
        BNE DONE_BANK
        LDA ERR
        BNE DONE_BANK
        LDA #3
        STA R+11
DONE_BANK:
        LDA SAVED_PCR
        STA $7FEC
        STZ BUSY
        STZ GBUSY
        PLP
        LDA ERR
        BEQ GOOD
        CLC
        RTS
GOOD:   SEC
        RTS
CORE_BEGIN:
DISPATCH:
        LDA OP
        BNE SRAM
        LDA R+13
        ORA R+14
        ORA R+15
        BNE BAD
        LDA R
        CMP #2
        BCS BAD
        TAX
        BNE RAW_ALLOWED
        LDA MANAGED
        BNE DENIED
RAW_ALLOWED:
        LDA #4
        CPX #0
        BEQ RAW_MASK
        ASL A
RAW_MASK:
        STA MASK
        LDA R
        JSR VALIDATE_SHAPE
        BCC BAD
        LDA R+1
        BEQ RAW_READY
        LDA R+4
        CMP R+7
        BNE BAD
        ; Duplex allows exact in-place or completely disjoint buffers.
DUP_OVERLAP:
        LDA R+5
        SEC
        SBC R+2
        STA T0
        LDA R+6
        SBC R+3
        BEQ DUP_POSITIVE
        CMP #$FF
        BNE RAW_READY
        LDA T0
        BEQ RAW_READY
        EOR #$FF
        INC A
        BRA DUP_DISTANCE
DUP_POSITIVE:
        LDA T0
        BEQ RAW_READY
DUP_DISTANCE:
        CMP R+4
        BCC BAD
        BRA RAW_READY
BAD:    LDA #9
        RTS
DENIED: LDA #6
        RTS
RAW_READY:
        JSR INIT
        BCC RETURN
        JSR SELECT
        LDA R+4
        STA LEFT
        BEQ RECEIVE
TRANSMIT:
        JSR LO
        JSR BYTE
        INC R+9
        JSR NEXT_TX
        LDX R+1
        BEQ TX_NEXT
        JSR HI
        JSR NEXT_RX
        INC R+10
TX_NEXT:
        DEC LEFT
        BNE TRANSMIT
        LDA R+1
        BNE SUCCESS
        LDA KIND
        BNE SUCCESS
RECEIVE:
        LDA R+7
        STA LEFT
        BEQ SUCCESS
RX_NEXT:
        LDA R+12
        JSR BYTE
        JSR HI
        JSR NEXT_RX
        INC R+10
        DEC LEFT
        BNE RX_NEXT
SUCCESS:
        LDA #0
RETURN: RTS
SRAM:
        BRA SRAM_VALIDATE
SRAM_BAD:
        LDA #9
        RTS
SRAM_DENIED:
        LDA #6
        RTS
SRAM_VALIDATE:
        LDA R+1
        ORA R+15
        BNE SRAM_BAD
        LDA R
        CMP #3
        BCS SRAM_BAD
        STA OP
        TAX
        BEQ PROBE_SETUP
        LDA MANAGED
        BEQ SRAM_RANGE
        LDA OP
        CMP #2
        BEQ SRAM_DENIED
SRAM_RANGE:
        LDA R+7
        BEQ SRAM_BAD
        LDA R+5
        LDX R+6
        LDY R+7
        JSR BUFFER
        BCC SRAM_BAD
        LDA R+4
        CMP #2
        BCS SRAM_BAD
        LDA R+7
        SEC
        SBC #1
        CLC
        ADC R+2
        LDA R+3
        ADC #0
        LDA R+4
        ADC #0
        CMP #2
        BCS SRAM_BAD
        LDX #2
ADDRESS_COPY:
        LDA R+2,X
        STA A0,X
        DEX
        BPL ADDRESS_COPY
        LDA R+7
        STA COUNT
        LDA R+5
        LDX R+6
        BRA SRAM_READY
PROBE_SETUP:
        LDA R+7
        BNE SRAM_BAD
        LDA #$FF
        STA A0
        LDA #$FF
        STA A1
        LDA #1
        STA A2
        LDA #1
        STA COUNT
        LDA #<BACKUP
        LDX #>BACKUP
SRAM_READY:
        STA LO+1
        STA HI+1
        STX LO+2
        STX HI+2
        LDA #4
        STA MASK
        JSR INIT
        BCC RETURN
        JSR READ_MODE
        STA OLDMODE
        CMP #$40
        BEQ MODE_READY
        CMP #0
        BEQ CHANGE_MODE
        CMP #$80
        BNE VERIFY_FAIL
CHANGE_MODE:
        INC CHANGED
        LDA #$40
        JSR WRITE_MODE
        JSR READ_MODE
        CMP #$40
        BNE VERIFY_FAIL
MODE_READY:
        LDA OP
        BEQ PROBE
        JSR MEMORY_FRAME
        LDA COUNT
        STA R+9
        BRA SUCCESS
VERIFY_FAIL:
        LDA #7
        RTS
READ_MODE:
        LDA #5
        JSR COMMAND
        LDA #0
        JSR BYTE
        PHA
        JSR DESELECT
        PLA
        RTS
WRITE_MODE:
        PHA
        LDA #1
        JSR COMMAND
        PLA
        JSR BYTE
        JMP DESELECT
COMMAND:
        PHA
        JSR SELECT
        PLA
        JMP BYTE
MEMORY_FRAME:
        LDA #3
        LDX OP
        CPX #2
        BNE MEMORY_COMMAND
        DEC A
MEMORY_COMMAND:
        JSR COMMAND
        LDA A2
        JSR BYTE
        LDA A1
        JSR BYTE
        LDA A0
        JSR BYTE
        LDA COUNT
        STA LEFT
        LDX OP
        CPX #2
        BNE MEMORY_READ
        JSR TRANSMIT
        JMP DESELECT
MEMORY_READ:
        JSR RX_NEXT
        JMP DESELECT
PROBE:
        ; Toggle one reserved byte, verify, restore and verify even on mismatch.
        LDA #1
        STA OP
        JSR MEMORY_FRAME
        LDA #2
        JSR COMMAND
        JSR PROBE_ADDRESS
        LDA BACKUP
        EOR #$FF
        JSR BYTE
        JSR DESELECT
        LDA #3
        JSR COMMAND
        JSR PROBE_ADDRESS
        LDA #0
        JSR BYTE
        STA T0
        LDA BACKUP
        EOR #$FF
        CMP T0
        BEQ PROBE_MATCH
        LDA #7
        STA ERR
PROBE_MATCH:
        JSR DESELECT
        LDA #2
        STA OP
        JSR MEMORY_FRAME
        LDA #3
        JSR COMMAND
        JSR PROBE_ADDRESS
        LDA #0
        JSR BYTE
        CMP BACKUP
        BEQ PROBE_RESTORED
        LDA #7
        STA ERR
PROBE_RESTORED:
        JSR DESELECT
        STZ R+9
        STZ R+10
        STZ R+12
        LDA ERR
        BNE PROBE_DONE
        LDA #2
        STA R+13
        LDA #$81            ; Usable, retention/battery continuity unknown.
        STA R+14
PROBE_DONE:
        LDA ERR
        RTS
PROBE_ADDRESS:
        LDA A2
        JSR BYTE
        LDA A1
        JSR BYTE
        LDA A0
        JMP BYTE
NEXT_RX:
        LDX #4
NEXT_TX:
        INC LO+1,X
        BNE NEXT_DONE
        INC LO+2,X
NEXT_DONE:
        RTS
INIT:
        ; Port B handshakes/pending IRQs cannot be preserved by ORB accesses.
        LDA IFR
        AND #$18
        BNE PIN_BUSY
        LDA PCR
        AND #$C0
        CMP #$80
        BEQ PIN_BUSY
        LDA $7FCB
        AND #2
        BNE PIN_BUSY
        LDA DDR
        STA ODDR
        LDA ORB
        STA OORB
        EOR #$FF
        AND ODDR
        AND #$0C
        BNE PIN_BUSY
        LDA OORB
        AND #$FC
        ORA #$0C
        STA PORT
        STA ORB
        LDA ODDR
        AND #$DF
        ORA #$0F
        STA DDR
        INC READY
        SEC
        RTS
PIN_BUSY:
        LDA #1
        CLC
        RTS
SELECT:
        LDA MASK
        EOR #$FF
        AND PORT
        STA PORT
        STA ORB
        RTS
DESELECT:
        LDA PORT
        ORA #$0C
        STA PORT
        STA ORB
        RTS
RESTORE:
        JSR DESELECT
        LDA ODDR
        STA DDR
        LDA OORB
        STA ORB
        RTS
BYTE:
        STA TX
        LDX #8
BIT_LOOP:
        LDA #2
        TRB PORT
        ASL TX
        BCC BIT_ZERO
        TSB PORT
BIT_ZERO:
        LDA PORT
        STA ORB
        INC A
        STA ORB
        LDA ORB
        ASL A
        ASL A
        ASL A
        ROL RX
        LDA PORT
        STA ORB
        DEX
        BNE BIT_LOOP
        LDA RX
        RTS
CORE_END:
        ENDMOD
        END
