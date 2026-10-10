; X bank NAME S NAME / X S NAME bank NAME. Verified copy, source retained.
; Fixed version-paired SRAM hooks are private to this foreground utility.
X_REQ EQU $6300
X_SOURCE_NAME EQU $6320
X_META EQU $6330
X_HEAD EQU $6340
X_BANK EQU $6380
X_DIRECTION EQU $6381
X_FLASH EQU $6382
X_PAYLOAD EQU $6384
X_DEST EQU $6386
X_FOUND EQU $6388
X_STARTED EQU $6389
X_OFFSET EQU $638A
X_SCAN EQU $638C
X_BP EQU $638E
X_VALUE EQU $6390
X_INDEX EQU $6391
X_ERROR EQU $6392
X_COPY:
        LDX #31
X_ZERO:
        STZ X_REQ,X
        DEX
        BPL X_ZERO
        STZ X_DIRECTION
        STZ X_STARTED
        JSR X_SPACE
        BCC X_BAD
        STA X_BANK
        CMP #$FF
        BNE X_PARSE_SOURCE
        INC X_DIRECTION
X_PARSE_SOURCE:
        LDA #<X_SOURCE_NAME
        STA TXT
        LDA #>X_SOURCE_NAME
        STA TXT+1
        JSR X_NAME
        BCC X_BAD
        JSR X_SPACE
        BCC X_BAD
        LDX X_DIRECTION
        BNE X_DEST_FLASH
        CMP #$FF
        BNE X_BAD
        BRA X_PARSE_DEST
X_DEST_FLASH:
        CMP #$FF
        BEQ X_BAD
        STA X_BANK
X_PARSE_DEST:
        LDA #<X_REQ+8
        STA TXT
        LDA #>X_REQ+8
        STA TXT+1
        JSR X_NAME
        BCC X_BAD
        JSR ENDLINE
        BCC X_BAD
        LDX #15
X_KEEP_DEST_NAME:
        LDA X_REQ+8,X
        STA X_DEST_NAME,X
        DEX
        BPL X_KEEP_DEST_NAME
        ; MAINT remains flash-only, on both sides of the transfer.
        LDX #4
X_MAINT_SOURCE:
        LDA X_SOURCE_NAME,X
        CMP X_MAINT_NAME,X
        BNE X_CHECK_DEST
        DEX
        BPL X_MAINT_SOURCE
        JMP X_BAD
X_CHECK_DEST:
        LDX #4
X_MAINT_DEST:
        LDA X_REQ+8,X
        CMP X_MAINT_NAME,X
        BNE X_DISCOVER
        DEX
        BPL X_MAINT_DEST
        JMP X_BAD
X_DISCOVER:
        LDX #3
X_EXEC_CHECK:
        LDA $EE92,X
        CMP X_EXEC_MAGIC,X
        BNE X_FAIL
        DEX
        BPL X_EXEC_CHECK
        LDA #3
        JSR $EF09
        BCC X_FAIL
        LDA X_DIRECTION
        BNE X_FROM_SRAM
        JSR X_FIND_FLASH
        BCC X_FAIL
        LDX #5
X_FLASH_META:
        LDA X_HEAD+4,X
        STA X_REQ+2,X
        DEX
        BPL X_FLASH_META
        ; Flash has no independent entry field; it runs at its load address.
        LDA X_HEAD+4
        STA X_REQ+6
        LDA X_HEAD+5
        STA X_REQ+7
        JSR X_END_RANGE
        LDA #1
        STA X_REQ
        JSR X_CONFIRM
        BCC X_CANCEL
        LDA #<X_READ_BYTE
        STA SM_SOURCE_BYTE_HOOK
        LDA #>X_READ_BYTE
        STA SM_SOURCE_BYTE_HOOK+1
        LDA #<X_SAVE_CHUNK
        STA SM_SAVE_TRANSFER_HOOK
        LDA #>X_SAVE_CHUNK
        STA SM_SAVE_TRANSFER_HOOK+1
        JSR X_API
        JMP X_RESULT
X_FROM_SRAM:
        ; A verified restore reaches this hook only after metadata/payload CRC.
        LDX #15
X_SRAM_NAME:
        LDA X_SOURCE_NAME,X
        STA X_REQ+8,X
        DEX
        BPL X_SRAM_NAME
        LDA #2
        STA X_REQ
        LDA #<X_INSPECT
        STA SM_RESTORE_TRANSFER_HOOK
        LDA #>X_INSPECT
        STA SM_RESTORE_TRANSFER_HOOK+1
        JSR X_API
        CMP #$46
        BNE X_FAIL
        LDX #3
X_KEEP_META:
        LDA SM_LOAD,X
        STA X_META,X
        DEX
        BPL X_KEEP_META
        LDA SM_ENTRY
        STA X_META+4
        LDA SM_ENTRY+1
        STA X_META+5
        LDA SM_BEST_SEQ
        STA X_META+6
        LDA SM_BEST_SEQ+1
        STA X_META+7
        LDA X_META
        CMP X_META+4
        BNE X_BAD
        LDA X_META+1
        CMP X_META+5
        BNE X_BAD
        ; SR v1 cannot express a distinct/restore-only SRAM entry point.
        LDA X_BANK
        STA $7D2C
        CLC
        LDA X_META+2
        ADC #24
        STA $7D2D
        LDA X_META+3
        ADC #0
        STA $7D2E
        BCS X_FAIL
        LDA #5
        JSR $EF09
        BCC X_FAIL
        STA X_FLASH
        STX X_FLASH+1
        STA X_DEST
        STX X_DEST+1
        LDX #<X_ADDRESS_TEXT
        LDY #>X_ADDRESS_TEXT
        JSR PRINT
        LDA X_BANK
        JSR HEX
        LDA #':'
        JSR PUTC
        LDA X_FLASH+1
        JSR HEX
        LDA X_FLASH
        JSR HEX
        JSR NL
        JSR X_CONFIRM
        BCC X_CANCEL
        ; AUTO uses staging, so reload the manager before the actual copy.
        LDA #3
        JSR $EF09
        BCC X_FAIL
        LDA #<X_RESTORE_CHUNK
        STA SM_RESTORE_TRANSFER_HOOK
        LDA #>X_RESTORE_CHUNK
        STA SM_RESTORE_TRANSFER_HOOK+1
        JSR X_API
        BCC X_RESULT
        ; Header marker is programmed only after verified restore CRC succeeds.
        CLC
        LDA X_FLASH
        ADC #3
        STA X_DEST
        LDA X_FLASH+1
        ADC #0
        STA X_DEST+1
        LDA #$3F
        JSR X_PROGRAM
        BCC X_FAIL
        LDA #0
X_RESULT:
        STA X_ERROR
        JSR X_UNHOOK
        LDA X_ERROR
        BNE X_FAIL_TEXT
        LDX #<X_DONE_TEXT
        LDY #>X_DONE_TEXT
        JMP MESSAGE
X_BAD:
        JSR X_UNHOOK
        JMP BM_BAD
X_CANCEL:
        JSR X_UNHOOK
        JMP BM_CANCEL
X_FAIL:
        JSR X_UNHOOK
X_FAIL_TEXT:
        LDX #<X_FAIL_MESSAGE
        LDY #>X_FAIL_MESSAGE
        JMP MESSAGE
X_UNHOOK:
        STZ SM_SOURCE_BYTE_HOOK
        STZ SM_SOURCE_BYTE_HOOK+1
        STZ SM_SAVE_TRANSFER_HOOK
        STZ SM_SAVE_TRANSFER_HOOK+1
        STZ SM_RESTORE_TRANSFER_HOOK
        STZ SM_RESTORE_TRANSFER_HOOK+1
        STZ V2_NMI_HOLD
        LDA RESIDENT
        STA V2_SELECTED
        JSR V2W_SELECT
        RTS
X_API:
        LDA #<X_REQ
        LDX #>X_REQ
        JMP $6C03
X_INSPECT:
        LDA #$46
        RTS
X_CONFIRM:
        LDX #<X_CONFIRM_TEXT
        LDY #>X_CONFIRM_TEXT
        JSR PRINT
        JSR READLINE
        BCC X_CONFIRM_NO
        LDA BM_LINE
        CMP #'Y'
        BNE X_CONFIRM_NO
        LDA BM_LINE+1
        BNE X_CONFIRM_NO
        SEC
        RTS
X_CONFIRM_NO:
        CLC
        RTS
X_SPACE:
        JSR SPACES
        CMP #'S'
        BNE X_FLASH_SPACE
        LDA #$FF
        BRA X_SPACE_END
X_FLASH_SPACE:
        SEC
        SBC #'0'
        CMP #3
        BCS X_PARSE_NO
X_SPACE_END:
        PHA
        INC INDEX
        LDX INDEX
        LDA BM_LINE,X
        CMP #' '
        BNE X_SPACE_BAD
        PLA
        SEC
        RTS
X_SPACE_BAD:
        PLA
X_PARSE_NO:
        CLC
        RTS
X_NAME:
        JSR SPACES
        LDY #15
X_NAME_ZERO:
        LDA #0
        STA (TXT),Y
        DEY
        BPL X_NAME_ZERO
        LDY #0
X_NAME_CHAR:
        LDX INDEX
        LDA BM_LINE,X
        BEQ X_NAME_END
        CMP #' '
        BEQ X_NAME_END
        CPY #16
        BCS X_PARSE_NO
        CMP #'-'
        BEQ X_NAME_OK
        CMP #'_'
        BEQ X_NAME_OK
        CMP #'0'
        BCC X_PARSE_NO
        CMP #'9'+1
        BCC X_NAME_OK
        CMP #'A'
        BCC X_PARSE_NO
        CMP #'Z'+1
        BCS X_PARSE_NO
X_NAME_OK:
        STA (TXT),Y
        INY
        INC INDEX
        BRA X_NAME_CHAR
X_NAME_END:
        CPY #1
        RTS
; Flash search, protecting complete SR extents, refusing ambiguous names.
X_FIND_FLASH:
        STZ X_FOUND
        STZ X_SCAN
        LDA #$80
        STA X_SCAN+1
X_FIND_NEXT:
        LDA X_SCAN+1
        CMP #$E0
        BCS X_FIND_DONE
        LDA X_BANK
        CMP #2
        BNE X_FIND_READ
        LDA X_SCAN+1
        CMP #$C8
        BCC X_FIND_READ
        CMP #$D0
        BCS X_FIND_READ
        STZ X_SCAN
        LDA #$D0
        STA X_SCAN+1
X_FIND_READ:
        LDA X_SCAN
        STA V2_ADDR
        LDA X_SCAN+1
        STA V2_ADDR+1
        LDA #16
        STA V2_COUNT
        JSR X_READ
        LDY #15
X_FIND_ERASED:
        LDA V2_BYTES,Y
        CMP #$FF
        BNE X_FIND_HEADER
        DEY
        BPL X_FIND_ERASED
        CLC
        LDA X_SCAN
        ADC #16
        STA X_SCAN
        BCC X_FIND_NEXT
        INC X_SCAN+1
        BRA X_FIND_NEXT
X_FIND_HEADER:
        LDA V2_BYTES+3
        CMP #$3F
        BEQ X_FIND_MAGIC
        CMP #$FF
        BNE X_FIND_BYTE
X_FIND_MAGIC:
        LDX #2
X_FIND_ID:
        LDA V2_BYTES,X
        CMP X_RECORD_ID,X
        BNE X_FIND_BYTE
        DEX
        BPL X_FIND_ID
        LDX #15
X_COPY_HEAD:
        LDA V2_BYTES,X
        STA X_HEAD,X
        DEX
        BPL X_COPY_HEAD
        CLC
        LDA V2_ADDR
        ADC #16
        STA V2_ADDR
        BCC X_HEAD_TAIL
        INC V2_ADDR+1
X_HEAD_TAIL:
        LDA #8
        STA V2_COUNT
        JSR X_READ
        LDX #7
X_COPY_TAIL:
        LDA V2_BYTES,X
        STA X_HEAD+16,X
        DEX
        BPL X_COPY_TAIL
        LDA X_HEAD+6
        ORA X_HEAD+7
        BEQ X_FIND_BYTE
        LDA X_HEAD+5
        CMP #2
        BCC X_FIND_BYTE
        CLC
        LDA X_HEAD+4
        ADC X_HEAD+6
        STA X_OFFSET
        LDA X_HEAD+5
        ADC X_HEAD+7
        BCS X_FIND_BYTE
        CMP #$65
        BCC X_FIND_RANGE_OK
        BNE X_FIND_BYTE
        LDA X_OFFSET
        BNE X_FIND_BYTE
X_FIND_RANGE_OK:
        CLC
        LDA X_SCAN
        ADC #24
        STA X_OFFSET
        LDA X_SCAN+1
        ADC #0
        STA X_OFFSET+1
        CLC
        LDA X_OFFSET
        ADC X_HEAD+6
        STA X_BP
        LDA X_OFFSET+1
        ADC X_HEAD+7
        BCS X_FIND_BYTE
        CMP #$E0
        BCC X_FIND_END_OK
        BNE X_FIND_BYTE
        LDX X_BP
        BNE X_FIND_BYTE
X_FIND_END_OK:
        STA X_BP+1
        LDA X_HEAD+3
        CMP #$3F
        BNE X_FIND_SKIP
        LDX #15
X_FIND_NAME:
        LDA X_HEAD+8,X
        CMP X_SOURCE_NAME,X
        BNE X_FIND_SKIP
        DEX
        BPL X_FIND_NAME
        LDA X_FOUND
        BEQ X_FOUND_FIRST
        LDA #2
        STA X_FOUND
        BRA X_FOUND_KEEP
X_FOUND_FIRST:
        INC X_FOUND
X_FOUND_KEEP:
        LDA X_SCAN
        STA X_FLASH
        LDA X_SCAN+1
        STA X_FLASH+1
        LDA X_OFFSET
        STA X_PAYLOAD
        LDA X_OFFSET+1
        STA X_PAYLOAD+1
        LDX #3
X_FIND_SAVE:
        LDA X_HEAD+4,X
        STA X_META,X
        DEX
        BPL X_FIND_SAVE
X_FIND_SKIP:
        LDA X_BP
        STA X_SCAN
        LDA X_BP+1
        STA X_SCAN+1
        BRA X_FIND_NEXT
X_FIND_BYTE:
        INC X_SCAN
        BNE X_FIND_NEXT
        INC X_SCAN+1
        BRA X_FIND_NEXT
X_FIND_DONE:
        LDA X_FOUND
        CMP #1
        BNE X_PARSE_NO
        LDX #3
X_FIND_RESTORE:
        LDA X_META,X
        STA X_HEAD+4,X
        DEX
        BPL X_FIND_RESTORE
        SEC
        RTS
X_END_RANGE:
        CLC
        LDA X_HEAD+4
        ADC X_HEAD+6
        STA X_REQ+4
        LDA X_HEAD+5
        ADC X_HEAD+7
        STA X_REQ+5
        LDA X_REQ+4
        BNE X_END_LOW
        DEC X_REQ+5
X_END_LOW:
        DEC X_REQ+4
        RTS
; Source byte for SAVE CRC: map logical PTR to flash payload.
X_READ_BYTE:
        SEC
        LDA $D2
        SBC SM_LOAD
        STA V2_ADDR
        LDA $D3
        SBC SM_LOAD+1
        STA V2_ADDR+1
        CLC
        LDA V2_ADDR
        ADC X_PAYLOAD
        STA V2_ADDR
        LDA V2_ADDR+1
        ADC X_PAYLOAD+1
        STA V2_ADDR+1
        LDA #1
        STA V2_COUNT
        JSR X_READ
        LDA V2_BYTES
        LDY #0
        RTS
X_READ:
        LDA X_BANK
        STA V2_SELECTED
        JMP V2W_READ
; Source transfer uses preserved BUF, never the source application's RAM.
X_SAVE_CHUNK:
        LDA SM_BP
        STA X_BP
        STA $D2
        LDA SM_BP+1
        STA X_BP+1
        STA $D3
        STZ X_INDEX
X_FILL_CHUNK:
        JSR X_READ_BYTE
        LDX X_INDEX
        STA $6400,X
        INC $D2
        BNE X_FILL_NEXT
        INC $D3
X_FILL_NEXT:
        INC X_INDEX
        LDA X_INDEX
        CMP SM_COUNT
        BNE X_FILL_CHUNK
        JSR X_STAGE_BP
        LDA #2
        JSR SM_TRANSFER
        BRA X_UNSTAGE_BP
X_STAGE_BP:
        STZ SM_BP
        LDA #$64
        STA SM_BP+1
        RTS
X_UNSTAGE_BP:
        PHA
        LDA X_BP
        STA SM_BP
        LDA X_BP+1
        STA SM_BP+1
        PLA
        RTS
X_RESTORE_CHUNK:
        LDA X_STARTED
        BNE X_RESTORE_DATA
        LDX #3
X_MATCH_META:
        LDA SM_LOAD,X
        CMP X_META,X
        BNE X_HOOK_FAIL
        DEX
        BPL X_MATCH_META
        LDA SM_ENTRY
        CMP X_META+4
        BNE X_HOOK_FAIL
        LDA SM_ENTRY+1
        CMP X_META+5
        BNE X_HOOK_FAIL
        LDA SM_BEST_SEQ
        CMP X_META+6
        BNE X_HOOK_FAIL
        LDA SM_BEST_SEQ+1
        CMP X_META+7
        BNE X_HOOK_FAIL
        INC X_STARTED
        LDX #3
X_NEW_HEAD:
        LDA X_RECORD_ID,X
        STA X_HEAD,X
        LDA X_META,X
        STA X_HEAD+4,X
        DEX
        BPL X_NEW_HEAD
        LDA #$FF
        STA X_HEAD+3
        ; Destination name survived READLINE in X_REQ; source name is kept
        ; separately. X_REQ now contains source, destination needs own copy.
        LDX #15
X_NEW_NAME:
        LDA X_DEST_NAME,X
        STA X_HEAD+8,X
        DEX
        BPL X_NEW_NAME
        STZ X_INDEX
X_WRITE_HEAD:
        LDX X_INDEX
        LDA X_HEAD,X
        JSR X_PROGRAM
        BCC X_HOOK_FAIL
        INC X_INDEX
        LDA X_INDEX
        CMP #24
        BNE X_WRITE_HEAD
X_RESTORE_DATA:
        LDA SM_BP
        STA X_BP
        LDA SM_BP+1
        STA X_BP+1
        JSR X_STAGE_BP
        LDA #1
        JSR SM_TRANSFER
        JSR X_UNSTAGE_BP
        CMP #0
        BNE X_HOOK_FAIL
        STZ X_INDEX
X_PROGRAM_DATA:
        LDX X_INDEX
        LDA $6400,X
        JSR X_PROGRAM
        BCC X_HOOK_FAIL
        INC X_INDEX
        LDA X_INDEX
        CMP SM_COUNT
        BNE X_PROGRAM_DATA
        LDA #0
        RTS
X_HOOK_FAIL:
        LDA #$46
        RTS
; Program fresh bytes only, read back each, never erase any occupied space.
X_PROGRAM:
        STA X_VALUE
        LDA X_DEST
        STA V2_ADDR
        STA V2_FLASH_PTR
        LDA X_DEST+1
        STA V2_ADDR+1
        STA V2_FLASH_PTR+1
        LDA #1
        STA V2_COUNT
        STA V2_NMI_HOLD
        JSR X_READ
        LDA V2_BYTES
        CMP #$FF
        BNE X_PROGRAM_FAIL
        LDA X_VALUE
        CMP #$FF
        BEQ X_PROGRAM_OK
        STA V2_FLASH_DATA
        LDA X_BANK
        JSR V2W_SELECT
        JSR V2W_BYTE
        PHP
        LDA RESIDENT
        JSR V2W_SELECT
        PLP
        BCC X_PROGRAM_FAIL
        JSR X_READ
        LDA V2_BYTES
        CMP X_VALUE
        BNE X_PROGRAM_FAIL
X_PROGRAM_OK:
        INC X_DEST
        BNE X_PROGRAM_NO_CARRY
        INC X_DEST+1
X_PROGRAM_NO_CARRY:
        SEC
        RTS
X_PROGRAM_FAIL:
        CLC
        RTS
X_DEST_NAME DS 16
X_RECORD_ID DB "SR",1,$3F
X_EXEC_MAGIC DB "ED",1,3
X_MAINT_NAME DB "MAINT"
X_ADDRESS_TEXT DB "Destination B",0
X_CONFIRM_TEXT DB "Copy program; source retained. Y to confirm: ",0
X_DONE_TEXT DB "Copied and verified; source retained.",13,10,0
X_FAIL_MESSAGE DB "Copy failed; source retained. Destination may be pending.",13,10,0
