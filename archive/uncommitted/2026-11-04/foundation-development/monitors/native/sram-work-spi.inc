; Private bridge for the old16-byte SM descriptor. Opcode0 only reads RDMR.
; All actual SRAM writes require an explicit volatile UNLOCK. No WRMR/flash.
SW_TRANSFER:
        STZ SM_C_R+9
        STZ SM_C_R+10
        LDA SW_EDU
        CMP #1
        BNE SW_SPI_ABSENT
        LDA SM_C_R
        STA SP_OP
        BEQ SW_SPI_QUERY
        CMP #1
        BEQ SW_SPI_REQUEST
        CMP #2
        BNE SW_SPI_ARGUMENT
        LDA SW_UNLOCKED
        CMP #1
        BNE SW_SPI_LOCKED
SW_SPI_REQUEST:
        LDA SM_C_R+7
        BEQ SW_SPI_ARGUMENT
        CMP #65
        BCS SW_SPI_ARGUMENT
        STA SP_COUNT
        STA SW_SPI_COUNT
        LDA SM_C_R+5
        STA SP_PTR
        LDA SM_C_R+6
        STA SP_PTR+1
        CMP #2
        BCC SW_SPI_ARGUMENT
        CMP #$20
        BCC SW_SPI_USER
        CMP #$64
        BNE SW_SPI_ARGUMENT
        LDA SP_PTR
        CLC
        ADC SP_COUNT
        BCS SW_SPI_ARGUMENT
        CMP #$41
        BCS SW_SPI_ARGUMENT
        BRA SW_SPI_ADDRESS
SW_SPI_USER:
        CLC
        LDA SP_PTR
        ADC SP_COUNT
        STA SW_TEMP
        LDA SP_PTR+1
        ADC #0
        CMP #$20
        BCC SW_SPI_ADDRESS
        BNE SW_SPI_ARGUMENT
        LDA SW_TEMP
        BNE SW_SPI_ARGUMENT
SW_SPI_ADDRESS:
        LDA SM_C_R+2
        STA SP_A0
        LDA SM_C_R+3
        STA SP_A1
        LDA SM_C_R+4
        STA SP_A2
        JSR SP_TRANSFER
        PHA
        LDA SW_SPI_COUNT
        SEC
        SBC SP_COUNT
        STA SM_C_R+9
        PLA
        BRA SW_SPI_RESULT
SW_SPI_QUERY:
        STZ SP_COUNT
        JSR SP_TRANSFER
        PHA
        LDA SW_MODE
        STA SM_C_R+8
        PLA
        BRA SW_SPI_RESULT
SW_SPI_ABSENT:
        LDA #$80
        BRA SW_SPI_RESULT
SW_SPI_ARGUMENT:
        LDA #$44
        BRA SW_SPI_RESULT
SW_SPI_LOCKED:
        LDA #$4C
SW_SPI_RESULT:
        STA SM_C_R+10
        CMP #0
        RTS

; Qualified addressed-byte SPI engine is inserted by the builder, with its
; PROGRAM-only partition gate replaced by the private bridge above. Public
; WORK calls still require validated owner/epoch/ticket/range and safe RAM.
        INCLUDE "sram-work-spi-engine.inc"

SW_EDU EQU $5B30
SW_UNLOCKED EQU $5B31
SW_ERROR EQU $5B32
SW_RETURN_VECTOR EQU $5B34
SW_RUN_VECTOR EQU $5B36
SW_LINE_COUNT EQU $5B38
SW_OVERFLOW EQU $5B39
SW_TEMP EQU $5B3A
SW_MODE EQU $5B3C
SW_LINE EQU $5B40
SW_TEXT_PTR EQU $D8
SW_INPUT_PTR EQU $DA
SP_PTR EQU $E8
SP_PROFILE EQU SW_EDU
SP_OP EQU $5B80
SP_COUNT EQU $5B81
SP_A0 EQU $5B82
SP_A1 EQU $5B83
SP_A2 EQU $5B84
SP_DDR EQU $5B85
SP_ORB EQU $5B86
SP_PORT EQU $5B87
SP_TX EQU $5B88
SP_RX EQU $5B89
SP_TEMP EQU $5B8A
SP_ERROR EQU $5B8B
SW_SPI_COUNT EQU $5B8C
W_ORB EQU $7FC0
W_DDR EQU $7FC2
W_ACR EQU $7FCB
W_PCR EQU $7FCC
W_IFR EQU $7FCD
W_IER EQU $7FCE
