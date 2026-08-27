; ----------------------------------------------------------------------------
; WDCMONV2STR8N-ARCHIVE-2000.ASM
;
; Read-only stock W65C02SXB (+ optional W65C02EDU) migration first stage.
;
; Load as an ordinary WDCMONv2 RAM program at $2000 and start $2000.  Once
; entered, this program uses only RAM code/data and the board FT245R/VIA
; registers.  It does not call WDCMONv2 and contains no flash erase/program
; sequence.
;
; M inventories all four 32K flash banks.  0-3 emits the selected bank as
; dense 32-byte S1 records followed by S9.  W2R-BEGIN/W2R-END receipts frame
; the S19 for a host terminal/file front end.  FNV1A is over exactly the
; $8000 bytes mapped at CPU $8000-$FFFF, in ascending address order.
;
; RAM ownership:
;   $00C0-$00C1  private indirect pointer
;   $2000-...    program, messages, and state
;   stack reset to $01FF
;
; Operational boundary:
;   - IRQ is disabled.  Do not assert NMI or RESET during a dump.
;   - Every bank operation returns selection to Bank 3 before the prompt.
;   - Q halts in RAM; physical RESET returns to the stock Bank-3 monitor.
; ----------------------------------------------------------------------------

                        MODULE          WDCMONV2STR8N_ARCHIVE
                        XDEF            START

W2R_PTR_LO              EQU             $C0
W2R_PTR_HI              EQU             $C1

W2R_FTDI_CTRL           EQU             $7FE0
W2R_FTDI_DATA           EQU             $7FE1
W2R_FTDI_DDRB           EQU             $7FE2
W2R_FTDI_DDRA           EQU             $7FE3
W2R_BANK_PCR            EQU             $7FEC

W2R_FTDI_TXE            EQU             $01
W2R_FTDI_RXF            EQU             $02
W2R_FTDI_WR             EQU             $04
W2R_FTDI_RD             EQU             $08
W2R_FTDI_INIT           EQU             $0C
W2R_BANK_MASK           EQU             $EE
W2R_BANK_COUNT          EQU             $04

                        CODE
                        ORG             $2000

START:
                        SEI
                        CLD
                        LDX             #$FF
                        TXS
                        JSR             W2R_CON_INIT
                        LDX             #<W2R_MSG_TITLE
                        LDY             #>W2R_MSG_TITLE
                        JSR             W2R_PUTS
                        JSR             W2R_MAP

W2R_COMMAND_LOOP:
                        LDX             #<W2R_MSG_PROMPT
                        LDY             #>W2R_MSG_PROMPT
                        JSR             W2R_PUTS
                        JSR             W2R_GET_COMMAND
                        CMP             #'M'
                        BEQ             W2R_COMMAND_MAP
                        CMP             #'Q'
                        BEQ             W2R_COMMAND_QUIT
                        CMP             #'0'
                        BCC             W2R_COMMAND_BAD
                        CMP             #'4'
                        BCS             W2R_COMMAND_BAD
                        SEC
                        SBC             #'0'
                        STA             W2R_BANK
                        JSR             W2R_DUMP_BANK
                        BRA             W2R_COMMAND_LOOP

W2R_COMMAND_MAP:
                        JSR             W2R_MAP
                        BRA             W2R_COMMAND_LOOP

W2R_COMMAND_BAD:
                        LDX             #<W2R_MSG_BAD
                        LDY             #>W2R_MSG_BAD
                        JSR             W2R_PUTS
                        BRA             W2R_COMMAND_LOOP

W2R_COMMAND_QUIT:
                        LDA             #$03
                        JSR             W2R_SELECT_BANK_A
                        LDX             #<W2R_MSG_HALT
                        LDY             #>W2R_MSG_HALT
                        JSR             W2R_PUTS
?HALT:                  BRA             ?HALT

; Print an inventory row for each bank, then compare the whole-bank B0 and B3
; fingerprints.  A hash match is identity evidence, not permission to erase.
W2R_MAP:
                        LDX             #<W2R_MSG_MAP
                        LDY             #>W2R_MSG_MAP
                        JSR             W2R_PUTS
                        STZ             W2R_BANK
?BANK:
                        LDA             W2R_BANK
                        JSR             W2R_SELECT_BANK_A
                        JSR             W2R_HASH_BANK
                        JSR             W2R_CAPTURE_VECTORS
                        JSR             W2R_STORE_BANK_HASH
                        JSR             W2R_PRINT_MAP_ROW
                        INC             W2R_BANK
                        LDA             W2R_BANK
                        CMP             #W2R_BANK_COUNT
                        BNE             ?BANK

                        LDX             #$00
?COMPARE:               LDA             W2R_BANK_HASHES,X
                        CMP             W2R_BANK_HASHES+12,X
                        BNE             ?DIFFERENT
                        INX
                        CPX             #$04
                        BNE             ?COMPARE
                        LDX             #<W2R_MSG_B0_B3_SAME
                        LDY             #>W2R_MSG_B0_B3_SAME
                        BRA             ?RESULT
?DIFFERENT:             LDX             #<W2R_MSG_B0_B3_DIFFERENT
                        LDY             #>W2R_MSG_B0_B3_DIFFERENT
?RESULT:                JSR             W2R_PUTS
                        LDA             #$03
                        JMP             W2R_SELECT_BANK_A

W2R_PRINT_MAP_ROW:
                        LDA             #'B'
                        JSR             W2R_OUT
                        LDA             W2R_BANK
                        ORA             #'0'
                        JSR             W2R_OUT
                        LDA             #' '
                        JSR             W2R_OUT
                        LDA             W2R_ERASED
                        BEQ             ?USED
                        LDX             #<W2R_MSG_ERASED
                        LDY             #>W2R_MSG_ERASED
                        BRA             ?STATE
?USED:                  LDX             #<W2R_MSG_USED
                        LDY             #>W2R_MSG_USED
?STATE:                 JSR             W2R_PUTS
                        LDX             #<W2R_MSG_FNV
                        LDY             #>W2R_MSG_FNV
                        JSR             W2R_PUTS
                        JSR             W2R_PRINT_HASH
                        LDX             #<W2R_MSG_NMI
                        LDY             #>W2R_MSG_NMI
                        JSR             W2R_PUTS
                        LDA             W2R_NMI_HI
                        JSR             W2R_PUT_HEX_BYTE
                        LDA             W2R_NMI_LO
                        JSR             W2R_PUT_HEX_BYTE
                        LDX             #<W2R_MSG_RESET
                        LDY             #>W2R_MSG_RESET
                        JSR             W2R_PUTS
                        LDA             W2R_RESET_HI
                        JSR             W2R_PUT_HEX_BYTE
                        LDA             W2R_RESET_LO
                        JSR             W2R_PUT_HEX_BYTE
                        LDX             #<W2R_MSG_IRQ
                        LDY             #>W2R_MSG_IRQ
                        JSR             W2R_PUTS
                        LDA             W2R_IRQ_HI
                        JSR             W2R_PUT_HEX_BYTE
                        LDA             W2R_IRQ_LO
                        JSR             W2R_PUT_HEX_BYTE
                        JMP             W2R_CRLF

; Produce one complete archive transaction.  The begin receipt states the
; pre-read hash.  A host extractor independently rehashes the emitted S19 and
; requires it to match both receipts before writing the canonical BIN.
W2R_DUMP_BANK:
                        LDA             W2R_BANK
                        JSR             W2R_SELECT_BANK_A
                        JSR             W2R_HASH_BANK
                        JSR             W2R_CAPTURE_VECTORS

                        LDX             #<W2R_MSG_BEGIN
                        LDY             #>W2R_MSG_BEGIN
                        JSR             W2R_PUTS
                        LDA             W2R_BANK
                        ORA             #'0'
                        JSR             W2R_OUT
                        LDX             #<W2R_MSG_RECEIPT_HASH
                        LDY             #>W2R_MSG_RECEIPT_HASH
                        JSR             W2R_PUTS
                        JSR             W2R_PRINT_HASH
                        LDX             #<W2R_MSG_RECEIPT_RESET
                        LDY             #>W2R_MSG_RECEIPT_RESET
                        JSR             W2R_PUTS
                        LDA             W2R_RESET_HI
                        JSR             W2R_PUT_HEX_BYTE
                        LDA             W2R_RESET_LO
                        JSR             W2R_PUT_HEX_BYTE
                        JSR             W2R_CRLF

                        STZ             W2R_PTR_LO
                        LDA             #$80
                        STA             W2R_PTR_HI
?RECORD:               JSR             W2R_EMIT_S1_32
                        LDA             W2R_PTR_HI
                        BNE             ?RECORD
                        JSR             W2R_EMIT_S9_RESET

                        LDX             #<W2R_MSG_END
                        LDY             #>W2R_MSG_END
                        JSR             W2R_PUTS
                        LDA             W2R_BANK
                        ORA             #'0'
                        JSR             W2R_OUT
                        LDX             #<W2R_MSG_RECEIPT_HASH
                        LDY             #>W2R_MSG_RECEIPT_HASH
                        JSR             W2R_PUTS
                        JSR             W2R_PRINT_HASH
                        JSR             W2R_CRLF
                        LDA             #$03
                        JMP             W2R_SELECT_BANK_A

; Emit S1 count=$23, current address, 32 bytes, checksum, CR/LF.  The pointer
; advances by exactly 32 and wraps to $0000 after the final $FFE0 record.
W2R_EMIT_S1_32:
                        STZ             W2R_SREC_SUM
                        LDA             #'S'
                        JSR             W2R_OUT
                        LDA             #'1'
                        JSR             W2R_OUT
                        LDA             #$23
                        JSR             W2R_SREC_PUT_SUM_A
                        LDA             W2R_PTR_HI
                        JSR             W2R_SREC_PUT_SUM_A
                        LDA             W2R_PTR_LO
                        JSR             W2R_SREC_PUT_SUM_A
                        LDX             #$20
?DATA:                 LDY             #$00
                        LDA             (W2R_PTR_LO),Y
                        JSR             W2R_SREC_PUT_SUM_A
                        INC             W2R_PTR_LO
                        BNE             ?COUNT
                        INC             W2R_PTR_HI
?COUNT:                DEX
                        BNE             ?DATA
                        LDA             W2R_SREC_SUM
                        EOR             #$FF
                        JSR             W2R_PUT_HEX_BYTE
                        JMP             W2R_CRLF

W2R_EMIT_S9_RESET:
                        STZ             W2R_SREC_SUM
                        LDA             #'S'
                        JSR             W2R_OUT
                        LDA             #'9'
                        JSR             W2R_OUT
                        LDA             #$03
                        JSR             W2R_SREC_PUT_SUM_A
                        LDA             W2R_RESET_HI
                        JSR             W2R_SREC_PUT_SUM_A
                        LDA             W2R_RESET_LO
                        JSR             W2R_SREC_PUT_SUM_A
                        LDA             W2R_SREC_SUM
                        EOR             #$FF
                        JSR             W2R_PUT_HEX_BYTE
                        JMP             W2R_CRLF

W2R_SREC_PUT_SUM_A:
                        PHA
                        CLC
                        ADC             W2R_SREC_SUM
                        STA             W2R_SREC_SUM
                        PLA
                        JMP             W2R_PUT_HEX_BYTE

; Whole-bank FNV-1a.  W2R_ERASED remains nonzero only when every byte is $FF.
W2R_HASH_BANK:
                        JSR             W2R_FNV_INIT
                        LDA             #$FF
                        STA             W2R_ERASED
                        STZ             W2R_PTR_LO
                        LDA             #$80
                        STA             W2R_PTR_HI
?BYTE:                 LDY             #$00
                        LDA             (W2R_PTR_LO),Y
                        CMP             #$FF
                        BEQ             ?HASH
                        STZ             W2R_ERASED
?HASH:                 JSR             W2R_FNV_UPDATE_A
                        INC             W2R_PTR_LO
                        BNE             ?BYTE
                        INC             W2R_PTR_HI
                        BNE             ?BYTE
                        RTS

W2R_FNV_INIT:
                        LDX             #$03
?BYTE:                 LDA             W2R_FNV_OFFSET,X
                        STA             W2R_HASH0,X
                        DEX
                        BPL             ?BYTE
                        RTS

; FNV prime $01000193 = 1 + 2 + 16 + 128 + 256 + 16777216.
W2R_FNV_UPDATE_A:
                        EOR             W2R_HASH0
                        STA             W2R_HASH0
                        JSR             W2R_COPY_HASH_TERM
                        LDX             #$01
                        JSR             W2R_SHLADD_TERM_N
                        LDX             #$03
                        JSR             W2R_SHLADD_TERM_N
                        LDX             #$03
                        JSR             W2R_SHLADD_TERM_N
                        LDX             #$01
                        JSR             W2R_SHLADD_TERM_N
                        LDA             W2R_HASH3
                        CLC
                        ADC             W2R_TERM1
                        STA             W2R_HASH3
                        RTS

W2R_COPY_HASH_TERM:
                        LDX             #$03
?BYTE:                 LDA             W2R_HASH0,X
                        STA             W2R_TERM0,X
                        DEX
                        BPL             ?BYTE
                        RTS

W2R_SHLADD_TERM_N:
?SHIFT:                ASL             W2R_TERM0
                        ROL             W2R_TERM1
                        ROL             W2R_TERM2
                        ROL             W2R_TERM3
                        DEX
                        BNE             ?SHIFT
                        CLC
                        LDA             W2R_HASH0
                        ADC             W2R_TERM0
                        STA             W2R_HASH0
                        LDA             W2R_HASH1
                        ADC             W2R_TERM1
                        STA             W2R_HASH1
                        LDA             W2R_HASH2
                        ADC             W2R_TERM2
                        STA             W2R_HASH2
                        LDA             W2R_HASH3
                        ADC             W2R_TERM3
                        STA             W2R_HASH3
                        RTS

W2R_CAPTURE_VECTORS:
                        LDA             $FFFA
                        STA             W2R_NMI_LO
                        LDA             $FFFB
                        STA             W2R_NMI_HI
                        LDA             $FFFC
                        STA             W2R_RESET_LO
                        LDA             $FFFD
                        STA             W2R_RESET_HI
                        LDA             $FFFE
                        STA             W2R_IRQ_LO
                        LDA             $FFFF
                        STA             W2R_IRQ_HI
                        RTS

W2R_STORE_BANK_HASH:
                        LDA             W2R_BANK
                        ASL             A
                        ASL             A
                        TAX
                        LDA             W2R_HASH0
                        STA             W2R_BANK_HASHES,X
                        INX
                        LDA             W2R_HASH1
                        STA             W2R_BANK_HASHES,X
                        INX
                        LDA             W2R_HASH2
                        STA             W2R_BANK_HASHES,X
                        INX
                        LDA             W2R_HASH3
                        STA             W2R_BANK_HASHES,X
                        RTS

W2R_PRINT_HASH:
                        LDA             W2R_HASH3
                        JSR             W2R_PUT_HEX_BYTE
                        LDA             W2R_HASH2
                        JSR             W2R_PUT_HEX_BYTE
                        LDA             W2R_HASH1
                        JSR             W2R_PUT_HEX_BYTE
                        LDA             W2R_HASH0
                        JMP             W2R_PUT_HEX_BYTE

; The exact selector used by STR8-N.  All caller code, data, messages, stack,
; and return addresses are below $8000.
W2R_SELECT_BANK_A:
                        AND             #$03
                        TAX
                        LDA             W2R_BANK_BITS,X
                        PHA
                        LDA             #W2R_BANK_MASK
                        TRB             W2R_BANK_PCR
                        PLA
                        TSB             W2R_BANK_PCR
                        RTS

W2R_CON_INIT:
                        LDA             #W2R_FTDI_INIT
                        STA             W2R_FTDI_CTRL
                        STA             W2R_FTDI_DDRB
                        STZ             W2R_FTDI_DDRA
                        RTS

W2R_GET_COMMAND:
?WAIT:                 JSR             W2R_IN
                        CMP             #$0D
                        BEQ             ?WAIT
                        CMP             #$0A
                        BEQ             ?WAIT
                        CMP             #'a'
                        BCC             ?ECHO
                        CMP             #'z'+1
                        BCS             ?ECHO
                        AND             #$DF
?ECHO:                 PHA
                        JSR             W2R_OUT
                        JSR             W2R_CRLF
                        PLA
                        RTS

W2R_IN:
                        STZ             W2R_FTDI_DDRA
                        LDA             #W2R_FTDI_RXF
?WAIT:                 BIT             W2R_FTDI_CTRL
                        BNE             ?WAIT
                        LDA             #W2R_FTDI_RD
                        TRB             W2R_FTDI_CTRL
                        NOP
                        NOP
                        LDA             W2R_FTDI_DATA
                        PHA
                        LDA             #W2R_FTDI_RD
                        TSB             W2R_FTDI_CTRL
                        PLA
                        RTS

W2R_OUT:
                        PHA
                        STZ             W2R_FTDI_DDRA
                        STA             W2R_FTDI_DATA
                        NOP
                        NOP
                        LDA             #W2R_FTDI_TXE
?WAIT:                 BIT             W2R_FTDI_CTRL
                        BNE             ?WAIT
                        LDA             #W2R_FTDI_WR
                        TSB             W2R_FTDI_CTRL
                        DEC             W2R_FTDI_DDRA
                        NOP
                        NOP
                        LDA             #W2R_FTDI_WR
                        TRB             W2R_FTDI_CTRL
                        STZ             W2R_FTDI_DDRA
                        PLA
                        RTS

W2R_PUTS:
                        STX             W2R_PTR_LO
                        STY             W2R_PTR_HI
                        LDY             #$00
?BYTE:                 LDA             (W2R_PTR_LO),Y
                        BEQ             ?DONE
                        JSR             W2R_OUT
                        INY
                        BNE             ?BYTE
                        INC             W2R_PTR_HI
                        BRA             ?BYTE
?DONE:                 RTS

W2R_PUT_HEX_BYTE:
                        PHA
                        LSR             A
                        LSR             A
                        LSR             A
                        LSR             A
                        JSR             W2R_PUT_HEX_NIBBLE
                        PLA
                        AND             #$0F
W2R_PUT_HEX_NIBBLE:
                        CMP             #$0A
                        BCC             ?DIGIT
                        CLC
                        ADC             #('A'-10)
                        JMP             W2R_OUT
?DIGIT:                CLC
                        ADC             #'0'
                        JMP             W2R_OUT

W2R_CRLF:
                        LDA             #$0D
                        JSR             W2R_OUT
                        LDA             #$0A
                        JMP             W2R_OUT

                        DATA
W2R_BANK_BITS:          DB              $CC,$CE,$EC,$EE
W2R_FNV_OFFSET:         DB              $C5,$9D,$1C,$81

W2R_MSG_TITLE:          DB              $0D,$0A,"WDCMONV2 -> STR8-N ARCHIVE 0.1",$0D,$0A
                        DB              "READ ONLY; NO FLASH WRITE CODE",$0D,$0A
                        DB              "DO NOT PRESS NMI/RESET DURING DUMP",$0D,$0A,0
W2R_MSG_MAP:            DB              $0D,$0A,"BANK INVENTORY",$0D,$0A,0
W2R_MSG_PROMPT:         DB              $0D,$0A,"0-3=DUMP M=MAP Q=HALT> ",0
W2R_MSG_BAD:            DB              "? USE 0-3, M, OR Q",$0D,$0A,0
W2R_MSG_HALT:           DB              "HALTED; PHYSICAL RESET RETURNS TO BANK 3",$0D,$0A,0
W2R_MSG_ERASED:         DB              "ERASED",0
W2R_MSG_USED:           DB              "USED",0
W2R_MSG_FNV:            DB              " FNV1A=",0
W2R_MSG_NMI:            DB              " NMI=",0
W2R_MSG_RESET:          DB              " RESET=",0
W2R_MSG_IRQ:            DB              " IRQ=",0
W2R_MSG_B0_B3_SAME:     DB              "B0_EQ_B3=YES (HASH ONLY)",$0D,$0A,0
W2R_MSG_B0_B3_DIFFERENT: DB             "B0_EQ_B3=NO",$0D,$0A,0
W2R_MSG_BEGIN:          DB              $0D,$0A,"W2R-BEGIN B=",0
W2R_MSG_END:            DB              "W2R-END B=",0
W2R_MSG_RECEIPT_HASH:   DB              " BYTES=8000 FNV1A=",0
W2R_MSG_RECEIPT_RESET:  DB              " RESET=",0

W2R_BANK:               DB              $00
W2R_ERASED:             DB              $00
W2R_SREC_SUM:           DB              $00
W2R_HASH0:              DB              $00
W2R_HASH1:              DB              $00
W2R_HASH2:              DB              $00
W2R_HASH3:              DB              $00
W2R_TERM0:              DB              $00
W2R_TERM1:              DB              $00
W2R_TERM2:              DB              $00
W2R_TERM3:              DB              $00
W2R_NMI_LO:             DB              $00
W2R_NMI_HI:             DB              $00
W2R_RESET_LO:           DB              $00
W2R_RESET_HI:           DB              $00
W2R_IRQ_LO:             DB              $00
W2R_IRQ_HI:             DB              $00
W2R_BANK_HASHES:        DS              16

                        END
