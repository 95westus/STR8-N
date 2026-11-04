; AREA admits a B0/B1 record arena. AUTO finds its append tail, never FF payload.
; S commits only fresh bytes. All code stays in RAM; F, C/D and SRAM never written.
WS_BANK_ARG:
        JSR W_SKIP
        SEC
        SBC #'0'
        CMP #2
        BCS WS_BAD_BANK
        STA W_TMP
        INX
        LDA W_LINE,X
        CMP #' '
        BNE WS_BAD_BANK
        SEC
        RTS
WS_BAD_BANK:
        CLC
        RTS
WS_AREA:
        JSR W_SKIP
        BNE WS_AREA_ARGS
        STZ W_AREA_ON
        BRA WS_AREA_MESSAGE
WS_AREA_ARGS:
        JSR WS_BANK_ARG
        BCC W_UNHANDLED
        LDA W_TMP
        STA W_STORE_INDEX
        JSR W_HEX_WORD
        BCC W_UNHANDLED
        LDA W_VALUE
        STA W_STORE_FIRST
        LDA W_VALUE+1
        STA W_STORE_FIRST+1
        CMP #$80
        BCC W_RANGE
        JSR W_HEX_WORD
        BCC W_UNHANDLED
        JSR W_END_ARGS
        BCC W_UNHANDLED
        LDA W_VALUE+1
        CMP #$E0
        BCS W_RANGE
        CMP W_STORE_FIRST+1
        BCC W_RANGE
        BNE WS_AREA_BOUNDS
        LDA W_VALUE
        CMP W_STORE_FIRST
        BCC W_RANGE
WS_AREA_BOUNDS:
        ; Store the exclusive window limit; user supplies an inclusive last.
        INC W_VALUE
        BNE WS_AREA_SET
        INC W_VALUE+1
WS_AREA_SET:
        LDA W_STORE_FIRST
        STA W_AREA_FIRST
        LDA W_STORE_FIRST+1
        STA W_AREA_FIRST+1
        LDA W_VALUE
        STA W_AREA_END
        LDA W_VALUE+1
        STA W_AREA_END+1
        LDA W_STORE_INDEX
        STA W_AREA_BANK
        LDA #1
        STA W_AREA_ON
WS_AREA_MESSAGE:
        JSR WB_SAVE
        LDX #<WS_AREA_TEXT
        LDY #>WS_AREA_TEXT
        JMP W_MESSAGE

WS_STORE:
        STZ WP_MODE
        JSR W_PROGRAM_ARGUMENT
        BCS WP_STORE
        INX
        JSR WS_BANK_ARG
        BCC W_UNHANDLED
        LDA W_AREA_ON
        BEQ WS_NO_AREA
        LDA W_TMP
        CMP W_AREA_BANK
        BNE WS_NO_AREA
        STA W_BANK
        JSR W_SKIP
        CMP #'A'
        BNE WS_EXPLICIT
        LDA W_LINE+1,X
        CMP #'U'
        BNE WS_EXPLICIT
        LDY #0
WS_AUTO_TOKEN:
        LDA W_LINE,X
        CMP WS_AUTO_WORD,Y
        BNE W_UNHANDLED
        INX
        INY
        CPY #4
        BCC WS_AUTO_TOKEN
        LDA W_LINE,X
        CMP #' '
        BNE W_UNHANDLED
        PHX
        JSR WS_AUTO_TAIL
        PLX
        BCS WS_FIRST_OK
        LDA W_BAD
        BNE WS_CANCEL
        LDX #<WS_AUTO_BAD_TEXT
        LDY #>WS_AUTO_BAD_TEXT
        JMP W_RECORD_ERROR
WS_EXPLICIT:
        JSR W_HEX_WORD
        BCC W_UNHANDLED
        LDA W_VALUE
        STA W_ADDR
        STA W_STORE_FIRST
        LDA W_VALUE+1
        STA W_ADDR+1
        STA W_STORE_FIRST+1
        CMP W_AREA_FIRST+1
        BCC W_RANGE
        BNE WS_FIRST_OK
        LDA W_ADDR
        CMP W_AREA_FIRST
        BCC W_RANGE
WS_FIRST_OK:
        LDY #23
        LDA #0
WS_CLEAR_HEADER:
        STA W_HEADER,Y
        DEY
        BPL WS_CLEAR_HEADER
        JSR W_HEX_WORD
        BCC W_UNHANDLED
        LDA W_VALUE
        STA W_HEADER+4
        LDA W_VALUE+1
        STA W_HEADER+5
        CMP #2
        BCC W_RANGE
        JSR W_HEX_WORD
        BCC W_UNHANDLED
        LDA W_VALUE+1
        CMP #>WB_ORIGIN
        BCS W_RANGE
        SEC
        LDA W_VALUE
        SBC W_HEADER+4
        STA W_HEADER+6
        LDA W_VALUE+1
        SBC W_HEADER+5
        BCC W_RANGE
        STA W_HEADER+7
        INC W_HEADER+6
        BNE WS_NAME
        INC W_HEADER+7
WS_NAME:
        JSR W_SKIP
        LDY #0
WS_NAME_BYTE:
        LDA W_LINE,X
        BEQ WS_NAME_END
        CMP #' '
        BEQ WS_NAME_END
        CPY #16
        BCS W_UNHANDLED
        STA W_HEADER+8,Y
        INX
        INY
        BRA WS_NAME_BYTE
WS_NAME_END:
        JSR W_END_ARGS
        BCC W_UNHANDLED
        LDA #'S'
        STA W_HEADER
        LDA #'R'
        STA W_HEADER+1
        LDA #1
        STA W_HEADER+2
        LDA #$FF
        STA W_HEADER+3
        LDA WP_MODE
        BNE WP_STORE_READY
        JSR W_CHECK_HEADER
        BCC W_RANGE
        LDA W_AREA_END+1
        CMP W_END+1
        BCC W_RANGE
        BNE WS_PREFLIGHT
        LDA W_AREA_END
        CMP W_END
        BCC W_RANGE
WS_PREFLIGHT:
        STZ W_CACHE_VALID
WS_BLANK_BYTE:
        JSR W_CANCEL
        BCS WS_CANCEL
        JSR W_FLASH_BYTE
        CMP #$FF
        BNE WS_OCCUPIED
        INC W_ADDR
        BNE WS_BLANK_NEXT
        INC W_ADDR+1
WS_BLANK_NEXT:
        LDA W_ADDR+1
        CMP W_END+1
        BNE WS_BLANK_BYTE
        LDA W_ADDR
        CMP W_END
        BNE WS_BLANK_BYTE
        LDA W_STORE_FIRST
        STA W_ADDR
        LDA W_STORE_FIRST+1
        STA W_ADDR+1
        LDX #<WS_TARGET_TEXT
        LDY #>WS_TARGET_TEXT
        JSR W_PUTS
        JSR W_SHOW_LOCATION
        JSR STR8V2_RAM_NEWLINE
WS_CONFIRM_DIALOG:
        LDX #<WS_CONFIRM_TEXT
        LDY #>WS_CONFIRM_TEXT
        JSR W_PUTS
        ; Keep the requesting console for confirmation and skip its optional LF.
        STZ W_LEN
        LDA W_RX_BAD
        STA W_BAD
        LDA W_DC_LAST
        STA W_DC_OWNER
        TSB W_SKIP_LF
        JSR W_KEEP_OWNER
        BCC WS_CANCEL
        LDX #<WS_YES_WORD
        LDY #>WS_YES_WORD
        JSR W_MATCH
        BCC WS_CANCEL
        JSR W_END_ARGS
        BCC WS_CANCEL
        JSR W_CANCEL
        BCS WS_CANCEL
        LDA WP_MODE
        BNE WP_STORE_COMMIT
        ; Suppress the foundation NMI path while the chip can be busy. An
        ; arbitrary owner NMI/DMA agent is outside this foreground contract.
        LDA W_F_NMI_GATE
        STA W_STORE_GATE
        LDA #1
        STA W_F_NMI_GATE
        LDA W_STORE_FIRST
        STA W_ADDR
        LDA W_STORE_FIRST+1
        STA W_ADDR+1
        STZ W_STORE_INDEX
WS_WRITE_HEADER:
        LDY W_STORE_INDEX
        LDA W_HEADER,Y
        JSR WS_BYTE
        JSR WS_ADVANCE
        INC W_STORE_INDEX
        LDA W_STORE_INDEX
        CMP #24
        BCC WS_WRITE_HEADER
        LDA W_HEADER+4
        STA W_STORE_NEXT
        LDA W_HEADER+5
        STA W_STORE_NEXT+1
        LDA W_HEADER+6
        STA W_STORE_LEFT
        LDA W_HEADER+7
        STA W_STORE_LEFT+1
WS_WRITE_BODY:
        LDA W_STORE_NEXT
        STA W_COPY
        LDA W_STORE_NEXT+1
        STA W_COPY+1
        LDA (W_COPY)
        JSR WS_BYTE
        JSR WS_ADVANCE
        INC W_STORE_NEXT
        BNE WS_BODY_LEFT
        INC W_STORE_NEXT+1
WS_BODY_LEFT:
        LDA W_STORE_LEFT
        BNE WS_BODY_DEC
        DEC W_STORE_LEFT+1
WS_BODY_DEC:
        DEC W_STORE_LEFT
        LDA W_STORE_LEFT
        ORA W_STORE_LEFT+1
        BNE WS_WRITE_BODY
        ; Commit once, last: fresh FF -> complete 3F. No sector rewrite.
        CLC
        LDA W_STORE_FIRST
        ADC #3
        STA W_ADDR
        LDA W_STORE_FIRST+1
        ADC #0
        STA W_ADDR+1
        LDA #$3F
        JSR WS_BYTE
        LDA W_STORE_GATE
        STA W_F_NMI_GATE
        STZ W_CACHE_VALID
        LDX #<WS_OK_TEXT
        LDY #>WS_OK_TEXT
        JMP W_MESSAGE
WS_ADVANCE:
        INC W_ADDR
        BNE WS_ADVANCE_DONE
        INC W_ADDR+1
WS_ADVANCE_DONE:
        RTS
WS_BYTE:
        STA W_F_DATA
        CMP #$FF
        BEQ WS_BYTE_DONE
        LDA W_BANK
        JSR WB_F_SELECT
        LDA W_ADDR
        STA W_F_FLASH_PTR
        LDA W_ADDR+1
        STA W_F_FLASH_PTR+1
        LDY #0
        JSR WB_F_BYTE
        BCC WS_FAILED
        LDY #0
        LDA (W_F_FLASH_PTR),Y
        CMP W_F_DATA
        BNE WS_FAILED
        LDA #3
        JSR WB_F_SELECT
        LDA #1
        STA W_LED
WS_BYTE_DONE:
        RTS
WS_FAILED:
        ; Never return into ROM while chip-idle status is uncertain.
        LDA #'!'
        JSR STR8V2_RAM_PUTC
        LDA #1
        STA W_LED
WS_HALT:
        BRA WS_HALT

; Scan from8000 so an AREA beginning inside a structural record is refused.
; Outside AREA, unknown bytes are ignored. Inside, only FF and valid SR01
; complete/pending records are admitted. Gaps are not reclaimed automatically.
; Called before building the new header: the validator may use W_HEADER.
WS_AUTO_TAIL:
        LDA W_AREA_FIRST
        STA W_STORE_FIRST
        LDA W_AREA_FIRST+1
        STA W_STORE_FIRST+1
        STZ W_ADDR
        LDA #$80
        STA W_ADDR+1
        STZ W_CACHE_VALID
WS_AUTO_SCAN:
        JSR W_CANCEL
        BCS WS_AUTO_BAD
        LDA W_ADDR+1
        CMP W_AREA_END+1
        BCC WS_AUTO_BYTE
        BNE WS_AUTO_DONE
        LDA W_ADDR
        CMP W_AREA_END
        BCS WS_AUTO_DONE
WS_AUTO_BYTE:
        JSR W_FLASH_BYTE
        CMP #$FF
        BEQ WS_AUTO_ADVANCE
        CMP #'S'
        BNE WS_AUTO_UNKNOWN
        JSR W_VALIDATE_RECORD
        BCC WS_AUTO_UNKNOWN
        ; A record ending before AREA does not occupy the admitted arena.
        LDA W_END+1
        CMP W_AREA_FIRST+1
        BCC WS_AUTO_SKIP
        BNE WS_AUTO_OVERLAP
        LDA W_END
        CMP W_AREA_FIRST
        BCC WS_AUTO_SKIP
        BEQ WS_AUTO_SKIP
WS_AUTO_OVERLAP:
        ; Crossing either AREA boundary is unsafe, even with erased payload.
        JSR WS_AUTO_IN_AREA
        BCC WS_AUTO_BAD
        LDA W_AREA_END+1
        CMP W_END+1
        BCC WS_AUTO_BAD
        BNE WS_AUTO_TAIL_SET
        LDA W_AREA_END
        CMP W_END
        BCC WS_AUTO_BAD
WS_AUTO_TAIL_SET:
        LDA W_END
        STA W_STORE_FIRST
        LDA W_END+1
        STA W_STORE_FIRST+1
WS_AUTO_SKIP:
        JSR W_SKIP_RECORD
        BRA WS_AUTO_SCAN
WS_AUTO_UNKNOWN:
        JSR WS_AUTO_IN_AREA
        BCS WS_AUTO_BAD
WS_AUTO_ADVANCE:
        INC W_ADDR
        BNE WS_AUTO_SCAN
        INC W_ADDR+1
        BRA WS_AUTO_SCAN
WS_AUTO_DONE:
        LDA W_STORE_FIRST
        STA W_ADDR
        LDA W_STORE_FIRST+1
        STA W_ADDR+1
        SEC
        RTS
WS_AUTO_IN_AREA:
        LDA W_ADDR+1
        CMP W_AREA_FIRST+1
        BNE WS_AUTO_RETURN
        LDA W_ADDR
        CMP W_AREA_FIRST
WS_AUTO_RETURN:
        RTS
WS_AUTO_BAD:
        CLC
        RTS
WS_NO_AREA:
        LDX #<WS_NO_AREA_TEXT
        LDY #>WS_NO_AREA_TEXT
        JMP W_RECORD_ERROR
WS_OCCUPIED:
        LDX #<WS_OCCUPIED_TEXT
        LDY #>WS_OCCUPIED_TEXT
        JMP W_RECORD_ERROR
WS_CANCEL:
        LDA #WB_CANCELED
        STA W_RESULT
        LDX #<WS_CANCEL_TEXT
        LDY #>WS_CANCEL_TEXT
        JMP W_MESSAGE
WS_AREA_WORD: DB "AREA",0
WS_HELP_WORD: DB "HELP",0
WS_YES_WORD: DB "YES",0
WS_AUTO_WORD: DB "AUTO"
WS_AUTO_BAD_TEXT: DB "REFUSED: AREA overlap/corrupt",13,10,0
WS_TARGET_TEXT: DB "Target ",0
WS_AREA_TEXT: DB "AREA updated (RAM only)",13,10,0
WS_NO_AREA_TEXT: DB "REFUSED: declare AREA bank first last (B0/B1)",13,10,0
WS_OCCUPIED_TEXT: DB "REFUSED: target not entirely erased",13,10,0
WS_CONFIRM_TEXT: DB "STORE, no erase; type YES> ",0
WS_CANCEL_TEXT: DB "Canceled; no record written",13,10,0
WS_OK_TEXT: DB "Stored; verified bytes, commit last; no payload CRC",13,10,0
