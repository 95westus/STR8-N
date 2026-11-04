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
        BPL JE_SAVE
        LDX #15
JE_IN:  LDA V2_CONFIG,X
        STA JE_INPUT,X
        DEX
        BPL JE_IN
        LDA J_COUNTINDEX
        STA JE_SAVE_INDEX
        LDA JE_MODE
        CMP #5
        BNE JE_LONG_3
        JMP JE_INIT
JE_LONG_3:
        JSR JE_READ
        BCS JE_LONG_4
        JMP JE_FAIL
JE_LONG_4:
        LDA JE_MODE
        BNE JE_LONG_5
        JMP JE_OK
JE_LONG_5:
        CMP #4
        BNE JE_LONG_6
        JMP JE_REPORT
JE_LONG_6:
        LDA JE_MODE
        CMP #2
        BEQ JE_COUNT
        CMP #3
        BEQ JE_PROMOTE
        LDA JE_REQUEST
        JMP JE_TARGET
JE_PROMOTE:
        LDX #15
JE_PROMOTE_COPY:
        LDA JE_INPUT,X
        STA JE_FRAME+$20,X
        DEX
        BPL JE_PROMOTE_COPY
        LDA JE_INPUT+8
        CMP #$A0
        BCC JE_FAIL
        BEQ JE_PROMOTE_A
        CMP #$B0
        BNE JE_FAIL
        LDA #'B'
        JMP JE_TARGET
JE_PROMOTE_A:
        LDA #'A'
JE_TARGET:
        STA JE_FRAME+7
        JSR BOOT_CHECK_FIELDS
        BCC JE_FAIL
        LDA JE_FRAME+7
        CMP #'A'
        BEQ JE_PIN_A
        CMP #'B'
        BNE JE_APPEND
        LDA #$B0
        JMP JE_PIN
JE_PIN_A: LDA #$A0
JE_PIN: STA BOOT_DEST
        STA V2_PTR+1
        STZ V2_PTR
        JSR BOOT_SLOT_CHECK
        BCC JE_FAIL
        LDY #8
JE_PIN_GEN:
        LDA (V2_PTR),Y
        STA JE_FRAME+$0A,Y
        INY
        CPY #12
        BNE JE_PIN_GEN
        JMP JE_APPEND
JE_COUNT:
        LDA JE_SAVE_INDEX
        JSR JE_INC
        BCC JE_FAIL
JE_APPEND:
        LDA JE_MODE
        CMP #5
        BEQ JE_COMMIT
        JSR JE_SPACE
        BCC JE_FAIL
JE_COMMIT:
        JSR JE_SEAL
        BCC JE_FAIL
        JSR JE_WRITE
        BCC JE_FAIL
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
        BPL JE_RESTORE
        PLY
        PLX
        LDA J_STATUS
        CMP #1
        RTS

JE_READ:
        JSR BOOT_READ_RECORD
        BCC JE_READ_BAD
        STZ V2_PTR
        LDA J_BEST+1
        STA V2_PTR+1
        LDY #0
JE_LOAD:
        LDA (V2_PTR),Y
        STA JE_FRAME,Y
        INY
        BNE JE_LOAD
        JSR J_CRC_INIT
        LDY #0
JE_FULL_CRC:
        LDA JE_FRAME,Y
        JSR J_CRC_BYTE
        INY
        CPY #$FC
        BNE JE_FULL_CRC
        LDA J_CRC
        CMP JE_FRAME+$FC
        BNE JE_READ_BAD
        LDA J_CRC+1
        CMP JE_FRAME+$FD
        BNE JE_READ_BAD
        LDA JE_FRAME+$FE
        CMP #$FF
        BNE JE_READ_BAD
        JSR JE_CHECK_DUPLICATES
        BCC JE_READ_BAD
        LDX #15
JE_CFG_COPY:
        LDA JE_FRAME+$20,X
        STA V2_CONFIG,X
        DEX
        BPL JE_CFG_COPY
        SEC
        RTS
JE_READ_BAD: CLC
        RTS

JE_INC:
        CMP #32
        BCS JE_READ_BAD
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
        BEQ JE_READ_BAD
        INC JE_FRAME,X
        BNE JE_INC_OK
        INC JE_FRAME+1,X
        BNE JE_INC_OK
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
        BCS JE_ROTATE
        BEQ JE_ROTATE
        LDA JE_DEST
        AND #$F0
        CMP JE_PEER
        BEQ JE_ROTATE
        LDA JE_DEST
        JSR JE_PAGE_BLANK
        BCS JE_SPACE_OK
        LDA JE_DEST
        INC A
        JMP JE_FIND
JE_ROTATE:
        LDA JE_PEER
        JSR JE_SECTOR_BLANK
        BCS JE_PEER_FREE
        LDA JE_DEST
        AND #$0F
        CMP #$0F
        BNE JE_SPACE_BAD
        LDA JE_DEST
        JSR JE_PAGE_BLANK
        BCC JE_SPACE_BAD
        LDA JE_PEER
        CMP #$D0
        LDA #28
        BCC JE_PEER_INDEX
        LDA #29
JE_PEER_INDEX:
        JSR JE_INC
        BCC JE_SPACE_BAD
        JSR JE_SEAL
        BCC JE_SPACE_BAD
        JSR JE_WRITE
        BCC JE_SPACE_BAD
        STZ V2_FLASH_PTR
        LDA JE_PEER
        STA V2_FLASH_PTR+1
        JSR V2W_ERASE_RAW
        BCC JE_SPACE_BAD
        LDA JE_PEER
        JSR JE_SECTOR_BLANK
        BCC JE_SPACE_BAD
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
        BNE JE_SPACE_BAD
        INY
        BNE JE_BLANK_BYTE
        SEC
        RTS
JE_SECTOR_BLANK:
        STA BOOT_IO_PAGE
JE_BLANK_PAGE:
        JSR JE_PAGE_BLANK
        BCC JE_SPACE_BAD
        INC BOOT_IO_PAGE
        LDA BOOT_IO_PAGE
        AND #15
        BNE JE_BLANK_PAGE_NEXT
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
        BPL JE_SEQ_FULL
        CMP #$FF
        BEQ JE_SPACE_BAD
        LDX #0
JE_SEQ_INC:
        INC JE_FRAME+8,X
        BNE JE_SEQ_OK
        INX
        CPX #4
        BNE JE_SEQ_INC
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
        BNE JE_BOOT_CRC
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
        BNE JE_SEAL_CRC
        LDA J_CRC
        STA JE_FRAME+$FC
        LDA J_CRC+1
        STA JE_FRAME+$FD
        SEC
        RTS

JE_WRITE:
        LDA JE_DEST
        JSR JE_PAGE_BLANK
        BCS JE_LONG_59
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
        BEQ JE_WRITE_NEXT
        STA V2_FLASH_DATA
        JSR V2W_BYTE
        BCS JE_LONG_61
        JMP JE_SPACE_BAD
JE_LONG_61:
JE_WRITE_NEXT:
        INC V2_FLASH_PTR
        INC J_INDEX
        LDA J_INDEX
        CMP #$FF
        BNE JE_WRITE_BYTE
        STZ V2_PTR
        LDA JE_DEST
        STA V2_PTR+1
        LDY #0
JE_VERIFY:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BEQ JE_LONG_63
        JMP JE_SPACE_BAD
JE_LONG_63:
        INY
        CPY #$FF
        BNE JE_VERIFY
        STZ V2_FLASH_DATA
        JSR V2W_BYTE
        BCS JE_LONG_65
        JMP JE_SPACE_BAD
JE_LONG_65:
        LDY #$FF
        LDA (V2_PTR),Y
        BEQ JE_LONG_66
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
        BNE JE_ROW
        LDA JE_FRAME+$A0
        ORA JE_FRAME+$A1
        ORA JE_FRAME+$A2
        ORA JE_FRAME+$A3
        BEQ JE_REPORT_DONE
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
        BCS JE_LONG_69
        JMP JE_FAIL
JE_LONG_69:
        LDA #$D0
        JSR JE_SECTOR_BLANK
        BCS JE_LONG_70
        JMP JE_FAIL
JE_LONG_70:
        LDY #0
        LDA #$FF
JE_INIT_FILL:
        STA JE_FRAME,Y
        INY
        BNE JE_INIT_FILL
        LDX #31
JE_INIT_HEADER:
        LDA JE_INITIAL,X
        STA JE_FRAME,X
        DEX
        BPL JE_INIT_HEADER
        LDX #95
        LDA #0
JE_INIT_COUNTS:
        STA JE_FRAME+$40,X
        DEX
        BPL JE_INIT_COUNTS
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
        BNE JE_DUP_NEXT
        LDY #5
JE_DUP_MAGIC:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BNE JE_DUP_NEXT
        DEY
        BPL JE_DUP_MAGIC
        LDY #11
JE_DUP_SEQUENCE:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BNE JE_DUP_NEXT
        DEY
        CPY #7
        BNE JE_DUP_SEQUENCE
        LDY #0
JE_DUP_BYTES:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BNE JE_DUP_REFUSED
        INY
        BNE JE_DUP_BYTES
JE_DUP_NEXT:
        INC V2_PTR+1
        LDA V2_PTR+1
        CMP #$E0
        BNE JE_DUP_PAGE
        SEC
        RTS
JE_DUP_REFUSED:
        CLC
        RTS

JE_END:
