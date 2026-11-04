MM_X_REQ EQU $6300
MM_X_SOURCE_NAME EQU $6320
MM_X_META EQU $6330
MM_X_HEAD EQU $6340
MM_X_BANK EQU $6380
MM_X_DIRECTION EQU $6381
MM_X_FLASH EQU $6382
MM_X_PAYLOAD EQU $6384
MM_X_DEST EQU $6386
MM_X_FOUND EQU $6388
MM_X_STARTED EQU $6389
MM_X_OFFSET EQU $638A
MM_X_SCAN EQU $638C
MM_X_BP EQU $638E
MM_X_VALUE EQU $6390
MM_X_INDEX EQU $6391
MM_X_ERROR EQU $6392
MM_X_COPY:
        LDX #31
MM_X_ZERO:
        STZ MM_X_REQ,X
        DEX
                        BPL MM_X_ZERO
        STZ MM_X_DIRECTION
        STZ MM_X_STARTED
        JSR MM_X_SPACE
                        BCC MM_X_BAD
        STA MM_X_BANK
        CMP #$FF
                        BNE MM_X_PARSE_SOURCE
        INC MM_X_DIRECTION
MM_X_PARSE_SOURCE:
        LDA #<MM_X_SOURCE_NAME
        STA MM_TXT
        LDA #>MM_X_SOURCE_NAME
        STA MM_TXT+1
        JSR MM_X_NAME
                        BCC MM_X_BAD
        JSR MM_X_SPACE
                        BCC MM_X_BAD
        LDX MM_X_DIRECTION
                        BNE MM_X_DEST_FLASH
        CMP #$FF
                        BNE MM_X_BAD
                        BRA MM_X_PARSE_DEST
MM_X_DEST_FLASH:
        CMP #$FF
                        BEQ MM_X_BAD
        STA MM_X_BANK
MM_X_PARSE_DEST:
        LDA #<MM_X_REQ+8
        STA MM_TXT
        LDA #>MM_X_REQ+8
        STA MM_TXT+1
        JSR MM_X_NAME
                        BCC MM_X_BAD
        JSR MM_ENDLINE
                        BCC MM_X_BAD
        LDX #15
MM_X_KEEP_DEST_NAME:
        LDA MM_X_REQ+8,X
        STA MM_X_DEST_NAME,X
        DEX
                        BPL MM_X_KEEP_DEST_NAME
        ; MAINT remains flash-only, on both sides of the transfer.
        LDX #4
MM_X_MAINT_SOURCE:
        LDA MM_X_SOURCE_NAME,X
        CMP MM_X_MAINT_NAME,X
                        BNE MM_X_CHECK_DEST
        DEX
                        BPL MM_X_MAINT_SOURCE
        JMP MM_X_BAD
MM_X_CHECK_DEST:
        LDA MM_X_DIRECTION
        BEQ MM_X28_X_DEST_OK
        LDA MM_X_BANK
        CMP #2
        BNE MM_X28_X_DEST_OK
        JMP MM_X_BAD
MM_X28_X_DEST_OK:
        LDX #4
MM_X_MAINT_DEST:
        LDA MM_X_REQ+8,X
        CMP MM_X_MAINT_NAME,X
                        BNE MM_X_DISCOVER
        DEX
                        BPL MM_X_MAINT_DEST
        JMP MM_X_BAD
MM_X_DISCOVER:
        JSR SM_INIT
        BCC MM_X_FAIL
        LDA MM_X_DIRECTION
                        BNE MM_X_FROM_SRAM
        JSR MM_X_FIND_FLASH
                        BCC MM_X_FAIL
        LDX #5
MM_X_FLASH_META:
        LDA MM_X_HEAD+4,X
        STA MM_X_REQ+2,X
        DEX
                        BPL MM_X_FLASH_META
        ; Flash has no independent entry field; it runs at its load address.
        LDA MM_X_HEAD+4
        STA MM_X_REQ+6
        LDA MM_X_HEAD+5
        STA MM_X_REQ+7
        JSR MM_X_END_RANGE
        LDA #1
        STA MM_X_REQ
        JSR MM_X_CONFIRM
                        BCC MM_X_CANCEL
        LDA #<MM_X_READ_BYTE
        STA SM_D_SOURCE_BYTE_HOOK
        LDA #>MM_X_READ_BYTE
        STA SM_D_SOURCE_BYTE_HOOK+1
        LDA #<MM_X_SAVE_CHUNK
        STA SM_D_SAVE_TRANSFER_HOOK
        LDA #>MM_X_SAVE_CHUNK
        STA SM_D_SAVE_TRANSFER_HOOK+1
        JSR MM_X_API
        JMP MM_X_RESULT
MM_X_FROM_SRAM:
        LDA MM_X_BANK
        CMP #2
        BCC MS_COPY_ALLOWED
        JMP MM_X_BAD
MS_COPY_ALLOWED:
        ; A verified restore reaches this hook only after metadata/payload CRC.
        LDX #15
MM_X_SRAM_NAME:
        LDA MM_X_SOURCE_NAME,X
        STA MM_X_REQ+8,X
        DEX
                        BPL MM_X_SRAM_NAME
        LDA #2
        STA MM_X_REQ
        LDA #<MM_X_INSPECT
        STA SM_D_RESTORE_TRANSFER_HOOK
        LDA #>MM_X_INSPECT
        STA SM_D_RESTORE_TRANSFER_HOOK+1
        JSR MM_X_API
        CMP #$46
                        BNE MM_X_FAIL
        LDX #3
MM_X_KEEP_META:
        LDA SM_D_LOAD,X
        STA MM_X_META,X
        DEX
                        BPL MM_X_KEEP_META
        LDA SM_D_ENTRY
        STA MM_X_META+4
        LDA SM_D_ENTRY+1
        STA MM_X_META+5
        LDA SM_D_BEST_SEQ
        STA MM_X_META+6
        LDA SM_D_BEST_SEQ+1
        STA MM_X_META+7
        LDA MM_X_META
        CMP MM_X_META+4
                        BNE MM_X_BAD
        LDA MM_X_META+1
        CMP MM_X_META+5
                        BNE MM_X_BAD
        ; SR v1 cannot express a distinct/restore-only SRAM entry point.
        LDA MM_X_BANK
        STA $7D2C
        CLC
        LDA MM_X_META+2
        ADC #24
        STA $7D2D
        LDA MM_X_META+3
        ADC #0
        STA $7D2E
                        BCS MM_X_FAIL
        LDA #5
        JSR MB_X_ALLOC
                        BCC MM_X_FAIL
        STA MM_X_FLASH
        STX MM_X_FLASH+1
        STA MM_X_DEST
        STX MM_X_DEST+1
        LDX #<MM_X_ADDRESS_TEXT
        LDY #>MM_X_ADDRESS_TEXT
        JSR MM_PRINT
        LDA MM_X_BANK
        JSR MM_HEX
        LDA #':'
        JSR MM_PUTC
        LDA MM_X_FLASH+1
        JSR MM_HEX
        LDA MM_X_FLASH
        JSR MM_HEX
        JSR MM_NL
        JSR MM_X_CONFIRM
                        BCC MM_X_CANCEL
        ; AUTO uses staging, so reload the manager before the actual copy.
        JSR SM_INIT
                        BCC MM_X_FAIL
        LDA #$09
        STA SM_D_RESTORE_TRANSFER_HOOK
        LDA #$20
        STA SM_D_RESTORE_TRANSFER_HOOK+1
        JSR MM_X_API
                        BCC MM_X_RESULT
        ; Header marker is programmed only after verified restore CRC succeeds.
        CLC
        LDA MM_X_FLASH
        ADC #3
        STA MM_X_DEST
        LDA MM_X_FLASH+1
        ADC #0
        STA MM_X_DEST+1
        LDA #$3F
        JSR MM_X_PROGRAM
                        BCC MM_X_FAIL
        LDA #0
MM_X_RESULT:
        STA MM_X_ERROR
        JSR MM_X_UNHOOK
        LDA MM_X_ERROR
                        BNE MM_X_FAIL_TEXT
        LDX #<MM_X_DONE_TEXT
        LDY #>MM_X_DONE_TEXT
        JMP MM_MESSAGE
MM_X_BAD: JSR B29_ERROR_HOOK

        JSR MM_X_UNHOOK
        JMP MM_BM_BAD
MM_X_CANCEL:
        JSR MM_X_UNHOOK
        JMP MM_BM_CANCEL
MM_X_FAIL: JSR B29_ERROR_HOOK

        JSR MM_X_UNHOOK
MM_X_FAIL_TEXT: JSR B29_ERROR_HOOK

        LDX #<MM_X_FAIL_MESSAGE
        LDY #>MM_X_FAIL_MESSAGE
        JMP MM_MESSAGE
MM_X_UNHOOK:
        STZ SM_D_SOURCE_BYTE_HOOK
        STZ SM_D_SOURCE_BYTE_HOOK+1
        STZ SM_D_SAVE_TRANSFER_HOOK
        STZ SM_D_SAVE_TRANSFER_HOOK+1
        STZ SM_D_RESTORE_TRANSFER_HOOK
        STZ SM_D_RESTORE_TRANSFER_HOOK+1
        STZ V2_NMI_HOLD
        LDA MM_RESIDENT
        STA V2_SELECTED
        JSR MM_V2W_SELECT
        RTS
MM_X_API:
        LDA #<MM_X_REQ
        LDX #>MM_X_REQ
        JMP SM_C_API
MM_X_INSPECT:
        LDA #$46
        RTS
MM_X_CONFIRM:
        LDX #<MM_X_CONFIRM_TEXT
        LDY #>MM_X_CONFIRM_TEXT
        JSR MM_PRINT
        JSR MM_READLINE
                        BCC MM_X_CONFIRM_NO
        LDA MM_BM_LINE
        CMP #'Y'
                        BNE MM_X_CONFIRM_NO
        LDA MM_BM_LINE+1
                        BNE MM_X_CONFIRM_NO
        SEC
        RTS
MM_X_CONFIRM_NO:
        CLC
        RTS
MM_X_SPACE:
        JSR MM_SPACES
        CMP #'P'
        BEQ MM_X_SRAM_SPACE
        CMP #'S'
                        BNE MM_X_FLASH_SPACE
MM_X_SRAM_SPACE:
        LDA #$FF
                        BRA MM_X_SPACE_END
MM_X_FLASH_SPACE:
        SEC
        SBC #'0'
        CMP #3
                        BCS MM_X_PARSE_NO
MM_X_SPACE_END:
        PHA
        INC MM_INDEX
        LDX MM_INDEX
        LDA MM_BM_LINE,X
        CMP #' '
                        BNE MM_X_SPACE_BAD
        PLA
        SEC
        RTS
MM_X_SPACE_BAD:
        PLA
MM_X_PARSE_NO:
        CLC
        RTS
MM_X_NAME:
        JSR MM_SPACES
        LDY #15
MM_X_NAME_ZERO:
        LDA #0
        STA (MM_TXT),Y
        DEY
                        BPL MM_X_NAME_ZERO
        LDY #0
MM_X_NAME_CHAR:
        LDX MM_INDEX
        LDA MM_BM_LINE,X
                        BEQ MM_X_NAME_END
        CMP #' '
                        BEQ MM_X_NAME_END
        CPY #16
                        BCS MM_X_PARSE_NO
        CMP #'-'
                        BEQ MM_X_NAME_OK
        CMP #'_'
                        BEQ MM_X_NAME_OK
        CMP #'0'
                        BCC MM_X_PARSE_NO
        CMP #'9'+1
                        BCC MM_X_NAME_OK
        CMP #'A'
                        BCC MM_X_PARSE_NO
        CMP #'Z'+1
                        BCS MM_X_PARSE_NO
MM_X_NAME_OK:
        STA (MM_TXT),Y
        INY
        INC MM_INDEX
                        BRA MM_X_NAME_CHAR
MM_X_NAME_END:
        CPY #1
        RTS
; Flash search, protecting complete SR extents, refusing ambiguous names.
MM_X_FIND_FLASH:
        STZ MM_X_FOUND
        STZ MM_X_SCAN
        LDA #$80
        STA MM_X_SCAN+1
MM_X_FIND_NEXT:
        LDA MM_X_SCAN+1
        CMP #$E0
                        BCS MM_X_FIND_DONE
        LDA MM_X_BANK
        CMP #2
                        BNE MM_X_FIND_READ
        LDA MM_X_SCAN+1
        CMP #$D8
                        BCC MM_X_FIND_READ
        CMP #$E0
                        BCS MM_X_FIND_READ
        STZ MM_X_SCAN
        LDA #$E0
        STA MM_X_SCAN+1
MM_X_FIND_READ:
        LDA MM_X_SCAN
        STA V2_ADDR
        LDA MM_X_SCAN+1
        STA V2_ADDR+1
        LDA #16
        STA V2_COUNT
        JSR MM_X_READ
        LDY #15
MM_X_FIND_ERASED:
        LDA V2_BYTES,Y
        CMP #$FF
                        BNE MM_X_FIND_HEADER
        DEY
                        BPL MM_X_FIND_ERASED
        CLC
        LDA MM_X_SCAN
        ADC #16
        STA MM_X_SCAN
                        BCC MM_X_FIND_NEXT
        INC MM_X_SCAN+1
                        JMP MM_X_FIND_NEXT
MM_X_FIND_HEADER:
        LDA V2_BYTES+3
        CMP #$3F
                        BEQ MM_X_FIND_MAGIC
        CMP #$FF
                        BNE MM_X_FIND_BYTE
MM_X_FIND_MAGIC:
        LDX #2
MM_X_FIND_ID:
        LDA V2_BYTES,X
        CMP MM_X_RECORD_ID,X
                        BNE MM_X_FIND_BYTE
        DEX
                        BPL MM_X_FIND_ID
        LDX #15
MM_X_COPY_HEAD:
        LDA V2_BYTES,X
        STA MM_X_HEAD,X
        DEX
                        BPL MM_X_COPY_HEAD
        CLC
        LDA V2_ADDR
        ADC #16
        STA V2_ADDR
                        BCC MM_X_HEAD_TAIL
        INC V2_ADDR+1
MM_X_HEAD_TAIL:
        LDA #8
        STA V2_COUNT
        JSR MM_X_READ
        LDX #7
MM_X_COPY_TAIL:
        LDA V2_BYTES,X
        STA MM_X_HEAD+16,X
        DEX
                        BPL MM_X_COPY_TAIL
        LDA MM_X_HEAD+6
        ORA MM_X_HEAD+7
                        BEQ MM_X_FIND_BYTE
        LDA MM_X_HEAD+5
        CMP #2
                        BCC MM_X_FIND_BYTE
        CLC
        LDA MM_X_HEAD+4
        ADC MM_X_HEAD+6
        STA MM_X_OFFSET
        LDA MM_X_HEAD+5
        ADC MM_X_HEAD+7
                        BCS MM_X_FIND_BYTE
        CMP #$67
                        BCC MM_X_FIND_RANGE_OK
                        BNE MM_X_FIND_BYTE
        LDA MM_X_OFFSET
                        BNE MM_X_FIND_BYTE
MM_X_FIND_RANGE_OK:
        CLC
        LDA MM_X_SCAN
        ADC #24
        STA MM_X_OFFSET
        LDA MM_X_SCAN+1
        ADC #0
        STA MM_X_OFFSET+1
        CLC
        LDA MM_X_OFFSET
        ADC MM_X_HEAD+6
        STA MM_X_BP
        LDA MM_X_OFFSET+1
        ADC MM_X_HEAD+7
                        BCS MM_X_FIND_BYTE
        CMP #$E0
                        BCC MM_X_FIND_END_OK
                        BNE MM_X_FIND_BYTE
        LDX MM_X_BP
                        BNE MM_X_FIND_BYTE
MM_X_FIND_END_OK:
        STA MM_X_BP+1
        LDA MM_X_HEAD+3
        CMP #$3F
                        BNE MM_X_FIND_SKIP
        LDX #15
MM_X_FIND_NAME:
        LDA MM_X_HEAD+8,X
        CMP MM_X_SOURCE_NAME,X
                        BNE MM_X_FIND_SKIP
        DEX
                        BPL MM_X_FIND_NAME
        LDA MM_X_FOUND
                        BEQ MM_X_FOUND_FIRST
        LDA #2
        STA MM_X_FOUND
                        BRA MM_X_FOUND_KEEP
MM_X_FOUND_FIRST:
        INC MM_X_FOUND
MM_X_FOUND_KEEP:
        LDA MM_X_SCAN
        STA MM_X_FLASH
        LDA MM_X_SCAN+1
        STA MM_X_FLASH+1
        LDA MM_X_OFFSET
        STA MM_X_PAYLOAD
        LDA MM_X_OFFSET+1
        STA MM_X_PAYLOAD+1
        LDX #3
MM_X_FIND_SAVE:
        LDA MM_X_HEAD+4,X
        STA MM_X_META,X
        DEX
                        BPL MM_X_FIND_SAVE
MM_X_FIND_SKIP:
        LDA MM_X_BP
        STA MM_X_SCAN
        LDA MM_X_BP+1
        STA MM_X_SCAN+1
                        JMP MM_X_FIND_NEXT
MM_X_FIND_BYTE:
        INC MM_X_SCAN
                        BNE MM_X_FIND_NEXT
        INC MM_X_SCAN+1
                        JMP MM_X_FIND_NEXT
MM_X_FIND_DONE:
        LDA MM_X_FOUND
        CMP #1
                        BNE MM_X_PARSE_NO
        LDX #3
MM_X_FIND_RESTORE:
        LDA MM_X_META,X
        STA MM_X_HEAD+4,X
        DEX
                        BPL MM_X_FIND_RESTORE
        SEC
        RTS
MM_X_END_RANGE:
        CLC
        LDA MM_X_HEAD+4
        ADC MM_X_HEAD+6
        STA MM_X_REQ+4
        LDA MM_X_HEAD+5
        ADC MM_X_HEAD+7
        STA MM_X_REQ+5
        LDA MM_X_REQ+4
                        BNE MM_X_END_LOW
        DEC MM_X_REQ+5
MM_X_END_LOW:
        DEC MM_X_REQ+4
        RTS
; Source byte for SAVE CRC: map logical PTR to flash payload.
MM_X_READ_BYTE:
        SEC
        LDA $D2
        SBC SM_D_LOAD
        STA V2_ADDR
        LDA $D3
        SBC SM_D_LOAD+1
        STA V2_ADDR+1
        CLC
        LDA V2_ADDR
        ADC MM_X_PAYLOAD
        STA V2_ADDR
        LDA V2_ADDR+1
        ADC MM_X_PAYLOAD+1
        STA V2_ADDR+1
        LDA #1
        STA V2_COUNT
        JSR MM_X_READ
        LDA V2_BYTES
        LDY #0
        RTS
MM_X_READ:
        LDA MM_X_BANK
        STA V2_SELECTED
        JMP X28_C8
; Source transfer uses preserved BUF, never the source application's RAM.
MM_X_SAVE_CHUNK:
        LDA SM_D_BP
        STA MM_X_BP
        STA $D2
        LDA SM_D_BP+1
        STA MM_X_BP+1
        STA $D3
        STZ MM_X_INDEX
MM_X_FILL_CHUNK:
        JSR MM_X_READ_BYTE
        LDX MM_X_INDEX
        STA $5000,X
        INC $D2
                        BNE MM_X_FILL_NEXT
        INC $D3
MM_X_FILL_NEXT:
        INC MM_X_INDEX
        LDA MM_X_INDEX
        CMP SM_D_COUNT
                        BNE MM_X_FILL_CHUNK
        JSR MM_X_STAGE_BP
        LDA #2
        JSR SM_C_TRANSFER
                        BRA MM_X_UNSTAGE_BP
MM_X_STAGE_BP:
        STZ SM_D_BP
        LDA #$50
        STA SM_D_BP+1
        RTS
MM_X_UNSTAGE_BP:
        PHA
        LDA MM_X_BP
        STA SM_D_BP
        LDA MM_X_BP+1
        STA SM_D_BP+1
        PLA
        RTS
MM_X_RESTORE_CHUNK:
        LDA MM_X_STARTED
                        BNE MM_X_RESTORE_DATA
        LDX #3
MM_X_MATCH_META:
        LDA SM_D_LOAD,X
        CMP MM_X_META,X
                        BNE MM_X_HOOK_FAIL
        DEX
                        BPL MM_X_MATCH_META
        LDA SM_D_ENTRY
        CMP MM_X_META+4
                        BNE MM_X_HOOK_FAIL
        LDA SM_D_ENTRY+1
        CMP MM_X_META+5
                        BNE MM_X_HOOK_FAIL
        LDA SM_D_BEST_SEQ
        CMP MM_X_META+6
                        BNE MM_X_HOOK_FAIL
        LDA SM_D_BEST_SEQ+1
        CMP MM_X_META+7
                        BNE MM_X_HOOK_FAIL
        INC MM_X_STARTED
        LDX #3
MM_X_NEW_HEAD:
        LDA MM_X_RECORD_ID,X
        STA MM_X_HEAD,X
        LDA MM_X_META,X
        STA MM_X_HEAD+4,X
        DEX
                        BPL MM_X_NEW_HEAD
        LDA #$FF
        STA MM_X_HEAD+3
        ; Destination name survived READLINE in X_REQ; source name is kept
        ; separately. X_REQ now contains source, destination needs own copy.
        LDX #15
MM_X_NEW_NAME:
        LDA MM_X_DEST_NAME,X
        STA MM_X_HEAD+8,X
        DEX
                        BPL MM_X_NEW_NAME
        STZ MM_X_INDEX
MM_X_WRITE_HEAD:
        LDX MM_X_INDEX
        LDA MM_X_HEAD,X
        JSR MM_X_PROGRAM
                        BCC MM_X_HOOK_FAIL
        INC MM_X_INDEX
        LDA MM_X_INDEX
        CMP #24
                        BNE MM_X_WRITE_HEAD
MM_X_RESTORE_DATA:
        LDA SM_D_BP
        STA MM_X_BP
        LDA SM_D_BP+1
        STA MM_X_BP+1
        JSR MM_X_STAGE_BP
        LDA #1
        JSR SM_C_TRANSFER
        JSR MM_X_UNSTAGE_BP
        CMP #0
                        BNE MM_X_HOOK_FAIL
        STZ MM_X_INDEX
MM_X_PROGRAM_DATA:
        LDX MM_X_INDEX
        LDA $5000,X
        JSR MM_X_PROGRAM
                        BCC MM_X_HOOK_FAIL
        INC MM_X_INDEX
        LDA MM_X_INDEX
        CMP SM_D_COUNT
                        BNE MM_X_PROGRAM_DATA
        LDA #0
        RTS
MM_X_HOOK_FAIL:
        LDA #$46
        RTS
; Program fresh bytes only, read back each, never erase any occupied space.
MM_X_PROGRAM:
        STA MM_X_VALUE
        LDA MM_X_DEST
        STA V2_ADDR
        STA V2_FLASH_PTR
        LDA MM_X_DEST+1
        STA V2_ADDR+1
        STA V2_FLASH_PTR+1
        LDA #1
        STA V2_COUNT
        STA V2_NMI_HOLD
        JSR MM_X_READ
        LDA V2_BYTES
        CMP #$FF
                        BNE MM_X_PROGRAM_FAIL
        LDA MM_X_VALUE
        CMP #$FF
                        BEQ MM_X_PROGRAM_OK
        STA V2_FLASH_DATA
        LDA MM_X_BANK
        JSR MM_V2W_SELECT
        JSR X28_C9
        PHP
        LDA MM_RESIDENT
        JSR MM_V2W_SELECT
        PLP
                        BCC MM_X_PROGRAM_FAIL
        JSR MM_X_READ
        LDA V2_BYTES
        CMP MM_X_VALUE
                        BNE MM_X_PROGRAM_FAIL
MM_X_PROGRAM_OK:
        INC MM_X_DEST
                        BNE MM_X_PROGRAM_NO_CARRY
        INC MM_X_DEST+1
MM_X_PROGRAM_NO_CARRY:
        SEC
        RTS
MM_X_PROGRAM_FAIL:
        CLC
        RTS
MM_X_DEST_NAME EQU $6200
MM_X_RECORD_ID DB "SR",1,$3F
MM_X_EXEC_MAGIC DB "ED",1,3
MM_X_MAINT_NAME DB "MAINT"
MM_X_ADDRESS_TEXT DB "Destination B",0
MM_X_CONFIRM_TEXT DB "Copy program; source retained. Y to confirm: ",0
MM_X_DONE_TEXT DB "Copied and verified; source retained.",13,10,0
MM_X_FAIL_MESSAGE DB "Copy failed; source retained; destination may be pending.",13,10,0

X28_C8:
        JMP V2W_READ
SM_INIT:
        STZ MM_BLEN
        STZ MM_BLEN+1 ; X borrows the editor buffer; no stale editor commit
        JMP MB_LOAD_XP

        INCLUDE "bank-transfer-alloc.inc"
