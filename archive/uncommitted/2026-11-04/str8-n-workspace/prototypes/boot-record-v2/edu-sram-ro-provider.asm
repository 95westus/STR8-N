; ES1 optional read-only 23LCV1024 provider. ROM body at B3:8040.
; B3 visible, foreground only, 65C02/816 E=1, IRQ masked, D/DBR/PBR=0.
; No SRAM WRITE/WRMR/probe/format opcode; every READ byte has its own address.
        MODULE EDU_SRAM_RO_PROVIDER
        INCLUDE "edu-sram-params.inc"
ER EQU $6000
ES_MAGIC EQU $6500
ES_BUSY EQU $6504
ES_ERR EQU $6505
ES_CRC EQU $6506
ES_LEFT EQU $6508
ES_COUNT EQU $650A
ES_A0 EQU $650B
ES_A1 EQU $650C
ES_A2 EQU $650D
ES_DST EQU $650E
ES_MODE EQU $6510
ES_ODDR EQU $6511
ES_OORB EQU $6512
ES_PORT EQU $6513
ES_TX EQU $6514
ES_RX EQU $6515
ES_REMAIN EQU $6516
ES_READY EQU $6517
ES_ACK EQU $6518
ES_PTR EQU $D0
ES_ORB EQU $7FC0
ES_DDR EQU $7FC2
ES_ACR EQU $7FCB
ES_PCR EQU $7FCC
ES_IFR EQU $7FCD
ES_IER EQU $7FCE
        CODE
ES_INIT:
        PHP
        SEI
        CLD
        JSR ES_IS_READY
        BCC ES_INIT_CLEAR
        LDA ES_BUSY
        BNE ES_BUSY_RETURN
ES_INIT_CLEAR:
        LDX #$FF
ES_CLEAR:
        STZ $6500,X
        DEX
        BNE ES_CLEAR
        STZ $6500
        LDA $7E60
        CMP #'R'
        BNE ES_BAD_ABI
        LDA $7E61
        CMP #'A'
        BNE ES_BAD_ABI
        LDA $7E62
        CMP #1
        BNE ES_BAD_ABI
        LDA $7E63
        CMP #$0D
        BNE ES_BAD_ABI
        STZ ES_PTR
        LDA #$F0
        STA ES_PTR+1
        STZ ES_LEFT
        LDA #$10
        STA ES_LEFT+1
        JSR ES_CRC_RANGE
        LDA ES_CRC
        CMP #ES_F_CRC_LO
        BNE ES_BAD_ABI
        LDA ES_CRC+1
        CMP #ES_F_CRC_HI
        BNE ES_BAD_ABI
        LDX #3
ES_INIT_MAGIC:
        LDA ES_EXPECTED_MAGIC,X
        STA ES_MAGIC,X
        DEX
        BPL ES_INIT_MAGIC
        BRA ES_OK_RETURN
ES_BAD_ABI:
        LDA #8
        BRA ES_STATUS_RETURN
ES_BUSY_RETURN:
        PLP
        LDA #1
        CLC
        RTS
ES_NOT_READY:
        LDA #2
        BRA ES_STATUS_RETURN
ES_BAD_REQUEST:
        LDA #3
        BRA ES_STATUS_RETURN
ES_STATUS_RETURN:
        STA ER+8
        STA ES_ERR
        PLP
        LDA ES_ERR
        BEQ ES_RETURN_OK
        CLC
        RTS
ES_OK_RETURN:
        LDA #0
        BRA ES_STATUS_RETURN
ES_RETURN_OK:
        SEC
        RTS
ES_QUERY:
        PHP
        SEI
        CLD
        JSR ES_IS_READY
        BCC ES_NOT_READY
        LDA ES_BUSY
        BNE ES_BUSY_RETURN
        STZ ER+9
        LDA #$FF
        STA ER+10
        LDA #$81             ; READ ONLY; physical presence is unproven.
        STA ER+11
        STZ ER+12
        STZ ER+13
        LDA #2
        STA ER+14
        LDA #1
        STA ER+15
        BRA ES_OK_RETURN
ES_IS_READY:
        LDX #3
ES_READY_BYTE:
        LDA ES_MAGIC,X
        CMP ES_EXPECTED_MAGIC,X
        BNE ES_NOT_MAGIC
        DEX
        BPL ES_READY_BYTE
        SEC
        RTS
ES_NOT_MAGIC:
        CLC
        RTS

; Explicit, narrow disabled-CB acknowledgment; no SPI clocks or register writes.
; Mirrors the earlier qualified guard. QUERY/INIT never acknowledge VIA flags.
ES_PREP:
        PHP
        SEI
        CLD
        JSR ES_IS_READY
        BCC ES_NOT_READY
        LDA ES_BUSY
        BNE ES_BUSY_RETURN
        STZ ES_ACK
        JSR ES_IDLE
        BCC ES_STATUS_RETURN
        LDA ES_IFR
        AND #$18
        BEQ ES_OK_RETURN
        LDA ES_ORB
        INC ES_ACK
        LDA ES_IFR
        AND #$18
        BEQ ES_OK_RETURN
        LDA #1
        BRA ES_STATUS_RETURN
ES_IDLE:
        LDA ES_IER
        AND #$18
        BNE ES_PIN_BUSY
        LDA ES_PCR
        AND #$F0
        BNE ES_PIN_BUSY
        LDA ES_ACR
        AND #$1E
        BNE ES_PIN_BUSY
        LDA ES_DDR
        AND #$2F
        BNE ES_PIN_BUSY
        SEC
        RTS
ES_PIN_BUSY:
        LDA #1
        CLC
        RTS

ES_READ:
        PHP
        SEI
        CLD
        JSR ES_IS_READY
        BCC ES_NOT_READY
        LDA ES_BUSY
        BNE ES_BUSY_RETURN
        LDA ER
        CMP #1
        BNE ES_BAD_REQUEST
        LDA ER+7
        BNE ES_BAD_REQUEST
        LDA ER+4
        BEQ ES_BAD_REQUEST
        CMP #65
        BCS ES_BAD_REQUEST
        STA ES_COUNT
        DEC A
        CLC
        ADC ER+1
        LDA ER+2
        ADC #0
        LDA ER+3
        ADC #0
        CMP #2
        BCS ES_BAD_REQUEST
        LDA ER+3
        CMP #2
        BCS ES_BAD_REQUEST
        LDA ER+6
        CMP #$20
        BCC ES_BAD_REQUEST
        LDA ER+4
        DEC A
        CLC
        ADC ER+5
        STA ES_DST
        LDA ER+6
        ADC #0
        BCS ES_BAD_REQUEST
        CMP #$65
        BCS ES_BAD_REQUEST
        ; The destination cannot overwrite the shared request at 6000-601F.
        CMP #$60
        BCC ES_READ_ARGS_OK
        LDA ER+6
        CMP #$60
        BCC ES_BAD_REQUEST
        BNE ES_READ_ARGS_OK
        LDA ER+5
        CMP #$20
        BCC ES_BAD_REQUEST
ES_READ_ARGS_OK:
        LDA ER+1
        STA ES_A0
        LDA ER+2
        STA ES_A1
        LDA ER+3
        STA ES_A2
        LDA ER+5
        STA ES_DST
        LDA ER+6
        STA ES_DST+1
        STZ ER+9
        STZ ES_READY
        STZ ES_ERR
        LDA #$80
        STA ER+11
        LDA ES_ACK
        BEQ ES_NO_ACK_NOTE
        INC ER+11
ES_NO_ACK_NOTE:
        JSR ES_IDLE
        BCC ES_READ_EARLY
        LDA ES_IFR
        AND #$18
        BNE ES_READ_PIN_BUSY
        INC ES_BUSY
        LDA ES_DDR
        STA ES_ODDR
        LDA ES_ORB
        STA ES_OORB
        AND #$FC
        ORA #$0C
        STA ES_PORT
        STA ES_ORB
        LDA ES_ODDR
        AND #$DF
        ORA #$0F
        STA ES_DDR
        INC ES_READY
        LDA #5
        JSR ES_COMMAND
        LDA #$FF
        JSR ES_BYTE
        STA ES_MODE
        STA ER+10
        JSR ES_DESELECT
        LDA ES_MODE
        BEQ ES_READ_LOOP
        CMP #$40
        BEQ ES_READ_LOOP
        CMP #$80
        BEQ ES_READ_LOOP
        LDA #7
        STA ES_ERR
        BRA ES_READ_FINISH
ES_READ_LOOP:
        LDA #3
        JSR ES_COMMAND
        LDA ES_A2
        JSR ES_BYTE
        LDA ES_A1
        JSR ES_BYTE
        LDA ES_A0
        JSR ES_BYTE
        LDA #$FF
        JSR ES_BYTE
        PHA
        JSR ES_DESELECT
        LDA ES_DST
        STA ES_PTR
        LDA ES_DST+1
        STA ES_PTR+1
        PLA
        STA (ES_PTR)
        INC ER+9
        INC ES_DST
        BNE ES_READ_NEXT_ADDR
        INC ES_DST+1
ES_READ_NEXT_ADDR:
        INC ES_A0
        BNE ES_READ_NEXT
        INC ES_A1
        BNE ES_READ_NEXT
        INC ES_A2
ES_READ_NEXT:
        DEC ES_COUNT
        BNE ES_READ_LOOP
ES_READ_FINISH:
        JSR ES_DESELECT
        LDA ES_ODDR
        STA ES_DDR
        LDA ES_OORB
        STA ES_ORB
        STZ ES_READY
        STZ ES_BUSY
        LDA ES_ERR
        JMP ES_STATUS_RETURN
ES_READ_PIN_BUSY:
        LDA #1
ES_READ_EARLY:
        JMP ES_STATUS_RETURN

ES_COMMAND:
        PHA
        LDA ES_PORT
        AND #$FB
        STA ES_PORT
        STA ES_ORB
        PLA
        JMP ES_BYTE
ES_DESELECT:
        LDA ES_PORT
        ORA #$0C
        STA ES_PORT
        STA ES_ORB
        RTS
; Mode-0 GPIO engine derived from the earlier hardware-qualified prototype.
ES_BYTE:
        STA ES_TX
        LDX #8
ES_BIT:
        LDA #2
        TRB ES_PORT
        ASL ES_TX
        BCC ES_BIT_ZERO
        TSB ES_PORT
ES_BIT_ZERO:
        LDA ES_PORT
        STA ES_ORB
        INC A
        STA ES_ORB
        LDA ES_ORB
        ASL A
        ASL A
        ASL A
        ROL ES_RX
        LDA ES_PORT
        STA ES_ORB
        DEX
        BNE ES_BIT
        LDA ES_RX
        RTS
ES_CRC_RANGE:
        LDA #$FF
        STA ES_CRC
        STA ES_CRC+1
ES_CRC_NEXT:
        LDA (ES_PTR)
        EOR ES_CRC+1
        STA ES_CRC+1
        LDX #8
ES_CRC_BIT:
        ASL ES_CRC
        ROL ES_CRC+1
        BCC ES_CRC_NO_XOR
        LDA ES_CRC
        EOR #$21
        STA ES_CRC
        LDA ES_CRC+1
        EOR #$10
        STA ES_CRC+1
ES_CRC_NO_XOR:
        DEX
        BNE ES_CRC_BIT
        INC ES_PTR
        BNE ES_CRC_ADVANCE
        INC ES_PTR+1
ES_CRC_ADVANCE:
        LDA ES_LEFT
        BNE ES_CRC_DEC
        DEC ES_LEFT+1
ES_CRC_DEC:
        DEC ES_LEFT
        LDA ES_LEFT
        ORA ES_LEFT+1
        BNE ES_CRC_NEXT
        RTS
ES_EXPECTED_MAGIC: DB "ESR",1
ES_END:
        ENDMOD
        END
