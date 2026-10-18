; Two 4K C/D journals, 32 snapshots each. Each 128-byte snapshot contains
; config[16], 32 saturating 24-bit erase-attempt counts, sequence and CRC16.
; Every byte is programmed once per erase; byte 127 is the final commit.
; A rollover records the peer's erase intent in the source BEFORE erasing it.
; If interrupted retries exhaust source space, refuse writes, never lose the
; last snapshot or issue an unaccounted erase. Counts start at provisioning.
BOOT_META_READ:         STZ J_MODE
                        JMP J_ENTER
BOOT_META_CFG:          LDA #$01
                        STA J_MODE
                        JMP J_ENTER
BOOT_META_ERASE:        LDA #$02
                        STA J_MODE
                        JMP J_ENTER
BOOT_META_PROMOTE:      LDA #$03
                        STA J_MODE
J_ENTER:                PHX
                        PHY
                        LDX #$1F
J_SAVE_ZP:              LDA $E0,X
                        STA J_SAVED_ZP,X
                        DEX
                        BMI str8n_v2_journal_LONG_22
                        JMP J_SAVE_ZP
str8n_v2_journal_LONG_22:
                        STZ J_STATUS
                        JSR J_SCAN_ALL
                        LDA J_BEST+1
                        BNE str8n_v2_journal_LONG_26
                        JMP J_NO_RECORD
str8n_v2_journal_LONG_26:
                        JSR J_LOAD_BEST
                        LDA J_MODE
                        BNE str8n_v2_journal_LONG_29
                        JMP J_READ_CONFIG
str8n_v2_journal_LONG_29:
                        CMP #$02
                        BNE str8n_v2_journal_LONG_31
                        JMP J_COUNT_ERASE
str8n_v2_journal_LONG_31:
                        CMP #$01
                        BEQ str8n_v2_journal_LONG_33
                        JMP J_CFG_START
str8n_v2_journal_LONG_33:
                        LDA J_BUFFER+15
                        CMP #'P'
                        BEQ str8n_v2_journal_LONG_36
                        JMP J_CFG_START
str8n_v2_journal_LONG_36:
; Old monitors clear the reserved config bytes when editing C. Preserve the
; promotion preference centrally so their C command cannot promote a candidate.
                        LDX #$06
J_KEEP_PREFERENCE:      LDA J_BUFFER+15,X
                        STA V2_CONFIG+7,X
                        DEX
                        BMI str8n_v2_journal_LONG_43
                        JMP J_KEEP_PREFERENCE
str8n_v2_journal_LONG_43:
                        JSR J_CONFIG_SUM
J_CFG_START:
                        LDX #$0F
J_CFG_COMPARE:          LDA V2_CONFIG,X
                        CMP J_BUFFER+8,X
                        BEQ str8n_v2_journal_LONG_49
                        JMP J_CFG_CHANGED
str8n_v2_journal_LONG_49:
                        DEX
                        BMI str8n_v2_journal_LONG_51
                        JMP J_CFG_COMPARE
str8n_v2_journal_LONG_51:
                        JMP J_SUCCESS
J_CFG_CHANGED:          LDX #$0F
J_CFG_COPY:             LDA V2_CONFIG,X
                        STA J_BUFFER+8,X
                        DEX
                        BMI str8n_v2_journal_LONG_57
                        JMP J_CFG_COPY
str8n_v2_journal_LONG_57:
                        JMP J_APPEND
J_COUNT_ERASE:          JSR J_INCREMENT_COUNT
                        BCS str8n_v2_journal_LONG_60
                        JMP J_EXIT
str8n_v2_journal_LONG_60:
J_APPEND:              JSR J_FIND_FREE
                        LDA J_BEST+1
                        AND #$F0
                        EOR #$10
                        STA BOOT_IO_PAGE
; Keep the final source record available for a peer erase intent. If the peer
; is already blank after an interruption, resume without erasing it again.
                        LDA J_OUT+1
                        BNE str8n_v2_journal_LONG_69
                        JMP J_ROTATE
str8n_v2_journal_LONG_69:
                        AND #$0F
                        CMP #$0F
                        BEQ str8n_v2_journal_LONG_72
                        JMP J_APPEND_NORMAL
str8n_v2_journal_LONG_72:
                        LDA J_OUT
                        CMP #$80
                        BCS str8n_v2_journal_LONG_75
                        JMP J_APPEND_NORMAL
str8n_v2_journal_LONG_75:
J_ROTATE:               STZ J_SCAN
                        LDA BOOT_IO_PAGE
                        STA J_SCAN+1
                        JSR J_SECTOR_BLANK
                        BCC str8n_v2_journal_LONG_80
                        JMP J_PEER_READY
str8n_v2_journal_LONG_80:
                        LDA J_OUT+1
                        BNE str8n_v2_journal_LONG_82
                        JMP J_EXIT
str8n_v2_journal_LONG_82:
                        LDA BOOT_IO_PAGE
                        CMP #$D0
                        BEQ str8n_v2_journal_LONG_85
                        JMP J_PEER_C
str8n_v2_journal_LONG_85:
                        LDA #$1D
                        JMP J_PEER_INDEX
J_PEER_C:               LDA #$1C
J_PEER_INDEX:           STA J_COUNTINDEX
                        JSR J_INCREMENT_COUNT
                        BCS str8n_v2_journal_LONG_91
                        JMP J_EXIT
str8n_v2_journal_LONG_91:
                        JSR J_PREPARE
                        BCS str8n_v2_journal_LONG_93
                        JMP J_EXIT
str8n_v2_journal_LONG_93:
                        JSR J_WRITE
                        BCS str8n_v2_journal_LONG_95
                        JMP J_EXIT
str8n_v2_journal_LONG_95:
                        STZ V2_FLASH_PTR
                        LDA BOOT_IO_PAGE
                        STA V2_FLASH_PTR+1
                        JSR V2W_ERASE_RAW
                        BCS str8n_v2_journal_LONG_100
                        JMP J_EXIT
str8n_v2_journal_LONG_100:
                        STZ J_SCAN
                        LDA BOOT_IO_PAGE
                        STA J_SCAN+1
                        JSR J_SECTOR_BLANK
                        BCS str8n_v2_journal_LONG_105
                        JMP J_EXIT
str8n_v2_journal_LONG_105:
J_PEER_READY:           STZ J_OUT
                        LDA BOOT_IO_PAGE
                        STA J_OUT+1
J_APPEND_NORMAL:        JSR J_PREPARE
                        BCS str8n_v2_journal_LONG_110
                        JMP J_EXIT
str8n_v2_journal_LONG_110:
                        JSR J_WRITE
                        BCS str8n_v2_journal_LONG_112
                        JMP J_EXIT
str8n_v2_journal_LONG_112:
                        JMP J_SUCCESS
J_READ_CONFIG:          LDX #$0F
J_READ_COPY:            LDA J_BUFFER+8,X
                        STA V2_CONFIG,X
                        DEX
                        BMI str8n_v2_journal_LONG_118
                        JMP J_READ_COPY
str8n_v2_journal_LONG_118:
J_SUCCESS:              INC J_STATUS
                        JMP J_EXIT
J_NO_RECORD:            LDX #$0F
                        LDA #$FF
J_ERASED_CONFIG:        STA V2_CONFIG,X
                        DEX
                        BMI str8n_v2_journal_LONG_125
                        JMP J_ERASED_CONFIG
str8n_v2_journal_LONG_125:
J_EXIT:                 LDX #$1F
J_RESTORE_ZP:           LDA J_SAVED_ZP,X
                        STA $E0,X
                        DEX
                        BMI str8n_v2_journal_LONG_130
                        JMP J_RESTORE_ZP
str8n_v2_journal_LONG_130:
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
                        BEQ str8n_v2_journal_LONG_149
                        JMP J_CONFIG_SUM_BYTE
str8n_v2_journal_LONG_149:
                        LDA J_CRC
                        STA V2_CONFIG+14
                        LDA J_CRC+1
                        STA V2_CONFIG+15
                        RTS

J_INCREMENT_COUNT:      LDA J_COUNTINDEX
                        CMP #$20
                        BCC str8n_v2_journal_LONG_158
                        JMP J_COUNT_FULL
str8n_v2_journal_LONG_158:
                        ASL A
                        CLC
                        ADC J_COUNTINDEX
                        TAX
                        LDA J_BUFFER+24,X
                        AND J_BUFFER+25,X
                        AND J_BUFFER+26,X
                        CMP #$FF
                        BNE str8n_v2_journal_LONG_167
                        JMP J_COUNT_FULL
str8n_v2_journal_LONG_167:
                        INC J_BUFFER+24,X
                        BEQ str8n_v2_journal_LONG_169
                        JMP J_COUNT_OK
str8n_v2_journal_LONG_169:
                        INC J_BUFFER+25,X
                        BEQ str8n_v2_journal_LONG_171
                        JMP J_COUNT_OK
str8n_v2_journal_LONG_171:
                        INC J_BUFFER+26,X
J_COUNT_OK:             SEC
                        RTS
J_COUNT_FULL:           CLC
                        RTS

J_PREPARE:              LDX #$03
                        LDA #$FF
J_SEQ_FULL:             AND J_BUFFER+4,X
                        DEX
                        BMI str8n_v2_journal_LONG_182
                        JMP J_SEQ_FULL
str8n_v2_journal_LONG_182:
                        CMP #$FF
                        BNE str8n_v2_journal_LONG_184
                        JMP J_COUNT_FULL
str8n_v2_journal_LONG_184:
                        INC J_BUFFER+4
                        BEQ str8n_v2_journal_LONG_186
                        JMP J_SEQ_READY
str8n_v2_journal_LONG_186:
                        INC J_BUFFER+5
                        BEQ str8n_v2_journal_LONG_188
                        JMP J_SEQ_READY
str8n_v2_journal_LONG_188:
                        INC J_BUFFER+6
                        BEQ str8n_v2_journal_LONG_190
                        JMP J_SEQ_READY
str8n_v2_journal_LONG_190:
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
                        BEQ str8n_v2_journal_LONG_202
                        JMP J_PREP_CRC
str8n_v2_journal_LONG_202:
                        LDA J_CRC
                        STA J_BUFFER+120
                        LDA J_CRC+1
                        STA J_BUFFER+121
                        SEC
                        RTS

J_WRITE:                LDA J_OUT+1
                        BNE str8n_v2_journal_LONG_211
                        JMP J_WRITE_FAIL
str8n_v2_journal_LONG_211:
                        LDA J_OUT
                        STA V2_FLASH_PTR
                        LDA J_OUT+1
                        STA V2_FLASH_PTR+1
                        STZ J_INDEX
; Refuse anything except a completely unused record, including torn records.
                        LDY #$00
J_DEST_BLANK:           LDA (V2_FLASH_PTR),Y
                        CMP #$FF
                        BEQ str8n_v2_journal_LONG_221
                        JMP J_WRITE_FAIL
str8n_v2_journal_LONG_221:
                        INY
                        BMI str8n_v2_journal_LONG_223
                        JMP J_DEST_BLANK
str8n_v2_journal_LONG_223:
J_WRITE_BYTE:           LDX J_INDEX
                        LDA J_BUFFER,X
                        CMP #$FF
                        BNE str8n_v2_journal_LONG_227
                        JMP J_WRITE_NEXT
str8n_v2_journal_LONG_227:
                        STA V2_FLASH_DATA
                        JSR V2W_BYTE
                        BCS str8n_v2_journal_LONG_230
                        JMP J_WRITE_FAIL
str8n_v2_journal_LONG_230:
J_WRITE_NEXT:           INC V2_FLASH_PTR
                        INC J_INDEX
                        LDA J_INDEX
                        CMP #$7F
                        BEQ str8n_v2_journal_LONG_235
                        JMP J_WRITE_BYTE
str8n_v2_journal_LONG_235:
; Verify the body before publishing the previously unwritten commit byte.
                        LDA J_OUT
                        STA V2_FLASH_PTR
                        LDY #$00
J_BODY_VERIFY:          LDA (V2_FLASH_PTR),Y
                        CMP J_BUFFER,Y
                        BEQ str8n_v2_journal_LONG_242
                        JMP J_WRITE_FAIL
str8n_v2_journal_LONG_242:
                        INY
                        CPY #$7F
                        BEQ str8n_v2_journal_LONG_245
                        JMP J_BODY_VERIFY
str8n_v2_journal_LONG_245:
                        TYA
                        CLC
                        ADC J_OUT
                        STA V2_FLASH_PTR
                        STZ V2_FLASH_DATA
                        JSR V2W_BYTE
                        BCS str8n_v2_journal_LONG_252
                        JMP J_WRITE_FAIL
str8n_v2_journal_LONG_252:
                        LDA J_OUT
                        STA V2_FLASH_PTR
                        LDY #$00
J_FINAL_VERIFY:         LDA (V2_FLASH_PTR),Y
                        CMP J_BUFFER,Y
                        BEQ str8n_v2_journal_LONG_258
                        JMP J_WRITE_FAIL
str8n_v2_journal_LONG_258:
                        INY
                        BMI str8n_v2_journal_LONG_260
                        JMP J_FINAL_VERIFY
str8n_v2_journal_LONG_260:
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
                        BCS str8n_v2_journal_LONG_276
                        JMP J_SCAN_NEXT
str8n_v2_journal_LONG_276:
                        LDA J_BEST+1
                        BNE str8n_v2_journal_LONG_278
                        JMP J_NEWEST
str8n_v2_journal_LONG_278:
                        LDA J_BEST
                        STA V2_ADDR
                        LDA J_BEST+1
                        STA V2_ADDR+1
                        LDY #$07
J_SEQ_COMPARE:          LDA (V2_PTR),Y
                        CMP (V2_ADDR),Y
                        BCS str8n_v2_journal_LONG_286
                        JMP J_SCAN_NEXT
str8n_v2_journal_LONG_286:
                        BEQ str8n_v2_journal_LONG_287
                        JMP J_NEWEST
str8n_v2_journal_LONG_287:
                        DEY
                        CPY #$03
                        BEQ str8n_v2_journal_LONG_290
                        JMP J_SEQ_COMPARE
str8n_v2_journal_LONG_290:
                        JMP J_SCAN_NEXT
J_NEWEST:               LDA J_SCAN
                        STA J_BEST
                        LDA J_SCAN+1
                        STA J_BEST+1
J_SCAN_NEXT:            LDA J_SCAN
                        EOR #$80
                        STA J_SCAN
                        BEQ str8n_v2_journal_LONG_299
                        JMP J_SCAN_RECORD
str8n_v2_journal_LONG_299:
                        INC J_SCAN+1
                        LDA J_SCAN+1
                        CMP #$E0
                        BEQ str8n_v2_journal_LONG_303
                        JMP J_SCAN_RECORD
str8n_v2_journal_LONG_303:
                        RTS

J_VALID:                LDY #$7F
                        LDA (V2_PTR),Y
                        BEQ str8n_v2_journal_LONG_308
                        JMP J_INVALID
str8n_v2_journal_LONG_308:
                        LDY #$00
                        LDA (V2_PTR),Y
                        CMP #'W'
                        BEQ str8n_v2_journal_LONG_312
                        JMP J_INVALID
str8n_v2_journal_LONG_312:
                        INY
                        LDA (V2_PTR),Y
                        CMP #'C'
                        BEQ str8n_v2_journal_LONG_316
                        JMP J_INVALID
str8n_v2_journal_LONG_316:
                        INY
                        LDA (V2_PTR),Y
                        CMP #$01
                        BEQ str8n_v2_journal_LONG_320
                        JMP J_INVALID
str8n_v2_journal_LONG_320:
                        INY
                        LDA (V2_PTR),Y
                        BEQ str8n_v2_journal_LONG_323
                        JMP J_INVALID
str8n_v2_journal_LONG_323:
                        JSR J_CRC_INIT
                        LDY #$00
J_VALID_CRC:            LDA (V2_PTR),Y
                        JSR J_CRC_BYTE
                        INY
                        CPY #$78
                        BEQ str8n_v2_journal_LONG_330
                        JMP J_VALID_CRC
str8n_v2_journal_LONG_330:
                        LDA (V2_PTR),Y
                        CMP J_CRC
                        BEQ str8n_v2_journal_LONG_333
                        JMP J_INVALID
str8n_v2_journal_LONG_333:
                        INY
                        LDA (V2_PTR),Y
                        CMP J_CRC+1
                        BEQ str8n_v2_journal_LONG_337
                        JMP J_INVALID
str8n_v2_journal_LONG_337:
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
                        BMI str8n_v2_journal_LONG_351
                        JMP J_LOAD_BYTE
str8n_v2_journal_LONG_351:
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
                        BEQ str8n_v2_journal_LONG_365
                        JMP J_FIND_TEST
str8n_v2_journal_LONG_365:
                        INC J_OUT+1
J_FIND_TEST:            LDA J_OUT+1
                        CMP BOOT_END_PAGE
                        BNE str8n_v2_journal_LONG_369
                        JMP J_NO_FREE
str8n_v2_journal_LONG_369:
                        LDA J_OUT
                        STA V2_PTR
                        LDA J_OUT+1
                        STA V2_PTR+1
                        LDY #$00
J_FREE_BYTE:            LDA (V2_PTR),Y
                        CMP #$FF
                        BEQ str8n_v2_journal_LONG_377
                        JMP J_FIND_NEXT
str8n_v2_journal_LONG_377:
                        INY
                        BMI str8n_v2_journal_LONG_379
                        JMP J_FREE_BYTE
str8n_v2_journal_LONG_379:
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
                        BEQ str8n_v2_journal_LONG_394
                        JMP J_INVALID
str8n_v2_journal_LONG_394:
                        INY
                        BEQ str8n_v2_journal_LONG_396
                        JMP J_SECTOR_BYTE
str8n_v2_journal_LONG_396:
                        INC V2_PTR+1
                        LDA V2_PTR+1
                        CMP BOOT_END_PAGE
                        BEQ str8n_v2_journal_LONG_400
                        JMP J_SECTOR_BYTE
str8n_v2_journal_LONG_400:
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
                        BCS str8n_v2_journal_LONG_414
                        JMP J_CRC_NEXT
str8n_v2_journal_LONG_414:
                        LDA J_CRC
                        EOR #$21
                        STA J_CRC
                        LDA J_CRC+1
                        EOR #$10
                        STA J_CRC+1
J_CRC_NEXT:             DEX
                        BEQ str8n_v2_journal_LONG_422
                        JMP J_CRC_BIT
str8n_v2_journal_LONG_422:
                        RTS

BOOT_REPORT:            JSR BOOT_META_READ
                        BCS str8n_v2_journal_LONG_426
                        JMP BOOT_COUNTS_UNKNOWN
str8n_v2_journal_LONG_426:
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
                        BEQ str8n_v2_journal_LONG_463
                        JMP BOOT_REPORT_NEXT
str8n_v2_journal_LONG_463:
                        RTS
BOOT_COUNTS_UNKNOWN:    LDX #<BOOT_UNKNOWN_TEXT
                        LDY #>BOOT_UNKNOWN_TEXT
                        JMP BOOT_PRINT
BOOT_UNKNOWN_TEXT:      DB "JOURNAL INVALID",$0D,$0A,0
