WK_ENTRY:  JSR WK_SAVE_WINDOW
        JSR WK_CLEAR_STATE
        JMP WK_CONSOLE
WK_SAVE_WINDOW:
        PHA
        PHX
        LDX #63
WK_SAVE_WINDOW_LOOP:
        LDA $6400,X
        STA $6A40,X
        DEX
        BPL WK_SAVE_WINDOW_LOOP
        PLX
        PLA
        RTS
WK_RESTORE_WINDOW:
        PHA
        PHX
        LDX #63
WK_RESTORE_WINDOW_LOOP:
        LDA $6A40,X
        STA $6400,X
        DEX
        BPL WK_RESTORE_WINDOW_LOOP
        PLX
        PLA
        RTS
WK_CLEAR_STATE:
        PHX
        LDX #0
WK_CLEAR_LOOP:
        STZ $6800,X
        STZ $6900,X
        INX
        BNE WK_CLEAR_LOOP
        LDX #30
WK_CLEAR_TAIL:
        STZ $6A00,X
        DEX
        BPL WK_CLEAR_TAIL
        PLX
        RTS
; Optional application library, not additional resident RAM. W65C02S/816E.
WK_P EQU $D0
WK_Q EQU $D2
WK_C EQU $D4
WK_R EQU $6650
WK_RESET_LATCH EQU $66AF
WK_MANAGED EQU $66AE
WK_PUTC EQU $7E6D
WK_GETC EQU $7E70
WK_HEX EQU $7E7C
WK_NL EQU $7E7F
WK_START:  JMP WK_CONSOLE
        BRA WK_API
        DB "WK",1,2
WK_API:    JSR WK_SAVE_WINDOW
        JSR WK_CLEAR_STATE
        SEI
        CLD
        STA WK_C
        STX WK_C+1
        LDA #32
        STA WK_N
        JSR WK_CPU_RANGE
                        BNE WK_API_RETURN
        LDY #31
WK_COPY_REQUEST:
        LDA (WK_C),Y
        STA WK_REQ,Y
        DEY
                        BPL WK_COPY_REQUEST
        JSR WK_OPERATION
        PHA
        LDY #31
WK_COPY_RESULT:
        LDA WK_REQ,Y
        STA (WK_C),Y
        DEY
                        BPL WK_COPY_RESULT
        PLA
WK_API_RETURN:
        JSR WK_RESTORE_WINDOW
        CMP #0
                        BNE WK_API_ERROR
        SEC
        RTS
WK_API_ERROR:
        CLC
        RTS
WK_OPERATION:
        STZ WK_CHECKING
        JSR WK_DISCOVER
                        BEQ WK_BM_LONG_52
                        JMP WK_OP_RETURN
WK_BM_LONG_52:
        LDA WK_REQ+1
                        BNE WK_BAD_ARG
        LDA WK_REQ
        CMP #9
                        BCS WK_BAD_ARG
        CMP #6
                        BNE WK_BM_LONG_59
                        JMP WK_FORMAT
WK_BM_LONG_59:
        CMP #7
                        BNE WK_BM_LONG_61
                        JMP WK_UPGRADE
WK_BM_LONG_61:
        JSR WK_LOAD_LAYOUT
                        BNE WK_OP_RETURN
        LDA WK_REQ
                        BNE WK_BM_LONG_65
                        JMP WK_QUERY
WK_BM_LONG_65:
        LDA WK_LEGACY
                        BNE WK_NEED_UPGRADE
        LDA WK_REQ
        CMP #8
                        BNE WK_BM_LONG_70
                        JMP WK_REPAIR
WK_BM_LONG_70:
        JSR WK_SESSION_LOAD
                        BNE WK_OP_RETURN
        LDA WK_RESET_LATCH
                        BNE WK_SESSION_READY
        JSR WK_NEW_EPOCH
                        BNE WK_OP_RETURN
WK_SESSION_READY:
        JSR WK_LOAD_CLAIMS
                        BNE WK_OP_RETURN
        JSR WK_PROGRAM_CHECK
                        BNE WK_OP_RETURN
        LDA WK_REQ
        CMP #5
                        BNE WK_BM_LONG_84
                        JMP WK_RESIZE
WK_BM_LONG_84:
        LDA WK_REQ+2
        ORA WK_REQ+3
                        BEQ WK_BAD_ARG
        LDA WK_REQ
        CMP #1
                        BNE WK_BM_LONG_90
                        JMP WK_CLAIM
WK_BM_LONG_90:
        JSR WK_HANDLE
                        BNE WK_OP_RETURN
        LDA WK_REQ
        CMP #2
                        BNE WK_BM_LONG_95
                        JMP WK_RELEASE
WK_BM_LONG_95:
        JMP WK_IO
WK_OP_RETURN:
        RTS
WK_BAD_ARG:LDA #$44
        RTS
WK_BAD_META:
        LDA #$41
        RTS
WK_NEED_UPGRADE:
        LDA #$49
        RTS
WK_STALE:  LDA #$4B
        RTS
WK_FULL:   LDA #$43
        RTS
WK_VERIFY_BAD:
        LDA #$45
        RTS
WK_EXHAUSTED:
        LDA #$48
        RTS
WK_DISCOVER:
        LDX #2
WK_DISCOVER_SV:
        LDA $7D04,X
        CMP WK_SV_MAGIC,X
                        BNE WK_ABSENT
        DEX
                        BPL WK_DISCOVER_SV
        LDA $7D07
        AND #8
                        BEQ WK_ABSENT
        LDA $7D08
                        BNE WK_ABSENT
        LDA $7D09
        CMP #$65
                        BNE WK_ABSENT
        LDX #3
WK_DISCOVER_SM:
        LDA $66A2,X
        CMP WK_SM_MAGIC,X
                        BNE WK_ABSENT
        DEX
                        BPL WK_DISCOVER_SM
        STZ WK_N
        LDA #0
        JMP WK_TRANSFER
WK_ABSENT: LDA #$80
        RTS
WK_BUF_PTR:
        LDA #<WK_BUF
        STA WK_BP
        LDA #>WK_BUF
        STA WK_BP+1
        RTS
WK_TRANSFER:
        PHA
        LDX #15
WK_REQUEST_ZERO:
        STZ WK_R,X
        DEX
                        BPL WK_REQUEST_ZERO
        LDX #2
WK_REQUEST_ADDR:
        LDA WK_ADDR,X
        STA WK_R+2,X
        DEX
                        BPL WK_REQUEST_ADDR
        LDA WK_BP
        STA WK_R+5
        LDA WK_BP+1
        STA WK_R+6
        LDA WK_N
        STA WK_R+7
        PLA
        STA WK_R
        CMP #2
                        BNE WK_TRAN_READ
        STZ WK_MANAGED
        JSR $66A6
        PHA
        LDA #1
        STA WK_MANAGED
        PLA
                        BRA WK_TRAN_RESULT
WK_TRAN_READ:
        JSR $66A6
WK_TRAN_RESULT:
        CMP #0
                        BNE WK_TRAN_RETURN
        LDA WK_R
                        BEQ WK_TRAN_RETURN
        LDA WK_R+9
        CMP WK_N
                        BNE WK_TRAN_SHORT
        LDA #0
WK_TRAN_RETURN:
        RTS
WK_TRAN_SHORT:
        LDA #7
        RTS
WK_READ64: LDA #64
                        BRA WK_READ_N
WK_READ32: LDA #32
WK_READ_N: STA WK_N
        JSR WK_BUF_PTR
        LDA #1
        JMP WK_TRANSFER
WK_WRITE_VERIFY:
        JSR WK_BUF_PTR
        LDX WK_N
        DEX
WK_EXPECT_COPY:
        LDA WK_BUF,X
        STA WK_EXPECT,X
        DEX
                        BPL WK_EXPECT_COPY
        LDA #2
        JSR WK_TRANSFER
                        BNE WK_WRITE_RETURN
        LDA #1
        JSR WK_TRANSFER
                        BNE WK_WRITE_RETURN
        LDX WK_N
        DEX
WK_EXPECT_CHECK:
        LDA WK_BUF,X
        CMP WK_EXPECT,X
                        BEQ WK_BM_LONG_224
                        JMP WK_VERIFY_BAD
WK_BM_LONG_224:
        DEX
                        BPL WK_EXPECT_CHECK
        LDA #0
WK_WRITE_RETURN:
        RTS
; Publish a 32/64-byte packet. Invalidate/verify old final marker first.
WK_PUBLISH:
        LDA WK_N
        STA WK_PACKET_N
        LDA #0
        JSR WK_MARKER
                        BNE WK_PUB_RETURN
        LDX WK_PACKET_N
        DEX
WK_PUB_RESTORE:
        LDA WK_EXPECT_PACKET,X
        STA WK_BUF,X
        DEX
                        BPL WK_PUB_RESTORE
        LDA WK_PACKET_N
        STA WK_N
        JSR WK_WRITE_VERIFY
                        BNE WK_PUB_RETURN
        LDA #$A5
        JSR WK_MARKER
WK_PUB_RETURN:
        RTS
WK_SAVE_PACKET:
        LDX WK_N
        DEX
WK_PACKET_COPY:
        LDA WK_BUF,X
        STA WK_EXPECT_PACKET,X
        DEX
                        BPL WK_PACKET_COPY
        RTS
WK_MARKER:
        PHA
        LDX #2
WK_MARK_SAVE:
        LDA WK_ADDR,X
        STA WK_SAVE_ADDR,X
        DEX
                        BPL WK_MARK_SAVE
        LDA WK_PACKET_N
        DEC A
        CLC
        ADC WK_ADDR
        STA WK_ADDR
                        BCC WK_MARK_ADDR
        INC WK_ADDR+1
                        BNE WK_MARK_ADDR
        INC WK_ADDR+2
WK_MARK_ADDR:
        PLA
        STA WK_BUF
        LDA #1
        STA WK_N
        JSR WK_WRITE_VERIFY
        PHA
        LDX #2
WK_MARK_RESTORE:
        LDA WK_SAVE_ADDR,X
        STA WK_ADDR,X
        DEX
                        BPL WK_MARK_RESTORE
        PLA
        CMP #0
        RTS
WK_CRC_INIT:
        LDA #$FF
        STA WK_CRC
        STA WK_CRC+1
        RTS
WK_CRC_BYTE:
        EOR WK_CRC+1
        STA WK_CRC+1
        LDX #8
WK_CRC_BIT:
        ASL WK_CRC
        ROL WK_CRC+1
                        BCC WK_CRC_NEXT
        LDA WK_CRC
        EOR #$21
        STA WK_CRC
        LDA WK_CRC+1
        EOR #$10
        STA WK_CRC+1
WK_CRC_NEXT:
        DEX
                        BNE WK_CRC_BIT
        RTS
WK_HEADER_CRC:
        LDA WK_N
        SEC
        SBC #2
                        BRA WK_CRC_BUFFER
WK_SEAL:   LDA WK_N
        SEC
        SBC #4
        JSR WK_CRC_BUFFER
        LDA WK_CRC+1
        STA WK_BUF,Y
        INY
        LDA WK_CRC
        STA WK_BUF,Y
        RTS
WK_CRC_BUFFER:
        STA WK_CRC_N
        JSR WK_CRC_INIT
        LDY #0
WK_CRC_LOOP:
        LDA WK_BUF,Y
        JSR WK_CRC_BYTE
        INY
        CPY WK_CRC_N
                        BNE WK_CRC_LOOP
        LDA WK_CRC
        ORA WK_CRC+1
        RTS
WK_ZERO_BUF:
        LDX #63
WK_ZERO_LOOP:
        STZ WK_BUF,X
        DEX
                        BPL WK_ZERO_LOOP
        RTS
WK_ZERO_ADDR:
        STZ WK_ADDR
        STZ WK_ADDR+1
        STZ WK_ADDR+2
        RTS
WK_LOAD_LAYOUT:
        STZ WK_FALLBACK
        JSR WK_ZERO_ADDR
        JSR WK_READ64
                        BEQ WK_BM_LONG_361
                        JMP WK_LAYOUT_RETURN
WK_BM_LONG_361:
        LDA WK_BUF+63
        CMP #$A5
                        BEQ WK_PRIMARY_FOUND
        LDA #$40
        STA WK_ADDR
        LDA #2
        STA WK_ADDR+1
        JSR WK_READ64
                        BEQ WK_BM_LONG_370
                        JMP WK_LAYOUT_RETURN
WK_BM_LONG_370:
        INC WK_FALLBACK
WK_PRIMARY_FOUND:
        LDA WK_BUF+63
        CMP #$A5
                        BEQ WK_BM_LONG_375
                        JMP WK_UNFORMATTED
WK_BM_LONG_375:
        JSR WK_HEADER_CRC
                        BEQ WK_BM_LONG_377
                        JMP WK_BAD_META
WK_BM_LONG_377:
        LDA WK_BUF+7
        ORA WK_BUF+62
                        BEQ WK_BM_LONG_380
                        JMP WK_BAD_META
WK_BM_LONG_380:
        LDX #59
WK_LAYOUT_RESERVED:
        LDA WK_BUF,X
                        BEQ WK_BM_LONG_384
                        JMP WK_BAD_META
WK_BM_LONG_384:
        DEX
        CPX #11
                        BNE WK_LAYOUT_RESERVED
        LDA WK_BUF
        CMP #'S'
                        BEQ WK_BM_LONG_390
                        JMP WK_BAD_META
WK_BM_LONG_390:
        LDA WK_BUF+1
        CMP #'S'
                        BEQ WK_BM_LONG_393
                        JMP WK_BAD_META
WK_BM_LONG_393:
        LDA WK_BUF+3
        CMP #8
                        BEQ WK_BM_LONG_396
                        JMP WK_BAD_META
WK_BM_LONG_396:
        LDA WK_BUF+4
        CMP #8
                        BEQ WK_BM_LONG_399
                        JMP WK_BAD_META
WK_BM_LONG_399:
        LDA WK_BUF+2
        CMP #1
                        BEQ WK_LEGACY_LAYOUT
        CMP #2
                        BEQ WK_BM_LONG_404
                        JMP WK_BAD_META
WK_BM_LONG_404:
        STZ WK_LEGACY
        LDA WK_BUF+8
        ORA WK_BUF+9
        ORA WK_BUF+10
        ORA WK_BUF+11
                        BNE WK_BM_LONG_410
                        JMP WK_BAD_META
WK_BM_LONG_410:
                        BRA WK_LAYOUT_LIMIT
WK_LEGACY_LAYOUT:
        LDA WK_BUF+8
        ORA WK_BUF+9
        ORA WK_BUF+10
        ORA WK_BUF+11
                        BEQ WK_BM_LONG_417
                        JMP WK_BAD_META
WK_BM_LONG_417:
        LDA WK_FALLBACK
                        BEQ WK_BM_LONG_419
                        JMP WK_BAD_META
WK_BM_LONG_419:
        LDA #1
        STA WK_LEGACY
        LDA WK_BUF+5
                        BEQ WK_BM_LONG_423
                        JMP WK_BAD_META
WK_BM_LONG_423:
        LDA WK_BUF+6
        CMP #1
                        BEQ WK_BM_LONG_426
                        JMP WK_BAD_META
WK_BM_LONG_426:
WK_LAYOUT_LIMIT:
        LDA WK_BUF+5
        AND #$3F
                        BEQ WK_BM_LONG_430
                        JMP WK_BAD_META
WK_BM_LONG_430:
        LDA WK_BUF+6
                        BEQ WK_LIMIT_SMALL
        CMP #1
                        BEQ WK_BM_LONG_434
                        JMP WK_BAD_META
WK_BM_LONG_434:
        LDA WK_BUF+5
                        BEQ WK_BM_LONG_436
                        JMP WK_BAD_META
WK_BM_LONG_436:
        LDA #4
                        BRA WK_LIMIT_SET
WK_LIMIT_SMALL:
        LDA WK_BUF+5
                        BNE WK_BM_LONG_441
                        JMP WK_BAD_META
WK_BM_LONG_441:
        LSR A
        LSR A
        LSR A
        LSR A
        LSR A
        LSR A
WK_LIMIT_SET:
        STA WK_UNITS
        LDX #63
WK_LAYOUT_COPY:
        LDA WK_BUF,X
        STA WK_LAYOUT,X
        DEX
                        BPL WK_LAYOUT_COPY
        LDA #0
WK_LAYOUT_RETURN:
        RTS
WK_UNFORMATTED:
        LDA #$40
        RTS
WK_QUERY:  STZ WK_REQ+12
        LDA WK_LAYOUT+5
        STA WK_REQ+13
        LDA WK_LAYOUT+6
        STA WK_REQ+14
        LDA #$E0
        STA WK_REQ+18
        SEC
        LDA #$FF
        SBC WK_LAYOUT+5
        STA WK_REQ+19
        LDA #1
        SBC WK_LAYOUT+6
        STA WK_REQ+20
        LDA WK_UNITS
        STA WK_REQ+21
        LDA WK_LEGACY
        STA WK_REQ+22
        LDA WK_FALLBACK
        STA WK_REQ+23
        LDA #0
        RTS
WK_SESSION_LOAD:
        STZ WK_SESSION_VALID
        LDA #$80
        STA WK_ADDR
        LDA #2
        STA WK_ADDR+1
        STZ WK_ADDR+2
WK_SESSION_SCAN:
        JSR WK_READ64
                        BEQ WK_BM_LONG_493
                        JMP WK_SESSION_RETURN
WK_BM_LONG_493:
        LDA WK_BUF+63
        CMP #$A5
                        BEQ WK_BM_LONG_496
                        JMP WK_SESSION_NEXT
WK_BM_LONG_496:
        JSR WK_HEADER_CRC
                        BEQ WK_BM_LONG_498
                        JMP WK_BAD_META
WK_BM_LONG_498:
        LDX #2
WK_SESSION_MAGIC:
        LDA WK_BUF,X
        CMP WK_WS_MAGIC,X
                        BEQ WK_BM_LONG_503
                        JMP WK_BAD_META
WK_BM_LONG_503:
        DEX
                        BPL WK_SESSION_MAGIC
        LDA WK_BUF+3
        ORA WK_BUF+62
                        BEQ WK_BM_LONG_508
                        JMP WK_BAD_META
WK_BM_LONG_508:
        LDX #59
WK_SESSION_RESERVED:
        LDA WK_BUF,X
                        BEQ WK_BM_LONG_512
                        JMP WK_BAD_META
WK_BM_LONG_512:
        DEX
        CPX #13
                        BNE WK_SESSION_RESERVED
        LDA WK_BUF+4
        ORA WK_BUF+5
        ORA WK_BUF+6
        ORA WK_BUF+7
                        BNE WK_BM_LONG_520
                        JMP WK_BAD_META
WK_BM_LONG_520:
        LDA WK_BUF+8
        ORA WK_BUF+9
        ORA WK_BUF+10
        ORA WK_BUF+11
                        BNE WK_BM_LONG_525
                        JMP WK_BAD_META
WK_BM_LONG_525:
        LDA WK_SESSION_VALID
                        BEQ WK_SESSION_SELECT
        LDX #3
WK_SESSION_COMPARE:
        LDA WK_BUF+4,X
        CMP WK_SESSION+4,X
                        BCC WK_SESSION_NEXT
                        BNE WK_SESSION_SELECT
        DEX
                        BPL WK_SESSION_COMPARE
        JMP WK_BAD_META
WK_SESSION_SELECT:
        INC WK_SESSION_VALID
        LDA WK_ADDR
        STA WK_SESSION_ADDR
        LDX #63
WK_SESSION_COPY:
        LDA WK_BUF,X
        STA WK_SESSION,X
        DEX
                        BPL WK_SESSION_COPY
WK_SESSION_NEXT:
        LDA WK_ADDR
        CMP #$C0
                        BEQ WK_SESSION_END
        LDA #$C0
        STA WK_ADDR
                        JMP WK_SESSION_SCAN
WK_SESSION_END:
        LDA WK_SESSION_VALID
                        BNE WK_BM_LONG_556
                        JMP WK_BAD_META
WK_BM_LONG_556:
        LDA #0
WK_SESSION_RETURN:
        RTS
WK_INC_REVISION:
        LDX #0
WK_REV_INCREMENT:
        INC WK_SESSION+4,X
                        BNE WK_REV_OK
        INX
        CPX #4
                        BNE WK_REV_INCREMENT
        JMP WK_EXHAUSTED
WK_REV_OK: LDA #0
        RTS
WK_NEW_EPOCH:
        LDX #0
WK_EPOCH_INCREMENT:
        INC WK_SESSION+8,X
                        BNE WK_EPOCH_OK
        INX
        CPX #4
                        BNE WK_EPOCH_INCREMENT
        JMP WK_EXHAUSTED
WK_EPOCH_OK:
        STZ WK_SESSION+12
        STZ WK_SESSION+13
        JSR WK_SESSION_COMMIT
                        BNE WK_EPOCH_RETURN
        LDA #1
        STA WK_RESET_LATCH
        LDA #0
WK_EPOCH_RETURN:
        RTS
WK_SESSION_COMMIT:
        JSR WK_INC_REVISION
                        BNE WK_EPOCH_RETURN
        LDX #63
WK_SESSION_PREP:
        LDA WK_SESSION,X
        STA WK_BUF,X
        DEX
                        BPL WK_SESSION_PREP
        STZ WK_BUF+63
        LDA #64
        STA WK_N
        JSR WK_SEAL
        JSR WK_SAVE_PACKET
        LDA WK_SESSION_ADDR
        EOR #$40
        STA WK_ADDR
        STA WK_SESSION_ADDR
        LDA #2
        STA WK_ADDR+1
        STZ WK_ADDR+2
        JMP WK_PUBLISH
WK_LOAD_CLAIMS:
        LDA #4
        STA WK_FREE_SLOT
        STZ WK_SLOT
WK_CLAIMS_SCAN:
        JSR WK_CLAIM_ADDRESS
        JSR WK_READ32
                        BEQ WK_BM_LONG_619
                        JMP WK_CLAIMS_RETURN
WK_BM_LONG_619:
        LDA WK_BUF+31
        CMP #$A5
                        BEQ WK_BM_LONG_622
                        JMP WK_CLAIMS_FREE
WK_BM_LONG_622:
        JSR WK_HEADER_CRC
                        BEQ WK_BM_LONG_624
                        JMP WK_BAD_META
WK_BM_LONG_624:
        LDX #2
WK_CLAIM_MAGIC:
        LDA WK_BUF,X
        CMP WK_WC_MAGIC,X
                        BEQ WK_BM_LONG_629
                        JMP WK_BAD_META
WK_BM_LONG_629:
        DEX
                        BPL WK_CLAIM_MAGIC
        LDA WK_BUF+3
        ORA WK_BUF+15
        ORA WK_BUF+19
        ORA WK_BUF+30
                        BEQ WK_BM_LONG_636
                        JMP WK_BAD_META
WK_BM_LONG_636:
        LDX #27
WK_CLAIM_RESERVED:
        LDA WK_BUF,X
                        BEQ WK_BM_LONG_640
                        JMP WK_BAD_META
WK_BM_LONG_640:
        DEX
        CPX #19
                        BNE WK_CLAIM_RESERVED
        LDX #3
WK_CLAIM_EPOCH:
        LDA WK_BUF+8,X
        CMP WK_SESSION+8,X
                        BNE WK_CLAIMS_FREE
        DEX
                        BPL WK_CLAIM_EPOCH
        LDA WK_BUF+4
        ORA WK_BUF+5
                        BNE WK_BM_LONG_653
                        JMP WK_BAD_META
WK_BM_LONG_653:
        LDA WK_BUF+6
        ORA WK_BUF+7
                        BNE WK_BM_LONG_656
                        JMP WK_BAD_META
WK_BM_LONG_656:
        LDA WK_BUF+12
                        BEQ WK_BM_LONG_658
                        JMP WK_BAD_META
WK_BM_LONG_658:
        LDA WK_BUF+16
        ORA WK_BUF+17
        ORA WK_BUF+18
                        BNE WK_BM_LONG_662
                        JMP WK_BAD_META
WK_BM_LONG_662:
        LDX #2
WK_CLAIM_SPAN:
        LDA WK_BUF+12,X
        STA WK_POS,X
        LDA WK_BUF+16,X
        STA WK_SIZE,X
        DEX
                        BPL WK_CLAIM_SPAN
        JSR WK_SPAN_END
                        BEQ WK_BM_LONG_672
                        JMP WK_BAD_META
WK_BM_LONG_672:
        LDA WK_POS+2
        CMP WK_LAYOUT+6
                        BCS WK_BM_LONG_675
                        JMP WK_BAD_META
WK_BM_LONG_675:
                        BNE WK_CLAIMS_CACHE
        LDA WK_POS+1
        CMP WK_LAYOUT+5
                        BCS WK_BM_LONG_679
                        JMP WK_BAD_META
WK_BM_LONG_679:
                        BRA WK_CLAIMS_CACHE
WK_CLAIMS_FREE:
        STZ WK_BUF+31
        LDA WK_SLOT
        STA WK_FREE_SLOT
WK_CLAIMS_CACHE:
        JSR WK_SLOT_POINTER
        LDY #31
WK_CLAIM_CACHE_COPY:
        LDA WK_BUF,Y
        STA (WK_P),Y
        DEY
                        BPL WK_CLAIM_CACHE_COPY
        INC WK_SLOT
        LDA WK_SLOT
        CMP #4
                        BEQ WK_BM_LONG_696
                        JMP WK_CLAIMS_SCAN
WK_BM_LONG_696:
        JSR WK_CHECK_OVERLAPS
WK_CLAIMS_RETURN:
        RTS
WK_CHECK_OVERLAPS:
        LDA #1
        STA WK_CHECKING
        STZ WK_CHECK_SLOT
WK_CHECK_OUTER:
        LDA WK_CHECK_SLOT
        STA WK_SLOT
        JSR WK_SLOT_POINTER
        LDY #31
        LDA (WK_P),Y
        CMP #$A5
                        BNE WK_CHECK_NEXT
        LDY #12
        LDX #0
WK_CHECK_START_COPY:
        LDA (WK_P),Y
        STA WK_POS,X
        INY
        INX
        CPX #3
                        BNE WK_CHECK_START_COPY
        LDY #16
        LDX #0
WK_CHECK_SIZE_COPY:
        LDA (WK_P),Y
        STA WK_SIZE,X
        INY
        INX
        CPX #3
                        BNE WK_CHECK_SIZE_COPY
        JSR WK_ALLOC_RESTART
                        BNE WK_CLAIMS_RETURN
WK_CHECK_NEXT:
        INC WK_CHECK_SLOT
        LDA WK_CHECK_SLOT
        CMP #4
                        BNE WK_CHECK_OUTER
        STZ WK_CHECKING
        LDA #0
        RTS
WK_CLAIM_ADDRESS:
        LDA WK_SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA WK_ADDR
        LDA #3
        STA WK_ADDR+1
        STZ WK_ADDR+2
        RTS
WK_SLOT_POINTER:
        LDA WK_SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #<WK_CLAIMS
        STA WK_P
        LDA #>WK_CLAIMS
        ADC #0
        STA WK_P+1
        RTS
WK_SPAN_END:
        LDA #3
        STA WK_ARITH_N
        CLC
        LDX #0
WK_SPAN_ADD:
        LDA WK_POS,X
        ADC WK_SIZE,X
        STA WK_END_POS,X
        INX
        DEC WK_ARITH_N
                        BNE WK_SPAN_ADD
                        BCC WK_BM_LONG_778
                        JMP WK_BAD_ARG
WK_BM_LONG_778:
        LDX #2
WK_SPAN_BOUND:
        LDA WK_END_POS,X
        CMP WK_MAX_END,X
                        BCC WK_SPAN_OK
                        BEQ WK_BM_LONG_784
                        JMP WK_BAD_ARG
WK_BM_LONG_784:
        DEX
                        BPL WK_SPAN_BOUND
WK_SPAN_OK:LDA #0
        RTS
WK_CLAIM:  LDA WK_FREE_SLOT
        CMP #4
                        BCC WK_BM_LONG_791
                        JMP WK_FULL
WK_BM_LONG_791:
        LDX #2
WK_CLAIM_SIZE:
        LDA WK_REQ+18,X
        STA WK_SIZE,X
        DEX
                        BPL WK_CLAIM_SIZE
        LDA WK_SIZE
        ORA WK_SIZE+1
        ORA WK_SIZE+2
                        BNE WK_BM_LONG_801
                        JMP WK_BAD_ARG
WK_BM_LONG_801:
        STZ WK_POS
        LDA WK_LAYOUT+5
        STA WK_POS+1
        LDA WK_LAYOUT+6
        STA WK_POS+2
WK_ALLOC_RESTART:
        JSR WK_SPAN_END
                        BEQ WK_BM_LONG_809
                        JMP WK_FULL
WK_BM_LONG_809:
        STZ WK_SLOT
WK_ALLOC_SCAN:
        LDA WK_CHECKING
                        BEQ WK_ALLOC_CHECK
        LDA WK_SLOT
        CMP WK_CHECK_SLOT
                        BNE WK_BM_LONG_816
                        JMP WK_ALLOC_NEXT
WK_BM_LONG_816:
WK_ALLOC_CHECK:
        JSR WK_SLOT_POINTER
        LDY #31
        LDA (WK_P),Y
        CMP #$A5
                        BNE WK_ALLOC_NEXT
        ; candidate end <= claim start: no overlap.
        LDY #14
        LDX #2
WK_ALLOC_BEFORE:
        LDA WK_END_POS,X
        CMP (WK_P),Y
                        BCC WK_ALLOC_NEXT
                        BNE WK_ALLOC_AFTER_START
        DEY
        DEX
                        BPL WK_ALLOC_BEFORE
                        JMP WK_ALLOC_NEXT
WK_ALLOC_AFTER_START:
        ; candidate start >= claim end: no overlap.
        LDY #12
        CLC
        LDX #0
WK_ALLOC_OLD_END:
        LDA (WK_P),Y
        STA WK_OLD_END,X
        INY
        INX
        CPX #3
                        BNE WK_ALLOC_OLD_END
        LDY #16
        LDA #3
        STA WK_ARITH_N
        CLC
        LDX #0
WK_ALLOC_OLD_ADD:
        LDA (WK_P),Y
        ADC WK_OLD_END,X
        STA WK_OLD_END,X
        INY
        INX
        DEC WK_ARITH_N
                        BNE WK_ALLOC_OLD_ADD
        LDX #2
WK_ALLOC_AFTER:
        LDA WK_POS,X
        CMP WK_OLD_END,X
                        BCC WK_ALLOC_COLLISION
                        BNE WK_ALLOC_NEXT
        DEX
                        BPL WK_ALLOC_AFTER
                        JMP WK_ALLOC_NEXT
WK_ALLOC_COLLISION:
        LDA WK_CHECKING
                        BEQ WK_BM_LONG_871
                        JMP WK_BAD_META
WK_BM_LONG_871:
        STZ WK_POS
        LDA WK_OLD_END
        CMP #1
        LDA WK_OLD_END+1
        ADC #0
        STA WK_POS+1
        LDA WK_OLD_END+2
        ADC #0
        STA WK_POS+2
                        JMP WK_ALLOC_RESTART
WK_ALLOC_NEXT:
        INC WK_SLOT
        LDA WK_SLOT
        CMP #4
                        BEQ WK_BM_LONG_886
                        JMP WK_ALLOC_SCAN
WK_BM_LONG_886:
        LDA WK_CHECKING
                        BEQ WK_ALLOC_PUBLISH
        LDA #0
        RTS
WK_ALLOC_PUBLISH:
        LDA WK_SESSION+12
        AND WK_SESSION+13
        CMP #$FF
                        BNE WK_BM_LONG_895
                        JMP WK_EXHAUSTED
WK_BM_LONG_895:
        INC WK_SESSION+12
                        BNE WK_CLAIM_TICKET
        INC WK_SESSION+13
WK_CLAIM_TICKET:
        JSR WK_SESSION_COMMIT
                        BEQ WK_BM_LONG_901
                        JMP WK_CLAIMS_RETURN
WK_BM_LONG_901:
        JSR WK_ZERO_BUF
        LDX #2
WK_CLAIM_NEW_MAGIC:
        LDA WK_WC_MAGIC,X
        STA WK_BUF,X
        DEX
                        BPL WK_CLAIM_NEW_MAGIC
        LDX #1
WK_CLAIM_OWNER:
        LDA WK_REQ+2,X
        STA WK_BUF+4,X
        LDA WK_SESSION+12,X
        STA WK_BUF+6,X
        DEX
                        BPL WK_CLAIM_OWNER
        LDX #3
WK_CLAIM_NEW_EPOCH:
        LDA WK_SESSION+8,X
        STA WK_BUF+8,X
        STA WK_REQ+6,X
        DEX
                        BPL WK_CLAIM_NEW_EPOCH
        LDX #2
WK_CLAIM_NEW_SPAN:
        LDA WK_POS,X
        STA WK_BUF+12,X
        LDA WK_SIZE,X
        STA WK_BUF+16,X
        STZ WK_REQ+12,X
        DEX
                        BPL WK_CLAIM_NEW_SPAN
        LDA WK_FREE_SLOT
        STA WK_SLOT
        STA WK_REQ+4
        STZ WK_REQ+5
        LDA WK_SESSION+12
        STA WK_REQ+10
        LDA WK_SESSION+13
        STA WK_REQ+11
        LDA #32
        STA WK_N
        JSR WK_SEAL
        JSR WK_SAVE_PACKET
        JSR WK_CLAIM_ADDRESS
        JMP WK_PUBLISH
WK_HANDLE:
        LDA WK_REQ+5
                        BEQ WK_BM_LONG_949
                        JMP WK_STALE
WK_BM_LONG_949:
        LDA WK_REQ+4
        CMP #4
                        BCC WK_BM_LONG_952
                        JMP WK_STALE
WK_BM_LONG_952:
        STA WK_SLOT
        JSR WK_SLOT_POINTER
        LDY #31
        LDA (WK_P),Y
        CMP #$A5
                        BEQ WK_BM_LONG_958
                        JMP WK_STALE
WK_BM_LONG_958:
        LDY #4
        LDX #2
WK_HANDLE_OWNER:
        LDA (WK_P),Y
        CMP WK_REQ,X
                        BEQ WK_BM_LONG_964
                        JMP WK_STALE
WK_BM_LONG_964:
        INY
        INX
        CPX #4
                        BNE WK_HANDLE_OWNER
        LDY #6
        LDX #10
WK_HANDLE_TICKET:
        LDA (WK_P),Y
        CMP WK_REQ,X
                        BEQ WK_BM_LONG_974
                        JMP WK_STALE
WK_BM_LONG_974:
        INY
        INX
        CPX #12
                        BNE WK_HANDLE_TICKET
        LDY #8
        LDX #6
WK_HANDLE_EPOCH:
        LDA (WK_P),Y
        CMP WK_REQ,X
                        BEQ WK_BM_LONG_984
                        JMP WK_STALE
WK_BM_LONG_984:
        INY
        INX
        CPX #10
                        BNE WK_HANDLE_EPOCH
        LDA #0
        RTS
WK_RELEASE:
        JSR WK_CLAIM_ADDRESS
        LDA #32
        STA WK_PACKET_N
        LDA #0
        JMP WK_MARKER
WK_IO:     LDA WK_REQ+15
                        BNE WK_BM_LONG_998
                        JMP WK_BAD_ARG
WK_BM_LONG_998:
        CMP #65
                        BCC WK_BM_LONG_1000
                        JMP WK_BAD_ARG
WK_BM_LONG_1000:
        STA WK_N
        LDA #3
        STA WK_ARITH_N
        CLC
        LDX #0
WK_IO_OFFSET_END:
        LDA WK_REQ+12,X
        ADC WK_N
        STA WK_END_POS,X
        INX
        LDA #0
        STA WK_N
        DEC WK_ARITH_N
                        BNE WK_IO_OFFSET_END
                        BCC WK_BM_LONG_1015
                        JMP WK_BAD_ARG
WK_BM_LONG_1015:
        LDY #18
        LDX #2
WK_IO_BOUND:
        LDA WK_END_POS,X
        CMP (WK_P),Y
                        BCC WK_IO_ADDRESS
                        BEQ WK_BM_LONG_1022
                        JMP WK_BAD_ARG
WK_BM_LONG_1022:
        DEY
        DEX
                        BPL WK_IO_BOUND
WK_IO_ADDRESS:
        LDY #12
        LDA #3
        STA WK_ARITH_N
        CLC
        LDX #0
WK_IO_ADDRESS_ADD:
        LDA (WK_P),Y
        ADC WK_REQ+12,X
        STA WK_ADDR,X
        INY
        INX
        DEC WK_ARITH_N
                        BNE WK_IO_ADDRESS_ADD
        LDA WK_REQ+15
        STA WK_N
        LDA WK_REQ+16
        STA WK_BP
        LDA WK_REQ+17
        STA WK_BP+1
        LDA WK_BP
        PHA
        LDA WK_BP+1
        PHA
        LDA WK_C
        STA WK_SAVE_C
        LDA WK_C+1
        STA WK_SAVE_C+1
        LDA WK_BP
        STA WK_C
        LDA WK_BP+1
        STA WK_C+1
        JSR WK_CPU_RANGE
        STA WK_ERROR
        PLA
        STA WK_BP+1
        PLA
        STA WK_BP
        LDA WK_SAVE_C
        STA WK_C
        LDA WK_SAVE_C+1
        STA WK_C+1
        LDA WK_ERROR
                        BEQ WK_BM_LONG_1069
                        JMP WK_OP_RETURN
WK_BM_LONG_1069:
        ; READ cannot overwrite the caller's request/result block.
        LDA WK_REQ
        CMP #3
                        BNE WK_IO_TRANSFER
        LDA WK_BP
        CLC
        ADC WK_N
        STA WK_TEMP
        LDA WK_BP+1
        ADC #0
        CMP WK_C+1
                        BCC WK_IO_TRANSFER
                        BNE WK_IO_READ_AFTER
        LDA WK_TEMP
        CMP WK_C
                        BCC WK_IO_TRANSFER
                        BEQ WK_IO_TRANSFER
WK_IO_READ_AFTER:
        LDA WK_C
        CLC
        ADC #32
        STA WK_TEMP
        LDA WK_C+1
        ADC #0
        CMP WK_BP+1
                        BCC WK_IO_TRANSFER
                        BEQ WK_BM_LONG_1096
                        JMP WK_BAD_ARG
WK_BM_LONG_1096:
        LDA WK_TEMP
        CMP WK_BP
                        BCC WK_IO_TRANSFER
                        BEQ WK_BM_LONG_1100
                        JMP WK_BAD_ARG
WK_BM_LONG_1100:
WK_IO_TRANSFER:
        LDA WK_REQ
        CMP #4
                        BNE WK_IO_READ
        LDA WK_BP
        STA WK_Q
        LDA WK_BP+1
        STA WK_Q+1
        LDY #0
WK_IO_STAGE:
        LDA (WK_Q),Y
        STA WK_BUF,Y
        INY
        CPY WK_N
                        BNE WK_IO_STAGE
        JSR WK_WRITE_VERIFY
                        BRA WK_IO_RESULT
WK_IO_READ:
        LDA #1
        JSR WK_TRANSFER
WK_IO_RESULT:
        PHA
        LDA WK_R+9
        STA WK_REQ+22
        LDA WK_R+10
        STA WK_REQ+23
        PLA
        CMP #0
        RTS
WK_CPU_RANGE:
        LDA WK_C+1
        CMP #2
                        BCS WK_BM_LONG_1133
                        JMP WK_BAD_ARG
WK_BM_LONG_1133:
        CLC
        LDA WK_C
        ADC WK_N
        STA WK_TEMP
        LDA WK_C+1
        ADC #0
        STA WK_TEMP+1
                        BCC WK_BM_LONG_1141
                        JMP WK_BAD_ARG
WK_BM_LONG_1141:
        CMP #$65
                        BCC WK_CPU_LIBRARY
                        BEQ WK_BM_LONG_1144
                        JMP WK_BAD_ARG
WK_BM_LONG_1144:
        LDA WK_TEMP
                        BEQ WK_BM_LONG_1146
                        JMP WK_BAD_ARG
WK_BM_LONG_1146:
WK_CPU_LIBRARY:
        LDA WK_TEMP+1
        CMP #>$5000
                        BCC WK_CPU_OK
                        BNE WK_CPU_AFTER
        LDA WK_TEMP
                        BEQ WK_CPU_OK
WK_CPU_AFTER:
        LDA WK_C+1
        CMP #>$5040
                        BCS WK_BM_LONG_1157
                        JMP WK_BAD_ARG
WK_BM_LONG_1157:
                        BNE WK_CPU_OK
        LDA WK_C
        CMP #<$5040
                        BCS WK_BM_LONG_1161
                        JMP WK_BAD_ARG
WK_BM_LONG_1161:
WK_CPU_OK:
        LDA WK_TEMP+1
        CMP #$64
        BCC WK_WINDOW_OK
        BNE WK_WINDOW_START
        LDA WK_TEMP
        BEQ WK_WINDOW_OK
WK_WINDOW_START:
        LDA WK_C+1
        CMP #$64
        BCC WK_WINDOW_BAD
        BNE WK_WINDOW_OK
        LDA WK_C
        CMP #$40
        BCS WK_WINDOW_OK
WK_WINDOW_BAD:
        JMP WK_BAD_ARG
WK_WINDOW_OK: LDA #0
        RTS
WK_PROGRAM_CHECK:
        STZ WK_PROG_SLOT
WK_PROG_SCAN:
        LDA WK_PROG_SLOT
        INC A
        LSR A
        LSR A
        STA WK_ADDR+1
        LDA WK_PROG_SLOT
        INC A
        AND #3
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA WK_ADDR
        STZ WK_ADDR+2
        JSR WK_READ64
                        BEQ WK_BM_LONG_1184
                        JMP WK_PROG_RETURN
WK_BM_LONG_1184:
        LDA WK_BUF+63
        CMP #$A5
                        BNE WK_PROG_NEXT
        JSR WK_HEADER_CRC
                        BEQ WK_BM_LONG_1189
                        JMP WK_BAD_META
WK_BM_LONG_1189:
        LDX #2
WK_PROG_MAGIC:
        LDA WK_BUF,X
        CMP WK_SP_MAGIC,X
                        BEQ WK_BM_LONG_1194
                        JMP WK_BAD_META
WK_BM_LONG_1194:
        DEX
                        BPL WK_PROG_MAGIC
        LDA WK_BUF+15
        CMP #2
                        BEQ WK_PROG_TOMBSTONE
        CMP #1
                        BEQ WK_BM_LONG_1201
                        JMP WK_BAD_META
WK_BM_LONG_1201:
        LDA WK_BUF+6
        ORA WK_BUF+7
                        BNE WK_BM_LONG_1204
                        JMP WK_BAD_META
WK_BM_LONG_1204:
        LDA WK_BUF+14
        CMP #8
                        BCS WK_BM_LONG_1207
                        JMP WK_BAD_META
WK_BM_LONG_1207:
        LDA WK_BUF+6
        CMP #1
        LDA WK_BUF+7
        ADC WK_BUF+14
        STA WK_PAGE_END
        LDA #0
        ADC #0
        STA WK_PAGE_END+1
        CMP WK_LAYOUT+6
                        BCC WK_PROG_NEXT
                        BEQ WK_BM_LONG_1218
                        JMP WK_BAD_META
WK_BM_LONG_1218:
        LDA WK_PAGE_END
        CMP WK_LAYOUT+5
                        BCC WK_PROG_NEXT
                        BEQ WK_PROG_NEXT
        JMP WK_BAD_META
WK_PROG_TOMBSTONE:
        LDA WK_BUF+6
        ORA WK_BUF+7
        ORA WK_BUF+14
                        BEQ WK_BM_LONG_1228
                        JMP WK_BAD_META
WK_BM_LONG_1228:
WK_PROG_NEXT:
        INC WK_PROG_SLOT
        LDA WK_PROG_SLOT
        CMP #8
                        BEQ WK_BM_LONG_1233
                        JMP WK_PROG_SCAN
WK_BM_LONG_1233:
        LDA #0
WK_PROG_RETURN:
        RTS
WK_RESIZE: LDX #7
WK_RESIZE_KEY:
        LDA WK_REQ+24,X
        CMP WK_RESIZE_MAGIC,X
                        BEQ WK_BM_LONG_1241
                        JMP WK_BAD_ARG
WK_BM_LONG_1241:
        DEX
                        BPL WK_RESIZE_KEY
        LDA WK_REQ+21
                        BNE WK_BM_LONG_1245
                        JMP WK_BAD_ARG
WK_BM_LONG_1245:
        CMP #5
                        BCC WK_BM_LONG_1247
                        JMP WK_BAD_ARG
WK_BM_LONG_1247:
        CMP WK_UNITS
                        BNE WK_BM_LONG_1249
                        JMP WK_QUERY
WK_BM_LONG_1249:
        STA WK_NEW_UNITS
        ; Check prospective boundary against all saved records and claims.
        LDA WK_LAYOUT+5
        PHA
        LDA WK_LAYOUT+6
        PHA
        JSR WK_NEW_BOUNDARY
        JSR WK_PROGRAM_CHECK
        STA WK_ERROR
        STZ WK_SLOT
WK_RESIZE_CLAIMS:
        LDA WK_ERROR
                        BNE WK_RESIZE_RESTORE
        JSR WK_SLOT_POINTER
        LDY #31
        LDA (WK_P),Y
        CMP #$A5
                        BNE WK_RESIZE_NEXT
        LDY #14
        LDA (WK_P),Y
        CMP WK_LAYOUT+6
                        BCC WK_RESIZE_CONFLICT
                        BNE WK_RESIZE_NEXT
        DEY
        LDA (WK_P),Y
        CMP WK_LAYOUT+5
                        BCC WK_RESIZE_CONFLICT
WK_RESIZE_NEXT:
        INC WK_SLOT
        LDA WK_SLOT
        CMP #4
                        BNE WK_RESIZE_CLAIMS
                        BRA WK_RESIZE_RESTORE
WK_RESIZE_CONFLICT:
        LDA #$4A
        STA WK_ERROR
WK_RESIZE_RESTORE:
        PLA
        STA WK_LAYOUT+6
        PLA
        STA WK_LAYOUT+5
        LDA WK_ERROR
                        BEQ WK_BM_LONG_1292
                        JMP WK_OP_RETURN
WK_BM_LONG_1292:
        JSR WK_REPAIR_PRIMARY
                        BEQ WK_BM_LONG_1294
                        JMP WK_OP_RETURN
WK_BM_LONG_1294:
        JSR WK_NEW_BOUNDARY
        JSR WK_LAYOUT_INCREMENT
                        BEQ WK_BM_LONG_1297
                        JMP WK_OP_RETURN
WK_BM_LONG_1297:
        JSR WK_LAYOUT_UPDATE
                        BEQ WK_BM_LONG_1299
                        JMP WK_OP_RETURN
WK_BM_LONG_1299:
        LDA WK_NEW_UNITS
        STA WK_UNITS
        JMP WK_QUERY
WK_NEW_BOUNDARY:
        LDA WK_NEW_UNITS
        LSR A
        LSR A
        STA WK_LAYOUT+6
        LDA WK_NEW_UNITS
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA WK_LAYOUT+5
        RTS
WK_LAYOUT_INCREMENT:
        LDX #0
WK_LAYOUT_INC:
        INC WK_LAYOUT+8,X
                        BNE WK_LAYOUT_INC_OK
        INX
        CPX #4
                        BNE WK_LAYOUT_INC
        JMP WK_EXHAUSTED
WK_LAYOUT_INC_OK:
        LDA #0
        RTS
WK_LAYOUT_PACKET:
        LDX #63
WK_LAYOUT_PACKET_COPY:
        LDA WK_LAYOUT,X
        STA WK_BUF,X
        DEX
                        BPL WK_LAYOUT_PACKET_COPY
        STZ WK_BUF+63
        LDA #64
        STA WK_N
        JSR WK_SEAL
        JMP WK_SAVE_PACKET
WK_LAYOUT_UPDATE:
        JSR WK_LAYOUT_PACKET
        JSR WK_ZERO_ADDR
        LDA #$40
        STA WK_ADDR
        LDA #2
        STA WK_ADDR+1
        JSR WK_PUBLISH
                        BNE WK_LAYOUT_WRITE_RETURN
        ; A remains authoritative until verified invalidation. Then B is
        ; authoritative; STORE refuses until A is repaired/republished.
        JSR WK_ZERO_ADDR
        LDA #64
        STA WK_PACKET_N
        LDA #0
        JSR WK_MARKER
                        BNE WK_LAYOUT_WRITE_RETURN
        BRA WK_WRITE_PRIMARY
WK_REPAIR_PRIMARY:
        LDA WK_FALLBACK
                        BEQ WK_LAYOUT_WRITE_RETURN
WK_WRITE_PRIMARY:
        JSR WK_LAYOUT_PACKET
        JSR WK_ZERO_ADDR
        LDA #64
        STA WK_N
        JSR WK_PUBLISH
                        BNE WK_LAYOUT_WRITE_RETURN
        STZ WK_FALLBACK
        LDA #0
WK_LAYOUT_WRITE_RETURN:
        RTS
WK_REPAIR: LDX #7
WK_REPAIR_KEY:
        LDA WK_REQ+24,X
        CMP WK_REPAIR_MAGIC,X
                        BEQ WK_BM_LONG_1377
                        JMP WK_BAD_ARG
WK_BM_LONG_1377:
        DEX
                        BPL WK_REPAIR_KEY
        BRA WK_REPAIR_PRIMARY
WK_UPGRADE:
        LDX #7
WK_UPGRADE_KEY:
        LDA WK_REQ+24,X
        CMP WK_UPGRADE_MAGIC,X
                        BEQ WK_BM_LONG_1386
                        JMP WK_BAD_ARG
WK_BM_LONG_1386:
        DEX
                        BPL WK_UPGRADE_KEY
        JSR WK_LOAD_LAYOUT
                        BEQ WK_BM_LONG_1390
                        JMP WK_OP_RETURN
WK_BM_LONG_1390:
        LDA WK_LEGACY
                        BEQ WK_UPGRADE_ALREADY
        JSR WK_PROGRAM_CHECK
                        BEQ WK_BM_LONG_1394
                        JMP WK_OP_RETURN
WK_BM_LONG_1394:
        JSR WK_INITIAL_SESSION
                        BEQ WK_BM_LONG_1396
                        JMP WK_OP_RETURN
WK_BM_LONG_1396:
        LDA #2
        STA WK_LAYOUT+2
        LDA #1
        STA WK_LAYOUT+8
        JSR WK_LAYOUT_UPDATE
                        BEQ WK_BM_LONG_1402
                        JMP WK_OP_RETURN
WK_BM_LONG_1402:
        STZ WK_LEGACY
WK_UPGRADE_ALREADY:
        LDA #0
        RTS
WK_FORMAT: LDX #7
WK_FORMAT_KEY:
        LDA WK_REQ+24,X
        CMP WK_FORMAT_MAGIC,X
                        BEQ WK_BM_LONG_1411
                        JMP WK_BAD_ARG
WK_BM_LONG_1411:
        DEX
                        BPL WK_FORMAT_KEY
        ; Both layout markers invalidated before changing any record.
        JSR WK_ZERO_ADDR
        LDA #64
        STA WK_PACKET_N
        LDA #0
        JSR WK_MARKER
                        BEQ WK_BM_LONG_1420
                        JMP WK_OP_RETURN
WK_BM_LONG_1420:
        LDA #$40
        STA WK_ADDR
        LDA #2
        STA WK_ADDR+1
        LDA #0
        JSR WK_MARKER
                        BEQ WK_BM_LONG_1427
                        JMP WK_OP_RETURN
WK_BM_LONG_1427:
        STZ WK_PROG_SLOT
WK_FORMAT_DIRECTORY:
        LDA WK_PROG_SLOT
        INC A
        LSR A
        LSR A
        STA WK_ADDR+1
        LDA WK_PROG_SLOT
        INC A
        AND #3
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA WK_ADDR
        LDA #0
        JSR WK_MARKER
                        BEQ WK_BM_LONG_1447
                        JMP WK_OP_RETURN
WK_BM_LONG_1447:
        INC WK_PROG_SLOT
        LDA WK_PROG_SLOT
        CMP #8
                        BNE WK_FORMAT_DIRECTORY
        ; Clear every claim marker, including corrupt old-epoch packets.
        ; LOAD_CLAIMS validates committed headers before checking epochs.
        JSR WK_CLEAR_CLAIMS
                        BEQ WK_BM_LONG_1455
                        JMP WK_OP_RETURN
WK_BM_LONG_1455:
        ; Retain a valid epoch counter when formatting an existing store.
        JSR WK_SESSION_LOAD
                        BNE WK_FORMAT_FRESH_SESSION
        JSR WK_NEW_EPOCH
                        BEQ WK_BM_LONG_1460
                        JMP WK_OP_RETURN
WK_BM_LONG_1460:
                        BRA WK_FORMAT_LAYOUT
WK_FORMAT_FRESH_SESSION:
        JSR WK_INITIAL_SESSION_RECORD
                        BEQ WK_BM_LONG_1464
                        JMP WK_OP_RETURN
WK_BM_LONG_1464:
WK_FORMAT_LAYOUT:
        JSR WK_ZERO_BUF
        LDX #7
WK_FORMAT_LAYOUT_COPY:
        LDA WK_INITIAL_LAYOUT,X
        STA WK_LAYOUT,X
        DEX
                        BPL WK_FORMAT_LAYOUT_COPY
        LDX #63
WK_FORMAT_LAYOUT_ZERO:
        STZ WK_LAYOUT,X
        DEX
        CPX #7
                        BNE WK_FORMAT_LAYOUT_ZERO
        LDA #1
        STA WK_LAYOUT+8
        STZ WK_FALLBACK
        JSR WK_LAYOUT_UPDATE
                        BEQ WK_BM_LONG_1483
                        JMP WK_OP_RETURN
WK_BM_LONG_1483:
        LDA #0
        RTS
WK_CLEAR_CLAIMS:
        STZ WK_SLOT
WK_INIT_CLEAR_CLAIMS:
        JSR WK_CLAIM_ADDRESS
        LDA #32
        STA WK_PACKET_N
        LDA #0
        JSR WK_MARKER
                        BNE WK_INIT_RETURN
        INC WK_SLOT
        LDA WK_SLOT
        CMP #4
                        BNE WK_INIT_CLEAR_CLAIMS
        LDA #0
        RTS
WK_INITIAL_SESSION:
        ; Explicit FORMAT/UPGRADE initializes only management cells.
        JSR WK_CLEAR_CLAIMS
                        BNE WK_INIT_RETURN
WK_INITIAL_SESSION_RECORD:
        LDA #$80
        STA WK_ADDR
        LDA #2
        STA WK_ADDR+1
        LDA #64
        STA WK_PACKET_N
        LDA #0
        JSR WK_MARKER
                        BNE WK_INIT_RETURN
        LDA #$C0
        STA WK_ADDR
        LDA #0
        JSR WK_MARKER
                        BNE WK_INIT_RETURN
        JSR WK_ZERO_BUF
        LDX #2
WK_INIT_WS_MAGIC:
        LDA WK_WS_MAGIC,X
        STA WK_BUF,X
        DEX
                        BPL WK_INIT_WS_MAGIC
        LDA #1
        STA WK_BUF+4
        STA WK_BUF+8
        LDX #63
WK_INIT_SESSION_COPY:
        LDA WK_BUF,X
        STA WK_SESSION,X
        DEX
                        BPL WK_INIT_SESSION_COPY
        LDA #64
        STA WK_N
        JSR WK_SEAL
        JSR WK_SAVE_PACKET
        LDA #$80
        STA WK_ADDR
        STA WK_SESSION_ADDR
        JSR WK_PUBLISH
                        BNE WK_INIT_RETURN
        LDA #1
        STA WK_RESET_LATCH
        LDA #0
WK_INIT_RETURN:
        RTS
WK_CONSOLE:
        SEI
        CLD
        LDX #<WK_TITLE
        LDY #>WK_TITLE
        JSR WK_PRINT
WK_CON_HELP_TEXT:
        LDX #<WK_HELP_TEXT
        LDY #>WK_HELP_TEXT
        JSR WK_PRINT
WK_PROMPT: LDX #<WK_PROMPT_TEXT
        LDY #>WK_PROMPT_TEXT
        JSR WK_PRINT
        JSR B29_LINE_3
                        BCC WK_PROMPT
        LDX #31
WK_CON_CLEAR:
        STZ WK_REQ,X
        DEX
                        BPL WK_CON_CLEAR
        LDA WK_LINE
                        BEQ WK_PROMPT
        CMP #'WK_P'
                        BEQ WK_CON_RESIZE
        CMP #'H'
                        BEQ WK_CON_HELP
        LDX WK_LINE+1
                        BEQ WK_BM_LONG_1577
                        JMP WK_CON_BAD
WK_BM_LONG_1577:
        CMP #'WK_Q'
                        BNE WK_BM_LONG_1579
                        JMP WK_QUIT
WK_BM_LONG_1579:
        CMP #'?'
                        BEQ WK_CON_QUERY
        CMP #'F'
                        BNE WK_BM_LONG_1583
                        JMP WK_CON_FORMAT
WK_BM_LONG_1583:
        CMP #'U'
                        BNE WK_BM_LONG_1585
                        JMP WK_CON_UPGRADE
WK_BM_LONG_1585:
        CMP #'V'
                        BNE WK_BM_LONG_1587
                        JMP WK_CON_REPAIR
WK_BM_LONG_1587:
        LDA #$44
                        JMP WK_CON_RESULT
WK_CON_HELP:
        LDX #4
WK_CON_HELP_MATCH:
        LDA WK_LINE,X
        CMP WK_HELP_COMMAND,X
                        BEQ WK_BM_LONG_1595
                        JMP WK_CON_BAD
WK_BM_LONG_1595:
        DEX
                        BPL WK_CON_HELP_MATCH
                        BRA WK_CON_HELP_TEXT
WK_CON_QUERY:
        JSR WK_OPERATION
                        BEQ WK_BM_LONG_1601
                        JMP WK_CON_RESULT
WK_BM_LONG_1601:
        JSR WK_CAPACITY_TEXT
                        JMP WK_PROMPT
WK_CON_RESIZE:
        LDA WK_LINE+1
        CMP #' '
                        BEQ WK_BM_LONG_1607
                        JMP WK_CON_BAD
WK_BM_LONG_1607:
        LDA WK_LINE+4
                        BEQ WK_BM_LONG_1609
                        JMP WK_CON_BAD
WK_BM_LONG_1609:
        LDX #6
WK_CON_SIZE_MATCH:
        LDA WK_LINE+2
        CMP WK_UNIT_TEXT,X
                        BNE WK_CON_SIZE_NEXT
        LDA WK_LINE+3
        CMP WK_UNIT_TEXT+1,X
                        BEQ WK_CON_SIZE_FOUND
WK_CON_SIZE_NEXT:
        DEX
        DEX
                        BPL WK_CON_SIZE_MATCH
                        JMP WK_CON_BAD
WK_CON_SIZE_FOUND:
        TXA
        LSR A
        INC A
        STA WK_CON_UNITS
        JSR WK_OPERATION
                        BEQ WK_BM_LONG_1629
                        JMP WK_CON_RESULT
WK_BM_LONG_1629:
        LDA WK_CON_UNITS
        CMP WK_REQ+21
                        BNE WK_CON_SIZE_PREVIEW
        LDX #<WK_NO_CHANGE_TEXT
        LDY #>WK_NO_CHANGE_TEXT
                        JMP WK_CON_MESSAGE
WK_CON_SIZE_PREVIEW:
        STA WK_REQ+21
        JSR WK_CAPACITY_TEXT
        LDA #5
        LDX #<WK_RESIZE_MAGIC
        LDY #>WK_RESIZE_MAGIC
                        JMP WK_CON_CONFIRM
WK_CON_FORMAT:
        LDA #6
        LDX #<WK_FORMAT_MAGIC
        LDY #>WK_FORMAT_MAGIC
                        JMP WK_CON_CONFIRM
WK_CON_UPGRADE:
        LDA #7
        LDX #<WK_UPGRADE_MAGIC
        LDY #>WK_UPGRADE_MAGIC
                        JMP WK_CON_CONFIRM
WK_CON_REPAIR:
        LDA #8
        LDX #<WK_REPAIR_MAGIC
        LDY #>WK_REPAIR_MAGIC
WK_CON_CONFIRM:
        STA WK_REQ
        STX WK_Q
        STY WK_Q+1
        LDY #7
WK_CON_KEY_COPY:
        LDA (WK_Q),Y
        STA WK_REQ+24,Y
        DEY
                        BPL WK_CON_KEY_COPY
        LDX #<WK_CONFIRM_TEXT
        LDY #>WK_CONFIRM_TEXT
        LDA WK_REQ
        CMP #6
                        BEQ WK_CON_FORMAT_PROMPT
        CMP #5
                        BNE WK_CON_PROMPT_CONFIRM
        LDX #<WK_APPLY_TEXT
        LDY #>WK_APPLY_TEXT
                        BRA WK_CON_PROMPT_CONFIRM
WK_CON_FORMAT_PROMPT:
        LDX #<WK_FORMAT_TEXT
        LDY #>WK_FORMAT_TEXT
WK_CON_PROMPT_CONFIRM:
        JSR WK_PRINT
        JSR WK_LINE_READ
                        BCC WK_CON_CANCEL
        LDA WK_REQ
        CMP #5
                        BEQ WK_CON_CHECK_Y
        CMP #6
                        BNE WK_CON_CHECK_YES
        LDX #11
WK_CON_FORMAT_CONFIRM:
        LDA WK_LINE,X
        CMP WK_FORMAT_CONFIRM,X
                        BNE WK_CON_CANCEL
        DEX
                        BPL WK_CON_FORMAT_CONFIRM
                        BRA WK_CON_EXEC
WK_CON_CHECK_Y:
        LDA WK_LINE
        CMP #'Y'
                        BNE WK_CON_CANCEL
        LDA WK_LINE+1
                        BEQ WK_CON_EXEC
                        BRA WK_CON_CANCEL
WK_CON_CHECK_YES:
        LDX #3
WK_CON_YES:
        LDA WK_LINE,X
        CMP WK_YES_MAGIC,X
                        BNE WK_CON_CANCEL
        DEX
                        BPL WK_CON_YES
WK_CON_EXEC:
        JSR WK_OPERATION
WK_CON_RESULT:
        CMP #0
                        BNE WK_CON_ERROR
        LDA WK_REQ
        SEC
        SBC #5
        TAX
        LDA WK_SUCCESS_LO,X
        LDY WK_SUCCESS_HI,X
        TAX
                        JMP WK_CON_MESSAGE
WK_CON_ERROR: JSR B29_ERROR_HOOK

        LDX #WK_STATUS_COUNT-1
WK_CON_STATUS_MATCH:
        CMP WK_STATUS_CODES,X
                        BEQ WK_CON_STATUS_TEXT
        DEX
                        BPL WK_CON_STATUS_MATCH
        PHA
        LDX #<WK_RESULT_TEXT
        LDY #>WK_RESULT_TEXT
        JSR WK_PRINT
        PLA
        JSR WK_HEX
        JSR WK_NL
        JMP WK_PROMPT
WK_CON_STATUS_TEXT:
        LDY WK_STATUS_HI,X
        LDA WK_STATUS_LO,X
        TAX
WK_CON_MESSAGE:
        JSR WK_PRINT
        JMP WK_PROMPT
WK_CON_CANCEL: JSR B29_ERROR_HOOK

        LDX #<WK_CANCELED_TEXT
        LDY #>WK_CANCELED_TEXT
                        JMP WK_CON_MESSAGE
WK_CON_BAD:LDA #$44
                        JMP WK_CON_RESULT
WK_QUIT:   JSR WK_RESTORE_WINDOW
        JMP $7E67
; Four fixed layouts: small decimal tables avoid a general 24-bit formatter.
WK_CAPACITY_TEXT:
        LDX #<WK_PROGRAM_TEXT
        LDY #>WK_PROGRAM_TEXT
        JSR WK_PRINT
        LDA WK_REQ+21
        DEC A
        ASL A
        TAX
        LDA WK_UNIT_TEXT,X
        JSR WK_PUTC
        INX
        LDA WK_UNIT_TEXT,X
        JSR WK_PUTC
        LDX #<WK_WORKSPACE_TEXT
        LDY #>WK_WORKSPACE_TEXT
        JSR WK_PRINT
        LDA WK_REQ+21
        DEC A
        TAX
        LDY WK_CAPACITY_HI,X
        LDA WK_CAPACITY_LO,X
        TAX
        JSR WK_PRINT
        LDX #<WK_BYTES_TEXT
        LDY #>WK_BYTES_TEXT
        BRA WK_PRINT
WK_LINE_READ:
        STZ WK_LINE_N
        STZ WK_OVERFLOW
WK_LINE_WAIT:
        JSR WK_GETC
        CMP #3
                        BEQ WK_LINE_CANCEL
        CMP #$1B
                        BEQ WK_LINE_CANCEL
        CMP #10
                        BEQ WK_LINE_WAIT
        CMP #13
                        BEQ WK_LINE_END
        CMP #'a'
                        BCC WK_LINE_CHAR
        CMP #'z'+1
                        BCS WK_LINE_CHAR
        AND #$DF
WK_LINE_CHAR:
        LDX WK_LINE_N
        CPX #15
                        BCS WK_LINE_FULL
        STA WK_LINE,X
        INC WK_LINE_N
        JSR WK_PUTC
                        JMP WK_LINE_WAIT
WK_LINE_FULL:
        LDA #1
        STA WK_OVERFLOW
                        JMP WK_LINE_WAIT
WK_LINE_END:
        LDX WK_LINE_N
        STZ WK_LINE,X
        JSR WK_NL
        LDA WK_OVERFLOW
                        BNE WK_LINE_CANCEL
        SEC
        RTS
WK_LINE_CANCEL: JSR B29_CANCEL_HOOK

        JSR WK_NL
        CLC
        RTS
WK_PRINT:  STX WK_Q
        STY WK_Q+1
        LDY #0
WK_PRINT_LOOP:
        LDA (WK_Q),Y
                        BEQ WK_PRINT_END
        JSR WK_PUTC
        INY
                        BRA WK_PRINT_LOOP
WK_PRINT_END:
        RTS
WK_SV_MAGIC DB "SV",1
WK_SM_MAGIC DB "SM",1,1
WK_WS_MAGIC DB "WS",1
WK_WC_MAGIC DB "WC",1
WK_SP_MAGIC DB "SP",1
WK_INITIAL_LAYOUT DB "SS",2,8,8,0,1,0
WK_MAX_END DB $E0,$FF,1
WK_FORMAT_MAGIC DB "FORMAT!!"
WK_RESIZE_MAGIC DB "RESIZE!!"
WK_UPGRADE_MAGIC DB "UPGRADE!"
WK_REPAIR_MAGIC DB "REPAIR!!"
WK_YES_MAGIC DB "YES",0
WK_FORMAT_CONFIRM DB "FORMAT SRAM",0
WK_TITLE DB "WORK 1.4",13,10,0
WK_HELP_COMMAND DB "HELP",0
WK_HELP_TEXT DB "? capacity; P 16/32/48/64 (KiB); U upgrade; V repair; F format; HELP; Q",13,10,0
WK_PROMPT_TEXT DB "WORK> ",0
WK_UNIT_TEXT DB "16324864"
WK_PROGRAM_TEXT DB "Programs: ",0
WK_WORKSPACE_TEXT DB " KiB; workspace: ",0
WK_BYTES_TEXT DB " bytes",13,10,0
WK_CAP16 DB "114656",0
WK_CAP32 DB "98272",0
WK_CAP48 DB "81888",0
WK_CAP64 DB "65504",0
WK_CAPACITY_LO DB <WK_CAP16,<WK_CAP32,<WK_CAP48,<WK_CAP64
WK_CAPACITY_HI DB >WK_CAP16,>WK_CAP32,>WK_CAP48,>WK_CAP64
WK_APPLY_TEXT DB "Apply? [y/N]: ",0
WK_CONFIRM_TEXT DB "Changes storage metadata. Type YES: ",0
WK_FORMAT_TEXT DB "Clear program/claim metadata. Type FORMAT SRAM: ",0
WK_RESULT_TEXT DB "WORK error: $",0
WK_NO_CHANGE_TEXT DB "No change.",13,10,0
WK_CANCELED_TEXT DB "Canceled.",13,10,0
WK_RESIZED_TEXT DB "Resized.",13,10,0
WK_FORMATTED_TEXT DB "Formatted.",13,10,0
WK_UPGRADED_TEXT DB "Upgraded.",13,10,0
WK_REPAIRED_TEXT DB "Repaired.",13,10,0
WK_SUCCESS_LO DB <WK_RESIZED_TEXT,<WK_FORMATTED_TEXT,<WK_UPGRADED_TEXT,<WK_REPAIRED_TEXT
WK_SUCCESS_HI DB >WK_RESIZED_TEXT,>WK_FORMATTED_TEXT,>WK_UPGRADED_TEXT,>WK_REPAIRED_TEXT
WK_STATUS_COUNT EQU 8
WK_STATUS_CODES DB $40,$41,$44,$45,$48,$49,$4A,$80
WK_UNINITIALIZED_TEXT DB "Storage not initialized.",13,10,0
WK_INVALID_STORAGE_TEXT DB "Storage invalid or program exceeds boundary.",13,10,0
WK_INVALID_COMMAND_TEXT DB "Invalid command. Use HELP.",13,10,0
WK_VERIFY_TEXT DB "Write verification failed.",13,10,0
WK_EXHAUSTED_TEXT DB "Counter exhausted.",13,10,0
WK_UPGRADE_TEXT DB "Upgrade required. Use U.",13,10,0
WK_CONFLICT_TEXT DB "Resize refused: workspace overlaps.",13,10,0
WK_ABSENT_TEXT DB "SPI SRAM unavailable.",13,10,0
WK_STATUS_LO DB <WK_UNINITIALIZED_TEXT,<WK_INVALID_STORAGE_TEXT,<WK_INVALID_COMMAND_TEXT,<WK_VERIFY_TEXT,<WK_EXHAUSTED_TEXT,<WK_UPGRADE_TEXT,<WK_CONFLICT_TEXT,<WK_ABSENT_TEXT
WK_STATUS_HI DB >WK_UNINITIALIZED_TEXT,>WK_INVALID_STORAGE_TEXT,>WK_INVALID_COMMAND_TEXT,>WK_VERIFY_TEXT,>WK_EXHAUSTED_TEXT,>WK_UPGRADE_TEXT,>WK_CONFLICT_TEXT,>WK_ABSENT_TEXT
WK_REQ EQU $6800
WK_BUF EQU $6400
WK_EXPECT EQU $6860
WK_EXPECT_PACKET EQU $68A0
WK_LAYOUT EQU $68E0
WK_SESSION EQU $6920
WK_CLAIMS EQU $6960
WK_LINE EQU $69E0
WK_ADDR EQU $69F0
WK_SAVE_ADDR EQU $69F3
WK_POS EQU $69F6
WK_SIZE EQU $69F9
WK_END_POS EQU $69FC
WK_OLD_END EQU $69FF
WK_BP EQU $6A02
WK_SAVE_C EQU $6A04
WK_CRC EQU $6A06
WK_TEMP EQU $6A08
WK_PAGE_END EQU $6A0A
WK_N EQU $6A0C
WK_CRC_N EQU $6A0D
WK_PACKET_N EQU $6A0E
WK_ERROR EQU $6A0F
WK_LEGACY EQU $6A10
WK_FALLBACK EQU $6A11
WK_UNITS EQU $6A12
WK_NEW_UNITS EQU $6A13
WK_SESSION_VALID EQU $6A14
WK_SESSION_ADDR EQU $6A15
WK_SLOT EQU $6A16
WK_FREE_SLOT EQU $6A17
WK_PROG_SLOT EQU $6A18
WK_LINE_N EQU $6A19
WK_OVERFLOW EQU $6A1A
WK_ARITH_N EQU $6A1B
WK_CHECKING EQU $6A1C
WK_CHECK_SLOT EQU $6A1D
WK_CON_UNITS EQU $6A1E
WK_APP_END:
