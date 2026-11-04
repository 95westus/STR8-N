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
        BCS ES_LONG_1
        JMP ES_INIT_CLEAR
ES_LONG_1:
        LDA ES_BUSY
        BEQ ES_LONG_2
        JMP ES_BUSY_RETURN
ES_LONG_2:
ES_INIT_CLEAR:
        LDX #$FF
ES_CLEAR:
        STZ $6500,X
        DEX
        BEQ ES_LONG_3
        JMP ES_CLEAR
ES_LONG_3:
        STZ $6500
        LDA $7E60
        CMP #'R'
        BEQ ES_LONG_4
        JMP ES_BAD_ABI
ES_LONG_4:
        LDA $7E61
        CMP #'A'
        BEQ ES_LONG_5
        JMP ES_BAD_ABI
ES_LONG_5:
        LDA $7E62
        CMP #1
        BEQ ES_LONG_6
        JMP ES_BAD_ABI
ES_LONG_6:
        LDA $7E63
        CMP #$0D
        BEQ ES_LONG_7
        JMP ES_BAD_ABI
ES_LONG_7:
        STZ ES_PTR
        LDA #$F0
        STA ES_PTR+1
        STZ ES_LEFT
        LDA #$10
        STA ES_LEFT+1
        JSR ES_CRC_RANGE
        LDA ES_CRC
        CMP #ES_F_CRC_LO
        BEQ ES_LONG_8
        JMP ES_BAD_ABI
ES_LONG_8:
        LDA ES_CRC+1
        CMP #ES_F_CRC_HI
        BEQ ES_LONG_9
        JMP ES_BAD_ABI
ES_LONG_9:
        LDX #3
ES_INIT_MAGIC:
        LDA ES_EXPECTED_MAGIC,X
        STA ES_MAGIC,X
        DEX
        BMI ES_LONG_10
        JMP ES_INIT_MAGIC
ES_LONG_10:
        JMP ES_OK_RETURN
ES_BAD_ABI:
        LDA #8
        JMP ES_STATUS_RETURN
ES_BUSY_RETURN:
        PLP
        LDA #1
        CLC
        RTS
ES_NOT_READY:
        LDA #2
        JMP ES_STATUS_RETURN
ES_BAD_REQUEST:
        LDA #3
        JMP ES_STATUS_RETURN
ES_STATUS_RETURN:
        STA ER+8
        STA ES_ERR
        PLP
        LDA ES_ERR
        BNE ES_LONG_11
        JMP ES_RETURN_OK
ES_LONG_11:
        CLC
        RTS
ES_OK_RETURN:
        LDA #0
        JMP ES_STATUS_RETURN
ES_RETURN_OK:
        SEC
        RTS
ES_QUERY:
        PHP
        SEI
        CLD
        JSR ES_IS_READY
        BCS ES_LONG_12
        JMP ES_NOT_READY
ES_LONG_12:
        LDA ES_BUSY
        BEQ ES_LONG_13
        JMP ES_BUSY_RETURN
ES_LONG_13:
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
        JMP ES_OK_RETURN
ES_IS_READY:
        LDX #3
ES_READY_BYTE:
        LDA ES_MAGIC,X
        CMP ES_EXPECTED_MAGIC,X
        BEQ ES_LONG_14
        JMP ES_NOT_MAGIC
ES_LONG_14:
        DEX
        BMI ES_LONG_15
        JMP ES_READY_BYTE
ES_LONG_15:
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
        BCS ES_LONG_16
        JMP ES_NOT_READY
ES_LONG_16:
        LDA ES_BUSY
        BEQ ES_LONG_17
        JMP ES_BUSY_RETURN
ES_LONG_17:
        STZ ES_ACK
        JSR ES_IDLE
        BCS ES_LONG_18
        JMP ES_STATUS_RETURN
ES_LONG_18:
        LDA ES_IFR
        AND #$18
        BNE ES_LONG_19
        JMP ES_OK_RETURN
ES_LONG_19:
        LDA ES_ORB
        INC ES_ACK
        LDA ES_IFR
        AND #$18
        BNE ES_LONG_20
        JMP ES_OK_RETURN
ES_LONG_20:
        LDA #1
        JMP ES_STATUS_RETURN
ES_IDLE:
        LDA ES_IER
        AND #$18
        BEQ ES_LONG_21
        JMP ES_PIN_BUSY
ES_LONG_21:
        LDA ES_PCR
        AND #$F0
        BEQ ES_LONG_22
        JMP ES_PIN_BUSY
ES_LONG_22:
        LDA ES_ACR
        AND #$1E
        BEQ ES_LONG_23
        JMP ES_PIN_BUSY
ES_LONG_23:
        LDA ES_DDR
        AND #$2F
        BEQ ES_LONG_24
        JMP ES_PIN_BUSY
ES_LONG_24:
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
        BCS ES_LONG_25
        JMP ES_NOT_READY
ES_LONG_25:
        LDA ES_BUSY
        BEQ ES_LONG_26
        JMP ES_BUSY_RETURN
ES_LONG_26:
        LDA ER
        CMP #1
        BEQ ES_LONG_27
        JMP ES_BAD_REQUEST
ES_LONG_27:
        LDA ER+7
        BEQ ES_LONG_28
        JMP ES_BAD_REQUEST
ES_LONG_28:
        LDA ER+4
        BNE ES_LONG_29
        JMP ES_BAD_REQUEST
ES_LONG_29:
        CMP #65
        BCC ES_LONG_30
        JMP ES_BAD_REQUEST
ES_LONG_30:
        STA ES_COUNT
        DEC A
        CLC
        ADC ER+1
        LDA ER+2
        ADC #0
        LDA ER+3
        ADC #0
        CMP #2
        BCC ES_LONG_31
        JMP ES_BAD_REQUEST
ES_LONG_31:
        LDA ER+3
        CMP #2
        BCC ES_LONG_32
        JMP ES_BAD_REQUEST
ES_LONG_32:
        LDA ER+6
        CMP #$20
        BCS ES_LONG_33
        JMP ES_BAD_REQUEST
ES_LONG_33:
        LDA ER+4
        DEC A
        CLC
        ADC ER+5
        STA ES_DST
        LDA ER+6
        ADC #0
        BCC ES_LONG_34
        JMP ES_BAD_REQUEST
ES_LONG_34:
        CMP #$65
        BCC ES_LONG_35
        JMP ES_BAD_REQUEST
ES_LONG_35:
        ; The destination cannot overwrite the shared request at 6000-601F.
        CMP #$60
        BCS ES_LONG_36
        JMP ES_READ_ARGS_OK
ES_LONG_36:
        LDA ER+6
        CMP #$60
        BCS ES_LONG_37
        JMP ES_BAD_REQUEST
ES_LONG_37:
        BEQ ES_LONG_38
        JMP ES_READ_ARGS_OK
ES_LONG_38:
        LDA ER+5
        CMP #$20
        BCS ES_LONG_39
        JMP ES_BAD_REQUEST
ES_LONG_39:
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
        BNE ES_LONG_40
        JMP ES_NO_ACK_NOTE
ES_LONG_40:
        INC ER+11
ES_NO_ACK_NOTE:
        JSR ES_IDLE
        BCS ES_LONG_41
        JMP ES_READ_EARLY
ES_LONG_41:
        LDA ES_IFR
        AND #$18
        BEQ ES_LONG_42
        JMP ES_READ_PIN_BUSY
ES_LONG_42:
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
        BNE ES_LONG_43
        JMP ES_READ_LOOP
ES_LONG_43:
        CMP #$40
        BNE ES_LONG_44
        JMP ES_READ_LOOP
ES_LONG_44:
        CMP #$80
        BNE ES_LONG_45
        JMP ES_READ_LOOP
ES_LONG_45:
        LDA #7
        STA ES_ERR
        JMP ES_READ_FINISH
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
        BEQ ES_LONG_46
        JMP ES_READ_NEXT_ADDR
ES_LONG_46:
        INC ES_DST+1
ES_READ_NEXT_ADDR:
        INC ES_A0
        BEQ ES_LONG_47
        JMP ES_READ_NEXT
ES_LONG_47:
        INC ES_A1
        BEQ ES_LONG_48
        JMP ES_READ_NEXT
ES_LONG_48:
        INC ES_A2
ES_READ_NEXT:
        DEC ES_COUNT
        BEQ ES_LONG_49
        JMP ES_READ_LOOP
ES_LONG_49:
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
        BCS ES_LONG_50
        JMP ES_BIT_ZERO
ES_LONG_50:
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
        BEQ ES_LONG_51
        JMP ES_BIT
ES_LONG_51:
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
        BCS ES_LONG_52
        JMP ES_CRC_NO_XOR
ES_LONG_52:
        LDA ES_CRC
        EOR #$21
        STA ES_CRC
        LDA ES_CRC+1
        EOR #$10
        STA ES_CRC+1
ES_CRC_NO_XOR:
        DEX
        BEQ ES_LONG_53
        JMP ES_CRC_BIT
ES_LONG_53:
        INC ES_PTR
        BEQ ES_LONG_54
        JMP ES_CRC_ADVANCE
ES_LONG_54:
        INC ES_PTR+1
ES_CRC_ADVANCE:
        LDA ES_LEFT
        BEQ ES_LONG_55
        JMP ES_CRC_DEC
ES_LONG_55:
        DEC ES_LEFT+1
ES_CRC_DEC:
        DEC ES_LEFT
        LDA ES_LEFT
        ORA ES_LEFT+1
        BEQ ES_LONG_56
        JMP ES_CRC_NEXT
ES_LONG_56:
        RTS
ES_EXPECTED_MAGIC: DB "ESR",1
ES_END:
        ENDMOD
        END
