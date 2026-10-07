; Flash identity records: EI,1,0; seq LE32; EUI[6]; reserved FF; CRC16[2]; FF; commit 0.
; All writes use the trusted existing RAM byte worker. Never erase automatically.
B_BEST EQU $6D30
B_FREE EQU $6D32
B_SEQ EQU $6D34
B_ERR EQU $6D38
B_LED EQU $6D39
B_DEST EQU $6D3A
B_INDEX EQU $6D3C
B_SAVED EQU $6D00
B_RECORD EQU $6B00
BIND_CHECK:
        STZ J_CURRENT_VALID
        JSR EUI_FETCH
        STA B_ERR
        BCC BIND_FETCHED
        INC J_CURRENT_VALID
BIND_FETCHED:
        JSR BIND_SCAN
        STZ J_BIND_STATUS
        LDA J_CURRENT_VALID
        BEQ BIND_UNAVAILABLE
        LDA B_BEST+1
        BEQ BIND_CHECK_OK
        INC J_BIND_STATUS
        LDX #5
BIND_COMPARE:
        LDA J_EUI,X
        CMP J_REMEMBERED,X
        BNE BIND_CHANGED
        DEX
        BPL BIND_COMPARE
        BRA BIND_CHECK_OK
BIND_CHANGED:
        INC J_BIND_STATUS
        BRA BIND_CHECK_OK
BIND_UNAVAILABLE:
        LDA #3
        STA J_BIND_STATUS
BIND_CHECK_OK:
        LDA #0
        SEC
        RTS
BIND_SCAN:
        STZ B_BEST+1
        STZ B_FREE+1
        LDX #5
BIND_RESET:
        STZ J_REMEMBERED,X
        DEX
        BPL BIND_RESET
        LDX #3
BIND_SEQ_RESET:
        STZ B_SEQ,X
        DEX
        BPL BIND_SEQ_RESET
        STZ P
        LDA #$9C
        STA P+1
BIND_SCAN_SLOT:
        LDY #0
BIND_BLANK:
        LDA (P),Y
        CMP #$FF
        BNE BIND_CHECK_SLOT
        INY
        CPY #32
        BNE BIND_BLANK
        LDA B_FREE+1
        BNE BIND_ADVANCE
        LDA P
        STA B_FREE
        LDA P+1
        STA B_FREE+1
        BRA BIND_ADVANCE
BIND_CHECK_SLOT:
        LDY #31
        LDA (P),Y
        BNE BIND_ADVANCE
        LDY #0
        LDA (P),Y
        CMP #'E'
        BNE BIND_ADVANCE
        INY
        LDA (P),Y
        CMP #'I'
        BNE BIND_ADVANCE
        INY
        LDA (P),Y
        CMP #1
        BNE BIND_ADVANCE
        INY
        LDA (P),Y
        BNE BIND_ADVANCE
        JSR RECORD_CRC
        BCC BIND_ADVANCE
        LDX #3
        LDY #7
BIND_NEWER:
        LDA (P),Y
        CMP B_SEQ,X
        BCC BIND_ADVANCE
        BNE BIND_KEEP
        DEY
        DEX
        BPL BIND_NEWER
BIND_KEEP:
        LDA P
        STA B_BEST
        LDA P+1
        STA B_BEST+1
        LDX #3
        LDY #7
BIND_COPY_SEQ:
        LDA (P),Y
        STA B_SEQ,X
        DEY
        DEX
        BPL BIND_COPY_SEQ
        LDX #5
        LDY #13
BIND_COPY_ID:
        LDA (P),Y
        STA J_REMEMBERED,X
        DEY
        DEX
        BPL BIND_COPY_ID
BIND_ADVANCE:
        LDA P
        CLC
        ADC #32
        STA P
        BCC BIND_PAGE_READY
        INC P+1
BIND_PAGE_READY:
        LDA P+1
        CMP #$A0
        BNE BIND_SCAN_SLOT
        RTS
BIND_ACCEPT:
        JSR BIND_CHECK
        LDA J_CURRENT_VALID
        BEQ BIND_NO_CURRENT
        LDX #5
BIND_REQUEST_MATCH:
        LDA J_BIND_REQUEST,X
        CMP J_EUI,X
        BNE BIND_BAD_REQUEST
        DEX
        BPL BIND_REQUEST_MATCH
        LDA J_BIND_STATUS
        CMP #1
        BEQ BIND_CHECK_OK
        LDA B_FREE+1
        BEQ BIND_IS_FULL
        LDX #31
        LDA #$FF
BIND_FILL:
        STA B_RECORD,X
        DEX
        BPL BIND_FILL
        LDA #'E'
        STA B_RECORD
        LDA #'I'
        STA B_RECORD+1
        LDA #1
        STA B_RECORD+2
        STZ B_RECORD+3
        INC B_SEQ
        BNE BIND_SEQUENCE_READY
        INC B_SEQ+1
        BNE BIND_SEQUENCE_READY
        INC B_SEQ+2
        BNE BIND_SEQUENCE_READY
        INC B_SEQ+3
        BEQ BIND_SEQ_FULL
BIND_SEQUENCE_READY:
        LDX #3
BIND_PREPARE_SEQ:
        LDA B_SEQ,X
        STA B_RECORD+4,X
        DEX
        BPL BIND_PREPARE_SEQ
        LDX #5
BIND_PREPARE_ID:
        LDA J_EUI,X
        STA B_RECORD+8,X
        DEX
        BPL BIND_PREPARE_ID
        LDA #<B_RECORD
        STA P
        LDA #>B_RECORD
        STA P+1
        JSR CRC_RECORD
        LDA J_CRC
        STA B_RECORD+28
        LDA J_CRC+1
        STA B_RECORD+29
        LDA B_FREE
        STA B_DEST
        LDA B_FREE+1
        STA B_DEST+1
        ; Save worker-owned ZP and LED. IRQ is already masked by ENTER.
        LDX #31
BIND_SAVE_ZP:
        LDA $E0,X
        STA B_SAVED,X
        DEX
        BPL BIND_SAVE_ZP
        LDA $7FA0
        STA B_LED
        LDA #1
        STA $F4              ; RAM NMI stub holds dispatch during flash polling.
        STZ B_ERR
        STZ B_INDEX
BIND_WRITE_NEXT:
        LDX B_INDEX
        LDA B_RECORD,X
        CMP #$FF
        BEQ BIND_WRITE_ADVANCE
        STA $F0
        TXA
        CLC
        ADC B_DEST
        STA $E4
        LDA B_DEST+1
        ADC #0
        STA $E5
        JSR BIND_FLASH_BYTE
        BCC BIND_WRITE_FAIL
BIND_WRITE_ADVANCE:
        INC B_INDEX
        LDA B_INDEX
        CMP #31
        BNE BIND_WRITE_NEXT
        ; Read back all immutable bytes before programming the commit marker.
        LDA B_DEST
        STA P
        LDA B_DEST+1
        STA P+1
        LDY #30
BIND_VERIFY_BODY:
        LDA (P),Y
        CMP B_RECORD,Y
        BNE BIND_WRITE_FAIL
        DEY
        BPL BIND_VERIFY_BODY
        LDA P
        CLC
        ADC #31
        STA $E4
        LDA P+1
        ADC #0
        STA $E5
        STZ $F0
        JSR BIND_FLASH_BYTE
        BCC BIND_WRITE_FAIL
        LDA (P)
        BNE BIND_WRITE_FAIL
        BRA BIND_RESTORE
BIND_WRITE_FAIL:
        LDA #J_BIND_WRITE_FAILED
        STA B_ERR
BIND_RESTORE:
        LDA B_LED
        STA $7FA0
        LDX #31
BIND_RESTORE_ZP:
        LDA B_SAVED,X
        STA $E0,X
        DEX
        BPL BIND_RESTORE_ZP
        LDA B_ERR
        BNE BIND_RETURN_ERROR
        JMP BIND_CHECK
BIND_NO_CURRENT:
        LDA B_ERR
        BRA BIND_RETURN_ERROR
BIND_IS_FULL:
        LDA #J_BIND_FULL
        BRA BIND_RETURN_ERROR
BIND_BAD_REQUEST:
        LDA #9
        BRA BIND_RETURN_ERROR
BIND_SEQ_FULL:
        LDA #J_SEQUENCE_FULL
BIND_RETURN_ERROR:
        CLC
        RTS
BIND_PRINT:
        JSR BIND_CHECK
        LDA J_CURRENT_VALID
        BEQ BIND_PRINT_UNAVAILABLE
        LDX #<BIND_EUI_TEXT
        LDY #>BIND_EUI_TEXT
        JSR BIND_TEXT
        STZ J_INDEX
BIND_PRINT_NEXT:
        LDX J_INDEX
        LDA J_EUI,X
        JSR $7E7C
        INC J_INDEX
        LDA J_INDEX
        CMP #6
        BEQ BIND_PRINT_STATUS
        LDA #':'
        JSR $7E6D
        BRA BIND_PRINT_NEXT
BIND_PRINT_STATUS:
        LDA J_BIND_STATUS
        BEQ BIND_PRINT_UNBOUND
        CMP #2
        BNE BIND_PRINT_DONE
        LDX #<BIND_CHANGED_TEXT
        LDY #>BIND_CHANGED_TEXT
        BRA BIND_TEXT
BIND_PRINT_UNBOUND:
        LDX #<BIND_UNBOUND_TEXT
        LDY #>BIND_UNBOUND_TEXT
        BRA BIND_TEXT
BIND_PRINT_UNAVAILABLE:
        LDX #<BIND_UNAVAILABLE_TEXT
        LDY #>BIND_UNAVAILABLE_TEXT
BIND_TEXT:
        STX $E0
        STY $E1
        LDY #0
BIND_TEXT_NEXT:
        LDA ($E0),Y
        BEQ BIND_PRINT_DONE
        JSR $7E6D
        INY
        BNE BIND_TEXT_NEXT
BIND_PRINT_DONE:
        RTS
BIND_EUI_TEXT DB "RTCC: EUI ",0
BIND_UNAVAILABLE_TEXT DB "RTCC: EUI unavailable",0
BIND_UNBOUND_TEXT DB ", unbound",0
BIND_CHANGED_TEXT DB ", changed",0
