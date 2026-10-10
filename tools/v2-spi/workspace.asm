; Optional application library, not additional resident RAM. W65C02S/816E.
        MODULE WORKSPACE
        XDEF START
        XDEF APP_END
P EQU $D0
Q EQU $D2
C EQU $D4
R EQU $6650
RESET_LATCH EQU $66AF
MANAGED EQU $66AE
PUTC EQU $7E6D
GETC EQU $7E70
HEX EQU $7E7C
NL EQU $7E7F
        CODE
START:  JMP CONSOLE
        JMP API
        DB "WK",1,1
API:    SEI
        CLD
        STA C
        STX C+1
        LDA #32
        STA N
        JSR CPU_RANGE
        BNE API_RETURN
        LDY #31
COPY_REQUEST:
        LDA (C),Y
        STA REQ,Y
        DEY
        BPL COPY_REQUEST
        JSR OPERATION
        PHA
        LDY #31
COPY_RESULT:
        LDA REQ,Y
        STA (C),Y
        DEY
        BPL COPY_RESULT
        PLA
API_RETURN:
        CMP #0
        BNE API_ERROR
        SEC
        RTS
API_ERROR:
        CLC
        RTS
OPERATION:
        STZ CHECKING
        JSR DISCOVER
        BNE OP_RETURN
        LDA REQ+1
        BNE BAD_ARG
        LDA REQ
        CMP #9
        BCS BAD_ARG
        CMP #6
        BEQ FORMAT
        CMP #7
        BEQ UPGRADE
        JSR LOAD_LAYOUT
        BNE OP_RETURN
        LDA REQ
        BEQ QUERY
        LDA LEGACY
        BNE NEED_UPGRADE
        LDA REQ
        CMP #8
        BEQ REPAIR
        JSR SESSION_LOAD
        BNE OP_RETURN
        LDA RESET_LATCH
        BNE SESSION_READY
        JSR NEW_EPOCH
        BNE OP_RETURN
SESSION_READY:
        JSR LOAD_CLAIMS
        BNE OP_RETURN
        JSR PROGRAM_CHECK
        BNE OP_RETURN
        LDA REQ
        CMP #5
        BEQ RESIZE
        LDA REQ+2
        ORA REQ+3
        BEQ BAD_ARG
        LDA REQ
        CMP #1
        BEQ CLAIM
        JSR HANDLE
        BNE OP_RETURN
        LDA REQ
        CMP #2
        BEQ RELEASE
        JMP IO
OP_RETURN:
        RTS
BAD_ARG:LDA #$44
        RTS
BAD_META:
        LDA #$41
        RTS
NEED_UPGRADE:
        LDA #$49
        RTS
STALE:  LDA #$4B
        RTS
FULL:   LDA #$43
        RTS
VERIFY_BAD:
        LDA #$45
        RTS
EXHAUSTED:
        LDA #$48
        RTS
DISCOVER:
        LDX #2
DISCOVER_SV:
        LDA $7D04,X
        CMP SV_MAGIC,X
        BNE ABSENT
        DEX
        BPL DISCOVER_SV
        LDA $7D07
        AND #8
        BEQ ABSENT
        LDA $7D08
        BNE ABSENT
        LDA $7D09
        CMP #$65
        BNE ABSENT
        LDX #3
DISCOVER_SM:
        LDA $66A2,X
        CMP SM_MAGIC,X
        BNE ABSENT
        DEX
        BPL DISCOVER_SM
        STZ N
        LDA #0
        JMP TRANSFER
ABSENT: LDA #$80
        RTS
BUF_PTR:
        LDA #<BUF
        STA BP
        LDA #>BUF
        STA BP+1
        RTS
TRANSFER:
        PHA
        LDX #15
REQUEST_ZERO:
        STZ R,X
        DEX
        BPL REQUEST_ZERO
        LDX #2
REQUEST_ADDR:
        LDA ADDR,X
        STA R+2,X
        DEX
        BPL REQUEST_ADDR
        LDA BP
        STA R+5
        LDA BP+1
        STA R+6
        LDA N
        STA R+7
        PLA
        STA R
        CMP #2
        BNE TRAN_READ
        STZ MANAGED
        JSR $66A6
        PHA
        LDA #1
        STA MANAGED
        PLA
        BRA TRAN_RESULT
TRAN_READ:
        JSR $66A6
TRAN_RESULT:
        CMP #0
        BNE TRAN_RETURN
        LDA R
        BEQ TRAN_RETURN
        LDA R+9
        CMP N
        BNE TRAN_SHORT
        LDA #0
TRAN_RETURN:
        RTS
TRAN_SHORT:
        LDA #7
        RTS
READ64: LDA #64
        BRA READ_N
READ32: LDA #32
READ_N: STA N
        JSR BUF_PTR
        LDA #1
        JMP TRANSFER
WRITE_VERIFY:
        JSR BUF_PTR
        LDX N
        DEX
EXPECT_COPY:
        LDA BUF,X
        STA EXPECT,X
        DEX
        BPL EXPECT_COPY
        LDA #2
        JSR TRANSFER
        BNE WRITE_RETURN
        LDA #1
        JSR TRANSFER
        BNE WRITE_RETURN
        LDX N
        DEX
EXPECT_CHECK:
        LDA BUF,X
        CMP EXPECT,X
        BNE VERIFY_BAD
        DEX
        BPL EXPECT_CHECK
        LDA #0
WRITE_RETURN:
        RTS
; Publish a 32/64-byte packet. Invalidate/verify old final marker first.
PUBLISH:
        LDA N
        STA PACKET_N
        LDA #0
        JSR MARKER
        BNE PUB_RETURN
        LDX PACKET_N
        DEX
PUB_RESTORE:
        LDA EXPECT_PACKET,X
        STA BUF,X
        DEX
        BPL PUB_RESTORE
        LDA PACKET_N
        STA N
        JSR WRITE_VERIFY
        BNE PUB_RETURN
        LDA #$A5
        JSR MARKER
PUB_RETURN:
        RTS
SAVE_PACKET:
        LDX N
        DEX
PACKET_COPY:
        LDA BUF,X
        STA EXPECT_PACKET,X
        DEX
        BPL PACKET_COPY
        RTS
MARKER:
        PHA
        LDX #2
MARK_SAVE:
        LDA ADDR,X
        STA SAVE_ADDR,X
        DEX
        BPL MARK_SAVE
        LDA PACKET_N
        DEC A
        CLC
        ADC ADDR
        STA ADDR
        BCC MARK_ADDR
        INC ADDR+1
        BNE MARK_ADDR
        INC ADDR+2
MARK_ADDR:
        PLA
        STA BUF
        LDA #1
        STA N
        JSR WRITE_VERIFY
        PHA
        LDX #2
MARK_RESTORE:
        LDA SAVE_ADDR,X
        STA ADDR,X
        DEX
        BPL MARK_RESTORE
        PLA
        CMP #0
        RTS
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
        LDA N
        SEC
        SBC #2
        BRA CRC_BUFFER
SEAL:   LDA N
        SEC
        SBC #4
        JSR CRC_BUFFER
        LDA CRC+1
        STA BUF,Y
        INY
        LDA CRC
        STA BUF,Y
        RTS
CRC_BUFFER:
        STA CRC_N
        JSR CRC_INIT
        LDY #0
CRC_LOOP:
        LDA BUF,Y
        JSR CRC_BYTE
        INY
        CPY CRC_N
        BNE CRC_LOOP
        LDA CRC
        ORA CRC+1
        RTS
ZERO_BUF:
        LDX #63
ZERO_LOOP:
        STZ BUF,X
        DEX
        BPL ZERO_LOOP
        RTS
ZERO_ADDR:
        STZ ADDR
        STZ ADDR+1
        STZ ADDR+2
        RTS
LOAD_LAYOUT:
        STZ FALLBACK
        JSR ZERO_ADDR
        JSR READ64
        BNE LAYOUT_RETURN
        LDA BUF+63
        CMP #$A5
        BEQ PRIMARY_FOUND
        LDA #$40
        STA ADDR
        LDA #2
        STA ADDR+1
        JSR READ64
        BNE LAYOUT_RETURN
        INC FALLBACK
PRIMARY_FOUND:
        LDA BUF+63
        CMP #$A5
        BNE UNFORMATTED
        JSR HEADER_CRC
        BNE BAD_META
        LDA BUF+7
        ORA BUF+62
        BNE BAD_META
        LDX #59
LAYOUT_RESERVED:
        LDA BUF,X
        BNE BAD_META
        DEX
        CPX #11
        BNE LAYOUT_RESERVED
        LDA BUF
        CMP #'S'
        BNE BAD_META
        LDA BUF+1
        CMP #'S'
        BNE BAD_META
        LDA BUF+3
        CMP #8
        BNE BAD_META
        LDA BUF+4
        CMP #8
        BNE BAD_META
        LDA BUF+2
        CMP #1
        BEQ LEGACY_LAYOUT
        CMP #2
        BNE BAD_META
        STZ LEGACY
        LDA BUF+8
        ORA BUF+9
        ORA BUF+10
        ORA BUF+11
        BEQ BAD_META
        BRA LAYOUT_LIMIT
LEGACY_LAYOUT:
        LDA BUF+8
        ORA BUF+9
        ORA BUF+10
        ORA BUF+11
        BNE BAD_META
        LDA FALLBACK
        BNE BAD_META
        LDA #1
        STA LEGACY
        LDA BUF+5
        BNE BAD_META
        LDA BUF+6
        CMP #1
        BNE BAD_META
LAYOUT_LIMIT:
        LDA BUF+5
        AND #$3F
        BNE BAD_META
        LDA BUF+6
        BEQ LIMIT_SMALL
        CMP #1
        BNE BAD_META
        LDA BUF+5
        BNE BAD_META
        LDA #4
        BRA LIMIT_SET
LIMIT_SMALL:
        LDA BUF+5
        BEQ BAD_META
        LSR A
        LSR A
        LSR A
        LSR A
        LSR A
        LSR A
LIMIT_SET:
        STA UNITS
        LDX #63
LAYOUT_COPY:
        LDA BUF,X
        STA LAYOUT,X
        DEX
        BPL LAYOUT_COPY
        LDA #0
LAYOUT_RETURN:
        RTS
UNFORMATTED:
        LDA #$40
        RTS
QUERY:  STZ REQ+12
        LDA LAYOUT+5
        STA REQ+13
        LDA LAYOUT+6
        STA REQ+14
        LDA #$E0
        STA REQ+18
        SEC
        LDA #$FF
        SBC LAYOUT+5
        STA REQ+19
        LDA #1
        SBC LAYOUT+6
        STA REQ+20
        LDA UNITS
        STA REQ+21
        LDA LEGACY
        STA REQ+22
        LDA FALLBACK
        STA REQ+23
        LDA #0
        RTS
SESSION_LOAD:
        STZ SESSION_VALID
        LDA #$80
        STA ADDR
        LDA #2
        STA ADDR+1
        STZ ADDR+2
SESSION_SCAN:
        JSR READ64
        BNE SESSION_RETURN
        LDA BUF+63
        CMP #$A5
        BNE SESSION_NEXT
        JSR HEADER_CRC
        BNE BAD_META
        LDX #2
SESSION_MAGIC:
        LDA BUF,X
        CMP WS_MAGIC,X
        BNE BAD_META
        DEX
        BPL SESSION_MAGIC
        LDA BUF+3
        ORA BUF+62
        BNE BAD_META
        LDX #59
SESSION_RESERVED:
        LDA BUF,X
        BNE BAD_META
        DEX
        CPX #13
        BNE SESSION_RESERVED
        LDA BUF+4
        ORA BUF+5
        ORA BUF+6
        ORA BUF+7
        BEQ BAD_META
        LDA BUF+8
        ORA BUF+9
        ORA BUF+10
        ORA BUF+11
        BEQ BAD_META
        LDA SESSION_VALID
        BEQ SESSION_SELECT
        LDX #3
SESSION_COMPARE:
        LDA BUF+4,X
        CMP SESSION+4,X
        BCC SESSION_NEXT
        BNE SESSION_SELECT
        DEX
        BPL SESSION_COMPARE
        JMP BAD_META
SESSION_SELECT:
        INC SESSION_VALID
        LDA ADDR
        STA SESSION_ADDR
        LDX #63
SESSION_COPY:
        LDA BUF,X
        STA SESSION,X
        DEX
        BPL SESSION_COPY
SESSION_NEXT:
        LDA ADDR
        CMP #$C0
        BEQ SESSION_END
        LDA #$C0
        STA ADDR
        BRA SESSION_SCAN
SESSION_END:
        LDA SESSION_VALID
        BEQ BAD_META
        LDA #0
SESSION_RETURN:
        RTS
INC_REVISION:
        LDX #0
REV_INCREMENT:
        INC SESSION+4,X
        BNE REV_OK
        INX
        CPX #4
        BNE REV_INCREMENT
        JMP EXHAUSTED
REV_OK: LDA #0
        RTS
NEW_EPOCH:
        LDX #0
EPOCH_INCREMENT:
        INC SESSION+8,X
        BNE EPOCH_OK
        INX
        CPX #4
        BNE EPOCH_INCREMENT
        JMP EXHAUSTED
EPOCH_OK:
        STZ SESSION+12
        STZ SESSION+13
        JSR SESSION_COMMIT
        BNE EPOCH_RETURN
        LDA #1
        STA RESET_LATCH
        LDA #0
EPOCH_RETURN:
        RTS
SESSION_COMMIT:
        JSR INC_REVISION
        BNE EPOCH_RETURN
        LDX #63
SESSION_PREP:
        LDA SESSION,X
        STA BUF,X
        DEX
        BPL SESSION_PREP
        STZ BUF+63
        LDA #64
        STA N
        JSR SEAL
        JSR SAVE_PACKET
        LDA SESSION_ADDR
        EOR #$40
        STA ADDR
        STA SESSION_ADDR
        LDA #2
        STA ADDR+1
        STZ ADDR+2
        JMP PUBLISH
LOAD_CLAIMS:
        LDA #4
        STA FREE_SLOT
        STZ SLOT
CLAIMS_SCAN:
        JSR CLAIM_ADDRESS
        JSR READ32
        BNE CLAIMS_RETURN
        LDA BUF+31
        CMP #$A5
        BNE CLAIMS_FREE
        JSR HEADER_CRC
        BNE BAD_META
        LDX #2
CLAIM_MAGIC:
        LDA BUF,X
        CMP WC_MAGIC,X
        BNE BAD_META
        DEX
        BPL CLAIM_MAGIC
        LDA BUF+3
        ORA BUF+15
        ORA BUF+19
        ORA BUF+30
        BNE BAD_META
        LDX #27
CLAIM_RESERVED:
        LDA BUF,X
        BNE BAD_META
        DEX
        CPX #19
        BNE CLAIM_RESERVED
        LDX #3
CLAIM_EPOCH:
        LDA BUF+8,X
        CMP SESSION+8,X
        BNE CLAIMS_FREE
        DEX
        BPL CLAIM_EPOCH
        LDA BUF+4
        ORA BUF+5
        BEQ BAD_META
        LDA BUF+6
        ORA BUF+7
        BEQ BAD_META
        LDA BUF+12
        BNE BAD_META
        LDA BUF+16
        ORA BUF+17
        ORA BUF+18
        BEQ BAD_META
        LDX #2
CLAIM_SPAN:
        LDA BUF+12,X
        STA POS,X
        LDA BUF+16,X
        STA SIZE,X
        DEX
        BPL CLAIM_SPAN
        JSR SPAN_END
        BNE BAD_META
        LDA POS+2
        CMP LAYOUT+6
        BCC BAD_META
        BNE CLAIMS_CACHE
        LDA POS+1
        CMP LAYOUT+5
        BCC BAD_META
        BRA CLAIMS_CACHE
CLAIMS_FREE:
        STZ BUF+31
        LDA SLOT
        STA FREE_SLOT
CLAIMS_CACHE:
        JSR SLOT_POINTER
        LDY #31
CLAIM_CACHE_COPY:
        LDA BUF,Y
        STA (P),Y
        DEY
        BPL CLAIM_CACHE_COPY
        INC SLOT
        LDA SLOT
        CMP #4
        BNE CLAIMS_SCAN
        JSR CHECK_OVERLAPS
CLAIMS_RETURN:
        RTS
CHECK_OVERLAPS:
        LDA #1
        STA CHECKING
        STZ CHECK_SLOT
CHECK_OUTER:
        LDA CHECK_SLOT
        STA SLOT
        JSR SLOT_POINTER
        LDY #31
        LDA (P),Y
        CMP #$A5
        BNE CHECK_NEXT
        LDY #12
        LDX #0
CHECK_START_COPY:
        LDA (P),Y
        STA POS,X
        INY
        INX
        CPX #3
        BNE CHECK_START_COPY
        LDY #16
        LDX #0
CHECK_SIZE_COPY:
        LDA (P),Y
        STA SIZE,X
        INY
        INX
        CPX #3
        BNE CHECK_SIZE_COPY
        JSR ALLOC_RESTART
        BNE CLAIMS_RETURN
CHECK_NEXT:
        INC CHECK_SLOT
        LDA CHECK_SLOT
        CMP #4
        BNE CHECK_OUTER
        STZ CHECKING
        LDA #0
        RTS
CLAIM_ADDRESS:
        LDA SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA ADDR
        LDA #3
        STA ADDR+1
        STZ ADDR+2
        RTS
SLOT_POINTER:
        LDA SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #<CLAIMS
        STA P
        LDA #>CLAIMS
        ADC #0
        STA P+1
        RTS
SPAN_END:
        LDA #3
        STA ARITH_N
        CLC
        LDX #0
SPAN_ADD:
        LDA POS,X
        ADC SIZE,X
        STA END_POS,X
        INX
        DEC ARITH_N
        BNE SPAN_ADD
        BCS BAD_ARG
        LDX #2
SPAN_BOUND:
        LDA END_POS,X
        CMP MAX_END,X
        BCC SPAN_OK
        BNE BAD_ARG
        DEX
        BPL SPAN_BOUND
SPAN_OK:LDA #0
        RTS
CLAIM:  LDA FREE_SLOT
        CMP #4
        BCS FULL
        LDX #2
CLAIM_SIZE:
        LDA REQ+18,X
        STA SIZE,X
        DEX
        BPL CLAIM_SIZE
        LDA SIZE
        ORA SIZE+1
        ORA SIZE+2
        BEQ BAD_ARG
        STZ POS
        LDA LAYOUT+5
        STA POS+1
        LDA LAYOUT+6
        STA POS+2
ALLOC_RESTART:
        JSR SPAN_END
        BNE FULL
        STZ SLOT
ALLOC_SCAN:
        LDA CHECKING
        BEQ ALLOC_CHECK
        LDA SLOT
        CMP CHECK_SLOT
        BEQ ALLOC_NEXT
ALLOC_CHECK:
        JSR SLOT_POINTER
        LDY #31
        LDA (P),Y
        CMP #$A5
        BNE ALLOC_NEXT
        ; candidate end <= claim start: no overlap.
        LDY #14
        LDX #2
ALLOC_BEFORE:
        LDA END_POS,X
        CMP (P),Y
        BCC ALLOC_NEXT
        BNE ALLOC_AFTER_START
        DEY
        DEX
        BPL ALLOC_BEFORE
        BRA ALLOC_NEXT
ALLOC_AFTER_START:
        ; candidate start >= claim end: no overlap.
        LDY #12
        CLC
        LDX #0
ALLOC_OLD_END:
        LDA (P),Y
        STA OLD_END,X
        INY
        INX
        CPX #3
        BNE ALLOC_OLD_END
        LDY #16
        LDA #3
        STA ARITH_N
        CLC
        LDX #0
ALLOC_OLD_ADD:
        LDA (P),Y
        ADC OLD_END,X
        STA OLD_END,X
        INY
        INX
        DEC ARITH_N
        BNE ALLOC_OLD_ADD
        LDX #2
ALLOC_AFTER:
        LDA POS,X
        CMP OLD_END,X
        BCC ALLOC_COLLISION
        BNE ALLOC_NEXT
        DEX
        BPL ALLOC_AFTER
        BRA ALLOC_NEXT
ALLOC_COLLISION:
        LDA CHECKING
        BNE BAD_META
        STZ POS
        LDA OLD_END
        CMP #1
        LDA OLD_END+1
        ADC #0
        STA POS+1
        LDA OLD_END+2
        ADC #0
        STA POS+2
        BRA ALLOC_RESTART
ALLOC_NEXT:
        INC SLOT
        LDA SLOT
        CMP #4
        BNE ALLOC_SCAN
        LDA CHECKING
        BEQ ALLOC_PUBLISH
        LDA #0
        RTS
ALLOC_PUBLISH:
        LDA SESSION+12
        AND SESSION+13
        CMP #$FF
        BEQ EXHAUSTED
        INC SESSION+12
        BNE CLAIM_TICKET
        INC SESSION+13
CLAIM_TICKET:
        JSR SESSION_COMMIT
        BNE CLAIMS_RETURN
        JSR ZERO_BUF
        LDX #2
CLAIM_NEW_MAGIC:
        LDA WC_MAGIC,X
        STA BUF,X
        DEX
        BPL CLAIM_NEW_MAGIC
        LDX #1
CLAIM_OWNER:
        LDA REQ+2,X
        STA BUF+4,X
        LDA SESSION+12,X
        STA BUF+6,X
        DEX
        BPL CLAIM_OWNER
        LDX #3
CLAIM_NEW_EPOCH:
        LDA SESSION+8,X
        STA BUF+8,X
        STA REQ+6,X
        DEX
        BPL CLAIM_NEW_EPOCH
        LDX #2
CLAIM_NEW_SPAN:
        LDA POS,X
        STA BUF+12,X
        LDA SIZE,X
        STA BUF+16,X
        STZ REQ+12,X
        DEX
        BPL CLAIM_NEW_SPAN
        LDA FREE_SLOT
        STA SLOT
        STA REQ+4
        STZ REQ+5
        LDA SESSION+12
        STA REQ+10
        LDA SESSION+13
        STA REQ+11
        LDA #32
        STA N
        JSR SEAL
        JSR SAVE_PACKET
        JSR CLAIM_ADDRESS
        JMP PUBLISH
HANDLE:
        LDA REQ+5
        BNE STALE
        LDA REQ+4
        CMP #4
        BCS STALE
        STA SLOT
        JSR SLOT_POINTER
        LDY #31
        LDA (P),Y
        CMP #$A5
        BNE STALE
        LDY #4
        LDX #2
HANDLE_OWNER:
        LDA (P),Y
        CMP REQ,X
        BNE STALE
        INY
        INX
        CPX #4
        BNE HANDLE_OWNER
        LDY #6
        LDX #10
HANDLE_TICKET:
        LDA (P),Y
        CMP REQ,X
        BNE STALE
        INY
        INX
        CPX #12
        BNE HANDLE_TICKET
        LDY #8
        LDX #6
HANDLE_EPOCH:
        LDA (P),Y
        CMP REQ,X
        BNE STALE
        INY
        INX
        CPX #10
        BNE HANDLE_EPOCH
        LDA #0
        RTS
RELEASE:
        JSR CLAIM_ADDRESS
        LDA #32
        STA PACKET_N
        LDA #0
        JMP MARKER
IO:     LDA REQ+15
        BEQ BAD_ARG
        CMP #65
        BCS BAD_ARG
        STA N
        LDA #3
        STA ARITH_N
        CLC
        LDX #0
IO_OFFSET_END:
        LDA REQ+12,X
        ADC N
        STA END_POS,X
        INX
        LDA #0
        STA N
        DEC ARITH_N
        BNE IO_OFFSET_END
        BCS BAD_ARG
        LDY #18
        LDX #2
IO_BOUND:
        LDA END_POS,X
        CMP (P),Y
        BCC IO_ADDRESS
        BNE BAD_ARG
        DEY
        DEX
        BPL IO_BOUND
IO_ADDRESS:
        LDY #12
        LDA #3
        STA ARITH_N
        CLC
        LDX #0
IO_ADDRESS_ADD:
        LDA (P),Y
        ADC REQ+12,X
        STA ADDR,X
        INY
        INX
        DEC ARITH_N
        BNE IO_ADDRESS_ADD
        LDA REQ+15
        STA N
        LDA REQ+16
        STA BP
        LDA REQ+17
        STA BP+1
        LDA BP
        PHA
        LDA BP+1
        PHA
        LDA C
        STA SAVE_C
        LDA C+1
        STA SAVE_C+1
        LDA BP
        STA C
        LDA BP+1
        STA C+1
        JSR CPU_RANGE
        STA ERROR
        PLA
        STA BP+1
        PLA
        STA BP
        LDA SAVE_C
        STA C
        LDA SAVE_C+1
        STA C+1
        LDA ERROR
        BNE OP_RETURN
        ; READ cannot overwrite the caller's request/result block.
        LDA REQ
        CMP #3
        BNE IO_TRANSFER
        LDA BP
        CLC
        ADC N
        STA TEMP
        LDA BP+1
        ADC #0
        CMP C+1
        BCC IO_TRANSFER
        BNE IO_READ_AFTER
        LDA TEMP
        CMP C
        BCC IO_TRANSFER
        BEQ IO_TRANSFER
IO_READ_AFTER:
        LDA C
        CLC
        ADC #32
        STA TEMP
        LDA C+1
        ADC #0
        CMP BP+1
        BCC IO_TRANSFER
        BNE BAD_ARG
        LDA TEMP
        CMP BP
        BCC IO_TRANSFER
        BNE BAD_ARG
IO_TRANSFER:
        LDA REQ
        CMP #4
        BNE IO_READ
        LDA BP
        STA Q
        LDA BP+1
        STA Q+1
        LDY #0
IO_STAGE:
        LDA (Q),Y
        STA BUF,Y
        INY
        CPY N
        BNE IO_STAGE
        JSR WRITE_VERIFY
        BRA IO_RESULT
IO_READ:
        LDA #1
        JSR TRANSFER
IO_RESULT:
        PHA
        LDA R+9
        STA REQ+22
        LDA R+10
        STA REQ+23
        PLA
        CMP #0
        RTS
CPU_RANGE:
        LDA C+1
        CMP #2
        BCC BAD_ARG
        CLC
        LDA C
        ADC N
        STA TEMP
        LDA C+1
        ADC #0
        STA TEMP+1
        BCS BAD_ARG
        CMP #$65
        BCC CPU_LIBRARY
        BNE BAD_ARG
        LDA TEMP
        BNE BAD_ARG
CPU_LIBRARY:
        LDA TEMP+1
        CMP #$40
        BCC CPU_OK
        BNE CPU_AFTER
        LDA TEMP
        BEQ CPU_OK
CPU_AFTER:
        LDA C+1
        CMP #>APP_END
        BCC BAD_ARG
        BNE CPU_OK
        LDA C
        CMP #<APP_END
        BCC BAD_ARG
CPU_OK: LDA #0
        RTS
PROGRAM_CHECK:
        STZ PROG_SLOT
PROG_SCAN:
        LDA PROG_SLOT
        INC A
        LSR A
        LSR A
        STA ADDR+1
        LDA PROG_SLOT
        INC A
        AND #3
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA ADDR
        STZ ADDR+2
        JSR READ64
        BNE PROG_RETURN
        LDA BUF+63
        CMP #$A5
        BNE PROG_NEXT
        JSR HEADER_CRC
        BNE BAD_META
        LDX #2
PROG_MAGIC:
        LDA BUF,X
        CMP SP_MAGIC,X
        BNE BAD_META
        DEX
        BPL PROG_MAGIC
        LDA BUF+15
        CMP #2
        BEQ PROG_TOMBSTONE
        CMP #1
        BNE BAD_META
        LDA BUF+6
        ORA BUF+7
        BEQ BAD_META
        LDA BUF+14
        CMP #8
        BCC BAD_META
        LDA BUF+6
        CMP #1
        LDA BUF+7
        ADC BUF+14
        STA PAGE_END
        LDA #0
        ADC #0
        STA PAGE_END+1
        CMP LAYOUT+6
        BCC PROG_NEXT
        BNE BAD_META
        LDA PAGE_END
        CMP LAYOUT+5
        BCC PROG_NEXT
        BEQ PROG_NEXT
        JMP BAD_META
PROG_TOMBSTONE:
        LDA BUF+6
        ORA BUF+7
        ORA BUF+14
        BNE BAD_META
PROG_NEXT:
        INC PROG_SLOT
        LDA PROG_SLOT
        CMP #8
        BNE PROG_SCAN
        LDA #0
PROG_RETURN:
        RTS
RESIZE: LDX #7
RESIZE_KEY:
        LDA REQ+24,X
        CMP RESIZE_MAGIC,X
        BNE BAD_ARG
        DEX
        BPL RESIZE_KEY
        LDA REQ+21
        BEQ BAD_ARG
        CMP #5
        BCS BAD_ARG
        CMP UNITS
        BEQ QUERY
        STA NEW_UNITS
        ; Check prospective boundary against all saved records and claims.
        LDA LAYOUT+5
        PHA
        LDA LAYOUT+6
        PHA
        JSR NEW_BOUNDARY
        JSR PROGRAM_CHECK
        STA ERROR
        STZ SLOT
RESIZE_CLAIMS:
        LDA ERROR
        BNE RESIZE_RESTORE
        JSR SLOT_POINTER
        LDY #31
        LDA (P),Y
        CMP #$A5
        BNE RESIZE_NEXT
        LDY #14
        LDA (P),Y
        CMP LAYOUT+6
        BCC RESIZE_CONFLICT
        BNE RESIZE_NEXT
        DEY
        LDA (P),Y
        CMP LAYOUT+5
        BCC RESIZE_CONFLICT
RESIZE_NEXT:
        INC SLOT
        LDA SLOT
        CMP #4
        BNE RESIZE_CLAIMS
        BRA RESIZE_RESTORE
RESIZE_CONFLICT:
        LDA #$4A
        STA ERROR
RESIZE_RESTORE:
        PLA
        STA LAYOUT+6
        PLA
        STA LAYOUT+5
        LDA ERROR
        BNE OP_RETURN
        JSR REPAIR_PRIMARY
        BNE OP_RETURN
        JSR NEW_BOUNDARY
        JSR LAYOUT_INCREMENT
        BNE OP_RETURN
        JSR LAYOUT_UPDATE
        BNE OP_RETURN
        LDA NEW_UNITS
        STA UNITS
        JMP QUERY
NEW_BOUNDARY:
        LDA NEW_UNITS
        LSR A
        LSR A
        STA LAYOUT+6
        LDA NEW_UNITS
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA LAYOUT+5
        RTS
LAYOUT_INCREMENT:
        LDX #0
LAYOUT_INC:
        INC LAYOUT+8,X
        BNE LAYOUT_INC_OK
        INX
        CPX #4
        BNE LAYOUT_INC
        JMP EXHAUSTED
LAYOUT_INC_OK:
        LDA #0
        RTS
LAYOUT_PACKET:
        LDX #63
LAYOUT_PACKET_COPY:
        LDA LAYOUT,X
        STA BUF,X
        DEX
        BPL LAYOUT_PACKET_COPY
        STZ BUF+63
        LDA #64
        STA N
        JSR SEAL
        JMP SAVE_PACKET
LAYOUT_UPDATE:
        JSR LAYOUT_PACKET
        JSR ZERO_ADDR
        LDA #$40
        STA ADDR
        LDA #2
        STA ADDR+1
        JSR PUBLISH
        BNE LAYOUT_WRITE_RETURN
        ; A remains authoritative until verified invalidation. Then B is
        ; authoritative; STORE refuses until A is repaired/republished.
        JSR ZERO_ADDR
        LDA #64
        STA PACKET_N
        LDA #0
        JSR MARKER
        BNE LAYOUT_WRITE_RETURN
        JMP WRITE_PRIMARY
REPAIR_PRIMARY:
        LDA FALLBACK
        BEQ LAYOUT_WRITE_RETURN
WRITE_PRIMARY:
        JSR LAYOUT_PACKET
        JSR ZERO_ADDR
        LDA #64
        STA N
        JSR PUBLISH
        BNE LAYOUT_WRITE_RETURN
        STZ FALLBACK
        LDA #0
LAYOUT_WRITE_RETURN:
        RTS
REPAIR: LDX #7
REPAIR_KEY:
        LDA REQ+24,X
        CMP REPAIR_MAGIC,X
        BNE BAD_ARG
        DEX
        BPL REPAIR_KEY
        JMP REPAIR_PRIMARY
UPGRADE:
        LDX #7
UPGRADE_KEY:
        LDA REQ+24,X
        CMP UPGRADE_MAGIC,X
        BNE BAD_ARG
        DEX
        BPL UPGRADE_KEY
        JSR LOAD_LAYOUT
        BNE OP_RETURN
        LDA LEGACY
        BEQ UPGRADE_ALREADY
        JSR PROGRAM_CHECK
        BNE OP_RETURN
        JSR INITIAL_SESSION
        BNE OP_RETURN
        LDA #2
        STA LAYOUT+2
        LDA #1
        STA LAYOUT+8
        JSR LAYOUT_UPDATE
        BNE OP_RETURN
        STZ LEGACY
UPGRADE_ALREADY:
        LDA #0
        RTS
FORMAT: LDX #7
FORMAT_KEY:
        LDA REQ+24,X
        CMP FORMAT_MAGIC,X
        BNE BAD_ARG
        DEX
        BPL FORMAT_KEY
        ; Both layout markers invalidated before changing any record.
        JSR ZERO_ADDR
        LDA #64
        STA PACKET_N
        LDA #0
        JSR MARKER
        BNE OP_RETURN
        LDA #$40
        STA ADDR
        LDA #2
        STA ADDR+1
        LDA #0
        JSR MARKER
        BNE OP_RETURN
        STZ PROG_SLOT
FORMAT_DIRECTORY:
        LDA PROG_SLOT
        INC A
        LSR A
        LSR A
        STA ADDR+1
        LDA PROG_SLOT
        INC A
        AND #3
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA ADDR
        LDA #0
        JSR MARKER
        BNE OP_RETURN
        INC PROG_SLOT
        LDA PROG_SLOT
        CMP #8
        BNE FORMAT_DIRECTORY
        ; Clear every claim marker, including corrupt old-epoch packets.
        ; LOAD_CLAIMS validates committed headers before checking epochs.
        JSR CLEAR_CLAIMS
        BNE OP_RETURN
        ; Retain a valid epoch counter when formatting an existing store.
        JSR SESSION_LOAD
        BNE FORMAT_FRESH_SESSION
        JSR NEW_EPOCH
        BNE OP_RETURN
        BRA FORMAT_LAYOUT
FORMAT_FRESH_SESSION:
        JSR INITIAL_SESSION_RECORD
        BNE OP_RETURN
FORMAT_LAYOUT:
        JSR ZERO_BUF
        LDX #7
FORMAT_LAYOUT_COPY:
        LDA INITIAL_LAYOUT,X
        STA LAYOUT,X
        DEX
        BPL FORMAT_LAYOUT_COPY
        LDX #63
FORMAT_LAYOUT_ZERO:
        STZ LAYOUT,X
        DEX
        CPX #7
        BNE FORMAT_LAYOUT_ZERO
        LDA #1
        STA LAYOUT+8
        STZ FALLBACK
        JSR LAYOUT_UPDATE
        BNE OP_RETURN
        LDA #0
        RTS
CLEAR_CLAIMS:
        STZ SLOT
INIT_CLEAR_CLAIMS:
        JSR CLAIM_ADDRESS
        LDA #32
        STA PACKET_N
        LDA #0
        JSR MARKER
        BNE INIT_RETURN
        INC SLOT
        LDA SLOT
        CMP #4
        BNE INIT_CLEAR_CLAIMS
        LDA #0
        RTS
INITIAL_SESSION:
        ; Explicit FORMAT/UPGRADE initializes only management cells.
        JSR CLEAR_CLAIMS
        BNE INIT_RETURN
INITIAL_SESSION_RECORD:
        LDA #$80
        STA ADDR
        LDA #2
        STA ADDR+1
        LDA #64
        STA PACKET_N
        LDA #0
        JSR MARKER
        BNE INIT_RETURN
        LDA #$C0
        STA ADDR
        LDA #0
        JSR MARKER
        BNE INIT_RETURN
        JSR ZERO_BUF
        LDX #2
INIT_WS_MAGIC:
        LDA WS_MAGIC,X
        STA BUF,X
        DEX
        BPL INIT_WS_MAGIC
        LDA #1
        STA BUF+4
        STA BUF+8
        LDX #63
INIT_SESSION_COPY:
        LDA BUF,X
        STA SESSION,X
        DEX
        BPL INIT_SESSION_COPY
        LDA #64
        STA N
        JSR SEAL
        JSR SAVE_PACKET
        LDA #$80
        STA ADDR
        STA SESSION_ADDR
        JSR PUBLISH
        BNE INIT_RETURN
        LDA #1
        STA RESET_LATCH
        LDA #0
INIT_RETURN:
        RTS
CONSOLE:
        SEI
        CLD
        LDX #<TITLE
        LDY #>TITLE
        JSR PRINT
CON_HELP_TEXT:
        LDX #<HELP_TEXT
        LDY #>HELP_TEXT
        JSR PRINT
PROMPT: LDX #<PROMPT_TEXT
        LDY #>PROMPT_TEXT
        JSR PRINT
        JSR LINE_READ
        BCC PROMPT
        LDX #31
CON_CLEAR:
        STZ REQ,X
        DEX
        BPL CON_CLEAR
        LDA LINE
        BEQ PROMPT
        CMP #'P'
        BEQ CON_RESIZE
        CMP #'H'
        BEQ CON_HELP
        LDX LINE+1
        BNE CON_BAD
        CMP #'Q'
        BEQ QUIT
        CMP #'?'
        BEQ CON_QUERY
        CMP #'F'
        BEQ CON_FORMAT
        CMP #'U'
        BEQ CON_UPGRADE
        CMP #'V'
        BEQ CON_REPAIR
        LDA #$44
        BRA CON_RESULT
CON_HELP:
        LDX #4
CON_HELP_MATCH:
        LDA LINE,X
        CMP HELP_COMMAND,X
        BNE CON_BAD
        DEX
        BPL CON_HELP_MATCH
        BRA CON_HELP_TEXT
CON_QUERY:
        JSR OPERATION
        BNE CON_RESULT
        JSR CAPACITY_TEXT
        BRA PROMPT
CON_RESIZE:
        LDA LINE+1
        CMP #' '
        BNE CON_BAD
        LDA LINE+4
        BNE CON_BAD
        LDX #6
CON_SIZE_MATCH:
        LDA LINE+2
        CMP UNIT_TEXT,X
        BNE CON_SIZE_NEXT
        LDA LINE+3
        CMP UNIT_TEXT+1,X
        BEQ CON_SIZE_FOUND
CON_SIZE_NEXT:
        DEX
        DEX
        BPL CON_SIZE_MATCH
        BRA CON_BAD
CON_SIZE_FOUND:
        TXA
        LSR A
        INC A
        STA CON_UNITS
        JSR OPERATION
        BNE CON_RESULT
        LDA CON_UNITS
        CMP REQ+21
        BNE CON_SIZE_PREVIEW
        LDX #<NO_CHANGE_TEXT
        LDY #>NO_CHANGE_TEXT
        BRA CON_MESSAGE
CON_SIZE_PREVIEW:
        STA REQ+21
        JSR CAPACITY_TEXT
        LDA #5
        LDX #<RESIZE_MAGIC
        LDY #>RESIZE_MAGIC
        BRA CON_CONFIRM
CON_FORMAT:
        LDA #6
        LDX #<FORMAT_MAGIC
        LDY #>FORMAT_MAGIC
        BRA CON_CONFIRM
CON_UPGRADE:
        LDA #7
        LDX #<UPGRADE_MAGIC
        LDY #>UPGRADE_MAGIC
        BRA CON_CONFIRM
CON_REPAIR:
        LDA #8
        LDX #<REPAIR_MAGIC
        LDY #>REPAIR_MAGIC
CON_CONFIRM:
        STA REQ
        STX Q
        STY Q+1
        LDY #7
CON_KEY_COPY:
        LDA (Q),Y
        STA REQ+24,Y
        DEY
        BPL CON_KEY_COPY
        LDX #<CONFIRM_TEXT
        LDY #>CONFIRM_TEXT
        LDA REQ
        CMP #6
        BEQ CON_FORMAT_PROMPT
        CMP #5
        BNE CON_PROMPT_CONFIRM
        LDX #<APPLY_TEXT
        LDY #>APPLY_TEXT
        BRA CON_PROMPT_CONFIRM
CON_FORMAT_PROMPT:
        LDX #<FORMAT_TEXT
        LDY #>FORMAT_TEXT
CON_PROMPT_CONFIRM:
        JSR PRINT
        JSR LINE_READ
        BCC CON_CANCEL
        LDA REQ
        CMP #5
        BEQ CON_CHECK_Y
        CMP #6
        BNE CON_CHECK_YES
        LDX #11
CON_FORMAT_CONFIRM:
        LDA LINE,X
        CMP FORMAT_CONFIRM,X
        BNE CON_CANCEL
        DEX
        BPL CON_FORMAT_CONFIRM
        BRA CON_EXEC
CON_CHECK_Y:
        LDA LINE
        CMP #'Y'
        BNE CON_CANCEL
        LDA LINE+1
        BEQ CON_EXEC
        BRA CON_CANCEL
CON_CHECK_YES:
        LDX #3
CON_YES:
        LDA LINE,X
        CMP YES_MAGIC,X
        BNE CON_CANCEL
        DEX
        BPL CON_YES
CON_EXEC:
        JSR OPERATION
CON_RESULT:
        CMP #0
        BNE CON_ERROR
        LDA REQ
        SEC
        SBC #5
        TAX
        LDA SUCCESS_LO,X
        LDY SUCCESS_HI,X
        TAX
        BRA CON_MESSAGE
CON_ERROR:
        LDX #STATUS_COUNT-1
CON_STATUS_MATCH:
        CMP STATUS_CODES,X
        BEQ CON_STATUS_TEXT
        DEX
        BPL CON_STATUS_MATCH
        PHA
        LDX #<RESULT_TEXT
        LDY #>RESULT_TEXT
        JSR PRINT
        PLA
        JSR HEX
        JSR NL
        JMP PROMPT
CON_STATUS_TEXT:
        LDY STATUS_HI,X
        LDA STATUS_LO,X
        TAX
CON_MESSAGE:
        JSR PRINT
        JMP PROMPT
CON_CANCEL:
        LDX #<CANCELED_TEXT
        LDY #>CANCELED_TEXT
        BRA CON_MESSAGE
CON_BAD:LDA #$44
        BRA CON_RESULT
QUIT:   JMP $7E67
; Four fixed layouts: small decimal tables avoid a general 24-bit formatter.
CAPACITY_TEXT:
        LDX #<PROGRAM_TEXT
        LDY #>PROGRAM_TEXT
        JSR PRINT
        LDA REQ+21
        DEC A
        ASL A
        TAX
        LDA UNIT_TEXT,X
        JSR PUTC
        INX
        LDA UNIT_TEXT,X
        JSR PUTC
        LDX #<WORKSPACE_TEXT
        LDY #>WORKSPACE_TEXT
        JSR PRINT
        LDA REQ+21
        DEC A
        TAX
        LDY CAPACITY_HI,X
        LDA CAPACITY_LO,X
        TAX
        JSR PRINT
        LDX #<BYTES_TEXT
        LDY #>BYTES_TEXT
        JMP PRINT
LINE_READ:
        STZ LINE_N
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
        BEQ LINE_END
        CMP #'a'
        BCC LINE_CHAR
        CMP #'z'+1
        BCS LINE_CHAR
        AND #$DF
LINE_CHAR:
        LDX LINE_N
        CPX #15
        BCS LINE_FULL
        STA LINE,X
        INC LINE_N
        JSR PUTC
        BRA LINE_WAIT
LINE_FULL:
        LDA #1
        STA OVERFLOW
        BRA LINE_WAIT
LINE_END:
        LDX LINE_N
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
PRINT:  STX Q
        STY Q+1
        LDY #0
PRINT_LOOP:
        LDA (Q),Y
        BEQ PRINT_END
        JSR PUTC
        INY
        BRA PRINT_LOOP
PRINT_END:
        RTS
SV_MAGIC DB "SV",1
SM_MAGIC DB "SM",1,1
WS_MAGIC DB "WS",1
WC_MAGIC DB "WC",1
SP_MAGIC DB "SP",1
INITIAL_LAYOUT DB "SS",2,8,8,0,1,0
MAX_END DB $E0,$FF,1
FORMAT_MAGIC DB "FORMAT!!"
RESIZE_MAGIC DB "RESIZE!!"
UPGRADE_MAGIC DB "UPGRADE!"
REPAIR_MAGIC DB "REPAIR!!"
YES_MAGIC DB "YES",0
FORMAT_CONFIRM DB "FORMAT SRAM",0
TITLE DB "WORK 1.1",13,10,0
HELP_COMMAND DB "HELP",0
HELP_TEXT DB "? capacity; P 16/32/48/64 (KiB); U upgrade; V repair; F format; HELP; Q",13,10,0
PROMPT_TEXT DB "WORK> ",0
UNIT_TEXT DB "16324864"
PROGRAM_TEXT DB "Programs: ",0
WORKSPACE_TEXT DB " KiB; workspace: ",0
BYTES_TEXT DB " bytes",13,10,0
CAP16 DB "114656",0
CAP32 DB "98272",0
CAP48 DB "81888",0
CAP64 DB "65504",0
CAPACITY_LO DB <CAP16,<CAP32,<CAP48,<CAP64
CAPACITY_HI DB >CAP16,>CAP32,>CAP48,>CAP64
APPLY_TEXT DB "Apply? [y/N]: ",0
CONFIRM_TEXT DB "Changes storage metadata. Type YES: ",0
FORMAT_TEXT DB "Clear program/claim metadata. Type FORMAT SRAM: ",0
RESULT_TEXT DB "WORK error: $",0
NO_CHANGE_TEXT DB "No change.",13,10,0
CANCELED_TEXT DB "Canceled.",13,10,0
RESIZED_TEXT DB "Resized.",13,10,0
FORMATTED_TEXT DB "Formatted.",13,10,0
UPGRADED_TEXT DB "Upgraded.",13,10,0
REPAIRED_TEXT DB "Repaired.",13,10,0
SUCCESS_LO DB <RESIZED_TEXT,<FORMATTED_TEXT,<UPGRADED_TEXT,<REPAIRED_TEXT
SUCCESS_HI DB >RESIZED_TEXT,>FORMATTED_TEXT,>UPGRADED_TEXT,>REPAIRED_TEXT
STATUS_COUNT EQU 8
STATUS_CODES DB $40,$41,$44,$45,$48,$49,$4A,$80
UNINITIALIZED_TEXT DB "Storage not initialized.",13,10,0
INVALID_STORAGE_TEXT DB "Storage invalid or program exceeds boundary.",13,10,0
INVALID_COMMAND_TEXT DB "Invalid command. Use HELP.",13,10,0
VERIFY_TEXT DB "Write verification failed.",13,10,0
EXHAUSTED_TEXT DB "Counter exhausted.",13,10,0
UPGRADE_TEXT DB "Upgrade required. Use U.",13,10,0
CONFLICT_TEXT DB "Resize refused: workspace overlaps.",13,10,0
ABSENT_TEXT DB "SPI SRAM unavailable.",13,10,0
STATUS_LO DB <UNINITIALIZED_TEXT,<INVALID_STORAGE_TEXT,<INVALID_COMMAND_TEXT,<VERIFY_TEXT,<EXHAUSTED_TEXT,<UPGRADE_TEXT,<CONFLICT_TEXT,<ABSENT_TEXT
STATUS_HI DB >UNINITIALIZED_TEXT,>INVALID_STORAGE_TEXT,>INVALID_COMMAND_TEXT,>VERIFY_TEXT,>EXHAUSTED_TEXT,>UPGRADE_TEXT,>CONFLICT_TEXT,>ABSENT_TEXT
REQ DS 32
BUF DS 64
EXPECT DS 64
EXPECT_PACKET DS 64
LAYOUT DS 64
SESSION DS 64
CLAIMS DS 128
LINE DS 16
ADDR DS 3
SAVE_ADDR DS 3
POS DS 3
SIZE DS 3
END_POS DS 3
OLD_END DS 3
BP DS 2
SAVE_C DS 2
CRC DS 2
TEMP DS 2
PAGE_END DS 2
N DB 0
CRC_N DB 0
PACKET_N DB 0
ERROR DB 0
LEGACY DB 0
FALLBACK DB 0
UNITS DB 0
NEW_UNITS DB 0
SESSION_VALID DB 0
SESSION_ADDR DB 0
SLOT DB 0
FREE_SLOT DB 0
PROG_SLOT DB 0
LINE_N DB 0
OVERFLOW DB 0
ARITH_N DB 0
CHECKING DB 0
CHECK_SLOT DB 0
CON_UNITS DB 0
APP_END:
        ENDMOD
        END
