; Durable EEPROM journal. B3-only ROM entry, foreground, no IRQ/NMI callers.
; Monitor-owned 6B00-6BFF scratch overlaps flash staging, never used concurrently.
        MODULE JOURNAL
        XDEF START
        XDEF JOURNAL_END
        INCLUDE "kernel-rtc-api.inc"
        INCLUDE "journal-eq.inc"
        INCLUDE "journal-transport.inc"
P EQU $E4
        CODE
START DB "PJ",2,1        ; internal format 2 reports durable save/ACK separately
        JMP ENTER
ENTER:
        PHP
        SEI
        CLD
        LDA J_LOCK
        BNE IN_USE
        INC J_LOCK
        STZ J_OUTCOME
        STX J_OP
        CPX #6
        BCS BAD_REQUEST
        CPX #J_CLEAR_ALL_OP
        BEQ AUTHORIZE_ALL
        CPX #J_CLEAR_OP
        BNE DISPATCH
        LDA J_KEY
        CMP #'C'
        BNE DENIED
        BRA AUTHORIZE_L
AUTHORIZE_ALL:
        LDA J_KEY
        CMP #'A'
        BNE DENIED
AUTHORIZE_L:
        LDA J_KEY+1
        CMP #'L'
        BNE DENIED
        STZ J_KEY
        STZ J_KEY+1
DISPATCH:
        LDA J_OP
        BEQ SCAN_RETURN
        CMP #J_CLEAR_ALL_OP
        BEQ CLEAR_ALL
        JSR SCAN
        BCC RETURN
        LDA J_OP
        CMP #J_CLEAR_OP
        BEQ CLEAR_ONE
        CMP #J_RECONCILE_OP
        BEQ RECONCILE
        JSR RTC_STATUS
        BCC RETURN
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
        BEQ NO_EVENT
        JSR WRITE_ALLOWED
        BCC RETURN
        JSR FIND_MATCH
        LDA J_MATCH
        CMP #$FF
        BNE SAVED
        JSR NEW_RECORD
        BCC RETURN
SAVED:
        LDA #1
        STA J_OUTCOME
        LDA J_OP
        CMP #J_SAVE_OP
        BEQ SUCCESS
        LDA #'P'
        STA RTC_KEY
        LDA #'A'
        STA RTC_KEY+1
        JSR RTC_ACK_POWER
        BCC RETURN
        JSR RTC_STATUS
        BCC RETURN
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
        BNE VERIFY_ERROR
        LDA #3
        STA J_OUTCOME
        JSR MARK_CLEARED
        BRA RETURN
NO_EVENT:
        BRA SUCCESS
RECONCILE:
        JSR RTC_STATUS
        BCC RETURN
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
        BNE BAD_REQUEST
        LDA J_LATEST
        STA J_MATCH
        CMP #$FF
        BEQ SUCCESS
        JSR WRITE_ALLOWED
        BCC RETURN
        JSR MARK_CLEARED
        BRA RETURN
SCAN_RETURN:
        JSR SCAN
        BRA RETURN
SUCCESS:
        LDA #0
RETURN:
        STA J_RESULT
        STZ J_LOCK
        PLP
        LDA J_RESULT
        BEQ GOOD
        CLC
        RTS
GOOD:
        SEC
        RTS
IN_USE:
        PLP
        LDA #8
        CLC
        RTS
DENIED:
        STZ J_KEY
        STZ J_KEY+1
        LDA #6
        BRA RETURN
BAD_REQUEST:
        LDA #9
        BRA RETURN
VERIFY_ERROR:
        LDA #J_VERIFY_FAILED
        BRA RETURN

; SCAN never writes. FF slots are available; unknown layouts require CLEAR ALL.
SCAN:
        STZ J_VALID
        STZ J_PENDING
        STZ J_SCAN_SLOT
        LDA #$FF
        STA J_NEXT
        STA J_LATEST
        STA J_OLDEST
        LDX #3
ZERO_SEQ:
        STZ J_SEQUENCE,X
        DEX
        BPL ZERO_SEQ
SCAN_NEXT:
        LDA J_SCAN_SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA J_OFFSET
        STA EE_PTR
        CLC
        ADC #J_EE_BASE
        STA EE_ADDR
        LDA #$6B
        STA EE_PTR+1
        LDA #32
        STA EE_COUNT
        STZ EE_WRITE
        JSR EE_TRANSFER
        BCC SCAN_END
        JSR CACHE_POINTER
        JSR HEADER_VALID
        BCS SCAN_OWNED
        LDY #0
BLANK_LOOP:
        LDA (P),Y
        CMP #$FF
        BNE FOREIGN
        INY
        CPY #32
        BNE BLANK_LOOP
        BRA FREE_SLOT
SCAN_OWNED:
        JSR RECORD_CRC
        BCC FREE_SLOT
        ; CRC-valid tombstones retain sequence, so CLEAR n doesn't reuse IDs.
        LDY #11
MAX_COMPARE:
        LDA (P),Y
        SEC
        SBC J_SEQUENCE-8,Y
        BNE MAX_DECIDED
        DEY
        CPY #7
        BNE MAX_COMPARE
        BRA CHECK_COMMIT
MAX_DECIDED:
        BCC CHECK_COMMIT
        LDY #8
MAX_COPY:
        LDA (P),Y
        STA J_SEQUENCE-8,Y
        INY
        CPY #12
        BNE MAX_COPY
CHECK_COMMIT:
        LDY #31
        LDA (P),Y
        CMP #J_COMMIT
        BNE FREE_SLOT
        LDX J_SCAN_SLOT
        LDA MASKS,X
        ORA J_VALID
        STA J_VALID
        LDY #30
        LDA (P),Y
        BEQ COMMITTED_STATE
        LDA MASKS,X
        ORA J_PENDING
        STA J_PENDING
COMMITTED_STATE:
        LDA J_LATEST
        CMP #$FF
        BEQ FIRST_VALID
        JSR COMPARE_LATEST
        BCC MAYBE_OLDEST
        LDA J_SCAN_SLOT
        STA J_LATEST
MAYBE_OLDEST:
        JSR COMPARE_OLDEST
        BCS SCAN_ADVANCE
        LDA J_SCAN_SLOT
        STA J_OLDEST
        BRA SCAN_ADVANCE
FIRST_VALID:
        LDA J_SCAN_SLOT
        STA J_LATEST
        STA J_OLDEST
        BRA SCAN_ADVANCE
FREE_SLOT:
        LDA J_NEXT
        CMP #$FF
        BNE SCAN_ADVANCE
        LDA J_SCAN_SLOT
        STA J_NEXT
SCAN_ADVANCE:
        INC J_SCAN_SLOT
        LDA J_SCAN_SLOT
        CMP #J_SLOTS
        BNE SCAN_NEXT
        LDA J_NEXT
        CMP #$FF
        BNE SCAN_SUCCESS
        LDA J_OLDEST
        STA J_NEXT
SCAN_SUCCESS:
        LDA #0
        SEC
SCAN_END:
        RTS
FOREIGN:
        LDA #J_FOREIGN
        CLC
        RTS
CACHE_POINTER:
        LDA J_OFFSET
        STA P
        LDA #$6B
        STA P+1
        RTS
HEADER_VALID:
        LDY #0
HEADER_LOOP:
        LDA (P),Y
        CPY #3
        BEQ HEADER_SLOT
        CMP HEADER,Y
        BNE HEADER_BAD
        BRA HEADER_NEXT
HEADER_SLOT:
        LDA J_SCAN_SLOT
        INC A
        CMP (P),Y
        BNE HEADER_BAD
HEADER_NEXT:
        INY
        CPY #8
        BNE HEADER_LOOP
        SEC
        RTS
HEADER_BAD:
        CLC
        RTS
RECORD_CRC:
        JSR CRC_RECORD
        LDY #28
        LDA (P),Y
        CMP J_CRC
        BNE HEADER_BAD
        INY
        LDA (P),Y
        CMP J_CRC+1
        BNE HEADER_BAD
        SEC
        RTS
CRC_RECORD:
        LDA #$FF
        STA J_CRC
        STA J_CRC+1
        LDY #0
CRC_BYTE:
        LDA (P),Y
        EOR J_CRC+1
        STA J_CRC+1
        LDX #8
CRC_BIT:
        ASL J_CRC
        ROL J_CRC+1
        BCC CRC_NEXT
        LDA J_CRC
        EOR #$21
        STA J_CRC
        LDA J_CRC+1
        EOR #$10
        STA J_CRC+1
CRC_NEXT:
        DEX
        BNE CRC_BIT
        INY
        CPY #28
        BNE CRC_BYTE
        RTS
COMPARE_LATEST:
        LDA J_LATEST
        BRA COMPARE_SLOT
COMPARE_OLDEST:
        LDA J_OLDEST
COMPARE_SLOT:
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #11
        TAX
        LDY #11
COMPARE_SEQ:
        LDA (P),Y
        SEC
        SBC J_CACHE,X
        BNE COMPARE_DONE
        DEX
        DEY
        CPY #7
        BNE COMPARE_SEQ
        SEC
COMPARE_DONE:
        RTS

WRITE_ALLOWED:
        LDA #$FF
        STA EE_ADDR
        LDA #<J_VERIFY
        STA EE_PTR
        LDA #>J_VERIFY
        STA EE_PTR+1
        LDA #1
        STA EE_COUNT
        STZ EE_WRITE
        JSR EE_TRANSFER
        BCC ALLOWED_DONE
        LDA J_VERIFY
        AND #$0C
        BEQ ALLOWED_GOOD
        LDA #6
        CLC
        RTS
ALLOWED_GOOD:
        LDA #0
        SEC
ALLOWED_DONE:
        RTS
FIND_MATCH:
        LDA #$FF
        STA J_MATCH
        STZ J_SCAN_SLOT
MATCH_SLOT:
        LDX J_SCAN_SLOT
        LDA MASKS,X
        AND J_VALID
        BEQ MATCH_ADVANCE
        LDA MASKS,X
        AND J_PENDING
        BEQ MATCH_ADVANCE
        TXA
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA J_OFFSET
        JSR CACHE_POINTER
        LDY #12
MATCH_RAW:
        LDA (P),Y
        CMP RTC_OUTAGE-12,Y
        BNE MATCH_ADVANCE
        INY
        CPY #20
        BNE MATCH_RAW
        LDA J_SCAN_SLOT
        STA J_MATCH
        RTS
MATCH_ADVANCE:
        INC J_SCAN_SLOT
        LDA J_SCAN_SLOT
        CMP #J_SLOTS
        BNE MATCH_SLOT
        RTS

NEW_RECORD:
        LDX #3
SEQ_FULL_CHECK:
        LDA J_SEQUENCE,X
        CMP #$FF
        BNE SEQ_INCREMENT
        DEX
        BPL SEQ_FULL_CHECK
        LDA #J_SEQUENCE_FULL
        CLC
        RTS
SEQ_INCREMENT:
        INC J_SEQUENCE
        BNE SEQ_READY
        INC J_SEQUENCE+1
        BNE SEQ_READY
        INC J_SEQUENCE+2
        BNE SEQ_READY
        INC J_SEQUENCE+3
SEQ_READY:
        LDA J_NEXT
        STA J_SLOT
        STA J_MATCH
        JSR MAKE_HEADER
        LDX #3
RECORD_SEQ:
        LDA J_SEQUENCE,X
        STA J_RECORD+8,X
        DEX
        BPL RECORD_SEQ
        LDX #7
RECORD_RAW:
        LDA RTC_OUTAGE,X
        STA J_RECORD+12,X
        STZ J_RECORD+20,X
        DEX
        BPL RECORD_RAW
        LDA RTC_FLAGS
        AND #7
        CMP #7
        BNE RECORD_QUALITY
        LDX #7
RECORD_CAPTURE:
        LDA RTC_TIME,X
        STA J_RECORD+20,X
        DEX
        BPL RECORD_CAPTURE
        LDA J_RECORD+24
        ORA #$80
        STA J_RECORD+24
RECORD_QUALITY:
        LDA J_RECORD+24
        ORA #$40
        STA J_RECORD+24
        LDA RTC_FLAGS
        AND #$10
        ASL A
        ORA J_RECORD+24
        STA J_RECORD+24
        LDA #$FF
        STA J_RECORD+30
        STZ J_RECORD+31
        JSR WRITE_RECORD
        BCC NEW_DONE
        LDA #J_COMMIT
        JSR WRITE_MARKER
        BCC NEW_DONE
        JSR READ_VERIFY
        BCC NEW_DONE
        LDA J_VERIFY+31
        CMP #J_COMMIT
        BNE WRITE_VERIFY_ERROR
        LDA #0
        SEC
NEW_DONE:
        RTS
MAKE_HEADER:
        LDX #7
MAKE_HEADER_LOOP:
        LDA HEADER,X
        STA J_RECORD,X
        DEX
        BPL MAKE_HEADER_LOOP
        LDA J_SLOT
        INC A
        STA J_RECORD+3
        RTS
WRITE_RECORD:
        ; Invalidate and verify before modifying a reused slot.
        LDA #0
        JSR WRITE_MARKER
        BCC WRITE_DONE
        LDA #<J_RECORD
        STA P
        LDA #>J_RECORD
        STA P+1
        JSR CRC_RECORD
        LDA J_CRC
        STA J_RECORD+28
        LDA J_CRC+1
        STA J_RECORD+29
        STZ J_INDEX
        LDX #7
HEADER_UNCHANGED:
        LDA J_VERIFY,X
        CMP J_RECORD,X
        BNE PAGE_LOOP
        DEX
        BPL HEADER_UNCHANGED
        LDA #8
        STA J_INDEX
PAGE_LOOP:
        LDA J_SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #J_EE_BASE
        ADC J_INDEX
        STA EE_ADDR
        LDX J_INDEX
        LDY #0
PAGE_COPY:
        LDA J_RECORD,X
        STA J_PACKET+1,Y
        INX
        INY
        CPY #8
        BNE PAGE_COPY
        LDA #8
        STA EE_COUNT
        JSR WRITE_WAIT
        BCC WRITE_DONE
        LDA J_INDEX
        CLC
        ADC #8
        STA J_INDEX
        CMP #32
        BNE PAGE_LOOP
        JSR READ_VERIFY
        BCC WRITE_DONE
        LDX #31
VERIFY_RECORD:
        LDA J_VERIFY,X
        CMP J_RECORD,X
        BNE WRITE_VERIFY_ERROR
        DEX
        BPL VERIFY_RECORD
        LDA #0
        SEC
WRITE_DONE:
        RTS
WRITE_VERIFY_ERROR:
        LDA #J_VERIFY_FAILED
        CLC
        RTS
READ_VERIFY:
        LDA J_SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #J_EE_BASE
        STA EE_ADDR
        LDA #<J_VERIFY
        STA EE_PTR
        LDA #>J_VERIFY
        STA EE_PTR+1
        LDA #32
        STA EE_COUNT
        STZ EE_WRITE
        JMP EE_TRANSFER
WRITE_MARKER:
        STA J_PACKET+1
        LDA J_SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #J_EE_BASE+31
        STA EE_ADDR
        LDA #1
        STA EE_COUNT
        JSR WRITE_WAIT
        BCC MARKER_DONE
        JSR READ_VERIFY
        BCC MARKER_DONE
        LDA J_VERIFY+31
        CMP J_PACKET+1
        BNE WRITE_VERIFY_ERROR
        LDA #0
        SEC
MARKER_DONE:
        RTS
WRITE_WAIT:
        LDA #1
        STA EE_WRITE
        JSR EE_TRANSFER
        BCC WAIT_DONE
        LDA #$FF
        STA J_POLL
WAIT_READY:
        LDA #$FF
        STA EE_ADDR
        LDA #1
        STA EE_COUNT
        LDA #<J_VERIFY
        STA EE_PTR
        LDA #>J_VERIFY
        STA EE_PTR+1
        STZ EE_WRITE
        JSR EE_TRANSFER
        BCS WAIT_DONE
        CMP #2
        BNE WAIT_DONE
        DEC J_POLL
        BNE WAIT_READY
        LDA #3
        CLC
WAIT_DONE:
        RTS
MARK_CLEARED:
        LDA J_MATCH
        CMP #$FF
        BEQ MARK_GOOD
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #J_EE_BASE+30
        STA EE_ADDR
        STZ J_PACKET+1
        LDA #1
        STA EE_COUNT
        JSR WRITE_WAIT
        BCC MARK_DONE
        LDA J_MATCH
        STA J_SLOT
        JSR READ_VERIFY
        BCC MARK_DONE
        LDA J_VERIFY+30
        BNE WRITE_VERIFY_ERROR
MARK_GOOD:
        LDA #0
        SEC
MARK_DONE:
        RTS
CLEAR_ONE:
        LDA J_PARAM
        CMP #J_SLOTS
        BCS BAD_REQUEST
        STA J_SLOT
        TAX
        LDA MASKS,X
        AND J_VALID
        BEQ SUCCESS
        JSR WRITE_ALLOWED
        BCC RETURN
        LDA #0
        JSR WRITE_MARKER
        BRA RETURN
CLEAR_ALL:
        JSR WRITE_ALLOWED
        BCC RETURN
        JSR SCAN
        BCS CLEAR_KNOWN
        CMP #J_FOREIGN
        BNE RETURN
        ; Explicit initialization is recovery for foreign/damaged layout.
        LDA #1
        STA J_TMP
        BRA CLEAR_START
CLEAR_KNOWN:
        STZ J_TMP
CLEAR_START:
        STZ J_SLOT
CLEAR_ALL_NEXT:
        LDA J_TMP
        BNE CLEAR_INITIALIZE
        LDA J_SLOT
        STA J_SCAN_SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        STA J_OFFSET
        JSR CACHE_POINTER
        JSR HEADER_VALID
        BCC CLEAR_INITIALIZE
        LDA #0
        JSR WRITE_MARKER
        BCC RETURN
        STZ J_PACKET+1
        STZ J_PACKET+2
        STZ J_PACKET+3
        STZ J_PACKET+4
        LDA J_SLOT
        ASL A
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #J_EE_BASE+8
        STA EE_ADDR
        LDA #4
        STA EE_COUNT
        JSR WRITE_WAIT
        BCC RETURN
        BRA CLEAR_ADVANCE
CLEAR_INITIALIZE:
        JSR MAKE_HEADER
        LDX #23
CLEAR_ALL_PAYLOAD:
        STZ J_RECORD+8,X
        DEX
        BPL CLEAR_ALL_PAYLOAD
        JSR WRITE_RECORD
        BCC RETURN
CLEAR_ADVANCE:
        INC J_SLOT
        LDA J_SLOT
        CMP #J_SLOTS
        BNE CLEAR_ALL_NEXT
        JMP SUCCESS
HEADER DB "PF",1,0,$4A,$52,32,$A5
MASKS DB 1,2,4,8
JOURNAL_END:
        ENDMOD
        END
