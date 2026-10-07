; Phase 2 beta5 candidate. RAM gateway; provider is a resident B3 extension.
; Cross-bank calls require a RAM NMI handler that preserves bank selection.
; Foreground only: 65C02 or 816 E=1, D=DBR=PBR=0. No native/IRQ/NMI calls.
; RESET installs/zeros this complete allocation before any caller prepares data.
        MODULE RTC_FLASH_GATEWAY
        XDEF START
        XDEF GATE_END
        INCLUDE "rtc-api.inc"
        INCLUDE "i2c-api.inc"
        INCLUDE "split-defs.inc"
PCR EQU $7FEC
G_BUSY EQU $6660
G_OP EQU $6661
G_PCR EQU $6662
G_RET EQU $6663
G_READY EQU $6664
CRC_LO EQU $6665
CRC_HI EQU $6666
LEFT_LO EQU $6667
LEFT_HI EQU $6668
        CODE
START DB "RG",1,4
        JMP GET_TIME
        JMP GET_STATUS
        JMP SET_TIME
        JMP ACK_POWER
        DB "I2",1,1
        JMP BUS_TRANSFER
GET_TIME LDX #0
        BRA ENTER
GET_STATUS LDX #1
        BRA ENTER
SET_TIME LDX #2
        BRA ENTER
ACK_POWER LDX #3
        BRA ENTER
BUS_TRANSFER LDX #4
ENTER   PHP
        SEI
        CLD
        LDA G_BUSY
        BEQ FREE
        PLP
        LDA #RTC_IN_USE
        CLC
        RTS
FREE    INC G_BUSY
        STX G_OP
        CPX #4
        BNE OUTPUT_READY
        STZ I2C_WRITTEN
        STZ I2C_READ
        STZ I2C_PHASE
OUTPUT_READY
        ; A flash NMI handler would be fetched from the provider's overlay.
        ; Reject before mapping, rather than silently changing its meaning.
        LDA PCR
        AND #$EE
        CMP #PROVIDER_BITS
        BEQ NMI_OK
        LDA $7E01
        BPL NMI_OK
        LDA #$82
        JMP EARLY_RETURN
NMI_OK  LDA PCR
        STA G_PCR
        AND #$11
        ORA #PROVIDER_BITS
        STA PCR
        LDA G_READY
        AND #1
        BNE DISPATCH
        LDA PROVIDER_BASE
        CMP #'R'
        BNE UNAVAILABLE
        LDA PROVIDER_BASE+1
        CMP #'C'
        BNE UNAVAILABLE
        LDA PROVIDER_BASE+2
        CMP #1
        BNE UNAVAILABLE
        LDA PROVIDER_BASE+3
        CMP #5
        BNE UNAVAILABLE
        JSR CHECK_CRC
        BEQ VERIFIED
        LDA #$81
        BRA RETURN_BANK
UNAVAILABLE LDA #$80
        BRA RETURN_BANK
VERIFIED
        LDA G_READY
        AND #2
        BNE STATE_READY
        LDX #PRIVATE_SIZE-1
CLEAR_STATE STZ PRIVATE_BASE,X
        DEX
        BPL CLEAR_STATE
        STZ RTC_EVIDENCE
STATE_READY
        LDA #3
        STA G_READY
DISPATCH
        LDA G_OP
        ASL A
        CLC
        ADC G_OP
        ADC #<(PROVIDER_BASE+4)
        STA CALL_FLASH+1
CALL_FLASH JSR PROVIDER_BASE+4
RETURN_BANK
        STA G_RET
        LDA G_PCR
        STA PCR
        LDA G_RET
EARLY_RETURN
        STA G_RET
        STA RTC_RESULT
        STA I2C_RESULT
        STZ G_BUSY
        PLP
        LDA G_RET
        BEQ SUCCESS
        CLC
        RTS
SUCCESS SEC
        RTS

; CRC16/CCITT-FALSE over the module including its big-endian seal.
; No code is executed from flash before this first-request integrity check.
CHECK_CRC
        LDA #$FF
        STA CRC_LO
        STA CRC_HI
        LDA #<PROVIDER_BASE
        STA FLASH_READ+1
        LDA #>PROVIDER_BASE
        STA FLASH_READ+2
        LDA #<PROVIDER_SIZE
        STA LEFT_LO
        LDA #>PROVIDER_SIZE
        STA LEFT_HI
FLASH_READ LDA PROVIDER_BASE
        EOR CRC_HI
        STA CRC_HI
        LDX #8
CRC_BIT ASL CRC_LO
        ROL CRC_HI
        BCC CRC_NEXT
        LDA CRC_LO
        EOR #$21
        STA CRC_LO
        LDA CRC_HI
        EOR #$10
        STA CRC_HI
CRC_NEXT DEX
        BNE CRC_BIT
        INC FLASH_READ+1
        BNE NEXT_ADDRESS
        INC FLASH_READ+2
NEXT_ADDRESS
        LDA LEFT_LO
        BNE DEC_LOW
        DEC LEFT_HI
DEC_LOW DEC LEFT_LO
        LDA LEFT_LO
        ORA LEFT_HI
        BNE FLASH_READ
        LDA CRC_LO
        ORA CRC_HI
        RTS
GATE_END
        ENDMOD
        END
