; Bounded LZSS RAM decoder. Packed input is an admitted RP component.
; Output below5000 for MAINT or6B00-77FF for its private PROGRAM provider.
; Flags low-bit first:1 literal;0 little12-bit(distance-1)/4-bit(length-3).
; Parameters6708-6717; sourceE0, outputE2, matchE6. No owner ZP.
        MODULE COMPACT_DECODE
        INCLUDE "compact-bindings.inc"
        CODE
CD_START:
        LDA CD_BANK
        JSR CD_SELECT
        STZ CD_BITS
CD_TOKEN:
        LDA CD_DST
        CMP CD_LIMIT
        LDA CD_DST+1
        SBC CD_LIMIT+1
        BCS CD_DONE
        LDA CD_BITS
        BNE CD_FLAG
        JSR CD_READ
        STA CD_FLAGS
        LDA #8
        STA CD_BITS
CD_FLAG:
        DEC CD_BITS
        LSR CD_FLAGS
        BCC CD_MATCH_TOKEN
        JSR CD_READ
        JSR CD_PUT
        BRA CD_TOKEN
CD_MATCH_TOKEN:
        JSR CD_READ
        STA CD_DISTANCE
        JSR CD_READ
        PHA
        AND #$F0
        LSR A
        LSR A
        LSR A
        LSR A
        STA CD_DISTANCE+1
        PLA
        AND #15
        CLC
        ADC #3
        STA CD_LENGTH
        INC CD_DISTANCE
        BNE CD_DISTANCE_READY
        INC CD_DISTANCE+1
CD_DISTANCE_READY:
        SEC
        LDA CD_DST
        SBC CD_DISTANCE
        STA CD_MATCH
        LDA CD_DST+1
        SBC CD_DISTANCE+1
        STA CD_MATCH+1
        BCC CD_BAD
        LDA CD_MATCH
        CMP CD_ORIGIN
        LDA CD_MATCH+1
        SBC CD_ORIGIN+1
        BCC CD_BAD
CD_COPY:
        LDA (CD_MATCH)
        JSR CD_PUT
        INC CD_MATCH
        BNE CD_COPY_NEXT
        INC CD_MATCH+1
CD_COPY_NEXT:
        DEC CD_LENGTH
        BNE CD_COPY
        BRA CD_TOKEN
CD_READ:
        ; RAM qualification uses two disjoint source regions so packed input
        ; never overlaps expanded code or the decoder. Production bank1 input
        ; is contiguous ROM; only the RAM fixture bank3 uses this split.
        LDA CD_BANK
        CMP #3
        BNE CD_CONTIGUOUS
        LDA CD_SRC+1
        CMP #$1F
        BNE CD_CONTIGUOUS
        LDA #$58
        STA CD_SRC+1
CD_CONTIGUOUS:
        LDA CD_SRC
        CMP CD_SOURCE_END
        LDA CD_SRC+1
        SBC CD_SOURCE_END+1
        BCS CD_BAD
        LDA (CD_SRC)
        INC CD_SRC
        BNE CD_READ_DONE
        INC CD_SRC+1
CD_READ_DONE:
        RTS
CD_PUT:
        PHA
        LDA CD_DST
        CMP CD_LIMIT
        LDA CD_DST+1
        SBC CD_LIMIT+1
        BCS CD_BAD
        PLA
        STA (CD_DST)
        INC CD_DST
        BNE CD_PUT_DONE
        INC CD_DST+1
CD_PUT_DONE:
        RTS
CD_DONE:
        LDA CD_SRC
        CMP CD_SOURCE_END
        BNE CD_BAD
        LDA CD_SRC+1
        CMP CD_SOURCE_END+1
        BNE CD_BAD
        LDA #3
        JSR CD_SELECT
        LDA CD_ORIGIN
        STA CD_SRC
        LDA CD_ORIGIN+1
        STA CD_SRC+1
        JSR CD_CRC_INIT
CD_CRC:
        LDA (CD_SRC)
        JSR CD_CRC_BYTE
        INC CD_SRC
        BNE CD_CRC_NEXT
        INC CD_SRC+1
CD_CRC_NEXT:
        LDA CD_SRC
        CMP CD_LIMIT
        BNE CD_CRC
        LDA CD_SRC+1
        CMP CD_LIMIT+1
        BNE CD_CRC
        LDA CD_CRC_VALUE
        CMP CD_EXPECTED
        BNE CD_BAD
        LDA CD_CRC_VALUE+1
        CMP CD_EXPECTED+1
        BNE CD_BAD
        RTS
CD_BAD:
        LDA #3
        JSR CD_SELECT
        JMP $F004
CD_END:
        ENDMOD
        END
