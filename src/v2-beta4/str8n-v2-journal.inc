; Two 4K C/D journals, 32 snapshots each. Each 128-byte snapshot contains
; config[16], 32 saturating 24-bit erase-attempt counts, sequence and CRC16.
; Every byte is programmed once per erase; byte 127 is the final commit.
; A rollover records the peer's erase intent in the source BEFORE erasing it.
; If interrupted retries exhaust source space, refuse writes, never lose the
; last snapshot or issue an unaccounted erase. Counts start at provisioning.
BOOT_META_READ:         STZ J_MODE
                        BRA J_ENTER
BOOT_META_CFG:          LDA #$01
                        STA J_MODE
                        BRA J_ENTER
BOOT_META_ERASE:        LDA #$02
                        STA J_MODE
                        BRA J_ENTER
BOOT_META_PROMOTE:      LDA #$03
                        STA J_MODE
J_ENTER:                PHX
                        PHY
                        LDX #$1F
J_SAVE_ZP:              LDA $E0,X
                        STA J_SAVED_ZP,X
                        DEX
                        BPL J_SAVE_ZP
                        STZ J_STATUS
                        JSR J_SCAN_ALL
                        LDA J_BEST+1
                        BEQ J_NO_RECORD
                        JSR J_LOAD_BEST
                        LDA J_MODE
                        BEQ J_READ_CONFIG
                        CMP #$02
                        BEQ J_COUNT_ERASE
                        CMP #$01
                        BNE J_CFG_START
                        LDA J_BUFFER+15
                        CMP #'P'
                        BNE J_CFG_START
; Old monitors clear the reserved config bytes when editing C. Preserve the
; promotion preference centrally so their C command cannot promote a candidate.
                        LDX #$06
J_KEEP_PREFERENCE:      LDA J_BUFFER+15,X
                        STA V2_CONFIG+7,X
                        DEX
                        BPL J_KEEP_PREFERENCE
                        JSR J_CONFIG_SUM
J_CFG_START:
                        LDX #$0F
J_CFG_COMPARE:          LDA V2_CONFIG,X
                        CMP J_BUFFER+8,X
                        BNE J_CFG_CHANGED
                        DEX
                        BPL J_CFG_COMPARE
                        BRA J_SUCCESS
J_CFG_CHANGED:          LDX #$0F
J_CFG_COPY:             LDA V2_CONFIG,X
                        STA J_BUFFER+8,X
                        DEX
                        BPL J_CFG_COPY
                        BRA J_APPEND
J_COUNT_ERASE:          JSR J_INCREMENT_COUNT
                        BCC J_EXIT
J_APPEND:              JSR J_FIND_FREE
                        LDA J_BEST+1
                        AND #$F0
                        EOR #$10
                        STA BOOT_IO_PAGE
; Keep the final source record available for a peer erase intent. If the peer
; is already blank after an interruption, resume without erasing it again.
                        LDA J_OUT+1
                        BEQ J_ROTATE
                        AND #$0F
                        CMP #$0F
                        BNE J_APPEND_NORMAL
                        LDA J_OUT
                        CMP #$80
                        BCC J_APPEND_NORMAL
J_ROTATE:               STZ J_SCAN
                        LDA BOOT_IO_PAGE
                        STA J_SCAN+1
                        JSR J_SECTOR_BLANK
                        BCS J_PEER_READY
                        LDA J_OUT+1
                        BEQ J_EXIT
                        LDA BOOT_IO_PAGE
                        CMP #$D0
                        BNE J_PEER_C
                        LDA #$1D
                        BRA J_PEER_INDEX
J_PEER_C:               LDA #$1C
J_PEER_INDEX:           STA J_COUNTINDEX
                        JSR J_INCREMENT_COUNT
                        BCC J_EXIT
                        JSR J_PREPARE
                        BCC J_EXIT
                        JSR J_WRITE
                        BCC J_EXIT
                        STZ V2_FLASH_PTR
                        LDA BOOT_IO_PAGE
                        STA V2_FLASH_PTR+1
                        JSR V2W_ERASE_RAW
                        BCC J_EXIT
                        STZ J_SCAN
                        LDA BOOT_IO_PAGE
                        STA J_SCAN+1
                        JSR J_SECTOR_BLANK
                        BCC J_EXIT
J_PEER_READY:           STZ J_OUT
                        LDA BOOT_IO_PAGE
                        STA J_OUT+1
J_APPEND_NORMAL:        JSR J_PREPARE
                        BCC J_EXIT
                        JSR J_WRITE
                        BCC J_EXIT
                        BRA J_SUCCESS
J_READ_CONFIG:          LDX #$0F
J_READ_COPY:            LDA J_BUFFER+8,X
                        STA V2_CONFIG,X
                        DEX
                        BPL J_READ_COPY
J_SUCCESS:              INC J_STATUS
                        BRA J_EXIT
J_NO_RECORD:            LDX #$0F
                        LDA #$FF
J_ERASED_CONFIG:        STA V2_CONFIG,X
                        DEX
                        BPL J_ERASED_CONFIG
J_EXIT:                 LDX #$1F
J_RESTORE_ZP:           LDA J_SAVED_ZP,X
                        STA $E0,X
                        DEX
                        BPL J_RESTORE_ZP
                        PLY
                        PLX
                        LDA J_STATUS
                        CMP #$01
                        RTS

J_CONFIG_SUM:           STZ J_CRC
                        STZ J_CRC+1
                        LDX #$00
J_CONFIG_SUM_BYTE:      LDA V2_CONFIG,X
                        CLC
                        ADC J_CRC
                        STA J_CRC
                        CLC
                        ADC J_CRC+1
                        STA J_CRC+1
                        INX
                        CPX #$0E
                        BNE J_CONFIG_SUM_BYTE
                        LDA J_CRC
                        STA V2_CONFIG+14
                        LDA J_CRC+1
                        STA V2_CONFIG+15
                        RTS

J_INCREMENT_COUNT:      LDA J_COUNTINDEX
                        CMP #$20
                        BCS J_COUNT_FULL
                        ASL A
                        CLC
                        ADC J_COUNTINDEX
                        TAX
                        LDA J_BUFFER+24,X
                        AND J_BUFFER+25,X
                        AND J_BUFFER+26,X
                        CMP #$FF
                        BEQ J_COUNT_FULL
                        INC J_BUFFER+24,X
                        BNE J_COUNT_OK
                        INC J_BUFFER+25,X
                        BNE J_COUNT_OK
                        INC J_BUFFER+26,X
J_COUNT_OK:             SEC
                        RTS
J_COUNT_FULL:           CLC
                        RTS

J_PREPARE:              LDX #$03
                        LDA #$FF
J_SEQ_FULL:             AND J_BUFFER+4,X
                        DEX
                        BPL J_SEQ_FULL
                        CMP #$FF
                        BEQ J_COUNT_FULL
                        INC J_BUFFER+4
                        BNE J_SEQ_READY
                        INC J_BUFFER+5
                        BNE J_SEQ_READY
                        INC J_BUFFER+6
                        BNE J_SEQ_READY
                        INC J_BUFFER+7
J_SEQ_READY:            LDA #<J_BUFFER
                        STA V2_PTR
                        LDA #>J_BUFFER
                        STA V2_PTR+1
                        JSR J_CRC_INIT
                        LDY #$00
J_PREP_CRC:             LDA (V2_PTR),Y
                        JSR J_CRC_BYTE
                        INY
                        CPY #$78
                        BNE J_PREP_CRC
                        LDA J_CRC
                        STA J_BUFFER+120
                        LDA J_CRC+1
                        STA J_BUFFER+121
                        SEC
                        RTS

J_WRITE:                LDA J_OUT+1
                        BEQ J_WRITE_FAIL
                        LDA J_OUT
                        STA V2_FLASH_PTR
                        LDA J_OUT+1
                        STA V2_FLASH_PTR+1
                        STZ J_INDEX
; Refuse anything except a completely unused record, including torn records.
                        LDY #$00
J_DEST_BLANK:           LDA (V2_FLASH_PTR),Y
                        CMP #$FF
                        BNE J_WRITE_FAIL
                        INY
                        BPL J_DEST_BLANK
J_WRITE_BYTE:           LDX J_INDEX
                        LDA J_BUFFER,X
                        CMP #$FF
                        BEQ J_WRITE_NEXT
                        STA V2_FLASH_DATA
                        JSR V2W_BYTE
                        BCC J_WRITE_FAIL
J_WRITE_NEXT:           INC V2_FLASH_PTR
                        INC J_INDEX
                        LDA J_INDEX
                        CMP #$7F
                        BNE J_WRITE_BYTE
; Verify the body before publishing the previously unwritten commit byte.
                        LDA J_OUT
                        STA V2_FLASH_PTR
                        LDY #$00
J_BODY_VERIFY:          LDA (V2_FLASH_PTR),Y
                        CMP J_BUFFER,Y
                        BNE J_WRITE_FAIL
                        INY
                        CPY #$7F
                        BNE J_BODY_VERIFY
                        TYA
                        CLC
                        ADC J_OUT
                        STA V2_FLASH_PTR
                        STZ V2_FLASH_DATA
                        JSR V2W_BYTE
                        BCC J_WRITE_FAIL
                        LDA J_OUT
                        STA V2_FLASH_PTR
                        LDY #$00
J_FINAL_VERIFY:         LDA (V2_FLASH_PTR),Y
                        CMP J_BUFFER,Y
                        BNE J_WRITE_FAIL
                        INY
                        BPL J_FINAL_VERIFY
                        SEC
                        RTS
J_WRITE_FAIL:           CLC
                        RTS

J_SCAN_ALL:             STZ J_BEST
                        STZ J_BEST+1
                        STZ J_SCAN
                        LDA #$C0
                        STA J_SCAN+1
J_SCAN_RECORD:          LDA J_SCAN
                        STA V2_PTR
                        LDA J_SCAN+1
                        STA V2_PTR+1
                        JSR J_VALID
                        BCC J_SCAN_NEXT
                        LDA J_BEST+1
                        BEQ J_NEWEST
                        LDA J_BEST
                        STA V2_ADDR
                        LDA J_BEST+1
                        STA V2_ADDR+1
                        LDY #$07
J_SEQ_COMPARE:          LDA (V2_PTR),Y
                        CMP (V2_ADDR),Y
                        BCC J_SCAN_NEXT
                        BNE J_NEWEST
                        DEY
                        CPY #$03
                        BNE J_SEQ_COMPARE
                        BRA J_SCAN_NEXT
J_NEWEST:               LDA J_SCAN
                        STA J_BEST
                        LDA J_SCAN+1
                        STA J_BEST+1
J_SCAN_NEXT:            LDA J_SCAN
                        EOR #$80
                        STA J_SCAN
                        BNE J_SCAN_RECORD
                        INC J_SCAN+1
                        LDA J_SCAN+1
                        CMP #$E0
                        BNE J_SCAN_RECORD
                        RTS

J_VALID:                LDY #$7F
                        LDA (V2_PTR),Y
                        BNE J_INVALID
                        LDY #$00
                        LDA (V2_PTR),Y
                        CMP #'W'
                        BNE J_INVALID
                        INY
                        LDA (V2_PTR),Y
                        CMP #'C'
                        BNE J_INVALID
                        INY
                        LDA (V2_PTR),Y
                        CMP #$01
                        BNE J_INVALID
                        INY
                        LDA (V2_PTR),Y
                        BNE J_INVALID
                        JSR J_CRC_INIT
                        LDY #$00
J_VALID_CRC:            LDA (V2_PTR),Y
                        JSR J_CRC_BYTE
                        INY
                        CPY #$78
                        BNE J_VALID_CRC
                        LDA (V2_PTR),Y
                        CMP J_CRC
                        BNE J_INVALID
                        INY
                        LDA (V2_PTR),Y
                        CMP J_CRC+1
                        BNE J_INVALID
                        SEC
                        RTS
J_INVALID:              CLC
                        RTS

J_LOAD_BEST:            LDA J_BEST
                        STA V2_PTR
                        LDA J_BEST+1
                        STA V2_PTR+1
                        LDY #$00
J_LOAD_BYTE:            LDA (V2_PTR),Y
                        STA J_BUFFER,Y
                        INY
                        BPL J_LOAD_BYTE
                        RTS

J_FIND_FREE:            LDA J_BEST
                        STA J_OUT
                        LDA J_BEST+1
                        STA J_OUT+1
                        AND #$F0
                        CLC
                        ADC #$10
                        STA BOOT_END_PAGE
J_FIND_NEXT:            LDA J_OUT
                        EOR #$80
                        STA J_OUT
                        BNE J_FIND_TEST
                        INC J_OUT+1
J_FIND_TEST:            LDA J_OUT+1
                        CMP BOOT_END_PAGE
                        BEQ J_NO_FREE
                        LDA J_OUT
                        STA V2_PTR
                        LDA J_OUT+1
                        STA V2_PTR+1
                        LDY #$00
J_FREE_BYTE:            LDA (V2_PTR),Y
                        CMP #$FF
                        BNE J_FIND_NEXT
                        INY
                        BPL J_FREE_BYTE
                        RTS
J_NO_FREE:              STZ J_OUT+1
                        RTS

J_SECTOR_BLANK:         LDA J_SCAN
                        STA V2_PTR
                        LDA J_SCAN+1
                        STA V2_PTR+1
                        CLC
                        ADC #$10
                        STA BOOT_END_PAGE
                        LDY #$00
J_SECTOR_BYTE:          LDA (V2_PTR),Y
                        CMP #$FF
                        BNE J_INVALID
                        INY
                        BNE J_SECTOR_BYTE
                        INC V2_PTR+1
                        LDA V2_PTR+1
                        CMP BOOT_END_PAGE
                        BNE J_SECTOR_BYTE
                        SEC
                        RTS

J_CRC_INIT:             LDA #$FF
                        STA J_CRC
                        STA J_CRC+1
                        RTS
; CRC16/CCITT-FALSE, polynomial 1021, initial FFFF. Y preserved.
J_CRC_BYTE:             EOR J_CRC+1
                        STA J_CRC+1
                        LDX #$08
J_CRC_BIT:              ASL J_CRC
                        ROL J_CRC+1
                        BCC J_CRC_NEXT
                        LDA J_CRC
                        EOR #$21
                        STA J_CRC
                        LDA J_CRC+1
                        EOR #$10
                        STA J_CRC+1
J_CRC_NEXT:             DEX
                        BNE J_CRC_BIT
                        RTS

BOOT_REPORT:            JSR BOOT_META_READ
                        BCC BOOT_COUNTS_UNKNOWN
                        LDX #<BOOT_COUNT_TITLE
                        LDY #>BOOT_COUNT_TITLE
                        JSR BOOT_PRINT
                        STZ J_INDEX
BOOT_REPORT_NEXT:       LDA #'B'
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
                        AND #$07
                        CLC
                        ADC #$08
                        JSR V2V_RAM_NIBBLE_OUT
                        LDA #' '
                        JSR V2W_PUTC
                        LDA J_INDEX
                        ASL A
                        CLC
                        ADC J_INDEX
                        TAX
                        LDA J_BUFFER+26,X
                        JSR V2V_RAM_HEX_OUT
                        LDA J_BUFFER+25,X
                        JSR V2V_RAM_HEX_OUT
                        LDA J_BUFFER+24,X
                        JSR V2V_RAM_HEX_OUT
                        JSR V2V_RAM_NEWLINE
                        INC J_INDEX
                        LDA J_INDEX
                        CMP #$20
                        BNE BOOT_REPORT_NEXT
                        RTS
BOOT_COUNTS_UNKNOWN:    LDX #<BOOT_UNKNOWN_TEXT
                        LDY #>BOOT_UNKNOWN_TEXT
                        JMP BOOT_PRINT
BOOT_COUNT_TITLE:       DB "ERASE ATTEMPTS SINCE PROVISIONING",$0D,$0A,0
BOOT_UNKNOWN_TEXT:      DB "JOURNAL INVALID; WRITES DISABLED",$0D,$0A,0
