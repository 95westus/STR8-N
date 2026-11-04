; PROGRAM provider ported from the preserved 2.0b35 SRAM manager.
; SS1/SS2 primary; SP/01 slots and payload CRC retained. No format/delete/reclaim.
; Private BASE1 component, foreground, E=1, SEI/CLD; owner ZP is never allocated.
        MODULE PROGRAM_PROVIDER
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "workbench-layout.inc"
        INCLUDE "program-layout.inc"
        INCLUDE "monitor-ui.inc"
        CODE
SP_START:
        DB "SP",1,13,"PR05"
        JMP API
        JMP SP_READ64
        JMP W_SPI_GUARD
        DB "SW",1,1 ; opt-in independent wide restore/run, op6/7
; A/X points to a32-byte request. Foreground, SEI/CLD.
; op0=query,1=save,2=restore,3=restore for run,4=lookup,5=preview Store.
; op8=wide Store,9=wide preview: source0200-66FF; no WB may be loaded first.
; bytes 1=0,2..3=start,4..5=inclusive end,6..7=entry (0=restore only),
; 8..23=name;24..25=explicit page-aligned start, zero means AUTO.
API:    SEI
        CLD
        STA PTR
        STX PTR+1
        CPX #2
                        BCC API_BAD
        CPX #$6A
                        BCS API_BAD
        CPX #$69
                        BNE API_COPY
        CMP #$E1
                        BCS API_BAD
API_COPY:
        LDY #31
API_COPY_LOOP:
        LDA (PTR),Y
        STA REQUEST,Y
        DEY
                        BPL API_COPY_LOOP
        LDA MU_EDU
        STA SP_PROFILE
        STZ SP_TAIL
        LDA REQUEST+26
        STA SP_RETURN
        LDA REQUEST+27
        STA SP_RETURN+1
        LDA REQUEST+28
        STA SP_BANK
        LDA REQUEST+29
        STA SP_FLOOR
        JSR OPERATION
        STA SP_STATUS
        LDA SP_TAIL
        BEQ SP_API_RESULT
        LDA COPYING
        BNE SP_TAIL_FINISH
SP_API_RESULT:
        LDA SP_STATUS
        CMP #0
                        BNE API_ERROR
        SEC
        RTS
API_BAD:LDA #$44
API_ERROR:
        CLC
        RTS
OPERATION:
        STZ COPYING
        STZ STATUS
        JSR DISCOVER
                        BNE FINISH
        LDA REQUEST+1
                        BNE ARG_BAD
        LDA REQUEST
        CMP #10
                        BCS ARG_BAD
        JSR MOUNT
        BNE FINISH
        LDA REQUEST
        BEQ FINISH
        JSR NAME_CHECK
                        BNE FINISH
        JSR FIND_NAME
                        BNE FINISH
        LDA REQUEST
        CMP #1
        BEQ SAVE
        CMP #5
        BEQ SAVE
        CMP #8
        BCS SAVE
BM_LONG_91:
        LDA BEST
        CMP #8
                        BCS NOT_FOUND
        JSR BEST_REC
        LDY #15
        LDA (REC),Y
        CMP #1
                        BNE NOT_FOUND
        LDA REQUEST
        CMP #4
        BEQ SP_FOUND_ONLY
        JSR VERIFY_PAYLOAD
                        BNE FINISH
        JMP RESTORE
SP_FOUND_ONLY:
        LDA #0
        JMP FINISH
ARG_BAD:LDA #$44
                        JMP FINISH
NOT_FOUND:
        LDA #$42
FINISH: STA STATUS
        RTS
DISCOVER:
        LDA MU_EDU
        BEQ ABSENT
        JSR W_SPI_GUARD
        BCC ABSENT
        LDA #0
        RTS
ABSENT: LDA #$80
        RTS
TRANSFER:
        STA SP_OP
        LDA ADDR
        STA SP_A0
        LDA ADDR+1
        STA SP_A1
        STZ SP_A2
        LDA BP
        STA SP_PTR
        LDA BP+1
        STA SP_PTR+1
        LDA COUNT
        STA SP_COUNT
        JSR SP_TRANSFER
        RTS
BUF_POINTER:
        LDA #<BUF
        STA BP
        LDA #>BUF
        STA BP+1
        RTS
READ_BLOCK:
        JSR BUF_POINTER
        LDA #64
        STA COUNT
        LDA #1
        BRA TRANSFER
MOUNT:  STZ ADDR
        STZ ADDR+1
        JSR READ_BLOCK
                        BEQ BM_LONG_218
                        JMP MOUNT_RETURN
BM_LONG_218:
        LDA BUF+63
        CMP #$A5
                        BEQ BM_LONG_221
                        JMP UNFORMATTED
BM_LONG_221:
        LDX #59
LAYOUT_CHECK:
        JSR SELECT_LAYOUT
                        BEQ BM_LONG_225
                        JMP CORRUPT
BM_LONG_225:
        LDX #31
MAP_CLEAR:
        STZ BITMAP,X
        DEX
                        BPL MAP_CLEAR
        LDA #$FF
        STA BITMAP
        STZ SEQUENCE
        STZ SEQUENCE+1
        STZ USED
        STZ INDEX
        LDA #8
        STA FREE_SLOT
SLOT_SCAN:
        JSR SLOT_ADDRESS
        JSR READ_BLOCK
                        BEQ BM_LONG_242
                        JMP MOUNT_RETURN
BM_LONG_242:
        JSR INDEX_REC
        LDY #31
CACHE_LOOP:
        LDA BUF,Y
        STA (REC),Y
        DEY
                        BPL CACHE_LOOP
        LDA BUF+63
        LDY #3
        STA (REC),Y
        CMP #$A5
                        BEQ SLOT_COMMITTED
        LDA INDEX
        STA FREE_SLOT
                        JMP NEXT_SLOT
SLOT_COMMITTED:
        JSR HEADER_CRC
                        BEQ BM_LONG_260
                        JMP CORRUPT
BM_LONG_260:
        LDA BUF+3
        ORA BUF+62
                        BEQ BM_LONG_263
                        JMP CORRUPT
BM_LONG_263:
        LDX #59
SLOT_RESERVED:
        LDA BUF,X
                        BEQ BM_LONG_267
                        JMP CORRUPT
BM_LONG_267:
        DEX
        CPX #31
                        BNE SLOT_RESERVED
        LDA #<BUF+16
        STA TEXT
        LDA #>BUF+16
        STA TEXT+1
        JSR CHECK_NAME_PTR
                        BEQ BM_LONG_276
                        JMP CORRUPT
BM_LONG_276:
        LDA BUF
        CMP #'S'
                        BEQ BM_LONG_279
                        JMP CORRUPT
BM_LONG_279:
        LDA BUF+1
        CMP #'P'
                        BEQ BM_LONG_282
                        JMP CORRUPT
BM_LONG_282:
        LDA BUF+2
        CMP #1
                        BEQ BM_LONG_285
                        JMP CORRUPT
BM_LONG_285:
        LDA BUF+15
        CMP #2
                        BEQ TOMBSTONE_CHECK
        CMP #1
                        BEQ BM_LONG_290
                        JMP CORRUPT
BM_LONG_290:
        LDA BUF+4
        STA LOAD
        LDA BUF+5
        STA LOAD+1
        LDA BUF+6
        STA LENGTH
        LDA BUF+7
        STA LENGTH+1
        LDA BUF+8
        STA ENTRY
        LDA BUF+9
        STA ENTRY+1
        JSR RANGE_CHECK
                        BNE CORRUPT
        LDA BUF+14
        CMP #8
                        BCC CORRUPT
        STA PAGE
        JSR PAGE_COUNT
        LDA PAGE
        CLC
        ADC PAGES
        JSR EXTENT_LIMIT
                        BNE CORRUPT
SLOT_MARK:
        JSR MARK_PAGES
                        BNE CORRUPT
                        BRA SLOT_SEQUENCE
TOMBSTONE_CHECK:
        LDA BUF+6
        ORA BUF+7
        ORA BUF+14
                        BNE CORRUPT
SLOT_SEQUENCE:
        LDA BUF+10
        ORA BUF+11
                        BEQ CORRUPT
        LDA BUF+11
        CMP SEQUENCE+1
                        BCC NEXT_SLOT
                        BNE SEQ_UPDATE
        LDA BUF+10
        CMP SEQUENCE
                        BCC NEXT_SLOT
SEQ_UPDATE:
        LDA BUF+10
        STA SEQUENCE
        LDA BUF+11
        STA SEQUENCE+1
NEXT_SLOT:
        INC INDEX
        LDA INDEX
        CMP #8
                        BEQ BM_LONG_344
                        JMP SLOT_SCAN
BM_LONG_344:
        LDA #0
MOUNT_RETURN:
        RTS
UNFORMATTED:
        LDA #$40
        RTS
CORRUPT:LDA #$41
        RTS
INDEX_REC:
        LDA #>DIR
        STA REC+1
        LDA INDEX
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA REC
        RTS
BEST_REC:
        LDA INDEX
        PHA
        LDA BEST
        STA INDEX
        JSR INDEX_REC
        PLA
        STA INDEX
        RTS
SLOT_ADDRESS:
        LDA INDEX
        INC A
        LSR A
        LSR A
        STA ADDR+1
        LDA INDEX
        INC A
        AND #3
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA ADDR
        RTS
PAGE_COUNT:
        LDA LENGTH+1
        STA PAGES
        LDA LENGTH
                        BEQ PAGE_COUNT_DONE
        INC PAGES
PAGE_COUNT_DONE:
        RTS
; MAP_BIT returns mask A, byte offset X for page PAGE. No wrap permitted.
MAP_BIT:
        LDA PAGE
        AND #7
        TAY
        LDA MASKS,Y
        PHA
        LDA PAGE
        LSR A
        LSR A
        LSR A
        TAX
        PLA
        RTS
MARK_PAGES:
        JSR MAP_BIT
        STA MASK
        AND BITMAP,X
                        BNE CORRUPT
        LDA MASK
        ORA BITMAP,X
        STA BITMAP,X
        INC USED
        INC PAGE
        DEC PAGES
                        BNE MARK_PAGES
        LDA #0
        RTS
ALLOCATE:
        JSR PAGE_COUNT
        LDA REQUEST+24
        ORA REQUEST+25
        BEQ SP_ALLOC_AUTO
        LDA REQUEST+24
        BNE NAME_BAD
        LDA REQUEST+25
        CMP #8
        BCC NAME_BAD
        STA PAGE
        STA FIRST_PAGE
        CLC
        ADC PAGES
        JSR EXTENT_LIMIT
        BNE ALLOC_RETURN
SP_ALLOC_EXPLICIT:
        JSR MAP_BIT
        AND BITMAP,X
        BNE FULL
        INC PAGE
        DEC PAGES
        BNE SP_ALLOC_EXPLICIT
        LDA #0
ALLOC_RETURN:
        RTS
SP_ALLOC_AUTO:
        JSR PAGE_COUNT
        STZ RUN_LENGTH
        LDA #8
        STA PAGE
ALLOC_LOOP:
        JSR MAP_BIT
        AND BITMAP,X
                        BNE ALLOC_OCCUPIED
        LDA RUN_LENGTH
                        BNE ALLOC_EXTEND
        LDA PAGE
        STA FIRST_PAGE
ALLOC_EXTEND:
        INC RUN_LENGTH
        LDA RUN_LENGTH
        CMP PAGES
                        BEQ ALLOC_DONE
                        BRA ALLOC_NEXT
ALLOC_OCCUPIED:
        STZ RUN_LENGTH
ALLOC_NEXT:
        INC PAGE
        LDA PAGE
        CMP LIMIT
                        BNE ALLOC_LOOP
FULL:   LDA #$43
        RTS
ALLOC_DONE:
        LDA #0
        RTS
NAME_CHECK:
        LDA #<REQUEST+8
        STA TEXT
        LDA #>REQUEST+8
        STA TEXT+1
CHECK_NAME_PTR:
        STZ PAD
        LDY #0
NAME_LOOP:
        LDA (TEXT),Y
                        BEQ NAME_PAD
        LDX PAD
                        BNE NAME_BAD
        CMP #'-'
                        BEQ NAME_NEXT
        CMP #'_'
                        BEQ NAME_NEXT
        CMP #'0'
                        BCC NAME_BAD
        CMP #'9'+1
                        BCC NAME_NEXT
        CMP #'A'
                        BCC NAME_BAD
        CMP #'Z'+1
                        BCS NAME_BAD
                        BRA NAME_NEXT
NAME_PAD:
        INC PAD
NAME_NEXT:
        INY
        CPY #16
                        BNE NAME_LOOP
        LDA (TEXT)
                        BEQ NAME_BAD
        LDA #0
        RTS
NAME_BAD:
        LDA #$44
        RTS
FIND_NAME:
        STZ AMBIG
        LDA #8
        STA BEST
        STZ BEST_SEQ
        STZ BEST_SEQ+1
        STZ INDEX
FIND_LOOP:
        JSR INDEX_REC
        LDY #3
        LDA (REC),Y
        CMP #$A5
                        BNE FIND_NEXT
        LDY #16
        LDX #0
FIND_COMPARE:
        LDA (REC),Y
        CMP REQUEST+8,X
                        BNE FIND_NEXT
        INY
        INX
        CPX #16
                        BNE FIND_COMPARE
        LDY #11
        LDA (REC),Y
        CMP BEST_SEQ+1
                        BCC FIND_NEXT
                        BNE FIND_UPDATE
        DEY
        LDA (REC),Y
        CMP BEST_SEQ
                        BCC FIND_NEXT
                        BNE FIND_UPDATE
        LDA #$41
        STA AMBIG
                        BRA FIND_NEXT
FIND_UPDATE:
        STZ AMBIG
        LDY #10
        LDA (REC),Y
        STA BEST_SEQ
        INY
        LDA (REC),Y
        STA BEST_SEQ+1
        LDA INDEX
        STA BEST
FIND_NEXT:
        INC INDEX
        LDA INDEX
        CMP #8
                        BNE FIND_LOOP
        LDA AMBIG
        RTS
RANGE_CHECK:
        LDA LENGTH
        ORA LENGTH+1
                        BEQ NAME_BAD
        LDA LOAD+1
        CMP #2
                        BCC NAME_BAD
        CLC
        LDA LOAD
        ADC LENGTH
        STA END_ADDR
        LDA LOAD+1
        ADC LENGTH+1
        STA END_ADDR+1
                        BCC BM_LONG_563
                        JMP NAME_BAD
BM_LONG_563:
        LDA END_ADDR
                        BNE RANGE_LIMIT
        DEC END_ADDR+1
RANGE_LIMIT:
        DEC END_ADDR
        LDA END_ADDR+1
        CMP #$67
        BCS NAME_BAD
RANGE_ENTRY:
        LDA ENTRY
        ORA ENTRY+1
                        BEQ RANGE_OK
        LDA ENTRY
        SEC
        SBC LOAD
        LDA ENTRY+1
        SBC LOAD+1
                        BCS BM_LONG_586
                        JMP NAME_BAD
BM_LONG_586:
        LDA END_ADDR
        SEC
        SBC ENTRY
        LDA END_ADDR+1
        SBC ENTRY+1
                        BCS BM_LONG_592
                        JMP NAME_BAD
BM_LONG_592:
RANGE_OK:
        LDA #0
        RTS
SAVE:
        LDA REQUEST+2
        STA LOAD
        LDA REQUEST+3
        STA LOAD+1
        SEC
        LDA REQUEST+4
        SBC LOAD
        STA LENGTH
        LDA REQUEST+5
        SBC LOAD+1
        STA LENGTH+1
                        BCS BM_LONG_608
                        JMP SAVE_BAD
BM_LONG_608:
        INC LENGTH
                        BNE SAVE_LENGTH
        INC LENGTH+1
SAVE_LENGTH:
        LDA REQUEST+6
        STA ENTRY
        LDA REQUEST+7
        STA ENTRY+1
        JSR RANGE_CHECK
                        BNE SAVE_RETURN
        JSR SP_CLIENT_RANGE
        BNE SAVE_RETURN
        JSR ALLOCATE
                        BNE SAVE_RETURN
        JSR NEW_RECORD
                        BNE SAVE_RETURN
        JSR CRC_INIT
        LDA LOAD
        STA PTR
        LDA LOAD+1
        STA PTR+1
        JSR SET_LEFT
SAVE_CRC_LOOP:
        LDY #0
        LDA (PTR),Y
        JSR CRC_BYTE
        INC PTR
                        BNE SAVE_CRC_NEXT
        INC PTR+1
SAVE_CRC_NEXT:
        JSR DEC_LEFT
                        BNE SAVE_CRC_LOOP
        LDY #12
        LDA CRC
        STA (REC),Y
        INY
        LDA CRC+1
        STA (REC),Y
        LDA REQUEST
        CMP #5
        BEQ SP_FOUND_ONLY
        CMP #9
        BEQ SP_FOUND_ONLY
        STZ ADDR
        LDA FIRST_PAGE
        STA ADDR+1
        LDA LOAD
        STA BP
        LDA LOAD+1
        STA BP+1
        JSR SET_LEFT
SAVE_WRITE_LOOP:
        JSR CHUNK
        LDA #2
        JSR TRANSFER
                        BNE SAVE_RETURN
        JSR ADVANCE
                        BNE SAVE_WRITE_LOOP
        JSR VERIFY_PAYLOAD
                        BNE SAVE_RETURN
        JSR PUBLISH
SAVE_RETURN:
        JMP FINISH
SAVE_BAD:
        LDA #$44
                        JMP SAVE_RETURN
NEW_RECORD:
        LDA FREE_SLOT
        CMP #8
                        BCC BM_LONG_689
                        JMP FULL
BM_LONG_689:
        LDA SEQUENCE
        AND SEQUENCE+1
        CMP #$FF
                        BEQ SEQ_FULL
        INC SEQUENCE
                        BNE NEW_SEQ
        INC SEQUENCE+1
NEW_SEQ:
        LDA FREE_SLOT
        STA INDEX
        JSR INDEX_REC
        LDY #31
        LDA #0
NEW_CLEAR:
        STA (REC),Y
        DEY
                        BPL NEW_CLEAR
        LDA #'S'
        STA (REC)
        LDY #1
        LDA #'P'
        STA (REC),Y
        INY
        LDA #1
        STA (REC),Y
        LDY #4
        LDA LOAD
        STA (REC),Y
        INY
        LDA LOAD+1
        STA (REC),Y
        INY
        LDA LENGTH
        STA (REC),Y
        INY
        LDA LENGTH+1
        STA (REC),Y
        INY
        LDA ENTRY
        STA (REC),Y
        INY
        LDA ENTRY+1
        STA (REC),Y
        INY
        LDA SEQUENCE
        STA (REC),Y
        INY
        LDA SEQUENCE+1
        STA (REC),Y
        LDY #14
        LDA FIRST_PAGE
        STA (REC),Y
        INY
        LDA #1
        STA (REC),Y
        LDY #16
        LDX #0
NEW_NAME:
        LDA REQUEST+8,X
        STA (REC),Y
        INY
        INX
        CPX #16
                        BNE NEW_NAME
        LDA #0
        RTS
SEQ_FULL:
        LDA #$48
        RTS
; Unpublished slot was free on mount. Payload is fully verified before header.
PUBLISH:
        LDY #63
        LDA #0
PUBLISH_CLEAR:
        STA BUF,Y
        DEY
        CPY #31
                        BNE PUBLISH_CLEAR
PUBLISH_COPY:
        LDA (REC),Y
        STA BUF,Y
        DEY
                        BPL PUBLISH_COPY
        JSR SEAL_HEADER
        JSR SLOT_ADDRESS
        JSR WRITE_VERIFY
                        BNE PUBLISH_RETURN
        LDA #$A5
        JSR COMMIT_BYTE
PUBLISH_RETURN:
        RTS
COMMIT_BYTE:
        STA BUF
        LDA ADDR
        CLC
        ADC #63
        STA ADDR
                        BCC COMMIT_ADDR
        INC ADDR+1
COMMIT_ADDR:
        JSR BUF_POINTER
        LDA #1
        STA COUNT
        BRA WRITE_VERIFY_COUNT
WRITE_VERIFY:
        JSR BUF_POINTER
        LDA #64
        STA COUNT
WRITE_VERIFY_COUNT:
        LDX COUNT
        DEX
VERIFY_BACKUP:
        LDA BUF,X
        STA EXPECTED,X
        DEX
                        BPL VERIFY_BACKUP
        LDA #2
        JSR TRANSFER
                        BNE WRITE_RETURN
        LDA #1
        JSR TRANSFER
                        BNE WRITE_RETURN
        LDX COUNT
        DEX
VERIFY_COMPARE:
        LDA BUF,X
        CMP EXPECTED,X
                        BNE CRC_BAD
        DEX
                        BPL VERIFY_COMPARE
        LDA #0
WRITE_RETURN:
        RTS
CRC_BAD:LDA #$45
        RTS
LOAD_RECORD:
        LDY #4
        LDA (REC),Y
        STA LOAD
        INY
        LDA (REC),Y
        STA LOAD+1
        INY
        LDA (REC),Y
        STA LENGTH
        INY
        LDA (REC),Y
        STA LENGTH+1
        INY
        LDA (REC),Y
        STA ENTRY
        INY
        LDA (REC),Y
        STA ENTRY+1
        LDY #14
        LDA (REC),Y
        STA ADDR+1
        STZ ADDR
SET_LEFT:
        LDA LENGTH
        STA LEFT
        LDA LENGTH+1
        STA LEFT+1
        RTS
CHUNK:  LDA #64
        LDX LEFT+1
                        BNE CHUNK_DONE
        CMP LEFT
                        BCC CHUNK_DONE
        LDA LEFT
CHUNK_DONE:
        STA COUNT
        RTS
ADVANCE:
        CLC
        LDA BP
        ADC COUNT
        STA BP
                        BCC ADVANCE_ADDR
        INC BP+1
ADVANCE_ADDR:
        CLC
        LDA ADDR
        ADC COUNT
        STA ADDR
                        BCC ADVANCE_LEFT
        INC ADDR+1
ADVANCE_LEFT:
        SEC
        LDA LEFT
        SBC COUNT
        STA LEFT
        LDA LEFT+1
        SBC #0
        STA LEFT+1
        ORA LEFT
        RTS
DEC_LEFT:
        LDA LEFT
                        BNE DEC_LOW
        DEC LEFT+1
DEC_LOW:DEC LEFT
        LDA LEFT
        ORA LEFT+1
        RTS
VERIFY_PAYLOAD:
        JSR LOAD_RECORD
        JSR CRC_INIT
PAYLOAD_LOOP:
        JSR STR8V2_RAM_CHECK_CANCEL
        BCC SP_VERIFY_NEXT
        LDA #$43
        RTS
SP_VERIFY_NEXT:
        JSR BUF_POINTER
        JSR CHUNK
        LDA #1
        JSR TRANSFER
                        BNE PAYLOAD_RETURN
        LDY #0
PAYLOAD_CRC:
        LDA BUF,Y
        JSR CRC_BYTE
        INY
        CPY COUNT
                        BNE PAYLOAD_CRC
        JSR ADVANCE
                        BNE PAYLOAD_LOOP
        LDY #12
        LDA (REC),Y
        CMP CRC
                        BEQ BM_LONG_916
                        JMP CRC_BAD
BM_LONG_916:
        INY
        LDA (REC),Y
        CMP CRC+1
                        BEQ BM_LONG_920
                        JMP CRC_BAD
BM_LONG_920:
        LDA #0
PAYLOAD_RETURN:
        RTS
RESTORE:
        JSR LOAD_RECORD
        JSR RANGE_CHECK
                        BEQ BM_LONG_927
                        JMP SAVE_RETURN
BM_LONG_927:
        LDA REQUEST
        CMP #6
        BCC SP_NARROW_RESTORE
        LDA SP_BANK
        CMP #4
        BCS ARG_BAD
        LDA SP_RETURN+1
        CMP #$7E
        BNE SP_RETURN_ROM
        LDA SP_RETURN
        CMP #$67
        BEQ SP_RETURN_VALID
SP_RETURN_ROM:
        LDA SP_RETURN+1
        CMP #$A0
        BCC ARG_BAD
        CMP #$C0
        BCS ARG_BAD
SP_RETURN_VALID:
        LDA LOAD+1
        CMP SP_FLOOR
        BCC ARG_BAD
        LDA END_ADDR+1
        CMP #>WB_ORIGIN
        BCC SP_WIDE_NOT_NEEDED
        LDA REQUEST
        STA SP_TAIL
        CMP #6
        BNE SP_RESTORE_MODE
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE SP_RESTORE_MODE
        LDA BQ_POS
        CMP BQ_SIZE
        BCC ARG_BAD
        BRA SP_RESTORE_MODE
SP_WIDE_NOT_NEEDED:
        LDA REQUEST
        SEC
        SBC #4
        STA REQUEST
SP_NARROW_RESTORE:
        JSR SP_CLIENT_RANGE
        BNE SAVE_RETURN
SP_RESTORE_MODE:
        LDA REQUEST
        AND #1
        CMP #1
                        BNE RESTORE_BEGIN
        LDA ENTRY
        ORA ENTRY+1
                        BEQ NO_RUN
RESTORE_BEGIN:
        LDA REQUEST
        AND #1
        BEQ SP_BATCH_ADMITTED
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE SP_BATCH_ADMITTED
        JSR SP_REGISTERED
        BNE FINISH
        JSR LOAD_RECORD
SP_BATCH_ADMITTED:
        INC COPYING
        LDA SP_TAIL
        BEQ SP_COPY_READY
        LDA #'>' ; admitted wide-copy phase; cancellation remains live
        JSR STR8V2_RAM_PUTC
SP_COPY_READY:
        LDA LOAD
        STA BP
        LDA LOAD+1
        STA BP+1
        JSR CRC_INIT
RESTORE_LOOP:
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS PARTIAL
        JSR CHUNK
        LDA #1
        JSR TRANSFER
                        BNE PARTIAL
        LDA BP
        STA PTR
        LDA BP+1
        STA PTR+1
        LDY #0
RESTORE_CRC:
        LDA (PTR),Y
        JSR CRC_BYTE
        INY
        CPY COUNT
                        BNE RESTORE_CRC
        JSR ADVANCE
                        BNE RESTORE_LOOP
        LDY #12
        LDA (REC),Y
        CMP CRC
                        BNE PARTIAL
        INY
        LDA (REC),Y
        CMP CRC+1
                        BNE PARTIAL
RESTORE_OK:
        LDA #0
        JMP FINISH
PARTIAL:LDA #$46
        JMP FINISH
NO_RUN: LDA #$47
        JMP FINISH
; Bounded reclaim: only superseded records. Validate newest live payload first.
; Tombstones remain until FORMAT; no data moves and no automatic collection.
CRC_INIT:
        LDA #$FF
        STA CRC
        STA CRC+1
        RTS
CRC_BYTE:
        EOR CRC+1
        STA CRC+1
        LDX #8
CRC_BIT:
        ASL CRC
        ROL CRC+1
                        BCC CRC_NEXT
        LDA CRC
        EOR #$21
        STA CRC
        LDA CRC+1
        EOR #$10
        STA CRC+1
CRC_NEXT:
        DEX
                        BNE CRC_BIT
        RTS
HEADER_CRC:
        JSR CRC_INIT
        LDY #0
HEADER_CRC_LOOP:
        LDA BUF,Y
        JSR CRC_BYTE
        INY
        CPY #62
                        BNE HEADER_CRC_LOOP
        LDA CRC
        ORA CRC+1
        RTS
SEAL_HEADER:
        JSR CRC_INIT
        LDY #0
SEAL_LOOP:
        LDA BUF,Y
        JSR CRC_BYTE
        INY
        CPY #60
                        BNE SEAL_LOOP
        LDA CRC+1
        STA BUF+60
        LDA CRC
        STA BUF+61
        RTS

SP_CLIENT_RANGE:
        LDA REQUEST
        CMP #8
        BCS SP_CLIENT_OK
        LDA END_ADDR+1
        CMP #>WB_ORIGIN
        BCS SP_CLIENT_BAD
        LDA LOAD+1
        CMP WB_CLIENT_FLOOR
        BCC SP_CLIENT_BAD
SP_CLIENT_OK:
        ; RANGE_CHECK already admitted the complete absolute0200-66FF range.
        ; Wide Store has no resident WB/caller floor inside that owner range.
        LDA #0
        RTS
SP_CLIENT_BAD:
        LDA #$44
        RTS
SP_TAIL_FINISH:
        JSR STR8V2_RAM_RX_RESET ; cancellation mutes text until acknowledged
        LDA #3
        JSR $7848
        LDA SP_BANK
        AND #3
        STA MU_BANK
        LDA SP_STATUS
        BEQ SP_TAIL_OK
        LDA #4
        STA BQ_ERROR
        LDX #<SP_PARTIAL_TEXT
        LDY #>SP_PARTIAL_TEXT
        BRA SP_TAIL_PRINT
SP_TAIL_OK:
        LDX #<SP_LOADED_TEXT
        LDY #>SP_LOADED_TEXT
SP_TAIL_PRINT:
        STX PTR
        STY PTR+1
        LDY #0
SP_TAIL_CHAR:
        LDA (PTR),Y
        BEQ SP_TAIL_PRINT_END
        JSR STR8V2_RAM_PUTC
        INY
        BRA SP_TAIL_CHAR
SP_TAIL_PRINT_END:
        LDA SP_STATUS
        BNE SP_TAIL_RETURN
        LDA SP_TAIL
        CMP #7
        BEQ SP_TAIL_RUN
        ; A final wide load-only must remain intact, rather than reloading WB.
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE SP_TAIL_RETURN
        STZ BQ_MAGIC
        LDX #<SP_DONE_TEXT
        LDY #>SP_DONE_TEXT
        STX PTR
        STY PTR+1
        LDY #0
SP_DONE_CHAR:
        LDA (PTR),Y
        BEQ SP_TAIL_RETURN
        JSR STR8V2_RAM_PUTC
        INY
        BRA SP_DONE_CHAR
SP_TAIL_RUN:
        LDA ENTRY
        STA $FE
        LDA ENTRY+1
        STA $FF
        LDA SP_BANK
        STA $F3
        JMP $7828
SP_TAIL_RETURN:
        LDX #$FF
        TXS
        JMP (SP_RETURN)
SP_REGISTERED:
        SEC
        LDA END_ADDR
        SBC ENTRY
        TAX
        LDA END_ADDR+1
        SBC ENTRY+1
        BNE SP_REG_ADDRESS
        CPX #9
        BCC SP_REG_BAD
SP_REG_ADDRESS:
        SEC
        LDA ENTRY
        SBC LOAD
        STA WORD
        LDA ENTRY+1
        SBC LOAD+1
        STA WORD+1
        CLC
        LDA WORD
        ADC ADDR
        STA ADDR
        LDA WORD+1
        ADC ADDR+1
        STA ADDR+1
        JSR READ_BLOCK
        BNE SP_REG_DONE
        LDX #9
SP_REG_BYTES:
        LDA BUF,X
        CMP SP_BT,X
        BNE SP_REG_BAD
        DEX
        BPL SP_REG_BYTES
        LDA #0
SP_REG_DONE:
        RTS
SP_REG_BAD:
        LDA #$47
        RTS
SP_BT: DB $80,8,"BT",1,2,"PR05"
SP_LOADED_TEXT: DB "PROGRAM OK",13,10,0
SP_DONE_TEXT: DB "Done",13,10,0
SP_PARTIAL_TEXT: DB "Partial",13,10,0
        INCLUDE "program-layout-check.inc"
        INCLUDE "program-spi.inc"
MASKS: DB 1,2,4,8,16,32,64,128
LAYOUT: DB "SS",1,8,8,0,1,0
        DS 52
SP_END:
        ENDMOD
        END
