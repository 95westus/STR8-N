; SRAM 1.0: standalone foreground manager. Linked at 6C00, R image at 4000.
; Borrows 6800-6AFF (tables/state) and 6C00-77FF (code), not journal 6Bxx.
; 6400-643F is a preserved transfer window; restore copies directly to target.
        MODULE SRAM_STORE
        XDEF START
        XDEF APP_END
TEXT EQU $D0
PTR EQU $D2
DST EQU $D4
REC EQU $D6
BUF EQU $6400
DIR EQU $6900
BACKUP EQU $6A00
EXPECTED EQU $6A40
BITMAP EQU $6A80
REQUEST EQU $6AA0
LINE EQU $6AC0
R EQU $6650
MANAGED EQU $66AE
PUTC EQU $7E6D
GETC EQU $7E70
HEX EQU $7E7C
NL EQU $7E7F
        CODE
START:  JMP CONSOLE
        JMP API
; API: A/X points to 32-byte request in user RAM. Foreground, SEI/CLD.
; op 0=query,1=save,2=restore,3=run,4=delete,5=reclaim,6=format.
; bytes 1=0,2..3=start,4..5=inclusive end,6..7=entry (0=restore only),
; 8..23=name (uppercase, zero padded),24..31=format key "FORMAT!!".
API:    SEI
        CLD
        STA PTR
        STX PTR+1
        CPX #2
        BCC API_BAD
        CPX #$65
        BCS API_BAD
        CPX #$64
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
        JSR OPERATION
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
        LDX #63
BACKUP_LOOP:
        LDA BUF,X
        STA BACKUP,X
        DEX
        BPL BACKUP_LOOP
        JSR DISCOVER
        BNE FINISH
        LDA REQUEST+1
        BNE ARG_BAD
        LDA REQUEST
        CMP #7
        BCS ARG_BAD
        CMP #6
        BEQ FORMAT
        JSR MOUNT
        BNE FINISH
        LDA REQUEST
        BEQ FINISH
        CMP #5
        BEQ RECLAIM
        JSR NAME_CHECK
        BNE FINISH
        JSR FIND_NAME
        BNE FINISH
        LDA REQUEST
        CMP #1
        BEQ SAVE
        CMP #4
        BEQ DELETE
        LDA BEST
        CMP #8
        BCS NOT_FOUND
        JSR BEST_REC
        LDY #15
        LDA (REC),Y
        CMP #1
        BNE NOT_FOUND
        JSR VERIFY_PAYLOAD
        BNE FINISH
        JMP RESTORE
ARG_BAD:LDA #$44
        BRA FINISH
NOT_FOUND:
        LDA #$42
FINISH: STA STATUS
        LDA COPYING
        BNE FINISH_RESULT
        JSR RESTORE_BUF
FINISH_RESULT:
        LDA STATUS
        RTS
RESTORE_BUF:
        LDX #63
RESTORE_BUF_LOOP:
        LDA BACKUP,X
        STA BUF,X
        DEX
        BPL RESTORE_BUF_LOOP
        RTS
DISCOVER:
        LDX #2
DISCOVER_LOOP:
        LDA $7D04,X
        CMP SV_MAGIC,X
        BNE ABSENT
        DEX
        BPL DISCOVER_LOOP
        LDA $7D07
        AND #8
        BEQ ABSENT
        LDA $7D08
        BNE ABSENT
        LDA $7D09
        CMP #$65
        BNE ABSENT
        LDX #3
SM_CHECK:
        LDA $66A2,X
        CMP SM_MAGIC,X
        BNE ABSENT
        DEX
        BPL SM_CHECK
        LDA #1
        STA MANAGED
        STZ COUNT
        LDA #0
        JSR TRANSFER
        RTS
ABSENT: LDA #$80
        RTS
; Each manager write is a privileged cooperative operation. Public clients
; never receive a setter. No IRQ/NMI service callers or concurrent managers.
TRANSFER:
        PHA
        LDX #15
TRANSFER_CLEAR:
        STZ R,X
        DEX
        BPL TRANSFER_CLEAR
        LDA ADDR
        STA R+2
        LDA ADDR+1
        STA R+3
        LDA BP
        STA R+5
        LDA BP+1
        STA R+6
        LDA COUNT
        STA R+7
        PLA
        STA R
        CMP #2
        BNE TRANSFER_READ
        PHP
        SEI
        STZ MANAGED
        JSR $66A6
        PHA
        LDA #1
        STA MANAGED
        PLA
        PLP
        BRA TRANSFER_DONE
TRANSFER_READ:
        JSR $66A6
TRANSFER_DONE:
        CMP #0
        BNE TRANSFER_RETURN
        LDA R
        BEQ TRANSFER_RETURN
        LDA R+9
        CMP COUNT
        BNE TRANSFER_SHORT
        LDA #0
TRANSFER_RETURN:
        RTS
TRANSFER_SHORT:
        LDA #7
        RTS
BUF_POINTER:
        STZ BP
        LDA #$64
        STA BP+1
        RTS
READ_BLOCK:
        JSR BUF_POINTER
        LDA #64
        STA COUNT
        LDA #1
        JMP TRANSFER
MOUNT:  STZ ADDR
        STZ ADDR+1
        JSR READ_BLOCK
        BNE MOUNT_RETURN
        LDA BUF+63
        CMP #$A5
        BNE UNFORMATTED
        LDX #59
LAYOUT_CHECK:
        JSR SELECT_LAYOUT
        BNE CORRUPT
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
        BNE MOUNT_RETURN
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
        BRA NEXT_SLOT
SLOT_COMMITTED:
        JSR HEADER_CRC
        BNE CORRUPT
        LDA BUF+3
        ORA BUF+62
        BNE CORRUPT
        LDX #59
SLOT_RESERVED:
        LDA BUF,X
        BNE CORRUPT
        DEX
        CPX #31
        BNE SLOT_RESERVED
        LDA #<BUF+16
        STA TEXT
        LDA #>BUF+16
        STA TEXT+1
        JSR CHECK_NAME_PTR
        BNE CORRUPT
        LDA BUF
        CMP #'S'
        BNE CORRUPT
        LDA BUF+1
        CMP #'P'
        BNE CORRUPT
        LDA BUF+2
        CMP #1
        BNE CORRUPT
        LDA BUF+15
        CMP #2
        BEQ TOMBSTONE_CHECK
        CMP #1
        BNE CORRUPT
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
        BNE SLOT_SCAN
        LDA #0
MOUNT_RETURN:
        RTS
UNFORMATTED:
        LDA #$40
        RTS
CORRUPT:LDA #$41
        RTS
INDEX_REC:
        LDA #$69
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
        BCS NAME_BAD
        LDA END_ADDR
        BNE RANGE_LIMIT
        DEC END_ADDR+1
RANGE_LIMIT:
        DEC END_ADDR
        LDA END_ADDR+1
        CMP $7D0B
        BCC RANGE_ENTRY
        BNE NAME_BAD
        LDA END_ADDR
        CMP $7D0A
        BCC RANGE_ENTRY
        BNE NAME_BAD
RANGE_ENTRY:
        LDA ENTRY
        ORA ENTRY+1
        BEQ RANGE_OK
        LDA ENTRY
        SEC
        SBC LOAD
        LDA ENTRY+1
        SBC LOAD+1
        BCC NAME_BAD
        LDA END_ADDR
        SEC
        SBC ENTRY
        LDA END_ADDR+1
        SBC ENTRY+1
        BCC NAME_BAD
RANGE_OK:
        LDA #0
        RTS
SAVE:   JSR RESTORE_BUF
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
        BCC SAVE_BAD
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
        BRA SAVE_RETURN
DELETE:
        LDA BEST
        CMP #8
        BCS NOT_FOUND
        JSR BEST_REC
        LDY #15
        LDA (REC),Y
        CMP #1
        BNE NOT_FOUND
        STZ LENGTH
        STZ LENGTH+1
        STZ FIRST_PAGE
        JSR NEW_RECORD
        BNE SAVE_RETURN
        LDY #15
        LDA #2
        STA (REC),Y
        JSR PUBLISH
        BRA SAVE_RETURN
NEW_RECORD:
        LDA FREE_SLOT
        CMP #8
        BCS FULL
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
        JMP WRITE_VERIFY_COUNT
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
        BNE CRC_BAD
        INY
        LDA (REC),Y
        CMP CRC+1
        BNE CRC_BAD
        LDA #0
PAYLOAD_RETURN:
        RTS
RESTORE:
        JSR LOAD_RECORD
        JSR RANGE_CHECK
        BNE SAVE_RETURN
        LDA REQUEST
        CMP #3
        BNE RESTORE_BEGIN
        LDA ENTRY
        ORA ENTRY+1
        BEQ NO_RUN
RESTORE_BEGIN:
        JSR RESTORE_BUF
        INC COPYING
        LDA LOAD
        STA BP
        LDA LOAD+1
        STA BP+1
        JSR CRC_INIT
RESTORE_LOOP:
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
        LDA REQUEST
        CMP #3
        BNE RESTORE_OK
        JMP (ENTRY)
RESTORE_OK:
        LDA #0
        JMP FINISH
PARTIAL:LDA #$46
        JMP FINISH
NO_RUN: LDA #$47
        JMP FINISH
; Bounded reclaim: only superseded records. Validate newest live payload first.
; Tombstones remain until FORMAT; no data moves and no automatic collection.
RECLAIM:
        STZ GC_INDEX
        STZ GC_PASS
GC_LOOP:
        LDA GC_INDEX
        STA INDEX
        JSR INDEX_REC
        LDY #3
        LDA (REC),Y
        CMP #$A5
        BNE GC_NEXT
        LDY #16
        LDX #0
GC_NAME:
        LDA (REC),Y
        STA REQUEST+8,X
        INY
        INX
        CPX #16
        BNE GC_NAME
        JSR FIND_NAME
        BNE GC_RETURN
        LDA BEST
        CMP GC_INDEX
        BNE GC_SUPERSEDED
        LDA GC_PASS
        BEQ GC_NEXT
        JSR BEST_REC
        LDY #15
        LDA (REC),Y
        CMP #2
        BEQ GC_CLEAR
        BRA GC_NEXT
GC_SUPERSEDED:
        JSR BEST_REC
        LDY #15
        LDA (REC),Y
        CMP #1
        BNE GC_CLEAR
        JSR VERIFY_PAYLOAD
        BNE GC_RETURN
GC_CLEAR:
        LDA GC_INDEX
        STA INDEX
        JSR SLOT_ADDRESS
        LDA #0
        JSR COMMIT_BYTE
        BNE GC_RETURN
        JSR INDEX_REC
        LDY #3
        LDA #0
        STA (REC),Y
GC_NEXT:
        INC GC_INDEX
        LDA GC_INDEX
        CMP #8
        BNE GC_LOOP
        LDA GC_PASS
        BNE GC_DONE
        INC GC_PASS
        STZ GC_INDEX
        BRA GC_LOOP
GC_DONE:
        LDA #0
GC_RETURN:
        JMP FINISH
FORMAT: LDX #7
FORMAT_KEY:
        LDA REQUEST+24,X
        CMP FORMAT_MAGIC,X
        BNE ARG_BAD
        DEX
        BPL FORMAT_KEY
        JSR FORMAT_GUARD
        BNE FORMAT_RETURN
        ; Invalidate and verify layout first. Never clear directory under a
        ; still-valid old header. Interrupted format requires explicit retry.
        STZ ADDR
        STZ ADDR+1
        LDA #0
        JSR COMMIT_BYTE
        BNE FORMAT_RETURN
        STZ INDEX
FORMAT_SLOTS:
        JSR SLOT_ADDRESS
        LDA #0
        JSR COMMIT_BYTE
        BNE FORMAT_RETURN
        INC INDEX
        LDA INDEX
        CMP #8
        BNE FORMAT_SLOTS
        LDX #59
FORMAT_LAYOUT:
        LDA LAYOUT,X
        STA BUF,X
        DEX
        BPL FORMAT_LAYOUT
        STZ BUF+62
        STZ BUF+63
        JSR SEAL_HEADER
        STZ ADDR
        STZ ADDR+1
        JSR WRITE_VERIFY
        BNE FORMAT_RETURN
        LDA #$A5
        JSR COMMIT_BYTE
FORMAT_RETURN:
        JMP FINISH
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
CONSOLE:
        SEI
        CLD
        LDX #<TITLE
        LDY #>TITLE
        JSR PRINT
        JSR HELP
PROMPT: LDX #<PROMPT_TEXT
        LDY #>PROMPT_TEXT
        JSR PRINT
        JSR READLINE
        BCC PROMPT
        LDX #31
REQUEST_CLEAR:
        STZ REQUEST,X
        DEX
        BPL REQUEST_CLEAR
        LDA LINE+1
        BEQ CON_COMMAND
        LDA LINE
        CMP #'S'
        BEQ CON_COMMAND
        CMP #'R'
        BEQ CON_COMMAND
        CMP #'G'
        BEQ CON_COMMAND
        CMP #'D'
        BNE CON_BAD
CON_COMMAND:
        LDA LINE
        CMP #'Q'
        BEQ QUIT
        CMP #'?'
        BEQ CON_HELP
        CMP #'T'
        BEQ TABLE
        CMP #'C'
        BEQ CON_RECLAIM
        CMP #'F'
        BEQ CON_FORMAT
        CMP #'S'
        BEQ CON_SAVE
        CMP #'R'
        BEQ CON_RESTORE
        CMP #'G'
        BEQ CON_RUN
        CMP #'D'
        BNE CON_BAD
        LDA #4
        BRA CON_NAMED
CON_RUN:LDA #3
        BRA CON_NAMED
CON_RESTORE:
        LDA #2
CON_NAMED:
        STA REQUEST
        JSR PARSE_NAME
        BCC CON_BAD
        LDA LINE,X
        BNE CON_BAD
        BRA CON_DO
CON_SAVE:
        LDA #1
        STA REQUEST
        JSR PARSE_NAME
        BCC CON_BAD
        LDY #2
PARSE_WORDS:
        LDA LINE,X
        CMP #' '
        BNE CON_BAD
        INX
        JSR PARSE_HEX
        BCC CON_BAD
        LDA WORD
        STA REQUEST,Y
        INY
        LDA WORD+1
        STA REQUEST,Y
        INY
        CPY #8
        BNE PARSE_WORDS
        LDA LINE,X
        BNE CON_BAD
CON_DO: JSR OPERATION
CON_RESULT:
        PHA
        LDX #<RESULT_TEXT
        LDY #>RESULT_TEXT
        JSR PRINT
        PLA
        JSR HEX
        JSR NL
        JMP PROMPT
CON_BAD:LDA #$44
        BRA CON_RESULT
CON_RECLAIM:
        LDA #5
        STA REQUEST
        BRA CON_DO
CON_FORMAT:
        LDX #<CONFIRM_TEXT
        LDY #>CONFIRM_TEXT
        JSR PRINT
        JSR READLINE
        BCC PROMPT
        LDX #11
CONFIRM_CHECK:
        LDA LINE,X
        CMP CONFIRM_MAGIC,X
        BNE CON_BAD
        DEX
        BPL CONFIRM_CHECK
        LDX #7
CON_FORMAT_KEY:
        LDA FORMAT_MAGIC,X
        STA REQUEST+24,X
        DEX
        BPL CON_FORMAT_KEY
        LDA #6
        STA REQUEST
        BRA CON_DO
CON_HELP:
        JSR HELP
        JMP PROMPT
QUIT:   JMP $7E67
HELP:   LDX #<HELP_TEXT
        LDY #>HELP_TEXT
        JMP PRINT
TABLE:  JSR OPERATION
        BNE CON_RESULT
        STZ GC_INDEX
TABLE_LOOP:
        LDA GC_INDEX
        STA INDEX
        JSR INDEX_REC
        LDY #3
        LDA (REC),Y
        CMP #$A5
        BNE TABLE_NEXT
        LDY #15
        LDA (REC),Y
        CMP #1
        BNE TABLE_NEXT
        LDY #16
        LDX #0
TABLE_NAME_COPY:
        LDA (REC),Y
        STA REQUEST+8,X
        INY
        INX
        CPX #16
        BNE TABLE_NAME_COPY
        JSR FIND_NAME
        BNE CON_RESULT
        LDA BEST
        CMP GC_INDEX
        BNE TABLE_NEXT
        JSR BEST_REC
        LDY #16
TABLE_NAME:
        LDA (REC),Y
        BEQ TABLE_FIELDS
        JSR PUTC
        INY
        CPY #32
        BNE TABLE_NAME
TABLE_FIELDS:
        LDA #' '
        JSR PUTC
        LDY #5
        LDA (REC),Y
        JSR HEX
        DEY
        LDA (REC),Y
        JSR HEX
        LDA #' '
        JSR PUTC
        LDY #7
        LDA (REC),Y
        JSR HEX
        DEY
        LDA (REC),Y
        JSR HEX
        JSR NL
TABLE_NEXT:
        INC GC_INDEX
        LDA GC_INDEX
        CMP #8
        BNE TABLE_LOOP
        LDX #<FREE_TEXT
        LDY #>FREE_TEXT
        JSR PRINT
        JSR FREE_PAGES
        JSR HEX
        LDA #0
        JSR HEX
        JSR NL
        JMP PROMPT
PARSE_NAME:
        LDX #1
        LDA LINE,X
        CMP #' '
        BNE PARSE_FAIL
        INX
        LDY #0
PARSE_NAME_LOOP:
        LDA LINE,X
        BEQ PARSE_NAME_DONE
        CMP #' '
        BEQ PARSE_NAME_DONE
        CPY #16
        BCS PARSE_FAIL
        STA REQUEST+8,Y
        INY
        INX
        BRA PARSE_NAME_LOOP
PARSE_NAME_DONE:
        CPY #0
        BEQ PARSE_FAIL
        SEC
        RTS
PARSE_HEX:
        STZ WORD
        STZ WORD+1
        LDA #4
        STA DIGITS
PARSE_HEX_LOOP:
        LDA LINE,X
        CMP #'0'
        BCC PARSE_FAIL
        CMP #'9'+1
        BCC PARSE_DIGIT
        CMP #'A'
        BCC PARSE_FAIL
        CMP #'F'+1
        BCS PARSE_FAIL
        SEC
        SBC #7
PARSE_DIGIT:
        SEC
        SBC #'0'
        PHX
        LDX #4
PARSE_SHIFT:
        ASL WORD
        ROL WORD+1
        DEX
        BNE PARSE_SHIFT
        PLX
        ORA WORD
        STA WORD
        INX
        DEC DIGITS
        BNE PARSE_HEX_LOOP
        SEC
        RTS
PARSE_FAIL:
        CLC
        RTS
READLINE:
        STZ LINE_LENGTH
        STZ OVERFLOW
LINE_WAIT:
        JSR GETC
        CMP #3
        BEQ LINE_CANCEL
        CMP #$1B
        BEQ LINE_CANCEL
        CMP #10
        BEQ LINE_WAIT
        CMP #13
        BEQ LINE_DONE
        CMP #8
        BEQ LINE_BACK
        CMP #$7F
        BEQ LINE_BACK
        CMP #$20
        BCC LINE_WAIT
        CMP #'a'
        BCC LINE_CHAR
        CMP #'z'+1
        BCS LINE_CHAR
        AND #$DF
LINE_CHAR:
        LDX LINE_LENGTH
        CPX #39
        BCS LINE_FULL
        STA LINE,X
        INC LINE_LENGTH
        JSR PUTC
        BRA LINE_WAIT
LINE_FULL:
        LDA #1
        STA OVERFLOW
        BRA LINE_WAIT
LINE_BACK:
        LDA LINE_LENGTH
        BEQ LINE_WAIT
        DEC LINE_LENGTH
        LDA #8
        JSR PUTC
        LDA #' '
        JSR PUTC
        LDA #8
        JSR PUTC
        BRA LINE_WAIT
LINE_DONE:
        LDX LINE_LENGTH
        STZ LINE,X
        JSR NL
        LDA OVERFLOW
        BNE LINE_CANCEL
        SEC
        RTS
LINE_CANCEL:
        JSR NL
        CLC
        RTS
PRINT:  STX TEXT
        STY TEXT+1
        LDY #0
PRINT_LOOP:
        LDA (TEXT),Y
        BEQ PRINT_DONE
        JSR PUTC
        INY
        BRA PRINT_LOOP
PRINT_DONE:
        RTS
SV_MAGIC DB "SV",1
SM_MAGIC DB "SM",1,1
MASKS DB 1,2,4,8,16,32,64,128
; SS v1: 8 x 64 directory at 0040; data 0800-FFFF; workspace 10000-1FFDF.
LAYOUT DB "SS",1,8,8,0,1,0
        DS 52
FORMAT_MAGIC DB "FORMAT!!"
CONFIRM_MAGIC DB "FORMAT SRAM",0
TITLE DB "SRAM 1.1",13,10,0
PROMPT_TEXT DB "SRAM> ",0
HELP_TEXT DB "S name start end entry; R/G/D name; T C F Q",13,10,0
CONFIRM_TEXT DB "Type FORMAT SRAM: ",0
RESULT_TEXT DB "SRAM: ",0
FREE_TEXT DB "Free bytes: $",0
ADDR DS 2
BP DS 2
LEFT DS 2
LOAD DS 2
LENGTH DS 2
END_ADDR DS 2
ENTRY DS 2
CRC DS 2
SEQUENCE DS 2
BEST_SEQ DS 2
WORD DS 2
COUNT DB 0
STATUS DB 0
COPYING DB 0
INDEX DB 0
FREE_SLOT DB 0
BEST DB 0
USED DB 0
PAGE DB 0
PAGES DB 0
MASK DB 0
RUN_LENGTH DB 0
FIRST_PAGE DB 0
PAD DB 0
GC_INDEX DB 0
GC_PASS DB 0
DIGITS DB 0
LINE_LENGTH DB 0
OVERFLOW DB 0
AMBIG DB 0
LIMIT DB 0
APP_END:
        ENDMOD
        END
