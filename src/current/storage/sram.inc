SM_INIT:
        LDX #47
SM_CLEAR:
        STZ $67C7,X
        DEX
        BPL SM_CLEAR
        SEC
        RTS
SM_ENTRY:
        JSR SM_INIT
        BRA SM_C_START
; SRAM 1.0: standalone foreground manager. Linked at 6C00, R image at 4000.
; Borrows 6800-6AFF (tables/state) and 6C00-77FF (code), not journal 6Bxx.
; 6400-643F is a preserved transfer window; restore copies directly to target.
SM_C_TEXT EQU $D0
SM_C_PTR EQU $D2
SM_C_DST EQU $D4
SM_C_REC EQU $D6
SM_C_BUF EQU $6400
SM_C_DIR EQU $6900
SM_C_BACKUP EQU $6A00
SM_C_EXPECTED EQU $6A40
SM_C_BITMAP EQU $6A80
SM_C_REQUEST EQU $6AA0
SM_C_LINE EQU $6AC0
SM_C_R EQU $6650
SM_C_MANAGED EQU $66AE
SM_C_PUTC EQU $7E6D
SM_C_GETC EQU $7E70
SM_C_HEX EQU $7E7C
SM_C_NL EQU $7E7F
SM_C_START:  JMP SM_C_CONSOLE
        JMP SM_C_API
; API: A/X points to 32-byte request in user RAM. Foreground, SEI/CLD.
; op 0=query,1=save,2=restore,3=run,4=delete,5=reclaim,6=format.
; bytes 1=0,2..3=start,4..5=inclusive end,6..7=entry (0=restore only),
; 8..23=name (uppercase, zero padded),24..31=format key "FORMAT!!".
SM_C_API:    SEI
        CLD
        STA SM_C_PTR
        STX SM_C_PTR+1
        CPX #2
                        BCC SM_C_API_BAD
        CPX #$65
                        BCS SM_C_API_BAD
        CPX #$64
                        BNE SM_C_API_COPY
        CMP #$E1
                        BCS SM_C_API_BAD
SM_C_API_COPY:
        LDY #31
SM_C_API_COPY_LOOP:
        LDA (SM_C_PTR),Y
        STA SM_C_REQUEST,Y
        DEY
                        BPL SM_C_API_COPY_LOOP
        JSR SM_C_OPERATION
        CMP #0
                        BNE SM_C_API_ERROR
        SEC
        RTS
SM_C_API_BAD:LDA #$44
SM_C_API_ERROR:
        CLC
        RTS
SM_C_OPERATION:
        STZ SM_D_COPYING
        STZ SM_D_STATUS
        LDX #63
SM_C_BACKUP_LOOP:
        LDA SM_C_BUF,X
        STA SM_C_BACKUP,X
        DEX
                        BPL SM_C_BACKUP_LOOP
        JSR SM_C_DISCOVER
                        BNE SM_C_FINISH
        LDA SM_C_REQUEST+1
                        BNE SM_C_ARG_BAD
        LDA SM_C_REQUEST
        CMP #7
                        BCS SM_C_ARG_BAD
        CMP #6
                        BNE SM_C_BM_LONG_78
                        JMP SM_C_FORMAT
SM_C_BM_LONG_78:
        JSR SM_C_MOUNT
                        BNE SM_C_FINISH
        LDA SM_C_REQUEST
                        BEQ SM_C_FINISH
        CMP #5
                        BNE SM_C_BM_LONG_84
                        JMP SM_C_RECLAIM
SM_C_BM_LONG_84:
        JSR SM_C_NAME_CHECK
                        BNE SM_C_FINISH
        JSR SM_C_FIND_NAME
                        BNE SM_C_FINISH
        LDA SM_C_REQUEST
        CMP #1
                        BNE SM_C_BM_LONG_91
                        JMP SM_C_SAVE
SM_C_BM_LONG_91:
        CMP #4
                        BNE SM_C_BM_LONG_93
                        JMP SM_C_DELETE
SM_C_BM_LONG_93:
        LDA SM_D_BEST
        CMP #8
                        BCS SM_C_NOT_FOUND
        JSR SM_C_BEST_REC
        LDY #15
        LDA (SM_C_REC),Y
        CMP #1
                        BNE SM_C_NOT_FOUND
        JSR SM_C_VERIFY_PAYLOAD
                        BNE SM_C_FINISH
        JMP SM_C_RESTORE
SM_C_ARG_BAD:LDA #$44
                        JMP SM_C_FINISH
SM_C_NOT_FOUND:
        LDA #$42
SM_C_FINISH: STA SM_D_STATUS
        LDA SM_D_COPYING
                        BNE SM_C_FINISH_RESULT
        JSR SM_C_RESTORE_BUF
SM_C_FINISH_RESULT:
        LDA SM_D_STATUS
        RTS
SM_C_RESTORE_BUF:
        LDX #63
SM_C_RESTORE_BUF_LOOP:
        LDA SM_C_BACKUP,X
        STA SM_C_BUF,X
        DEX
                        BPL SM_C_RESTORE_BUF_LOOP
        RTS
SM_C_DISCOVER:
        LDX #2
SM_C_DISCOVER_LOOP:
        LDA $7D04,X
        CMP SM_D_SV_MAGIC,X
                        BNE SM_C_ABSENT
        DEX
                        BPL SM_C_DISCOVER_LOOP
        LDA $7D07
        AND #8
                        BEQ SM_C_ABSENT
        LDA $7D08
                        BNE SM_C_ABSENT
        LDA $7D09
        CMP #$65
                        BNE SM_C_ABSENT
        LDX #3
SM_C_SM_CHECK:
        LDA $66A2,X
        CMP SM_D_SM_MAGIC,X
                        BNE SM_C_ABSENT
        DEX
                        BPL SM_C_SM_CHECK
        LDA #1
        STA SM_C_MANAGED
        STZ SM_D_COUNT
        LDA #0
        JSR SM_C_TRANSFER
        RTS
SM_C_ABSENT: LDA #$80
        RTS
; Each manager write is a privileged cooperative operation. Public clients
; never receive a setter. No IRQ/NMI service callers or concurrent managers.
SM_C_TRANSFER:
        PHA
        LDX #15
SM_C_TRANSFER_CLEAR:
        STZ SM_C_R,X
        DEX
                        BPL SM_C_TRANSFER_CLEAR
        LDA SM_D_ADDR
        STA SM_C_R+2
        LDA SM_D_ADDR+1
        STA SM_C_R+3
        LDA SM_D_BP
        STA SM_C_R+5
        LDA SM_D_BP+1
        STA SM_C_R+6
        LDA SM_D_COUNT
        STA SM_C_R+7
        PLA
        STA SM_C_R
        CMP #2
                        BNE SM_C_TRANSFER_READ
        PHP
        SEI
        STZ SM_C_MANAGED
        JSR $66A6
        PHA
        LDA #1
        STA SM_C_MANAGED
        PLA
        PLP
                        BRA SM_C_TRANSFER_DONE
SM_C_TRANSFER_READ:
        JSR $66A6
SM_C_TRANSFER_DONE:
        CMP #0
                        BNE SM_C_TRANSFER_RETURN
        LDA SM_C_R
                        BEQ SM_C_TRANSFER_RETURN
        LDA SM_C_R+9
        CMP SM_D_COUNT
                        BNE SM_C_TRANSFER_SHORT
        LDA #0
SM_C_TRANSFER_RETURN:
        RTS
SM_C_TRANSFER_SHORT:
        LDA #7
        RTS
SM_C_BUF_POINTER:
        STZ SM_D_BP
        LDA #$64
        STA SM_D_BP+1
        RTS
SM_C_READ_BLOCK:
        JSR SM_C_BUF_POINTER
        LDA #64
        STA SM_D_COUNT
        LDA #1
        BRA SM_C_TRANSFER
SM_C_MOUNT:  STZ SM_D_ADDR
        STZ SM_D_ADDR+1
        JSR SM_C_READ_BLOCK
                        BEQ SM_C_BM_LONG_218
                        JMP SM_C_MOUNT_RETURN
SM_C_BM_LONG_218:
        LDA SM_C_BUF+63
        CMP #$A5
                        BEQ SM_C_BM_LONG_221
                        JMP SM_C_UNFORMATTED
SM_C_BM_LONG_221:
        LDX #59
SM_C_LAYOUT_CHECK:
        JSR SM_A_SELECT_LAYOUT
                        BEQ SM_C_BM_LONG_225
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_225:
        LDX #31
SM_C_MAP_CLEAR:
        STZ SM_C_BITMAP,X
        DEX
                        BPL SM_C_MAP_CLEAR
        LDA #$FF
        STA SM_C_BITMAP
        STZ SM_D_SEQUENCE
        STZ SM_D_SEQUENCE+1
        STZ SM_D_USED
        STZ SM_D_INDEX
        LDA #8
        STA SM_D_FREE_SLOT
SM_C_SLOT_SCAN:
        JSR SM_C_SLOT_ADDRESS
        JSR SM_C_READ_BLOCK
                        BEQ SM_C_BM_LONG_242
                        JMP SM_C_MOUNT_RETURN
SM_C_BM_LONG_242:
        JSR SM_C_INDEX_REC
        LDY #31
SM_C_CACHE_LOOP:
        LDA SM_C_BUF,Y
        STA (SM_C_REC),Y
        DEY
                        BPL SM_C_CACHE_LOOP
        LDA SM_C_BUF+63
        LDY #3
        STA (SM_C_REC),Y
        CMP #$A5
                        BEQ SM_C_SLOT_COMMITTED
        LDA SM_D_INDEX
        STA SM_D_FREE_SLOT
                        JMP SM_C_NEXT_SLOT
SM_C_SLOT_COMMITTED:
        JSR SM_C_HEADER_CRC
                        BEQ SM_C_BM_LONG_260
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_260:
        LDA SM_C_BUF+3
        ORA SM_C_BUF+62
                        BEQ SM_C_BM_LONG_263
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_263:
        LDX #59
SM_C_SLOT_RESERVED:
        LDA SM_C_BUF,X
                        BEQ SM_C_BM_LONG_267
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_267:
        DEX
        CPX #31
                        BNE SM_C_SLOT_RESERVED
        LDA #<SM_C_BUF+16
        STA SM_C_TEXT
        LDA #>SM_C_BUF+16
        STA SM_C_TEXT+1
        JSR SM_C_CHECK_NAME_PTR
                        BEQ SM_C_BM_LONG_276
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_276:
        LDA SM_C_BUF
        CMP #'S'
                        BEQ SM_C_BM_LONG_279
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_279:
        LDA SM_C_BUF+1
        CMP #'P'
                        BEQ SM_C_BM_LONG_282
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_282:
        LDA SM_C_BUF+2
        CMP #1
                        BEQ SM_C_BM_LONG_285
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_285:
        LDA SM_C_BUF+15
        CMP #2
                        BEQ SM_C_TOMBSTONE_CHECK
        CMP #1
                        BEQ SM_C_BM_LONG_290
                        JMP SM_C_CORRUPT
SM_C_BM_LONG_290:
        LDA SM_C_BUF+4
        STA SM_D_LOAD
        LDA SM_C_BUF+5
        STA SM_D_LOAD+1
        LDA SM_C_BUF+6
        STA SM_D_LENGTH
        LDA SM_C_BUF+7
        STA SM_D_LENGTH+1
        LDA SM_C_BUF+8
        STA SM_D_ENTRY
        LDA SM_C_BUF+9
        STA SM_D_ENTRY+1
        JSR SM_C_RANGE_CHECK
                        BNE SM_C_CORRUPT
        LDA SM_C_BUF+14
        CMP #8
                        BCC SM_C_CORRUPT
        STA SM_D_PAGE
        JSR SM_C_PAGE_COUNT
        LDA SM_D_PAGE
        CLC
        ADC SM_D_PAGES
        JSR SM_A_EXTENT_LIMIT
                        BNE SM_C_CORRUPT
SM_C_SLOT_MARK:
        JSR SM_C_MARK_PAGES
                        BNE SM_C_CORRUPT
                        BRA SM_C_SLOT_SEQUENCE
SM_C_TOMBSTONE_CHECK:
        LDA SM_C_BUF+6
        ORA SM_C_BUF+7
        ORA SM_C_BUF+14
                        BNE SM_C_CORRUPT
SM_C_SLOT_SEQUENCE:
        LDA SM_C_BUF+10
        ORA SM_C_BUF+11
                        BEQ SM_C_CORRUPT
        LDA SM_C_BUF+11
        CMP SM_D_SEQUENCE+1
                        BCC SM_C_NEXT_SLOT
                        BNE SM_C_SEQ_UPDATE
        LDA SM_C_BUF+10
        CMP SM_D_SEQUENCE
                        BCC SM_C_NEXT_SLOT
SM_C_SEQ_UPDATE:
        LDA SM_C_BUF+10
        STA SM_D_SEQUENCE
        LDA SM_C_BUF+11
        STA SM_D_SEQUENCE+1
SM_C_NEXT_SLOT:
        INC SM_D_INDEX
        LDA SM_D_INDEX
        CMP #8
                        BEQ SM_C_BM_LONG_344
                        JMP SM_C_SLOT_SCAN
SM_C_BM_LONG_344:
        LDA #0
SM_C_MOUNT_RETURN:
        RTS
SM_C_UNFORMATTED:
        LDA #$40
        RTS
SM_C_CORRUPT:LDA #$41
        RTS
SM_C_INDEX_REC:
        LDA #$69
        STA SM_C_REC+1
        LDA SM_D_INDEX
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA SM_C_REC
        RTS
SM_C_BEST_REC:
        LDA SM_D_INDEX
        PHA
        LDA SM_D_BEST
        STA SM_D_INDEX
        JSR SM_C_INDEX_REC
        PLA
        STA SM_D_INDEX
        RTS
SM_C_SLOT_ADDRESS:
        LDA SM_D_INDEX
        INC A
        LSR A
        LSR A
        STA SM_D_ADDR+1
        LDA SM_D_INDEX
        INC A
        AND #3
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA SM_D_ADDR
        RTS
SM_C_PAGE_COUNT:
        LDA SM_D_LENGTH+1
        STA SM_D_PAGES
        LDA SM_D_LENGTH
                        BEQ SM_C_PAGE_COUNT_DONE
        INC SM_D_PAGES
SM_C_PAGE_COUNT_DONE:
        RTS
; MAP_BIT returns mask A, byte offset X for page PAGE. No wrap permitted.
SM_C_MAP_BIT:
        LDA SM_D_PAGE
        AND #7
        TAY
        LDA SM_D_MASKS,Y
        PHA
        LDA SM_D_PAGE
        LSR A
        LSR A
        LSR A
        TAX
        PLA
        RTS
SM_C_MARK_PAGES:
        JSR SM_C_MAP_BIT
        STA SM_D_MASK
        AND SM_C_BITMAP,X
                        BNE SM_C_CORRUPT
        LDA SM_D_MASK
        ORA SM_C_BITMAP,X
        STA SM_C_BITMAP,X
        INC SM_D_USED
        INC SM_D_PAGE
        DEC SM_D_PAGES
                        BNE SM_C_MARK_PAGES
        LDA #0
        RTS
SM_C_ALLOCATE:
        JSR SM_C_PAGE_COUNT
        STZ SM_D_RUN_LENGTH
        LDA #8
        STA SM_D_PAGE
SM_C_ALLOC_LOOP:
        JSR SM_C_MAP_BIT
        AND SM_C_BITMAP,X
                        BNE SM_C_ALLOC_OCCUPIED
        LDA SM_D_RUN_LENGTH
                        BNE SM_C_ALLOC_EXTEND
        LDA SM_D_PAGE
        STA SM_D_FIRST_PAGE
SM_C_ALLOC_EXTEND:
        INC SM_D_RUN_LENGTH
        LDA SM_D_RUN_LENGTH
        CMP SM_D_PAGES
                        BEQ SM_C_ALLOC_DONE
                        BRA SM_C_ALLOC_NEXT
SM_C_ALLOC_OCCUPIED:
        STZ SM_D_RUN_LENGTH
SM_C_ALLOC_NEXT:
        INC SM_D_PAGE
        LDA SM_D_PAGE
        CMP SM_D_LIMIT
                        BNE SM_C_ALLOC_LOOP
SM_C_FULL:   LDA #$43
        RTS
SM_C_ALLOC_DONE:
        LDA #0
        RTS
SM_C_NAME_CHECK:
        LDA #<SM_C_REQUEST+8
        STA SM_C_TEXT
        LDA #>SM_C_REQUEST+8
        STA SM_C_TEXT+1
SM_C_CHECK_NAME_PTR:
        STZ SM_D_PAD
        LDY #0
SM_C_NAME_LOOP:
        LDA (SM_C_TEXT),Y
                        BEQ SM_C_NAME_PAD
        LDX SM_D_PAD
                        BNE SM_C_NAME_BAD
        CMP #'-'
                        BEQ SM_C_NAME_NEXT
        CMP #'_'
                        BEQ SM_C_NAME_NEXT
        CMP #'0'
                        BCC SM_C_NAME_BAD
        CMP #'9'+1
                        BCC SM_C_NAME_NEXT
        CMP #'A'
                        BCC SM_C_NAME_BAD
        CMP #'Z'+1
                        BCS SM_C_NAME_BAD
                        BRA SM_C_NAME_NEXT
SM_C_NAME_PAD:
        INC SM_D_PAD
SM_C_NAME_NEXT:
        INY
        CPY #16
                        BNE SM_C_NAME_LOOP
        LDA (SM_C_TEXT)
                        BEQ SM_C_NAME_BAD
        LDA #0
        RTS
SM_C_NAME_BAD:
        LDA #$44
        RTS
SM_C_FIND_NAME:
        STZ SM_D_AMBIG
        LDA #8
        STA SM_D_BEST
        STZ SM_D_BEST_SEQ
        STZ SM_D_BEST_SEQ+1
        STZ SM_D_INDEX
SM_C_FIND_LOOP:
        JSR SM_C_INDEX_REC
        LDY #3
        LDA (SM_C_REC),Y
        CMP #$A5
                        BNE SM_C_FIND_NEXT
        LDY #16
        LDX #0
SM_C_FIND_COMPARE:
        LDA (SM_C_REC),Y
        CMP SM_C_REQUEST+8,X
                        BNE SM_C_FIND_NEXT
        INY
        INX
        CPX #16
                        BNE SM_C_FIND_COMPARE
        LDY #11
        LDA (SM_C_REC),Y
        CMP SM_D_BEST_SEQ+1
                        BCC SM_C_FIND_NEXT
                        BNE SM_C_FIND_UPDATE
        DEY
        LDA (SM_C_REC),Y
        CMP SM_D_BEST_SEQ
                        BCC SM_C_FIND_NEXT
                        BNE SM_C_FIND_UPDATE
        LDA #$41
        STA SM_D_AMBIG
                        BRA SM_C_FIND_NEXT
SM_C_FIND_UPDATE:
        STZ SM_D_AMBIG
        LDY #10
        LDA (SM_C_REC),Y
        STA SM_D_BEST_SEQ
        INY
        LDA (SM_C_REC),Y
        STA SM_D_BEST_SEQ+1
        LDA SM_D_INDEX
        STA SM_D_BEST
SM_C_FIND_NEXT:
        INC SM_D_INDEX
        LDA SM_D_INDEX
        CMP #8
                        BNE SM_C_FIND_LOOP
        LDA SM_D_AMBIG
        RTS
SM_C_RANGE_CHECK:
        LDA SM_D_LENGTH
        ORA SM_D_LENGTH+1
                        BEQ SM_C_NAME_BAD
        LDA SM_D_LOAD+1
        CMP #2
                        BCC SM_C_NAME_BAD
        CLC
        LDA SM_D_LOAD
        ADC SM_D_LENGTH
        STA SM_D_END_ADDR
        LDA SM_D_LOAD+1
        ADC SM_D_LENGTH+1
        STA SM_D_END_ADDR+1
                        BCC SM_C_BM_LONG_563
                        JMP SM_C_NAME_BAD
SM_C_BM_LONG_563:
        LDA SM_D_END_ADDR
                        BNE SM_C_RANGE_LIMIT
        DEC SM_D_END_ADDR+1
SM_C_RANGE_LIMIT:
        DEC SM_D_END_ADDR
        LDA SM_D_END_ADDR+1
        CMP $7D0B
                        BCC SM_C_RANGE_ENTRY
                        BEQ SM_C_BM_LONG_572
                        JMP SM_C_NAME_BAD
SM_C_BM_LONG_572:
        LDA SM_D_END_ADDR
        CMP $7D0A
                        BCC SM_C_RANGE_ENTRY
                        BEQ SM_C_BM_LONG_576
                        JMP SM_C_NAME_BAD
SM_C_BM_LONG_576:
SM_C_RANGE_ENTRY:
        LDA SM_D_ENTRY
        ORA SM_D_ENTRY+1
                        BEQ SM_C_RANGE_OK
        LDA SM_D_ENTRY
        SEC
        SBC SM_D_LOAD
        LDA SM_D_ENTRY+1
        SBC SM_D_LOAD+1
                        BCS SM_C_BM_LONG_586
                        JMP SM_C_NAME_BAD
SM_C_BM_LONG_586:
        LDA SM_D_END_ADDR
        SEC
        SBC SM_D_ENTRY
        LDA SM_D_END_ADDR+1
        SBC SM_D_ENTRY+1
                        BCS SM_C_BM_LONG_592
                        JMP SM_C_NAME_BAD
SM_C_BM_LONG_592:
SM_C_RANGE_OK:
        LDA #0
        RTS
SM_C_SAVE:   JSR SM_C_RESTORE_BUF
        LDA SM_C_REQUEST+2
        STA SM_D_LOAD
        LDA SM_C_REQUEST+3
        STA SM_D_LOAD+1
        SEC
        LDA SM_C_REQUEST+4
        SBC SM_D_LOAD
        STA SM_D_LENGTH
        LDA SM_C_REQUEST+5
        SBC SM_D_LOAD+1
        STA SM_D_LENGTH+1
                        BCS SM_C_BM_LONG_608
                        JMP SM_C_SAVE_BAD
SM_C_BM_LONG_608:
        INC SM_D_LENGTH
                        BNE SM_C_SAVE_LENGTH
        INC SM_D_LENGTH+1
SM_C_SAVE_LENGTH:
        LDA SM_C_REQUEST+6
        STA SM_D_ENTRY
        LDA SM_C_REQUEST+7
        STA SM_D_ENTRY+1
        JSR SM_C_RANGE_CHECK
                        BNE SM_C_SAVE_RETURN
        JSR SM_C_ALLOCATE
                        BNE SM_C_SAVE_RETURN
        JSR SM_C_NEW_RECORD
                        BNE SM_C_SAVE_RETURN
        JSR SM_C_CRC_INIT
        LDA SM_D_LOAD
        STA SM_C_PTR
        LDA SM_D_LOAD+1
        STA SM_C_PTR+1
        JSR SM_C_SET_LEFT
SM_C_SAVE_CRC_LOOP:
        LDY #0
        JSR SM_S_SOURCE_BYTE
        JSR SM_C_CRC_BYTE
        INC SM_C_PTR
                        BNE SM_C_SAVE_CRC_NEXT
        INC SM_C_PTR+1
SM_C_SAVE_CRC_NEXT:
        JSR SM_C_DEC_LEFT
                        BNE SM_C_SAVE_CRC_LOOP
        LDY #12
        LDA SM_D_CRC
        STA (SM_C_REC),Y
        INY
        LDA SM_D_CRC+1
        STA (SM_C_REC),Y
        STZ SM_D_ADDR
        LDA SM_D_FIRST_PAGE
        STA SM_D_ADDR+1
        LDA SM_D_LOAD
        STA SM_D_BP
        LDA SM_D_LOAD+1
        STA SM_D_BP+1
        JSR SM_C_SET_LEFT
SM_C_SAVE_WRITE_LOOP:
        JSR SM_C_CHUNK
        JSR SM_S_SAVE_TRANSFER
                        BNE SM_C_SAVE_RETURN
        JSR SM_C_ADVANCE
                        BNE SM_C_SAVE_WRITE_LOOP
        JSR SM_C_VERIFY_PAYLOAD
                        BNE SM_C_SAVE_RETURN
        JSR SM_C_PUBLISH
SM_C_SAVE_RETURN:
        JMP SM_C_FINISH
SM_C_SAVE_BAD:
        LDA #$44
                        JMP SM_C_SAVE_RETURN
SM_C_DELETE:
        LDA SM_D_BEST
        CMP #8
                        BCC SM_C_BM_LONG_670
                        JMP SM_C_NOT_FOUND
SM_C_BM_LONG_670:
        JSR SM_C_BEST_REC
        LDY #15
        LDA (SM_C_REC),Y
        CMP #1
                        BEQ SM_C_BM_LONG_675
                        JMP SM_C_NOT_FOUND
SM_C_BM_LONG_675:
        STZ SM_D_LENGTH
        STZ SM_D_LENGTH+1
        STZ SM_D_FIRST_PAGE
        JSR SM_C_NEW_RECORD
                        BNE SM_C_SAVE_RETURN
        LDY #15
        LDA #2
        STA (SM_C_REC),Y
        JSR SM_C_PUBLISH
                        JMP SM_C_SAVE_RETURN
SM_C_NEW_RECORD:
        LDA SM_D_FREE_SLOT
        CMP #8
                        BCC SM_C_BM_LONG_689
                        JMP SM_C_FULL
SM_C_BM_LONG_689:
        LDA SM_D_SEQUENCE
        AND SM_D_SEQUENCE+1
        CMP #$FF
                        BEQ SM_C_SEQ_FULL
        INC SM_D_SEQUENCE
                        BNE SM_C_NEW_SEQ
        INC SM_D_SEQUENCE+1
SM_C_NEW_SEQ:
        LDA SM_D_FREE_SLOT
        STA SM_D_INDEX
        JSR SM_C_INDEX_REC
        LDY #31
        LDA #0
SM_C_NEW_CLEAR:
        STA (SM_C_REC),Y
        DEY
                        BPL SM_C_NEW_CLEAR
        LDA #'S'
        STA (SM_C_REC)
        LDY #1
        LDA #'P'
        STA (SM_C_REC),Y
        INY
        LDA #1
        STA (SM_C_REC),Y
        LDY #4
        LDA SM_D_LOAD
        STA (SM_C_REC),Y
        INY
        LDA SM_D_LOAD+1
        STA (SM_C_REC),Y
        INY
        LDA SM_D_LENGTH
        STA (SM_C_REC),Y
        INY
        LDA SM_D_LENGTH+1
        STA (SM_C_REC),Y
        INY
        LDA SM_D_ENTRY
        STA (SM_C_REC),Y
        INY
        LDA SM_D_ENTRY+1
        STA (SM_C_REC),Y
        INY
        LDA SM_D_SEQUENCE
        STA (SM_C_REC),Y
        INY
        LDA SM_D_SEQUENCE+1
        STA (SM_C_REC),Y
        LDY #14
        LDA SM_D_FIRST_PAGE
        STA (SM_C_REC),Y
        INY
        LDA #1
        STA (SM_C_REC),Y
        LDY #16
        LDX #0
SM_C_NEW_NAME:
        LDA SM_C_REQUEST+8,X
        STA (SM_C_REC),Y
        INY
        INX
        CPX #16
                        BNE SM_C_NEW_NAME
        LDA #0
        RTS
SM_C_SEQ_FULL:
        LDA #$48
        RTS
; Unpublished slot was free on mount. Payload is fully verified before header.
SM_C_PUBLISH:
        LDY #63
        LDA #0
SM_C_PUBLISH_CLEAR:
        STA SM_C_BUF,Y
        DEY
        CPY #31
                        BNE SM_C_PUBLISH_CLEAR
SM_C_PUBLISH_COPY:
        LDA (SM_C_REC),Y
        STA SM_C_BUF,Y
        DEY
                        BPL SM_C_PUBLISH_COPY
        JSR SM_C_SEAL_HEADER
        JSR SM_C_SLOT_ADDRESS
        JSR SM_C_WRITE_VERIFY
                        BNE SM_C_PUBLISH_RETURN
        LDA #$A5
        JSR SM_C_COMMIT_BYTE
SM_C_PUBLISH_RETURN:
        RTS
SM_C_COMMIT_BYTE:
        STA SM_C_BUF
        LDA SM_D_ADDR
        CLC
        ADC #63
        STA SM_D_ADDR
                        BCC SM_C_COMMIT_ADDR
        INC SM_D_ADDR+1
SM_C_COMMIT_ADDR:
        JSR SM_C_BUF_POINTER
        LDA #1
        STA SM_D_COUNT
        BRA SM_C_WRITE_VERIFY_COUNT
SM_C_WRITE_VERIFY:
        JSR SM_C_BUF_POINTER
        LDA #64
        STA SM_D_COUNT
SM_C_WRITE_VERIFY_COUNT:
        LDX SM_D_COUNT
        DEX
SM_C_VERIFY_BACKUP:
        LDA SM_C_BUF,X
        STA SM_C_EXPECTED,X
        DEX
                        BPL SM_C_VERIFY_BACKUP
        LDA #2
        JSR SM_C_TRANSFER
                        BNE SM_C_WRITE_RETURN
        LDA #1
        JSR SM_C_TRANSFER
                        BNE SM_C_WRITE_RETURN
        LDX SM_D_COUNT
        DEX
SM_C_VERIFY_COMPARE:
        LDA SM_C_BUF,X
        CMP SM_C_EXPECTED,X
                        BNE SM_C_CRC_BAD
        DEX
                        BPL SM_C_VERIFY_COMPARE
        LDA #0
SM_C_WRITE_RETURN:
        RTS
SM_C_CRC_BAD:LDA #$45
        RTS
SM_C_LOAD_RECORD:
        LDY #4
        LDA (SM_C_REC),Y
        STA SM_D_LOAD
        INY
        LDA (SM_C_REC),Y
        STA SM_D_LOAD+1
        INY
        LDA (SM_C_REC),Y
        STA SM_D_LENGTH
        INY
        LDA (SM_C_REC),Y
        STA SM_D_LENGTH+1
        INY
        LDA (SM_C_REC),Y
        STA SM_D_ENTRY
        INY
        LDA (SM_C_REC),Y
        STA SM_D_ENTRY+1
        LDY #14
        LDA (SM_C_REC),Y
        STA SM_D_ADDR+1
        STZ SM_D_ADDR
SM_C_SET_LEFT:
        LDA SM_D_LENGTH
        STA SM_D_LEFT
        LDA SM_D_LENGTH+1
        STA SM_D_LEFT+1
        RTS
SM_C_CHUNK:  LDA #64
        LDX SM_D_LEFT+1
                        BNE SM_C_CHUNK_DONE
        CMP SM_D_LEFT
                        BCC SM_C_CHUNK_DONE
        LDA SM_D_LEFT
SM_C_CHUNK_DONE:
        STA SM_D_COUNT
        RTS
SM_C_ADVANCE:
        CLC
        LDA SM_D_BP
        ADC SM_D_COUNT
        STA SM_D_BP
                        BCC SM_C_ADVANCE_ADDR
        INC SM_D_BP+1
SM_C_ADVANCE_ADDR:
        CLC
        LDA SM_D_ADDR
        ADC SM_D_COUNT
        STA SM_D_ADDR
                        BCC SM_C_ADVANCE_LEFT
        INC SM_D_ADDR+1
SM_C_ADVANCE_LEFT:
        SEC
        LDA SM_D_LEFT
        SBC SM_D_COUNT
        STA SM_D_LEFT
        LDA SM_D_LEFT+1
        SBC #0
        STA SM_D_LEFT+1
        ORA SM_D_LEFT
        RTS
SM_C_DEC_LEFT:
        LDA SM_D_LEFT
                        BNE SM_C_DEC_LOW
        DEC SM_D_LEFT+1
SM_C_DEC_LOW:DEC SM_D_LEFT
        LDA SM_D_LEFT
        ORA SM_D_LEFT+1
        RTS
SM_C_VERIFY_PAYLOAD:
        JSR SM_C_LOAD_RECORD
        JSR SM_C_CRC_INIT
SM_C_PAYLOAD_LOOP:
        JSR SM_C_BUF_POINTER
        JSR SM_C_CHUNK
        LDA #1
        JSR SM_C_TRANSFER
                        BNE SM_C_PAYLOAD_RETURN
        LDY #0
SM_C_PAYLOAD_CRC:
        LDA SM_C_BUF,Y
        JSR SM_C_CRC_BYTE
        INY
        CPY SM_D_COUNT
                        BNE SM_C_PAYLOAD_CRC
        JSR SM_C_ADVANCE
                        BNE SM_C_PAYLOAD_LOOP
        LDY #12
        LDA (SM_C_REC),Y
        CMP SM_D_CRC
                        BEQ SM_C_BM_LONG_916
                        JMP SM_C_CRC_BAD
SM_C_BM_LONG_916:
        INY
        LDA (SM_C_REC),Y
        CMP SM_D_CRC+1
                        BEQ SM_C_BM_LONG_920
                        JMP SM_C_CRC_BAD
SM_C_BM_LONG_920:
        LDA #0
SM_C_PAYLOAD_RETURN:
        RTS
SM_C_RESTORE:
        JSR SM_C_LOAD_RECORD
        JSR NS_CHECKED_RANGE
                        BEQ SM_C_BM_LONG_927
                        JMP SM_C_SAVE_RETURN
SM_C_BM_LONG_927:
        LDA SM_C_REQUEST
        CMP #3
                        BNE SM_C_RESTORE_BEGIN
        LDA SM_D_ENTRY
        ORA SM_D_ENTRY+1
                        BEQ SM_C_NO_RUN
SM_C_RESTORE_BEGIN:
        JSR SM_C_RESTORE_BUF
        JSR SM_S_COPY_BEGIN
        LDA SM_D_LOAD
        STA SM_D_BP
        LDA SM_D_LOAD+1
        STA SM_D_BP+1
        JSR SM_C_CRC_INIT
SM_C_RESTORE_LOOP:
        JSR SM_C_CHUNK
        JSR SM_S_RESTORE_TRANSFER
                        BNE SM_C_PARTIAL
        LDA SM_D_BP
        STA SM_C_PTR
        LDA SM_D_BP+1
        STA SM_C_PTR+1
        LDY #0
SM_C_RESTORE_CRC:
        JSR SM_S_SOURCE_BYTE
        JSR SM_C_CRC_BYTE
        INY
        CPY SM_D_COUNT
                        BNE SM_C_RESTORE_CRC
        JSR SM_C_ADVANCE
                        BNE SM_C_RESTORE_LOOP
        LDY #12
        LDA (SM_C_REC),Y
        CMP SM_D_CRC
                        BNE SM_C_PARTIAL
        INY
        LDA (SM_C_REC),Y
        CMP SM_D_CRC+1
                        BNE SM_C_PARTIAL
        LDA SM_C_REQUEST
        CMP #3
                        BNE SM_C_RESTORE_OK
        LDA SM_D_ENTRY
        STA $FE
        LDA SM_D_ENTRY+1
        STA $FF
        JSR B29_APP_CHECK
        BCS B29_APP_OK
        LDA #$4A
        JMP SM_C_FINISH
B29_APP_OK:
        JMP X28_EXEC
SM_C_RESTORE_OK:
        LDA #0
        JMP SM_C_FINISH
SM_C_PARTIAL:LDA #$46
        JMP SM_C_FINISH
SM_C_NO_RUN: LDA #$47
        JMP SM_C_FINISH
; Bounded reclaim: only superseded records. Validate newest live payload first.
; Tombstones remain until FORMAT; no data moves and no automatic collection.
SM_C_RECLAIM:
        STZ SM_D_GC_INDEX
        STZ SM_D_GC_PASS
SM_C_GC_LOOP:
        LDA SM_D_GC_INDEX
        STA SM_D_INDEX
        JSR SM_C_INDEX_REC
        LDY #3
        LDA (SM_C_REC),Y
        CMP #$A5
                        BNE SM_C_GC_NEXT
        LDY #16
        LDX #0
SM_C_GC_NAME:
        LDA (SM_C_REC),Y
        STA SM_C_REQUEST+8,X
        INY
        INX
        CPX #16
                        BNE SM_C_GC_NAME
        JSR SM_C_FIND_NAME
                        BNE SM_C_GC_RETURN
        LDA SM_D_BEST
        CMP SM_D_GC_INDEX
                        BNE SM_C_GC_SUPERSEDED
        LDA SM_D_GC_PASS
                        BEQ SM_C_GC_NEXT
        JSR SM_C_BEST_REC
        LDY #15
        LDA (SM_C_REC),Y
        CMP #2
                        BEQ SM_C_GC_CLEAR
                        BRA SM_C_GC_NEXT
SM_C_GC_SUPERSEDED:
        JSR SM_C_BEST_REC
        LDY #15
        LDA (SM_C_REC),Y
        CMP #1
                        BNE SM_C_GC_CLEAR
        JSR SM_C_VERIFY_PAYLOAD
                        BNE SM_C_GC_RETURN
SM_C_GC_CLEAR:
        LDA SM_D_GC_INDEX
        STA SM_D_INDEX
        JSR SM_C_SLOT_ADDRESS
        LDA #0
        JSR SM_C_COMMIT_BYTE
                        BNE SM_C_GC_RETURN
        JSR SM_C_INDEX_REC
        LDY #3
        LDA #0
        STA (SM_C_REC),Y
SM_C_GC_NEXT:
        INC SM_D_GC_INDEX
        LDA SM_D_GC_INDEX
        CMP #8
                        BNE SM_C_GC_LOOP
        LDA SM_D_GC_PASS
                        BNE SM_C_GC_DONE
        INC SM_D_GC_PASS
        STZ SM_D_GC_INDEX
                        BRA SM_C_GC_LOOP
SM_C_GC_DONE:
        LDA #0
SM_C_GC_RETURN:
        JMP SM_C_FINISH
SM_C_FORMAT: LDX #7
SM_C_FORMAT_KEY:
        LDA SM_C_REQUEST+24,X
        CMP SM_D_FORMAT_MAGIC,X
                        BEQ SM_C_BM_LONG_1050
                        JMP SM_C_ARG_BAD
SM_C_BM_LONG_1050:
        DEX
                        BPL SM_C_FORMAT_KEY
        JSR SM_A_FORMAT_GUARD
                        BNE SM_C_FORMAT_RETURN
        ; Invalidate and verify layout first. Never clear directory under a
        ; still-valid old header. Interrupted format requires explicit retry.
        STZ SM_D_ADDR
        STZ SM_D_ADDR+1
        LDA #0
        JSR SM_C_COMMIT_BYTE
                        BNE SM_C_FORMAT_RETURN
        STZ SM_D_INDEX
SM_C_FORMAT_SLOTS:
        JSR SM_C_SLOT_ADDRESS
        LDA #0
        JSR SM_C_COMMIT_BYTE
                        BNE SM_C_FORMAT_RETURN
        INC SM_D_INDEX
        LDA SM_D_INDEX
        CMP #8
                        BNE SM_C_FORMAT_SLOTS
        LDX #59
SM_C_FORMAT_LAYOUT:
        LDA SM_D_LAYOUT,X
        STA SM_C_BUF,X
        DEX
                        BPL SM_C_FORMAT_LAYOUT
        STZ SM_C_BUF+62
        STZ SM_C_BUF+63
        JSR SM_C_SEAL_HEADER
        STZ SM_D_ADDR
        STZ SM_D_ADDR+1
        JSR SM_C_WRITE_VERIFY
                        BNE SM_C_FORMAT_RETURN
        LDA #$A5
        JSR SM_C_COMMIT_BYTE
SM_C_FORMAT_RETURN:
        JMP SM_C_FINISH
SM_C_CRC_INIT:
        LDA #$FF
        STA SM_D_CRC
        STA SM_D_CRC+1
        RTS
SM_C_CRC_BYTE:
        EOR SM_D_CRC+1
        STA SM_D_CRC+1
        LDX #8
SM_C_CRC_BIT:
        ASL SM_D_CRC
        ROL SM_D_CRC+1
                        BCC SM_C_CRC_NEXT
        LDA SM_D_CRC
        EOR #$21
        STA SM_D_CRC
        LDA SM_D_CRC+1
        EOR #$10
        STA SM_D_CRC+1
SM_C_CRC_NEXT:
        DEX
                        BNE SM_C_CRC_BIT
        RTS
SM_C_HEADER_CRC:
        JSR SM_C_CRC_INIT
        LDY #0
SM_C_HEADER_CRC_LOOP:
        LDA SM_C_BUF,Y
        JSR SM_C_CRC_BYTE
        INY
        CPY #62
                        BNE SM_C_HEADER_CRC_LOOP
        LDA SM_D_CRC
        ORA SM_D_CRC+1
        RTS
SM_C_SEAL_HEADER:
        JSR SM_C_CRC_INIT
        LDY #0
SM_C_SEAL_LOOP:
        LDA SM_C_BUF,Y
        JSR SM_C_CRC_BYTE
        INY
        CPY #60
                        BNE SM_C_SEAL_LOOP
        LDA SM_D_CRC+1
        STA SM_C_BUF+60
        LDA SM_D_CRC
        STA SM_C_BUF+61
        RTS
SM_C_CONSOLE:
        SEI
        CLD
        LDX #<SM_D_TITLE
        LDY #>SM_D_TITLE
        JSR SM_C_PRINT
        JSR SM_C_HELP
SM_C_PROMPT: LDX #<SM_D_PROMPT_TEXT
        LDY #>SM_D_PROMPT_TEXT
        JSR SM_C_PRINT
        JSR B29_LINE_2
                        BCC SM_C_PROMPT
        LDX #31
SM_C_REQUEST_CLEAR:
        STZ SM_C_REQUEST,X
        DEX
                        BPL SM_C_REQUEST_CLEAR
        LDA SM_C_LINE+1
                        BEQ SM_C_CON_COMMAND
        LDA SM_C_LINE
        CMP #'S'
                        BEQ SM_C_CON_COMMAND
        CMP #'SM_C_R'
                        BEQ SM_C_CON_COMMAND
        CMP #'G'
                        BEQ SM_C_CON_COMMAND
        CMP #'D'
                        BEQ SM_C_BM_LONG_1165
                        JMP SM_C_CON_BAD
SM_C_BM_LONG_1165:
SM_C_CON_COMMAND:
        LDA SM_C_LINE
        CMP #'Q'
                        BNE SM_C_BM_LONG_1169
                        JMP SM_C_QUIT
SM_C_BM_LONG_1169:
        CMP #'?'
                        BNE SM_C_BM_LONG_1171
                        JMP SM_C_CON_HELP
SM_C_BM_LONG_1171:
        CMP #'T'
                        BNE SM_C_BM_LONG_1173
                        JMP SM_C_TABLE
SM_C_BM_LONG_1173:
        CMP #'C'
                        BNE SM_C_BM_LONG_1175
                        JMP SM_C_CON_RECLAIM
SM_C_BM_LONG_1175:
        CMP #'F'
                        BNE SM_C_BM_LONG_1177
                        JMP SM_C_CON_FORMAT
SM_C_BM_LONG_1177:
        CMP #'S'
                        BEQ SM_C_CON_SAVE
        CMP #'SM_C_R'
                        BEQ SM_C_CON_RESTORE
        CMP #'G'
                        BEQ SM_C_CON_RUN
        CMP #'D'
                        BNE SM_C_CON_BAD
        LDA #4
                        JMP SM_C_CON_NAMED
SM_C_CON_RUN:LDA #3
                        JMP SM_C_CON_NAMED
SM_C_CON_RESTORE:
        LDA #2
SM_C_CON_NAMED:
        STA SM_C_REQUEST
        JSR SM_C_PARSE_NAME
                        BCC SM_C_CON_BAD
        LDA SM_C_LINE,X
                        BNE SM_C_CON_BAD
                        JMP SM_C_CON_DO
SM_C_CON_SAVE:
        LDA #1
        STA SM_C_REQUEST
        JSR SM_C_PARSE_NAME
                        BCC SM_C_CON_BAD
        LDY #2
SM_C_PARSE_WORDS:
        LDA SM_C_LINE,X
        CMP #' '
                        BNE SM_C_CON_BAD
        INX
        JSR SM_C_PARSE_HEX
                        BCC SM_C_CON_BAD
        LDA SM_D_WORD
        STA SM_C_REQUEST,Y
        INY
        LDA SM_D_WORD+1
        STA SM_C_REQUEST,Y
        INY
        CPY #8
                        BNE SM_C_PARSE_WORDS
        LDA SM_C_LINE,X
                        BNE SM_C_CON_BAD
SM_C_CON_DO: JSR SM_C_OPERATION
SM_C_CON_RESULT:
        CMP #0
        BEQ B29_SRAM_OK
        JSR B29_ERROR_HOOK
B29_SRAM_OK:
        PHA
        LDX #<SM_D_RESULT_TEXT
        LDY #>SM_D_RESULT_TEXT
        JSR SM_C_PRINT
        PLA
        JSR SM_C_HEX
        JSR SM_C_NL
        JMP SM_C_PROMPT
SM_C_CON_BAD:LDA #$44
                        JMP SM_C_CON_RESULT
SM_C_CON_RECLAIM:
        LDA #5
        STA SM_C_REQUEST
                        JMP SM_C_CON_DO
SM_C_CON_FORMAT:
        LDX #<SM_D_CONFIRM_TEXT
        LDY #>SM_D_CONFIRM_TEXT
        JSR SM_C_PRINT
        JSR SM_C_READLINE
                        BCS SM_C_BM_LONG_1243
                        JMP SM_C_PROMPT
SM_C_BM_LONG_1243:
        LDX #11
SM_C_CONFIRM_CHECK:
        LDA SM_C_LINE,X
        CMP SM_D_CONFIRM_MAGIC,X
                        BNE SM_C_CON_BAD
        DEX
                        BPL SM_C_CONFIRM_CHECK
        LDX #7
SM_C_CON_FORMAT_KEY:
        LDA SM_D_FORMAT_MAGIC,X
        STA SM_C_REQUEST+24,X
        DEX
                        BPL SM_C_CON_FORMAT_KEY
        LDA #6
        STA SM_C_REQUEST
                        JMP SM_C_CON_DO
SM_C_CON_HELP:
        JSR SM_C_HELP
        JMP SM_C_PROMPT
SM_C_QUIT:   JMP $7E67
SM_C_HELP:   LDX #<SM_D_HELP_TEXT
        LDY #>SM_D_HELP_TEXT
        JMP SM_C_PRINT
SM_C_TABLE:  JSR SM_C_OPERATION
                        BNE SM_C_CON_RESULT
        STZ SM_D_GC_INDEX
SM_C_TABLE_LOOP:
        LDA SM_D_GC_INDEX
        STA SM_D_INDEX
        JSR SM_C_INDEX_REC
        LDY #3
        LDA (SM_C_REC),Y
        CMP #$A5
                        BNE SM_C_TABLE_NEXT
        LDY #15
        LDA (SM_C_REC),Y
        CMP #1
                        BNE SM_C_TABLE_NEXT
        LDY #16
        LDX #0
SM_C_TABLE_NAME_COPY:
        LDA (SM_C_REC),Y
        STA SM_C_REQUEST+8,X
        INY
        INX
        CPX #16
                        BNE SM_C_TABLE_NAME_COPY
        JSR SM_C_FIND_NAME
                        BEQ SM_C_BM_LONG_1292
                        JMP SM_C_CON_RESULT
SM_C_BM_LONG_1292:
        LDA SM_D_BEST
        CMP SM_D_GC_INDEX
                        BNE SM_C_TABLE_NEXT
        JSR SM_C_BEST_REC
        LDY #16
SM_C_TABLE_NAME:
        LDA (SM_C_REC),Y
                        BEQ SM_C_TABLE_FIELDS
        JSR SM_C_PUTC
        INY
        CPY #32
                        BNE SM_C_TABLE_NAME
SM_C_TABLE_FIELDS:
        LDA #' '
        JSR SM_C_PUTC
        LDY #5
        LDA (SM_C_REC),Y
        JSR SM_C_HEX
        DEY
        LDA (SM_C_REC),Y
        JSR SM_C_HEX
        LDA #' '
        JSR SM_C_PUTC
        LDY #7
        LDA (SM_C_REC),Y
        JSR SM_C_HEX
        DEY
        LDA (SM_C_REC),Y
        JSR SM_C_HEX
        JSR SM_C_NL
SM_C_TABLE_NEXT:
        INC SM_D_GC_INDEX
        LDA SM_D_GC_INDEX
        CMP #8
                        BNE SM_C_TABLE_LOOP
        LDX #<SM_D_FREE_TEXT
        LDY #>SM_D_FREE_TEXT
        JSR SM_C_PRINT
        JSR SM_A_FREE_PAGES
        JSR SM_C_HEX
        LDA #0
        JSR SM_C_HEX
        JSR SM_C_NL
        JMP SM_C_PROMPT
SM_C_PARSE_NAME:
        LDX #1
        LDA SM_C_LINE,X
        CMP #' '
                        BNE SM_C_PARSE_FAIL
        INX
        LDY #0
SM_C_PARSE_NAME_LOOP:
        LDA SM_C_LINE,X
                        BEQ SM_C_PARSE_NAME_DONE
        CMP #' '
                        BEQ SM_C_PARSE_NAME_DONE
        CPY #16
                        BCS SM_C_PARSE_FAIL
        STA SM_C_REQUEST+8,Y
        INY
        INX
                        BRA SM_C_PARSE_NAME_LOOP
SM_C_PARSE_NAME_DONE:
        CPY #0
                        BEQ SM_C_PARSE_FAIL
        SEC
        RTS
SM_C_PARSE_HEX:
        STZ SM_D_WORD
        STZ SM_D_WORD+1
        LDA #4
        STA SM_D_DIGITS
SM_C_PARSE_HEX_LOOP:
        LDA SM_C_LINE,X
        CMP #'0'
                        BCC SM_C_PARSE_FAIL
        CMP #'9'+1
                        BCC SM_C_PARSE_DIGIT
        CMP #'A'
                        BCC SM_C_PARSE_FAIL
        CMP #'F'+1
                        BCS SM_C_PARSE_FAIL
        SEC
        SBC #7
SM_C_PARSE_DIGIT:
        SEC
        SBC #'0'
        PHX
        LDX #4
SM_C_PARSE_SHIFT:
        ASL SM_D_WORD
        ROL SM_D_WORD+1
        DEX
                        BNE SM_C_PARSE_SHIFT
        PLX
        ORA SM_D_WORD
        STA SM_D_WORD
        INX
        DEC SM_D_DIGITS
                        BNE SM_C_PARSE_HEX_LOOP
        SEC
        RTS
SM_C_PARSE_FAIL:
        CLC
        RTS
SM_C_READLINE:
        STZ SM_D_LINE_LENGTH
        STZ SM_D_OVERFLOW
SM_C_LINE_WAIT:
        JSR SM_C_GETC
        CMP #3
                        BEQ SM_C_LINE_CANCEL
        CMP #$1B
                        BEQ SM_C_LINE_CANCEL
        CMP #10
                        BEQ SM_C_LINE_WAIT
        CMP #13
                        BEQ SM_C_LINE_DONE
        CMP #8
                        BEQ SM_C_LINE_BACK
        CMP #$7F
                        BEQ SM_C_LINE_BACK
        CMP #$20
                        BCC SM_C_LINE_WAIT
        CMP #'a'
                        BCC SM_C_LINE_CHAR
        CMP #'z'+1
                        BCS SM_C_LINE_CHAR
        AND #$DF
SM_C_LINE_CHAR:
        LDX SM_D_LINE_LENGTH
        CPX #39
                        BCS SM_C_LINE_FULL
        STA SM_C_LINE,X
        INC SM_D_LINE_LENGTH
        JSR SM_C_PUTC
                        JMP SM_C_LINE_WAIT
SM_C_LINE_FULL:
        LDA #1
        STA SM_D_OVERFLOW
                        JMP SM_C_LINE_WAIT
SM_C_LINE_BACK:
        LDA SM_D_LINE_LENGTH
                        BEQ SM_C_LINE_WAIT
        DEC SM_D_LINE_LENGTH
        LDA #8
        JSR SM_C_PUTC
        LDA #' '
        JSR SM_C_PUTC
        LDA #8
        JSR SM_C_PUTC
                        JMP SM_C_LINE_WAIT
SM_C_LINE_DONE:
        LDX SM_D_LINE_LENGTH
        STZ SM_C_LINE,X
        JSR SM_C_NL
        LDA SM_D_OVERFLOW
                        BNE SM_C_LINE_CANCEL
        SEC
        RTS
SM_C_LINE_CANCEL: JSR B29_CANCEL_HOOK

        JSR SM_C_NL
        CLC
        RTS
SM_C_PRINT:  STX SM_C_TEXT
        STY SM_C_TEXT+1
        LDY #0
SM_C_PRINT_LOOP:
        LDA (SM_C_TEXT),Y
                        BEQ SM_C_PRINT_DONE
        JSR SM_C_PUTC
        INY
                        BRA SM_C_PRINT_LOOP
SM_C_PRINT_DONE:
        RTS
SM_C_APP_END:

; SRAM 1.1 layout reader: primary only. WORK repairs interrupted primary.
SM_A_SELECT_LAYOUT:
        JSR SM_C_HEADER_CRC
                        BEQ SM_A_BM_LONG_8
                        JMP SM_A_LAYOUT_BAD
SM_A_BM_LONG_8:
        LDA SM_S_BUF
        CMP #'S'
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+1
        CMP #'S'
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+3
        CMP #8
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+4
        CMP #8
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+2
        CMP #1
                        BEQ SM_A_SELECT_LEGACY
        CMP #2
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+7
        ORA SM_S_BUF+62
                        BNE SM_A_LAYOUT_BAD
        LDX #59
SM_A_LAYOUT_RESERVED:
        LDA SM_S_BUF,X
                        BNE SM_A_LAYOUT_BAD
        DEX
        CPX #11
                        BNE SM_A_LAYOUT_RESERVED
        LDA SM_S_BUF+8
        ORA SM_S_BUF+9
        ORA SM_S_BUF+10
        ORA SM_S_BUF+11
                        BEQ SM_A_LAYOUT_BAD
        LDA SM_S_BUF+5
        AND #$3F
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+6
                        BEQ SM_A_SELECT_SMALL
        CMP #1
                        BNE SM_A_LAYOUT_BAD
        LDA SM_S_BUF+5
                        BNE SM_A_LAYOUT_BAD
                        JMP SM_A_SELECT_OK
SM_A_SELECT_SMALL:
        LDA SM_S_BUF+5
                        BEQ SM_A_LAYOUT_BAD
SM_A_SELECT_OK:
        LDA SM_S_BUF+5
        STA SM_D_LIMIT
        LDA #0
        RTS
SM_A_SELECT_LEGACY:
        LDX #59
SM_A_LEGACY_COMPARE:
        LDA SM_S_BUF,X
        CMP SM_D_LAYOUT,X
                        BNE SM_A_LAYOUT_BAD
        DEX
                        BPL SM_A_LEGACY_COMPARE
                        JMP SM_A_SELECT_OK
SM_A_LAYOUT_BAD:
        LDA #$41
        RTS
SM_A_EXTENT_LIMIT:
                        BCC SM_A_EXTENT_NORMAL
                        BNE SM_A_LAYOUT_BAD
        LDX SM_D_LIMIT
                        BNE SM_A_LAYOUT_BAD
                        BRA SM_A_EXTENT_OK
SM_A_EXTENT_NORMAL:
        LDX SM_D_LIMIT
                        BEQ SM_A_EXTENT_OK
        CMP SM_D_LIMIT
                        BCC SM_A_EXTENT_OK
                        BNE SM_A_LAYOUT_BAD
SM_A_EXTENT_OK:
        LDA #0
        RTS
SM_A_FREE_PAGES:
        LDA SM_D_LIMIT
        SEC
        SBC #8
        SEC
        SBC SM_D_USED
        RTS
SM_A_FORMAT_GUARD:
        STZ SM_D_ADDR
        STZ SM_D_ADDR+1
        JSR SM_C_READ_BLOCK
                        BNE SM_A_GUARD_RETURN
        JSR SM_A_CHECK_V2
                        BNE SM_A_GUARD_RETURN
        LDA #$40
        STA SM_D_ADDR
        LDA #2
        STA SM_D_ADDR+1
        JSR SM_C_READ_BLOCK
                        BNE SM_A_GUARD_RETURN
SM_A_CHECK_V2:
        LDA SM_S_BUF+2
        CMP #2
                        BNE SM_A_GUARD_OK
        LDA SM_S_BUF+63
        CMP #$A5
                        BNE SM_A_GUARD_OK
        LDA SM_S_BUF
        CMP #'S'
                        BNE SM_A_GUARD_OK
        LDA SM_S_BUF+1
        CMP #'S'
                        BNE SM_A_GUARD_OK
        LDA #$49
SM_A_GUARD_RETURN:
        RTS
SM_A_GUARD_OK:
        LDA #0
        RTS
SM_A_AUX_END:

; Trusted MAINT streaming hooks. Ordinary SRAM API/console uses zero hooks.
SM_S_PTR EQU $D2
SM_S_BUF EQU $6400
SM_S_SOURCE_BYTE:
        LDA SM_D_RESTORE_TRANSFER_HOOK+1
                        BNE SM_S_STAGED_BYTE
        LDA SM_D_SOURCE_BYTE_HOOK+1
                        BNE SM_S_HOOK_BYTE
        LDA (SM_S_PTR),Y
        RTS
SM_S_STAGED_BYTE:
        LDA SM_S_BUF,Y
        RTS
SM_S_HOOK_BYTE:
        JMP (SM_D_SOURCE_BYTE_HOOK)
SM_S_SAVE_TRANSFER:
        LDA SM_D_SAVE_TRANSFER_HOOK+1
                        BNE SM_S_HOOK_SAVE
        LDA #2
        JMP SM_C_TRANSFER
SM_S_HOOK_SAVE:
        JMP (SM_D_SAVE_TRANSFER_HOOK)
SM_S_RESTORE_TRANSFER:
        LDA SM_D_RESTORE_TRANSFER_HOOK+1
                        BNE SM_S_HOOK_RESTORE
        LDA #1
        JMP SM_C_TRANSFER
SM_S_HOOK_RESTORE:
        JMP (SM_D_RESTORE_TRANSFER_HOOK)
SM_S_COPY_BEGIN:
        LDA SM_D_RESTORE_TRANSFER_HOOK+1
                        BNE SM_S_COPY_RETURN
        INC SM_D_COPYING
SM_S_COPY_RETURN:
        RTS
SM_S_EXT_END:

SM_D_SV_MAGIC DB "SV",1
SM_D_SM_MAGIC DB "SM",1,1
SM_D_MASKS DB 1,2,4,8,16,32,64,128
; SS v1: 8 x 64 directory at 0040; data 0800-FFFF; workspace 10000-1FFDF.
SM_D_LAYOUT DB "SS",1,8,8,0,1,0
        DS 52
SM_D_FORMAT_MAGIC DB "FORMAT!!"
SM_D_CONFIRM_MAGIC DB "FORMAT SRAM",0
SM_D_TITLE DB "SRAM 1.4",13,10,0
SM_D_PROMPT_TEXT DB "SRAM> ",0
SM_D_HELP_TEXT DB "S name start end entry; R/G/D name; T C F Q",13,10,0
SM_D_CONFIRM_TEXT DB "Type FORMAT SRAM: ",0
SM_D_RESULT_TEXT DB "SRAM: ",0
SM_D_FREE_TEXT DB "Free bytes: $",0
SM_D_ADDR EQU $67C7
SM_D_BP EQU $67C9
SM_D_LEFT EQU $67CB
SM_D_LOAD EQU $67CD
SM_D_LENGTH EQU $67CF
SM_D_END_ADDR EQU $67D1
SM_D_ENTRY EQU $67D3
SM_D_CRC EQU $67D5
SM_D_SEQUENCE EQU $67D7
SM_D_BEST_SEQ EQU $67D9
SM_D_WORD EQU $67DB
SM_D_COUNT EQU $67DD
SM_D_STATUS EQU $67DE
SM_D_COPYING EQU $67DF
SM_D_INDEX EQU $67E0
SM_D_FREE_SLOT EQU $67E1
SM_D_BEST EQU $67E2
SM_D_USED EQU $67E3
SM_D_PAGE EQU $67E4
SM_D_PAGES EQU $67E5
SM_D_MASK EQU $67E6
SM_D_RUN_LENGTH EQU $67E7
SM_D_FIRST_PAGE EQU $67E8
SM_D_PAD EQU $67E9
SM_D_GC_INDEX EQU $67EA
SM_D_GC_PASS EQU $67EB
SM_D_DIGITS EQU $67EC
SM_D_LINE_LENGTH EQU $67ED
SM_D_OVERFLOW EQU $67EE
SM_D_AMBIG EQU $67EF
SM_D_LIMIT EQU $67F0
SM_D_SOURCE_BYTE_HOOK EQU $67F1
SM_D_SAVE_TRANSFER_HOOK EQU $67F3
SM_D_RESTORE_TRANSFER_HOOK EQU $67F5
SM_D_DATA_END:
