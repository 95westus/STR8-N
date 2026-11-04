; Load-only S0/S1/S9 above frozen BASE1. Callable high-RAM overlay.
; Code6B00-70FF, state7500-750F, record7700-77FB; ZP E0-E3 only.
; Every S1 is checked completely before committing to0200-66FF.
; S9 reports entry, never runs it. Earlier records survive an error/cancel.
        MODULE S19_LOADER
        INCLUDE "str8n-v2-public.inc"
        CODE
SL_START:
        DB "SL",1,6,"PR05"
        JMP SL_ENTRY
SL_PTR EQU $E0
SL_DST EQU $E2
SL_ADDR EQU $7500
SL_COUNT EQU $7502
SL_TYPE EQU $7503
SL_SUM EQU $7504
SL_NIB EQU $7505
SL_ERROR EQU $7506
SL_RECORD EQU $7700
; Exact frozen BASE1 console boolean, consumed after each GETC.
SL_RX_BAD EQU $F1
SL_ENTRY:
        SEI
        CLD
        JSR STR8V2_RAM_RX_RESET
        LDX #<SL_READY_TEXT
        LDY #>SL_READY_TEXT
        JSR SL_PRINT
SL_NEXT:
        JSR SL_RECORD_READ
        BCC SL_FAILED
        LDA SL_TYPE
        BEQ SL_NEXT
        CMP #9
        BEQ SL_DONE
        LDA SL_ADDR+1
        CMP #2
        BCC SL_RANGE
        LDA SL_COUNT
        DEC A
        CLC
        ADC SL_ADDR
        LDA SL_ADDR+1
        ADC #0
        BCS SL_RANGE
        CMP #$67
        BCS SL_RANGE
        LDA SL_ADDR
        STA SL_DST
        LDA SL_ADDR+1
        STA SL_DST+1
        LDY #0
SL_COPY:
        LDA SL_RECORD,Y
        STA (SL_DST),Y
        INY
        CPY SL_COUNT
        BCC SL_COPY
        BRA SL_NEXT
SL_DONE:
        ; Consume the optional LF after a CR terminator before returning to
        ; MON. Otherwise it becomes a blank command and a second prompt.
        JSR SL_DRAIN
        LDX #<SL_DONE_TEXT
        LDY #>SL_DONE_TEXT
        JSR SL_PRINT
        LDA SL_ADDR+1
        JSR STR8V2_RAM_HEX_OUT
        LDA SL_ADDR
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        LDA #0
        SEC
        RTS
SL_RANGE:
        LDA #4
SL_FAILED:
        STA SL_ERROR
        ; Stop the sender, discard its tail, then return to the caller.
        JSR SL_DRAIN
        LDX #<SL_ERROR_TEXT
        LDY #>SL_ERROR_TEXT
        JSR SL_PRINT
        LDA SL_ERROR
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        LDA SL_ERROR
        CLC
        RTS
SL_RECORD_READ:
        STZ SL_SUM
SL_RECORD_START:
        JSR SL_CHAR
        BCC SL_RETURN
        CMP #13
        BEQ SL_RECORD_START
        CMP #10
        BEQ SL_RECORD_START
        AND #$DF
        CMP #'S'
        BNE SL_BAD
        JSR SL_CHAR
        BCC SL_RETURN
        ; SL_CHAR returns carry set; SBC therefore subtracts exactly '0'.
        SBC #'0'
        CMP #2
        BCC SL_TYPE_OK
        CMP #9
        BNE SL_BAD
SL_TYPE_OK:
        STA SL_TYPE
        JSR SL_BYTE
        BCC SL_RETURN
        CMP #3
        BCC SL_BAD
        SBC #3
        STA SL_COUNT
        LDA SL_TYPE
        BEQ SL_ADDRESS
        CMP #9
        BEQ SL_TERMINATOR
        LDA SL_COUNT
        BEQ SL_BAD
        BRA SL_ADDRESS
SL_TERMINATOR:
        LDA SL_COUNT
        BNE SL_BAD
SL_ADDRESS:
        JSR SL_BYTE
        BCC SL_RETURN
        STA SL_ADDR+1
        JSR SL_BYTE
        BCC SL_RETURN
        STA SL_ADDR
        LDX #0
SL_DATA:
        CPX SL_COUNT
        BEQ SL_CHECK
        JSR SL_BYTE
        BCC SL_RETURN
        STA SL_RECORD,X
        INX
        BRA SL_DATA
SL_CHECK:
        JSR SL_BYTE
        BCC SL_RETURN
        LDA SL_SUM
        CMP #$FF
        BNE SL_CHECKSUM
        JSR SL_CHAR
        BCC SL_RETURN
        CMP #13
        BEQ SL_OK
        CMP #10
        BNE SL_BAD
SL_OK:
        SEC
SL_RETURN:
        RTS
SL_BAD:
        LDA #1
        CLC
        RTS
SL_CHECKSUM:
        LDA #2
        CLC
        RTS
SL_CHAR:
        JSR STR8V2_RAM_GETC
        CMP #3
        BEQ SL_CANCEL
        LSR SL_RX_BAD
        BCS SL_BAD
        SEC
        RTS
SL_CANCEL:
        CLC
        RTS
SL_BYTE:
        JSR SL_CHAR
        BCC SL_RETURN
        JSR SL_HEX
        BCC SL_BAD
        ASL A
        ASL A
        ASL A
        ASL A
        STA SL_NIB
        JSR SL_CHAR
        BCC SL_RETURN
        JSR SL_HEX
        BCC SL_BAD
        ORA SL_NIB
        PHA
        CLC
        ADC SL_SUM
        STA SL_SUM
        PLA
        SEC
        RTS
SL_HEX:
        CMP #'0'
        BCC SL_HEX_BAD
        CMP #':'
        BCC SL_DECIMAL
        AND #$DF
        CMP #'A'
        BCC SL_HEX_BAD
        CMP #'G'
        BCS SL_HEX_BAD
        SEC
        SBC #('A'-10)
        SEC
        RTS
SL_DECIMAL:
        SEC
        SBC #'0'
        SEC
        RTS
SL_HEX_BAD:
        CLC
        RTS
SL_DRAIN:
        JSR STR8V2_RAM_RX_RESET
SL_DRAIN_RESTART:
        LDX #0
        LDY #$20
SL_DRAIN_POLL:
        JSR STR8V2_RAM_RAW_POLL
        BCS SL_DRAIN_RESTART
        DEX
        BNE SL_DRAIN_POLL
        DEY
        BNE SL_DRAIN_POLL
        JMP STR8V2_RAM_RX_RESET
SL_PRINT:
        STX SL_PTR
        STY SL_PTR+1
        LDY #0
SL_PRINT_CHAR:
        LDA (SL_PTR),Y
        BEQ SL_PRINT_DONE
        JSR STR8V2_RAM_PUTC
        INY
        BRA SL_PRINT_CHAR
SL_PRINT_DONE:
        RTS
SL_READY_TEXT: DB "SEND S19 (S0/S1/S9); Ctrl-C cancels",13,10,0
SL_DONE_TEXT: DB "S19 loaded; entry $",0
SL_ERROR_TEXT: DB "S19 stopped $",0
SL_END:
        ENDMOD
        END
