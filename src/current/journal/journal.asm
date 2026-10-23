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
START DB "PJ",6,1        ; adds confirmed fine-trim control; identity layout unchanged
        JMP ENTER
ENTER:
        PHP
        SEI
        CLD
        LDA J_LOCK
                        BEQ JS_LONG_17
                        JMP IN_USE
JS_LONG_17:
        INC J_LOCK
        STZ J_OUTCOME
        STX J_OP
        CPX #11
                        BCC JS_LONG_22
                        JMP BAD_REQUEST
JS_LONG_22:
        CPX #10
                        BNE NOT_TRIM
        LDA J_KEY
        CMP #'T'
                        BEQ JS_LONG_27
                        JMP DENIED
JS_LONG_27:
        LDA J_KEY+1
        CMP #'R'
                        BEQ JS_LONG_30
                        JMP DENIED
JS_LONG_30:
        STZ J_KEY
        STZ J_KEY+1
        JSR TRIM_CONTROL
                        JMP RETURN
NOT_TRIM:
        CPX #J_BIND_PRINT_OP
                        BNE NOT_BIND_PRINT
        JSR BIND_PRINT
                        JMP SUCCESS
NOT_BIND_PRINT:
        CPX #J_BIND_CHECK_OP
                        BEQ BIND_CHECK_ENTRY
        CPX #J_BIND_ACCEPT_OP
                        BNE NOT_BIND_ACCEPT
        LDA J_KEY
        CMP #'A'
                        BEQ JS_LONG_47
                        JMP DENIED
JS_LONG_47:
        LDA J_KEY+1
        CMP #'I'
                        BEQ JS_LONG_50
                        JMP DENIED
JS_LONG_50:
        STZ J_KEY
        STZ J_KEY+1
        JSR BIND_ACCEPT
                        JMP RETURN
BIND_CHECK_ENTRY:
        JSR BIND_CHECK
                        JMP RETURN
NOT_BIND_ACCEPT:
        CPX #J_EUI_OP
                        BNE JS_LONG_60
                        JMP READ_EUI
JS_LONG_60:
        CPX #J_CLEAR_ALL_OP
                        BEQ AUTHORIZE_ALL
        CPX #J_CLEAR_OP
                        BNE DISPATCH
        LDA J_KEY
        CMP #'C'
                        BEQ JS_LONG_67
                        JMP DENIED
JS_LONG_67:
                        BRA AUTHORIZE_L
AUTHORIZE_ALL:
        LDA J_KEY
        CMP #'A'
                        BEQ JS_LONG_72
                        JMP DENIED
JS_LONG_72:
AUTHORIZE_L:
        LDA J_KEY+1
        CMP #'L'
                        BEQ JS_LONG_76
                        JMP DENIED
JS_LONG_76:
        STZ J_KEY
        STZ J_KEY+1
DISPATCH:
        LDA J_OP
                        BNE JS_LONG_81
                        JMP SCAN_RETURN
JS_LONG_81:
        CMP #J_CLEAR_ALL_OP
                        BNE JS_LONG_83
                        JMP CLEAR_ALL
JS_LONG_83:
        JSR SCAN
                        BCS JS_LONG_85
                        JMP RETURN
JS_LONG_85:
        LDA J_OP
        CMP #J_CLEAR_OP
                        BNE JS_LONG_88
                        JMP CLEAR_ONE
JS_LONG_88:
        CMP #J_RECONCILE_OP
                        BEQ RECONCILE
        JSR RTC_STATUS
                        BCS JS_LONG_92
                        JMP RETURN
JS_LONG_92:
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
                        BEQ NO_EVENT
        JSR WRITE_ALLOWED
                        BCS JS_LONG_97
                        JMP RETURN
JS_LONG_97:
        JSR FIND_MATCH
        LDA J_MATCH
        CMP #$FF
                        BNE SAVED
        JSR NEW_RECORD
                        BCS JS_LONG_103
                        JMP RETURN
JS_LONG_103:
SAVED:
        LDA #1
        STA J_OUTCOME
        LDA J_OP
        CMP #J_SAVE_OP
                        BNE JS_LONG_109
                        JMP SUCCESS
JS_LONG_109:
        LDA #'P'
        STA RTC_KEY
        LDA #'A'
        STA RTC_KEY+1
        JSR RTC_ACK_POWER
                        BCS JS_LONG_115
                        JMP RETURN
JS_LONG_115:
        JSR RTC_STATUS
                        BCS JS_LONG_117
                        JMP RETURN
JS_LONG_117:
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
                        BEQ JS_LONG_120
                        JMP VERIFY_ERROR
JS_LONG_120:
        LDA #3
        STA J_OUTCOME
        JSR MARK_CLEARED
                        JMP RETURN
NO_EVENT:
                        JMP SUCCESS
RECONCILE:
        JSR RTC_STATUS
                        BCC RETURN
        LDA RTC_FLAGS
        AND #RTC_F_POWERFAIL
                        BEQ JS_LONG_132
                        JMP BAD_REQUEST
JS_LONG_132:
        LDA J_LATEST
        STA J_MATCH
        CMP #$FF
                        BEQ SUCCESS
        JSR WRITE_ALLOWED
                        BCC RETURN
        JSR MARK_CLEARED
                        JMP RETURN
READ_EUI:
        JSR EUI_FETCH
                        JMP RETURN
EUI_FETCH:
        LDA #$F2
        STA EE_ADDR
        LDA #<J_EUI
        STA EE_PTR
        LDA #>J_EUI
        STA EE_PTR+1
        LDA #6
        STA EE_COUNT
        STZ EE_WRITE
        JSR EE_TRANSFER
                        BCC EUI_FETCH_DONE
        ; Reject erased/zero identity; never manufacture an EUI from them.
        STZ J_TMP
        LDA #$FF
        STA J_MASK
        LDX #5
EUI_VALIDATE:
        LDA J_EUI,X
        ORA J_TMP
        STA J_TMP
        LDA J_EUI,X
        AND J_MASK
        STA J_MASK
        DEX
                        BPL EUI_VALIDATE
        LDA J_TMP
                        BEQ EUI_FETCH_BAD
        LDA J_MASK
        CMP #$FF
                        BEQ EUI_FETCH_BAD
        LDA #0
        SEC
EUI_FETCH_DONE:
        RTS
EUI_FETCH_BAD:
        LDA #J_VERIFY_FAILED
        CLC
        RTS
SCAN_RETURN:
        JSR SCAN
                        JMP RETURN
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
                        JMP RETURN
BAD_REQUEST:
        LDA #9
                        JMP RETURN
VERIFY_ERROR:
        LDA #J_VERIFY_FAILED
                        JMP RETURN

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
                        BCS JS_LONG_248
                        JMP SCAN_END
JS_LONG_248:
        JSR CACHE_POINTER
        JSR HEADER_VALID
                        BCS SCAN_OWNED
        LDY #0
BLANK_LOOP:
        LDA (P),Y
        CMP #$FF
                        BEQ JS_LONG_256
                        JMP FOREIGN
JS_LONG_256:
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
                        JMP SCAN_ADVANCE
FIRST_VALID:
        LDA J_SCAN_SLOT
        STA J_LATEST
        STA J_OLDEST
                        JMP SCAN_ADVANCE
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
                        BEQ JS_LONG_328
                        JMP SCAN_NEXT
JS_LONG_328:
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
                        BEQ JS_LONG_571
                        JMP WRITE_VERIFY_ERROR
JS_LONG_571:
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
                        BEQ JS_LONG_749
                        JMP WRITE_VERIFY_ERROR
JS_LONG_749:
MARK_GOOD:
        LDA #0
        SEC
MARK_DONE:
        RTS
CLEAR_ONE:
        LDA J_PARAM
        CMP #J_SLOTS
                        BCC JS_LONG_758
                        JMP BAD_REQUEST
JS_LONG_758:
        STA J_SLOT
        TAX
        LDA MASKS,X
        AND J_VALID
                        BNE JS_LONG_763
                        JMP SUCCESS
JS_LONG_763:
        JSR WRITE_ALLOWED
                        BCS JS_LONG_765
                        JMP RETURN
JS_LONG_765:
        LDA #0
        JSR WRITE_MARKER
                        JMP RETURN
CLEAR_ALL:
        JSR WRITE_ALLOWED
                        BCS JS_LONG_771
                        JMP RETURN
JS_LONG_771:
        JSR SCAN
                        BCS CLEAR_KNOWN
        CMP #J_FOREIGN
                        BEQ JS_LONG_775
                        JMP RETURN
JS_LONG_775:
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
                        BCS JS_LONG_800
                        JMP RETURN
JS_LONG_800:
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
                        BCS JS_LONG_817
                        JMP RETURN
JS_LONG_817:
                        BRA CLEAR_ADVANCE
CLEAR_INITIALIZE:
        JSR MAKE_HEADER
        LDX #23
CLEAR_ALL_PAYLOAD:
        STZ J_RECORD+8,X
        DEX
                        BPL CLEAR_ALL_PAYLOAD
        JSR WRITE_RECORD
                        BCS JS_LONG_827
                        JMP RETURN
JS_LONG_827:
CLEAR_ADVANCE:
        INC J_SLOT
        LDA J_SLOT
        CMP #J_SLOTS
                        BNE CLEAR_ALL_NEXT
        JMP SUCCESS
HEADER DB "PF",1,0,$4A,$52,32,$A5
MASKS DB 1,2,4,8
        INCLUDE "binding.inc"
SP_R EQU $6650
SP_GBUSY EQU $6660
SP_BUSY EQU $6669
SP_OP EQU $666A
SP_ODDR EQU $666B
SP_OORB EQU $666C
SP_PORT EQU $666D
SP_TX EQU $666E
SP_RX EQU $666F
SP_LEFT EQU $6670
SP_MASK EQU $6671
SP_OLDMODE EQU $6672
SP_ERR EQU $6673
SP_A0 EQU $6674
SP_A1 EQU $6675
SP_A2 EQU $6676
SP_COUNT EQU $6677
SP_CHANGED EQU $6678
SP_READY EQU $6679
SP_T0 EQU $667A
SP_KIND EQU $667B
SP_SAVED_PCR EQU $667C
SP_LO EQU $66B0
SP_HI EQU $66B4
SP_DDR EQU $7FC2
SP_ORB EQU $7FC0
SP_IFR EQU $7FCD
SP_PCR EQU $7FCC
SP_MANAGED EQU $66AE
SP_BACKUP EQU $6B80

        INCLUDE "spi-links.inc"
SPI_HANDLE:
        JSR SPI_PREP
        JSR SP_DISPATCH
        STA SP_ERR
        LDA SP_READY
                        BEQ SPI_DONE
        LDA SP_KIND
                        BEQ SPI_RESTORE
        LDA SP_CHANGED
                        BEQ SPI_RESTORE
        JSR SPI_REPAIR_MODE
SPI_RESTORE:
        JSR SP_RESTORE
SPI_DONE:
        JSR SPI_FINISH_PHASE
SPI_RETURN:
        STZ $7D22
        STZ $6669
        LDA SP_ERR
        RTS
SP_DISPATCH:
        LDA SP_OP
                        BEQ JS_LONG_891
                        JMP SP_SRAM
JS_LONG_891:
        LDA SP_R+13
        ORA SP_R+14
        ORA SP_R+15
                        BNE SP_BAD
        LDA SP_R
        CMP #2
                        BCS SP_BAD
        TAX
                        BNE SP_RAW_ALLOWED
                        BRA SP_DENIED
SP_RAW_ALLOWED:
        LDA #4
        CPX #0
                        BEQ SP_RAW_MASK
        ASL A
SP_RAW_MASK:
        STA SP_MASK
        LDA SP_R
        JSR SP_VALIDATE_SHAPE
                        BCC SP_BAD
        LDA SP_R+1
                        BEQ SP_RAW_READY
        LDA SP_R+4
        CMP SP_R+7
                        BNE SP_BAD
        ; Duplex allows exact in-place or completely disjoint buffers.
SP_DUP_OVERLAP:
        LDA SP_R+5
        SEC
        SBC SP_R+2
        STA SP_T0
        LDA SP_R+6
        SBC SP_R+3
                        BEQ SP_DUP_POSITIVE
        CMP #$FF
                        BNE SP_RAW_READY
        LDA SP_T0
                        BEQ SP_RAW_READY
        EOR #$FF
        INC A
                        BRA SP_DUP_DISTANCE
SP_DUP_POSITIVE:
        LDA SP_T0
                        BEQ SP_RAW_READY
SP_DUP_DISTANCE:
        CMP SP_R+4
                        BCC SP_BAD
                        BRA SP_RAW_READY
SP_BAD:    LDA #9
        RTS
SP_DENIED: LDA #6
        RTS
SP_RAW_READY:
        JSR SP_INIT
                        BCC SP_RETURN
        JSR SP_SELECT
        LDA SP_R+4
        STA SP_LEFT
                        BEQ SP_RECEIVE
SP_TRANSMIT:
        JSR SP_LO
        JSR SP_BYTE
        INC SP_R+9
        JSR SP_NEXT_TX
        LDX SP_R+1
                        BEQ SP_TX_NEXT
        JSR SP_HI
        JSR SP_NEXT_RX
        INC SP_R+10
SP_TX_NEXT:
        DEC SP_LEFT
                        BNE SP_TRANSMIT
        LDA SP_R+1
                        BNE SP_SUCCESS
        LDA SP_KIND
                        BNE SP_SUCCESS
SP_RECEIVE:
        LDA SP_R+7
        STA SP_LEFT
                        BEQ SP_SUCCESS
SP_RX_NEXT:
        LDA SP_R+12
        JSR SP_BYTE
        JSR SP_HI
        JSR SP_NEXT_RX
        INC SP_R+10
        DEC SP_LEFT
                        BNE SP_RX_NEXT
SP_SUCCESS:
        LDA #0
SP_RETURN: RTS
SP_SRAM:
                        BRA SP_SRAM_VALIDATE
SP_SRAM_BAD:
        LDA #9
        RTS
SP_SRAM_DENIED:
        LDA #6
        RTS
SP_SRAM_VALIDATE:
        LDA SP_R+1
        ORA SP_R+15
                        BNE SP_SRAM_BAD
        LDA SP_R
        CMP #3
                        BCS SP_SRAM_BAD
        STA SP_OP
        TAX
                        BEQ SP_PROBE_SETUP
        LDA SP_MANAGED
                        BEQ SP_SRAM_RANGE
        LDA SP_OP
        CMP #2
                        BEQ SP_SRAM_DENIED
SP_SRAM_RANGE:
        LDA SP_R+7
                        BEQ SP_SRAM_BAD
        LDA SP_R+5
        LDX SP_R+6
        LDY SP_R+7
        JSR SP_BUFFER
                        BCC SP_SRAM_BAD
        LDA SP_R+4
        CMP #2
                        BCS SP_SRAM_BAD
        LDA SP_R+7
        SEC
        SBC #1
        CLC
        ADC SP_R+2
        LDA SP_R+3
        ADC #0
        LDA SP_R+4
        ADC #0
        CMP #2
                        BCS SP_SRAM_BAD
        LDX #2
SP_ADDRESS_COPY:
        LDA SP_R+2,X
        STA SP_A0,X
        DEX
                        BPL SP_ADDRESS_COPY
        LDA SP_R+7
        STA SP_COUNT
        LDA SP_R+5
        LDX SP_R+6
                        BRA SP_SRAM_READY
SP_PROBE_SETUP:
        LDA SP_R+7
                        BNE SP_SRAM_BAD
        LDA #$FF
        STA SP_A0
        LDA #$FF
        STA SP_A1
        LDA #1
        STA SP_A2
        LDA #1
        STA SP_COUNT
        LDA #<SP_BACKUP
        LDX #>SP_BACKUP
SP_SRAM_READY:
        STA SP_LO+1
        STA SP_HI+1
        STX SP_LO+2
        STX SP_HI+2
        LDA #4
        STA SP_MASK
        JSR SP_INIT
                        BCS JS_LONG_1060
                        JMP SP_RETURN
JS_LONG_1060:
        JSR SP_READ_MODE
        STA SP_OLDMODE
        CMP #$40
                        BEQ SP_MODE_READY
        CMP #0
                        BEQ SP_CHANGE_MODE
        CMP #$80
                        BNE SP_VERIFY_FAIL
SP_CHANGE_MODE:
        INC SP_CHANGED
        LDA #$40
        JSR SP_WRITE_MODE
        JSR SP_READ_MODE
        CMP #$40
                        BNE SP_VERIFY_FAIL
SP_MODE_READY:
        LDA SP_OP
                        BEQ SP_PROBE
        JSR SP_MEMORY_FRAME
        LDA SP_COUNT
        STA SP_R+9
                        JMP SP_SUCCESS
SP_VERIFY_FAIL:
        LDA #7
        RTS
SP_MEMORY_FRAME:
        LDA #3
        LDX SP_OP
        CPX #2
                        BNE SP_MEMORY_COMMAND
        DEC A
SP_MEMORY_COMMAND:
        JSR SP_COMMAND
        LDA SP_A2
        JSR SP_BYTE
        LDA SP_A1
        JSR SP_BYTE
        LDA SP_A0
        JSR SP_BYTE
        LDA SP_COUNT
        STA SP_LEFT
        LDX SP_OP
        CPX #2
                        BNE SP_MEMORY_READ
        JSR SP_TRANSMIT
        JMP SP_DESELECT
SP_MEMORY_READ:
        JSR SP_RX_NEXT
        JMP SP_DESELECT
SP_PROBE:
        ; Toggle one reserved byte, verify, restore and verify even on mismatch.
        LDA #1
        STA SP_OP
        JSR SP_MEMORY_FRAME
        LDA #2
        JSR SP_COMMAND
        JSR SP_PROBE_ADDRESS
        LDA SP_BACKUP
        EOR #$FF
        JSR SP_BYTE
        JSR SP_DESELECT
        LDA #3
        JSR SP_COMMAND
        JSR SP_PROBE_ADDRESS
        LDA #0
        JSR SP_BYTE
        STA SP_T0
        LDA SP_BACKUP
        EOR #$FF
        CMP SP_T0
                        BEQ SP_PROBE_MATCH
        LDA #7
        STA SP_ERR
SP_PROBE_MATCH:
        JSR SP_DESELECT
        LDA #2
        STA SP_OP
        JSR SP_MEMORY_FRAME
        LDA #3
        JSR SP_COMMAND
        JSR SP_PROBE_ADDRESS
        LDA #0
        JSR SP_BYTE
        CMP SP_BACKUP
                        BEQ SP_PROBE_RESTORED
        LDA #7
        STA SP_ERR
SP_PROBE_RESTORED:
        JSR SP_DESELECT
        STZ SP_R+9
        STZ SP_R+10
        STZ SP_R+12
        LDA SP_ERR
                        BNE SP_PROBE_DONE
        LDA #2
        STA SP_R+13
        LDA #$81            ; Usable, retention/battery continuity unknown.
        STA SP_R+14
SP_PROBE_DONE:
        LDA SP_ERR
        RTS
SP_PROBE_ADDRESS:
        LDA SP_A2
        JSR SP_BYTE
        LDA SP_A1
        JSR SP_BYTE
        LDA SP_A0
        JMP SP_BYTE

JOURNAL_END:
        ENDMOD
        END
