; Shared implementation: linked in each MON and in standalone RAM CONFIG.
; F owns no journal mutation. Input mode in A: read/set default/count/promote/W/init.
JE_HANDLER EQU $7C60
JE_REQUEST EQU $7C62
JE_MODE EQU $7C63
JE_DEST EQU $7C64
JE_PEER EQU $7C65
JE_SAVE_INDEX EQU $7C66
JE_INPUT EQU $7C40
JE_FRAME EQU $6700
JE_ENTER:
        STA JE_MODE
        PHX
        PHY
        LDX #31
JE_SAVE: LDA $E0,X
        STA J_SAVED_ZP,X
        DEX
        BMI CE_LONG_1
        JMP JE_SAVE
CE_LONG_1:
        LDX #15
JE_IN:  LDA V2_CONFIG,X
        STA JE_INPUT,X
        DEX
        BMI CE_LONG_2
        JMP JE_IN
CE_LONG_2:
        LDA J_COUNTINDEX
        STA JE_SAVE_INDEX
        LDA JE_MODE
        CMP #5
        BEQ CE_LONG_3
        JMP JE_LONG_3
CE_LONG_3:
        JMP JE_INIT
JE_LONG_3:
        JSR JE_READ
        BCC CE_LONG_4
        JMP JE_LONG_4
CE_LONG_4:
        JMP JE_FAIL
JE_LONG_4:
        LDA JE_MODE
        BEQ CE_LONG_5
        JMP JE_LONG_5
CE_LONG_5:
        JMP JE_OK
JE_LONG_5:
        CMP #4
        BEQ CE_LONG_6
        JMP JE_LONG_6
CE_LONG_6:
        JMP JE_REPORT
JE_LONG_6:
        LDA JE_MODE
        CMP #2
        BNE CE_LONG_7
        JMP JE_COUNT
CE_LONG_7:
        CMP #3
        BNE CE_LONG_8
        JMP JE_PROMOTE
CE_LONG_8:
        CMP #6
        BEQ CE_LONG_9
        JMP CONFIG_NOT_BANK
CE_LONG_9:
        JMP CONFIG_BANK_APPLY
CONFIG_NOT_BANK:
        LDA JE_REQUEST
        JMP JE_TARGET
JE_PROMOTE:
        LDX #15
JE_PROMOTE_COPY:
        LDA JE_INPUT,X
        STA JE_FRAME+$20,X
        DEX
        BMI CE_LONG_10
        JMP JE_PROMOTE_COPY
CE_LONG_10:
        LDA JE_INPUT+8
        CMP #$A0
        BCS CE_LONG_11
        JMP JE_FAIL
CE_LONG_11:
        BNE CE_LONG_12
        JMP JE_PROMOTE_A
CE_LONG_12:
        CMP #$B0
        BEQ CE_LONG_13
        JMP JE_FAIL
CE_LONG_13:
        LDA #'B'
        JMP JE_TARGET
JE_PROMOTE_A:
        LDA #'A'
JE_TARGET:
        STA JE_FRAME+7
        JSR BOOT_CHECK_FIELDS
        BCS CE_LONG_14
        JMP JE_FAIL
CE_LONG_14:
        LDA JE_FRAME+7
        CMP #'A'
        BNE CE_LONG_15
        JMP JE_PIN_A
CE_LONG_15:
        CMP #'B'
        BEQ CE_LONG_16
        JMP JE_APPEND
CE_LONG_16:
        LDA #$B0
        JMP JE_PIN
JE_PIN_A: LDA #$A0
JE_PIN: STA BOOT_DEST
        STA V2_PTR+1
        STZ V2_PTR
        JSR BOOT_SLOT_CHECK
        BCS CE_LONG_17
        JMP JE_FAIL
CE_LONG_17:
        LDY #8
JE_PIN_GEN:
        LDA (V2_PTR),Y
        STA JE_FRAME+$0A,Y
        INY
        CPY #12
        BEQ CE_LONG_18
        JMP JE_PIN_GEN
CE_LONG_18:
        JMP JE_APPEND
JE_COUNT:
        LDA JE_SAVE_INDEX
        JSR JE_INC
        BCS CE_LONG_19
        JMP JE_FAIL
CE_LONG_19:
JE_APPEND:
        LDA JE_MODE
        CMP #5
        BNE CE_LONG_20
        JMP JE_COMMIT
CE_LONG_20:
        JSR JE_SPACE
        BCS CE_LONG_21
        JMP JE_FAIL
CE_LONG_21:
JE_COMMIT:
        JSR JE_SEAL
        BCS CE_LONG_22
        JMP JE_FAIL
CE_LONG_22:
        JSR JE_WRITE
        BCS CE_LONG_23
        JMP JE_FAIL
CE_LONG_23:
JE_OK:  LDA #1
        JMP JE_EXIT
JE_FAIL: LDA #0
JE_EXIT:
        STA J_STATUS
        LDX #31
JE_RESTORE:
        LDA J_SAVED_ZP,X
        STA $E0,X
        DEX
        BMI CE_LONG_24
        JMP JE_RESTORE
CE_LONG_24:
        PLY
        PLX
        LDA J_STATUS
        CMP #1
        RTS

JE_READ:
        JSR BOOT_READ_RECORD
        BCS CE_LONG_25
        JMP JE_READ_BAD
CE_LONG_25:
        STZ V2_PTR
        LDA J_BEST+1
        STA V2_PTR+1
        LDY #0
JE_LOAD:
        LDA (V2_PTR),Y
        STA JE_FRAME,Y
        INY
        BEQ CE_LONG_26
        JMP JE_LOAD
CE_LONG_26:
        JSR J_CRC_INIT
        LDY #0
JE_FULL_CRC:
        LDA JE_FRAME,Y
        JSR J_CRC_BYTE
        INY
        CPY #$FC
        BEQ CE_LONG_27
        JMP JE_FULL_CRC
CE_LONG_27:
        LDA J_CRC
        CMP JE_FRAME+$FC
        BEQ CE_LONG_28
        JMP JE_READ_BAD
CE_LONG_28:
        LDA J_CRC+1
        CMP JE_FRAME+$FD
        BEQ CE_LONG_29
        JMP JE_READ_BAD
CE_LONG_29:
        LDA JE_FRAME+$FE
        CMP #$FF
        BEQ CE_LONG_30
        JMP JE_READ_BAD
CE_LONG_30:
        JSR JE_CHECK_DUPLICATES
        BCS CE_LONG_31
        JMP JE_READ_BAD
CE_LONG_31:
        LDX #15
JE_CFG_COPY:
        LDA JE_FRAME+$20,X
        STA V2_CONFIG,X
        DEX
        BMI CE_LONG_32
        JMP JE_CFG_COPY
CE_LONG_32:
        SEC
        RTS
JE_READ_BAD: CLC
        RTS

JE_INC:
        CMP #32
        BCC CE_LONG_33
        JMP JE_READ_BAD
CE_LONG_33:
        STA J_INDEX
        ASL A
        CLC
        ADC J_INDEX
        ADC #$40
        TAX
        LDA JE_FRAME,X
        AND JE_FRAME+1,X
        AND JE_FRAME+2,X
        CMP #$FF
        BNE CE_LONG_34
        JMP JE_READ_BAD
CE_LONG_34:
        INC JE_FRAME,X
        BEQ CE_LONG_35
        JMP JE_INC_OK
CE_LONG_35:
        INC JE_FRAME+1,X
        BEQ CE_LONG_36
        JMP JE_INC_OK
CE_LONG_36:
        INC JE_FRAME+2,X
JE_INC_OK: SEC
        RTS

; Keep the final page for a committed peer-erase intent. No retry without room.
JE_SPACE:
        LDA J_BEST+1
        AND #$F0
        EOR #$10
        STA JE_PEER
        LDA J_BEST+1
        INC A
JE_FIND:
        STA JE_DEST
        AND #$0F
        CMP #$0F
        BCC CE_LONG_37
        JMP JE_ROTATE
CE_LONG_37:
        BNE CE_LONG_38
        JMP JE_ROTATE
CE_LONG_38:
        LDA JE_DEST
        AND #$F0
        CMP JE_PEER
        BNE CE_LONG_39
        JMP JE_ROTATE
CE_LONG_39:
        LDA JE_DEST
        JSR JE_PAGE_BLANK
        BCC CE_LONG_40
        JMP JE_SPACE_OK
CE_LONG_40:
        LDA JE_DEST
        INC A
        JMP JE_FIND
JE_ROTATE:
        LDA JE_PEER
        JSR JE_SECTOR_BLANK
        BCC CE_LONG_41
        JMP JE_PEER_FREE
CE_LONG_41:
        LDA JE_DEST
        AND #$0F
        CMP #$0F
        BEQ CE_LONG_42
        JMP JE_SPACE_BAD
CE_LONG_42:
        LDA JE_DEST
        JSR JE_PAGE_BLANK
        BCS CE_LONG_43
        JMP JE_SPACE_BAD
CE_LONG_43:
        LDA JE_PEER
        CMP #$D0
        LDA #28
        BCS CE_LONG_44
        JMP JE_PEER_INDEX
CE_LONG_44:
        LDA #29
JE_PEER_INDEX:
        JSR JE_INC
        BCS CE_LONG_45
        JMP JE_SPACE_BAD
CE_LONG_45:
        JSR JE_SEAL
        BCS CE_LONG_46
        JMP JE_SPACE_BAD
CE_LONG_46:
        JSR JE_WRITE
        BCS CE_LONG_47
        JMP JE_SPACE_BAD
CE_LONG_47:
        STZ V2_FLASH_PTR
        LDA JE_PEER
        STA V2_FLASH_PTR+1
        JSR V2W_ERASE_RAW
        BCS CE_LONG_48
        JMP JE_SPACE_BAD
CE_LONG_48:
        LDA JE_PEER
        JSR JE_SECTOR_BLANK
        BCS CE_LONG_49
        JMP JE_SPACE_BAD
CE_LONG_49:
JE_PEER_FREE:
        LDA JE_PEER
        STA JE_DEST
JE_SPACE_OK: SEC
        RTS
JE_SPACE_BAD: CLC
        RTS

JE_PAGE_BLANK:
        STZ V2_PTR
        STA V2_PTR+1
        LDY #0
JE_BLANK_BYTE:
        LDA (V2_PTR),Y
        CMP #$FF
        BEQ CE_LONG_50
        JMP JE_SPACE_BAD
CE_LONG_50:
        INY
        BEQ CE_LONG_51
        JMP JE_BLANK_BYTE
CE_LONG_51:
        SEC
        RTS
JE_SECTOR_BLANK:
        STA BOOT_IO_PAGE
JE_BLANK_PAGE:
        JSR JE_PAGE_BLANK
        BCS CE_LONG_52
        JMP JE_SPACE_BAD
CE_LONG_52:
        INC BOOT_IO_PAGE
        LDA BOOT_IO_PAGE
        AND #15
        BEQ CE_LONG_53
        JMP JE_BLANK_PAGE_NEXT
CE_LONG_53:
        SEC
        RTS
JE_BLANK_PAGE_NEXT:
        LDA BOOT_IO_PAGE
        JMP JE_BLANK_PAGE

JE_SEAL:
        LDX #3
        LDA #$FF
JE_SEQ_FULL:
        AND JE_FRAME+8,X
        DEX
        BMI CE_LONG_54
        JMP JE_SEQ_FULL
CE_LONG_54:
        CMP #$FF
        BNE CE_LONG_55
        JMP JE_SPACE_BAD
CE_LONG_55:
        LDX #0
JE_SEQ_INC:
        INC JE_FRAME+8,X
        BEQ CE_LONG_56
        JMP JE_SEQ_OK
CE_LONG_56:
        INX
        CPX #4
        BEQ CE_LONG_57
        JMP JE_SEQ_INC
CE_LONG_57:
JE_SEQ_OK:
        LDA #$FF
        STA JE_FRAME+$FF
        JSR J_CRC_INIT
        LDY #0
JE_BOOT_CRC:
        LDA JE_FRAME,Y
        JSR J_CRC_BYTE
        INY
        CPY #30
        BEQ CE_LONG_58
        JMP JE_BOOT_CRC
CE_LONG_58:
        LDA J_CRC
        STA JE_FRAME+30
        LDA J_CRC+1
        STA JE_FRAME+31
        JSR J_CRC_INIT
        LDY #0
JE_SEAL_CRC:
        LDA JE_FRAME,Y
        JSR J_CRC_BYTE
        INY
        CPY #$FC
        BEQ CE_LONG_59
        JMP JE_SEAL_CRC
CE_LONG_59:
        LDA J_CRC
        STA JE_FRAME+$FC
        LDA J_CRC+1
        STA JE_FRAME+$FD
        SEC
        RTS

JE_WRITE:
        LDA JE_DEST
        JSR JE_PAGE_BLANK
        BCC CE_LONG_60
        JMP JE_LONG_59
CE_LONG_60:
        JMP JE_SPACE_BAD
JE_LONG_59:
        STZ V2_FLASH_PTR
        LDA JE_DEST
        STA V2_FLASH_PTR+1
        STZ J_INDEX
JE_WRITE_BYTE:
        LDX J_INDEX
        LDA JE_FRAME,X
        CMP #$FF
        BNE CE_LONG_61
        JMP JE_WRITE_NEXT
CE_LONG_61:
        STA V2_FLASH_DATA
        JSR V2W_BYTE
        BCC CE_LONG_62
        JMP JE_LONG_61
CE_LONG_62:
        JMP JE_SPACE_BAD
JE_LONG_61:
JE_WRITE_NEXT:
        INC V2_FLASH_PTR
        INC J_INDEX
        LDA J_INDEX
        CMP #$FF
        BEQ CE_LONG_63
        JMP JE_WRITE_BYTE
CE_LONG_63:
        STZ V2_PTR
        LDA JE_DEST
        STA V2_PTR+1
        LDY #0
JE_VERIFY:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BNE CE_LONG_64
        JMP JE_LONG_63
CE_LONG_64:
        JMP JE_SPACE_BAD
JE_LONG_63:
        INY
        CPY #$FF
        BEQ CE_LONG_65
        JMP JE_VERIFY
CE_LONG_65:
        STZ V2_FLASH_DATA
        JSR V2W_BYTE
        BCC CE_LONG_66
        JMP JE_LONG_65
CE_LONG_66:
        JMP JE_SPACE_BAD
JE_LONG_65:
        LDY #$FF
        LDA (V2_PTR),Y
        BNE CE_LONG_67
        JMP JE_LONG_66
CE_LONG_67:
        JMP JE_SPACE_BAD
JE_LONG_66:
        SEC
        RTS

JE_REPORT:
        STZ J_INDEX
JE_ROW:
        LDA #'B'
        JSR V2W_PUTC
        LDA J_INDEX
        LSR A
        LSR A
        LSR A
        ORA #'0'
        JSR V2W_PUTC
        LDA #':'
        JSR V2W_PUTC
        LDA J_INDEX
        AND #7
        CLC
        ADC #8
        JSR V2V_RAM_NIBBLE_OUT
        LDA #' '
        JSR V2W_PUTC
        LDA J_INDEX
        ASL A
        ADC J_INDEX
        TAX
        LDA JE_FRAME+$42,X
        JSR V2V_RAM_HEX_OUT
        LDA JE_FRAME+$41,X
        JSR V2V_RAM_HEX_OUT
        LDA JE_FRAME+$40,X
        JSR V2V_RAM_HEX_OUT
        JSR V2V_RAM_NEWLINE
        INC J_INDEX
        LDA J_INDEX
        CMP #32
        BEQ CE_LONG_68
        JMP JE_ROW
CE_LONG_68:
        LDA JE_FRAME+$A0
        ORA JE_FRAME+$A1
        ORA JE_FRAME+$A2
        ORA JE_FRAME+$A3
        BNE CE_LONG_69
        JMP JE_REPORT_DONE
CE_LONG_69:
        LDX #<JE_UNKNOWN
        LDY #>JE_UNKNOWN
        JSR BOOT_PRINT
JE_REPORT_DONE:
        JMP JE_OK
JE_UNKNOWN: DB "UNKNOWN HISTORY",13,10,0

; Initialization never erases. Nonblank/damaged C/D need inspected repair.
JE_INIT:
        LDA #$C0
        JSR JE_SECTOR_BLANK
        BCC CE_LONG_70
        JMP JE_LONG_69
CE_LONG_70:
        JMP JE_FAIL
JE_LONG_69:
        LDA #$D0
        JSR JE_SECTOR_BLANK
        BCC CE_LONG_71
        JMP JE_LONG_70
CE_LONG_71:
        JMP JE_FAIL
JE_LONG_70:
        LDY #0
        LDA #$FF
JE_INIT_FILL:
        STA JE_FRAME,Y
        INY
        BEQ CE_LONG_72
        JMP JE_INIT_FILL
CE_LONG_72:
        LDX #31
JE_INIT_HEADER:
        LDA JE_INITIAL,X
        STA JE_FRAME,X
        DEX
        BMI CE_LONG_73
        JMP JE_INIT_HEADER
CE_LONG_73:
        LDX #95
        LDA #0
JE_INIT_COUNTS:
        STA JE_FRAME+$40,X
        DEX
        BMI CE_LONG_74
        JMP JE_INIT_COUNTS
CE_LONG_74:
        LDA #$C0
        STA JE_DEST
        JMP JE_APPEND
JE_INITIAL:
        DB "SNBT",1,32,0,'S',0,0,0,0,30,0,8,8,8,8
        DB 0,0,0,0,0,0,0,0,0,0,0,0,0,0
; Mutation admission is stricter than F's boot-record-only reader.
; A committed same-sequence SNBT page must agree in every byte. Refuse even
; if a disagreeing candidate has a bad body CRC: history is then uncertain.
; Uncommitted/torn pages and other formats/sequences do not participate.
JE_CHECK_DUPLICATES:
        STZ V2_PTR
        LDA #$C0
        STA V2_PTR+1
JE_DUP_PAGE:
        LDY #$FF
        LDA (V2_PTR),Y
        BEQ CE_LONG_75
        JMP JE_DUP_NEXT
CE_LONG_75:
        LDY #5
JE_DUP_MAGIC:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BEQ CE_LONG_76
        JMP JE_DUP_NEXT
CE_LONG_76:
        DEY
        BMI CE_LONG_77
        JMP JE_DUP_MAGIC
CE_LONG_77:
        LDY #11
JE_DUP_SEQUENCE:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BEQ CE_LONG_78
        JMP JE_DUP_NEXT
CE_LONG_78:
        DEY
        CPY #7
        BEQ CE_LONG_79
        JMP JE_DUP_SEQUENCE
CE_LONG_79:
        LDY #0
JE_DUP_BYTES:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BEQ CE_LONG_80
        JMP JE_DUP_REFUSED
CE_LONG_80:
        INY
        BEQ CE_LONG_81
        JMP JE_DUP_BYTES
CE_LONG_81:
JE_DUP_NEXT:
        INC V2_PTR+1
        LDA V2_PTR+1
        CMP #$E0
        BEQ CE_LONG_82
        JMP JE_DUP_PAGE
CE_LONG_82:
        SEC
        RTS
JE_DUP_REFUSED:
        CLC
        RTS

JE_END:
