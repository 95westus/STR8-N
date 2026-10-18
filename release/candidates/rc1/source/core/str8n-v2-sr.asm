; STR8-N 2.0a24 Bank-3 S/R/T extension. The F monitor remains bootable without it.
; All target-bank reads and writes pass through the already-copied RAM worker.
                        MODULE  V2_SR
                        XDEF    SR_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "sr-monitor-symbols.inc"
                        INCLUDE "vectors-symbols.inc"

; Private extension state. This window is unused by the alpha21 monitor.
SR_REQUEST              EQU     $7D90   ; bank, flash, RAM start/end, label[16]
SR_HEADER               EQU     $7DA8   ; 24-byte on-flash header
SR_RECORD               EQU     $7DC0
SR_CURSOR               EQU     $7DC2
SR_LIMIT                EQU     $7DC4
SR_OLD_BANK             EQU     $7DC6
SR_BANK                 EQU     $7DC7
SR_INDEX                EQU     $7DC8
SR_SCAN                 EQU     $7DC9
SR_ERROR                EQU     $7DCA
SR_HEADER_SIZE          EQU     $18
SR_PENDING              EQU     $FF
SR_COMPLETE             EQU     $3F

                        CODE
; The descriptor and five three-byte JMP slots are a separate, versioned ABI.
SR_DESCRIPTOR:          DB      "SR",$03,$01,$18,$00,$00,$00
SR_COMMAND_SAVE:        JMP     SR_CLI_SAVE       ; $E808
SR_COMMAND_RESTORE:     JMP     SR_CLI_RESTORE    ; $E80B
SR_COMMAND_TABLE:       JMP     SR_CLI_TABLE      ; $E80E
SR_ENTRY_SAVE:          JMP     SR_API_SAVE       ; $E811
SR_ENTRY_RESTORE:       JMP     SR_API_RESTORE    ; $E814

; API: A/X = low/high byte of a 23-byte request in application RAM.
; C=1,A=0 success; C=0,A=error: 1 argument, 2 occupied, 3 flash failure,
; 4 invalid record. X/Y and monitor scratch clobbered. Bank 3 on entry/exit.
; IRQ disabled, decimal clear, 65C02 or 816 emulation with DBR/PBR=0.
SR_API_SAVE:            JSR     SR_COPY_REQUEST
                        LDA     SR_REQUEST
                        CMP     #$04
                        BCS SR_SAVE_BAD
                        STA     SR_BANK
                        LDA     SR_REQUEST+1
                        STA     SR_RECORD
                        LDA     SR_REQUEST+2
                        STA     SR_RECORD+1
                        LDA     SR_REQUEST+3
                        STA     SR_HEADER+4
                        LDA     SR_REQUEST+4
                        STA     SR_HEADER+5
                        LDA     SR_REQUEST+5
                        SEC
                        SBC     SR_REQUEST+3
                        STA     SR_HEADER+6
                        LDA     SR_REQUEST+6
                        SBC     SR_REQUEST+4
                        BCC SR_SAVE_BAD
                        STA     SR_HEADER+7
                        INC     SR_HEADER+6
                        BNE SR_SAVE_LENGTH
                        INC     SR_HEADER+7
                        BEQ SR_SAVE_BAD
                        JMP SR_SAVE_LENGTH
SR_SAVE_BAD:            JMP     SR_ARGUMENT
SR_SAVE_LENGTH:         LDA     #'S'
                        STA     SR_HEADER
                        LDA     #'R'
                        STA     SR_HEADER+1
                        LDA     #$01
                        STA     SR_HEADER+2
                        LDA     #SR_PENDING
                        STA     SR_HEADER+3
                        LDX     #$0F
SR_SAVE_LABEL:          LDA     SR_REQUEST+7,X
                        STA     SR_HEADER+8,X
                        DEX
                        BPL SR_SAVE_LABEL
                        JSR     SR_VALIDATE
                        BCC SR_SAVE_BAD
                        LDA     V2_SELECTED
                        STA     SR_OLD_BANK
                        LDA     SR_BANK
                        STA     V2_SELECTED
                        JSR     SR_PREFLIGHT
                        BCC SR_SAVE_EXIT
                        JSR     SR_WRITE_RECORD
                        BCC SR_SAVE_EXIT
                        JSR     SR_COMMIT_MARKER
SR_SAVE_EXIT:           JMP     SR_RETURN_BANK

SR_API_RESTORE:         JSR     SR_COPY_REQUEST
                        LDA     SR_REQUEST
                        CMP     #$04
                        BCS SR_ARGUMENT
                        STA     SR_BANK
                        LDA     SR_REQUEST+1
                        STA     SR_RECORD
                        LDA     SR_REQUEST+2
                        STA     SR_RECORD+1
                        LDA     V2_SELECTED
                        STA     SR_OLD_BANK
                        LDA     SR_BANK
                        STA     V2_SELECTED
                        JSR     SR_HEADER_FITS
                        BCC SR_RECORD_ERROR
                        JSR     SR_LOAD_HEADER
                        JSR     SR_VALIDATE
                        BCC SR_RECORD_ERROR
                        LDA     SR_HEADER+3
                        CMP     #SR_COMPLETE
                        BNE SR_RECORD_ERROR
                        LDA     SR_HEADER+4
                        STA     V2_PTR
                        LDA     SR_HEADER+5
                        STA     V2_PTR+1
                        JSR     SR_SET_BODY_CURSOR
SR_RESTORE_BYTE:        JSR     SR_READ
                        STA     (V2_PTR)
                        INC     V2_PTR
                        BNE SR_RESTORE_NEXT
                        INC     V2_PTR+1
SR_RESTORE_NEXT:        JSR     SR_NEXT
                        JSR     SR_AT_LIMIT
                        BNE SR_RESTORE_BYTE
                        JSR     SR_SUCCESS
                        JMP SR_RETURN_BANK
SR_RECORD_ERROR:        LDA     #$04
                        JSR     SR_FAILURE
SR_RETURN_BANK:         PHP
                        PHA
                        LDA     SR_OLD_BANK
                        STA     V2_SELECTED
                        PLA
                        PLP
                        RTS
SR_ARGUMENT:            LDA     #$01
                        JMP     SR_FAILURE
SR_SUCCESS:             LDA     #$00
                        SEC
                        RTS
SR_FAILURE:             CLC
                        RTS

SR_COPY_REQUEST:        STA     V2_PTR
                        STX     V2_PTR+1
                        LDY     #$16
SR_COPY_REQ_BYTE:       LDA     (V2_PTR),Y
                        STA     SR_REQUEST,Y
                        DEY
                        BPL SR_COPY_REQ_BYTE
                        RTS

; Validate fixed metadata and calculate the exclusive flash limit. No checksum.
; Both pending and complete headers are accepted here; restore checks complete.
SR_VALIDATE:            LDA     SR_HEADER
                        CMP     #'S'
                        BNE SR_BAD_HEAD
                        LDA     SR_HEADER+1
                        CMP     #'R'
                        BNE SR_BAD_HEAD
                        LDA     SR_HEADER+2
                        CMP     #$01
                        BNE SR_BAD_HEAD
                        LDA     SR_HEADER+3
                        CMP     #SR_PENDING
                        BEQ SR_VALID_STATE
                        CMP     #SR_COMPLETE
                        BEQ SR_VALID_STATE
SR_BAD_HEAD:            JMP     SR_INVALID
SR_VALID_STATE:         LDA     SR_HEADER+6
                        ORA     SR_HEADER+7
                        BEQ SR_BAD_HEAD
                        LDA     SR_HEADER+5
                        CMP     #$02
                        BCC SR_BAD_HEAD
                        JSR SR_APPLICATION_LIMIT
                        BCS SR_BAD_HEAD
                        LDA     SR_HEADER+4
                        CLC
                        ADC     SR_HEADER+6
                        LDA     SR_HEADER+5
                        ADC     SR_HEADER+7
                        BCC str8n_v2_sr_LONG_181
                        JMP SR_INVALID
str8n_v2_sr_LONG_181:
                        JSR SR_APPLICATION_LIMIT
                        BCC SR_VALID_RAM
                        BEQ str8n_v2_sr_LONG_184
                        JMP SR_INVALID
str8n_v2_sr_LONG_184:
                        LDA     SR_HEADER+4
                        CLC
                        ADC     SR_HEADER+6
                        BEQ str8n_v2_sr_LONG_188
                        JMP SR_INVALID
str8n_v2_sr_LONG_188:
SR_VALID_RAM:           LDA     SR_RECORD+1
                        CMP     #$80
                        BCS str8n_v2_sr_LONG_191
                        JMP SR_INVALID
str8n_v2_sr_LONG_191:
                        CMP     #$E0
                        BCS SR_INVALID
                        LDA     SR_RECORD
                        CLC
                        ADC     #SR_HEADER_SIZE
                        STA     SR_LIMIT
                        LDA     SR_RECORD+1
                        ADC     #$00
                        STA     SR_LIMIT+1
                        LDA     SR_LIMIT
                        CLC
                        ADC     SR_HEADER+6
                        STA     SR_LIMIT
                        LDA     SR_LIMIT+1
                        ADC     SR_HEADER+7
                        BCS SR_INVALID
                        STA     SR_LIMIT+1
                        CMP     #$E0
                        BCC SR_VALID_EXTENT
                        BNE SR_INVALID
                        LDA     SR_LIMIT
                        BNE SR_INVALID
SR_VALID_EXTENT:       LDA SR_BANK
                        CMP #$03
                        BNE SR_VALID_NONRESIDENT
                        LDA SR_LIMIT+1
                        CMP #$A0
                        BCC SR_VALID_NONRESIDENT
                        BNE SR_INVALID
                        LDA SR_LIMIT
                        BNE SR_INVALID
                        LDA SR_BANK
                        CMP #3
                        BNE SR_VALID_NONRESIDENT
                        LDA SR_RECORD+1
                        CMP #$A0
                        BCC SR_INVALID
SR_VALID_NONRESIDENT:        LDX     #$00
SR_LABEL_CHAR:          LDA     SR_HEADER+8,X
                        BEQ SR_LABEL_PAD
                        CMP     #$21
                        BCC SR_LABEL_BAD
                        CMP     #$7F
                        BCS SR_LABEL_BAD
                        INX
                        CPX     #$10
                        BNE SR_LABEL_CHAR
                        JMP SR_VALID
SR_LABEL_PAD:           LDA     SR_HEADER+8,X
                        BNE SR_LABEL_BAD
                        INX
                        CPX     #$10
                        BNE SR_LABEL_PAD
                        JMP SR_VALID
SR_LABEL_BAD:           CLC
                        RTS
SR_VALID:               SEC
                        RTS
SR_INVALID:             CLC
                        RTS

; Do not read beyond the designated storage range while fetching a header.
SR_HEADER_FITS:         LDA     SR_RECORD+1
                        CMP     #$80
                        BCC SR_INVALID
                        CMP     #$DF
                        BCC SR_VALID
                        BNE SR_INVALID
                        LDA     SR_RECORD
                        CMP     #$E9
                        BCS SR_INVALID
                        JMP SR_VALID

SR_LOAD_HEADER:         LDA     SR_RECORD
                        STA     SR_CURSOR
                        LDA     SR_RECORD+1
                        STA     SR_CURSOR+1
                        LDX     #$00
SR_LOAD_BYTE:           PHX
                        JSR     SR_READ
                        PLX
                        STA     SR_HEADER,X
                        JSR     SR_NEXT
                        INX
                        CPX     #SR_HEADER_SIZE
                        BNE SR_LOAD_BYTE
                        RTS
SR_SET_BODY_CURSOR:     LDA     SR_RECORD
                        CLC
                        ADC     #SR_HEADER_SIZE
                        STA     SR_CURSOR
                        LDA     SR_RECORD+1
                        ADC     #$00
                        STA     SR_CURSOR+1
                        RTS
SR_READ:                LDA     SR_CURSOR
                        STA     V2_ADDR
                        LDA     SR_CURSOR+1
                        STA     V2_ADDR+1
                        LDA     #$01
                        STA     V2_COUNT
                        JSR     V2W_READ
                        LDA     V2_BYTES
                        RTS
SR_NEXT:                INC     SR_CURSOR
                        BNE SR_NEXT_DONE
                        INC     SR_CURSOR+1
SR_NEXT_DONE:           RTS
SR_AT_LIMIT:            LDA     SR_CURSOR
                        CMP     SR_LIMIT
                        BNE SR_NOT_LIMIT
                        LDA     SR_CURSOR+1
                        CMP     SR_LIMIT+1
SR_NOT_LIMIT:           RTS

SR_PREFLIGHT:           LDA     SR_RECORD
                        STA     SR_CURSOR
                        LDA     SR_RECORD+1
                        STA     SR_CURSOR+1
SR_PREFLIGHT_BYTE:      JSR     SR_READ
                        CMP     #$FF
                        BNE SR_OCCUPIED
                        JSR     SR_NEXT
                        JSR     SR_AT_LIMIT
                        BNE SR_PREFLIGHT_BYTE
                        SEC
                        RTS
SR_OCCUPIED:            LDA     #$02
                        CLC
                        RTS

; Stage each touched sector from a full snapshot. The source range and full
; target range have already been checked. Only FF cells are changed.
SR_WRITE_RECORD:        LDA     SR_RECORD
                        STA     SR_CURSOR
                        LDA     SR_RECORD+1
                        STA     SR_CURSOR+1
                        LDA     SR_HEADER+4
                        STA     V2_PTR
                        LDA     SR_HEADER+5
                        STA     V2_PTR+1
                        STZ     SR_INDEX
                        JSR     SR_SNAPSHOT
SR_STAGE_BYTE:          LDX     SR_INDEX
                        CPX     #SR_HEADER_SIZE
                        BCS SR_STAGE_BODY
                        LDA     SR_HEADER,X
                        INC     SR_INDEX
                        JMP SR_STAGE_STORE
SR_STAGE_BODY:          LDA     (V2_PTR)
                        INC     V2_PTR
                        BNE SR_STAGE_STORE
                        INC     V2_PTR+1
SR_STAGE_STORE:         STA     (V2_BUF_PTR)
                        INC     V2_BUF_PTR
                        BNE SR_STAGE_ADVANCE
                        INC     V2_BUF_PTR+1
SR_STAGE_ADVANCE:       JSR     SR_NEXT
                        JSR     SR_AT_LIMIT
                        BEQ SR_STAGE_FINAL
                        LDA     SR_CURSOR+1
                        AND     #$F0
                        CMP     V2_SECTOR
                        BEQ SR_STAGE_BYTE
                        JSR     SR_WRITE_SECTOR
                        BCC SR_STAGE_FAIL
                        JSR     SR_SNAPSHOT
                        JMP SR_STAGE_BYTE
SR_STAGE_FINAL:         JMP     SR_WRITE_SECTOR
SR_STAGE_FAIL:          RTS
SR_SNAPSHOT:            LDA     SR_CURSOR+1
                        AND     #$F0
                        STA     V2_SECTOR
                        JSR     V2W_SNAPSHOT
                        LDA     SR_CURSOR
                        STA     V2_BUF_PTR
                        LDA     SR_CURSOR+1
                        AND     #$0F
                        CLC
                        ADC     #$68
                        STA     V2_BUF_PTR+1
                        RTS
SR_WRITE_SECTOR:        STZ     V2_ERASE
                        STZ     V2_SELF
                        JSR     V2W_MUTATE
                        BCC SR_SECTOR_OK
                        LDA     #$03
                        CLC
                        RTS
SR_SECTOR_OK:           SEC
                        RTS
SR_COMMIT_MARKER:       LDA     SR_RECORD
                        CLC
                        ADC     #$03
                        STA     SR_CURSOR
                        LDA     SR_RECORD+1
                        ADC     #$00
                        STA     SR_CURSOR+1
                        JSR     SR_SNAPSHOT
                        LDA     #SR_COMPLETE
                        STA     (V2_BUF_PTR)
                        JSR     SR_WRITE_SECTOR
                        BCC SR_MARK_DONE
                        JMP     SR_SUCCESS
SR_MARK_DONE:           RTS

; Console wrappers use the same request block as the application ABI.
SR_CLI_SAVE:            LDX     #$01
                        JSR     SR_PARSE_BANK
                        BCS str8n_v2_sr_LONG_401
                        JMP SR_CLI_BAD
str8n_v2_sr_LONG_401:
                        JSR     SR_PARSE_FLASH
                        BCS str8n_v2_sr_LONG_403
                        JMP SR_CLI_BAD
str8n_v2_sr_LONG_403:
                        JSR     V2_HEX_WORD
                        BCS str8n_v2_sr_LONG_405
                        JMP SR_CLI_BAD
str8n_v2_sr_LONG_405:
                        LDA     V2_VALUE
                        STA     SR_REQUEST+3
                        LDA     V2_VALUE+1
                        STA     SR_REQUEST+4
                        JSR     V2_HEX_WORD
                        BCS str8n_v2_sr_LONG_411
                        JMP SR_CLI_BAD
str8n_v2_sr_LONG_411:
                        LDA     V2_VALUE
                        STA     SR_REQUEST+5
                        LDA     V2_VALUE+1
                        STA     SR_REQUEST+6
                        LDY     #$0F
                        LDA     #$00
SR_CLI_CLEAR_LABEL:     STA     SR_REQUEST+7,Y
                        DEY
                        BPL SR_CLI_CLEAR_LABEL
                        JSR     V2_SKIP_SPACES
                        LDY     #$00
SR_CLI_LABEL:           LDA     V2_LINE,X
                        BEQ SR_CLI_SAVE_GO
                        CMP     #' '
                        BNE str8n_v2_sr_LONG_426
                        JMP SR_CLI_BAD
str8n_v2_sr_LONG_426:
                        CPY     #$10
                        BCC str8n_v2_sr_LONG_428
                        JMP SR_CLI_BAD
str8n_v2_sr_LONG_428:
                        STA     SR_REQUEST+7,Y
                        INY
                        INX
                        JMP SR_CLI_LABEL
SR_CLI_SAVE_GO:         LDA     #<SR_REQUEST
                        LDX     #>SR_REQUEST
                        JSR     SR_API_SAVE
                        JMP SR_CLI_RESULT
; R [bank] label [L], or R bank address [L]. Run at stored RAM start by
; default; L is load-only. Unqualified labels must be unique across banks.
SR_CLI_RESTORE:         STZ SR_ERROR
                        LDX #$01
                        JSR V2_SKIP_SPACES
                        STX SR_INDEX
                        JSR SR_PARSE_BANK
                        BCC SR_R_UNQUALIFIED
                        LDA SR_REQUEST
                        STA SR_BANK
                        STA SR_SCAN
                        JSR V2_SKIP_SPACES
                        BNE str8n_v2_sr_LONG_449
                        JMP SR_CLI_BAD
str8n_v2_sr_LONG_449:
                        STX SR_INDEX
                        JSR SR_PARSE_FLASH
                        BCS SR_R_ADDRESS
                        LDX SR_INDEX
                        JMP SR_R_NAME
SR_R_UNQUALIFIED:       LDX SR_INDEX
                        STZ SR_BANK
                        LDA #$03
                        STA SR_SCAN
SR_R_NAME:              LDY #$0F
                        LDA #$00
SR_R_CLEAR:             STA SR_REQUEST+7,Y
                        DEY
                        BPL SR_R_CLEAR
                        LDY #$00
SR_R_CHAR:              LDA V2_LINE,X
                        BEQ SR_R_NAME_END
                        CMP #' '
                        BEQ SR_R_NAME_END
                        CPY #$10
                        BCS SR_CLI_BAD
                        STA SR_REQUEST+7,Y
                        INY
                        INX
                        JMP SR_R_CHAR
SR_R_NAME_END:          CPY #$00
                        BEQ SR_CLI_BAD
                        JSR SR_R_SUFFIX
                        STZ SR_INDEX
                        JMP SR_SCAN_BEGIN
SR_R_ADDRESS:           JSR SR_R_SUFFIX
                        JMP SR_R_LOAD
SR_R_SUFFIX:            JSR V2_SKIP_SPACES
                        BEQ SR_R_SUFFIX_OK
                        CMP #'L'
                        BNE SR_CLI_BAD
                        INX
                        INC SR_ERROR
                        JSR V2_SKIP_SPACES
                        BNE SR_CLI_BAD
SR_R_SUFFIX_OK:         RTS
SR_R_LOAD:
                        LDA     #<SR_REQUEST
                        LDX     #>SR_REQUEST
                        JSR     SR_API_RESTORE
                        BCC SR_CLI_ERROR
                        LDA SR_ERROR
                        BNE SR_CLI_RESULT
                        LDA SR_HEADER+4
                        STA V2_VECTOR
                        LDA SR_HEADER+5
                        STA V2_VECTOR+1
                        LDA V2_RESIDENT
                        STA V2_SELECTED
                        JMP V2W_EXECUTE
SR_CLI_RESULT:
                        BCC SR_CLI_ERROR
                        JMP     V2_FLASH_DONE
SR_CLI_BAD:             JMP     V2_BAD_HEX
SR_CLI_ERROR:           PHA
                        LDX     #V2_SR_ERROR_TEXT
                        JSR     V2_PRINT
                        PLA
                        JSR     V2_HEX_OUT
                        JMP     V2_PROMPT
; Bank 0-3, 00-03 or B0-B3; permit '-' as a range delimiter for T.
SR_PARSE_BANK:          JSR V2_SKIP_SPACES
                        CMP #'B'
                        BNE SR_BANK_DIGIT
                        INX
SR_BANK_DIGIT:          LDA V2_LINE,X
                        CMP #'0'
                        BNE SR_BANK_SINGLE
                        INX
                        LDA V2_LINE,X
                        CMP #'0'
                        BCC SR_BANK_ZERO
                        CMP #'4'
                        BCS SR_BANK_ZERO
                        JMP SR_BANK_SINGLE
SR_BANK_ZERO:           DEX
                        LDA #'0'
SR_BANK_SINGLE:         SEC
                        SBC #'0'
                        CMP #$04
                        BCS SR_PARSE_FAIL
                        STA     SR_REQUEST
                        INX
                        LDA V2_LINE,X
                        BEQ SR_BANK_OK
                        CMP #' '
                        BEQ SR_BANK_OK
                        CMP #'-'
                        BNE SR_PARSE_FAIL
SR_BANK_OK:
                        SEC
                        RTS
SR_PARSE_FLASH:         JSR     V2_HEX_WORD
                        BCC SR_PARSE_FAIL
                        LDA     V2_VALUE
                        STA     SR_REQUEST+1
                        LDA     V2_VALUE+1
                        STA     SR_REQUEST+2
                        SEC
                        RTS
SR_PARSE_FAIL:          CLC
                        RTS

; Read-only inventory. A valid candidate advances over its entire payload.
SR_CLI_TABLE:           LDX     #$01
                        LDA #$80
                        STA SR_ERROR
                        STZ SR_BANK
                        LDA #$03
                        STA SR_SCAN
                        JSR V2_SKIP_SPACES
                        BEQ SR_SCAN_BEGIN
                        JSR     SR_PARSE_BANK
                        BCC SR_CLI_BAD
                        LDA SR_REQUEST
                        STA SR_BANK
                        STA SR_SCAN
                        LDA V2_LINE,X
                        CMP #'-'
                        BNE SR_T_END
                        INX
                        JSR SR_PARSE_BANK
                        BCS str8n_v2_sr_LONG_576
                        JMP SR_CLI_BAD
str8n_v2_sr_LONG_576:
                        LDA SR_REQUEST
                        CMP SR_BANK
                        BCS str8n_v2_sr_LONG_579
                        JMP SR_CLI_BAD
str8n_v2_sr_LONG_579:
                        STA SR_SCAN
SR_T_END:
                        JSR     V2_SKIP_SPACES
                        BEQ str8n_v2_sr_LONG_583
                        JMP SR_CLI_BAD
str8n_v2_sr_LONG_583:
SR_SCAN_BEGIN:
                        LDA     V2_SELECTED
                        STA     SR_OLD_BANK
SR_SCAN_BANK:           LDA     SR_BANK
                        STA     V2_SELECTED
                        LDA     #$00
                        STA     SR_RECORD
                        LDA     #$80
                        STA     SR_RECORD+1
SR_TABLE_NEXT:          LDA SR_BANK
                        CMP #2
                        BEQ X28_SR_SKIP_BANK
                        CMP #3
                        LDA SR_RECORD+1
                        BCC X28_SR_OTHER_BANK
                        CMP #$A0
                        BRA X28_SR_LIMIT
X28_SR_OTHER_BANK:      CMP #$E0
X28_SR_LIMIT:           BCC str8n_v2_sr_LONG_601
X28_SR_SKIP_BANK:       JMP SR_TABLE_DONE
                        NOP
                        NOP
str8n_v2_sr_LONG_601:
                        JSR     SR_HEADER_FITS
                        BCS str8n_v2_sr_LONG_603
                        JMP SR_TABLE_DONE
str8n_v2_sr_LONG_603:
                        LDA     SR_RECORD
                        BNE SR_TABLE_NO_POLL
                        JSR     V2_CHECK_CANCEL
                        BCC SR_TABLE_NO_POLL
                        JMP     SR_TABLE_ABORT
SR_TABLE_NO_POLL:
                        LDA     SR_RECORD+1
                        STA     SR_CURSOR+1
                        LDA     SR_RECORD
                        STA     SR_CURSOR
                        JSR     SR_READ
                        CMP     #'S'
                        BNE SR_TABLE_ADVANCE
                        JSR     SR_LOAD_HEADER
                        JSR     SR_VALIDATE
                        BCC SR_TABLE_ADVANCE
                        BIT SR_ERROR
                        BMI SR_TABLE_PRINT
                        LDA SR_HEADER+3
                        CMP #SR_COMPLETE
                        BNE SR_TABLE_SKIP
                        LDY #$00
SR_NAME_MATCH:          LDA SR_HEADER+8,Y
                        CMP SR_REQUEST+7,Y
                        BNE SR_TABLE_SKIP
                        INY
                        CPY #$10
                        BNE SR_NAME_MATCH
                        INC SR_INDEX
                        LDA SR_BANK
                        STA SR_REQUEST
                        LDA SR_RECORD
                        STA SR_REQUEST+1
                        LDA SR_RECORD+1
                        STA SR_REQUEST+2
                        LDA SR_INDEX
                        CMP #$02
                        BCS SR_R_DUPLICATE
                        JMP SR_TABLE_SKIP
SR_TABLE_PRINT:         LDA #'B'
                        JSR V2_PUTC
                        LDA SR_BANK
                        ORA #'0'
                        JSR V2_PUTC
                        LDA #':'
                        JSR V2_PUTC
                        JSR     SR_TABLE_ROW
SR_TABLE_SKIP:
                        LDA     SR_LIMIT
                        STA     SR_RECORD
                        LDA     SR_LIMIT+1
                        STA     SR_RECORD+1
                        JMP SR_TABLE_NEXT
SR_TABLE_ADVANCE:       INC     SR_RECORD
                        BEQ str8n_v2_sr_LONG_658
                        JMP SR_TABLE_NEXT
str8n_v2_sr_LONG_658:
                        INC     SR_RECORD+1
                        JMP SR_TABLE_NEXT
SR_TABLE_DONE:          LDA SR_BANK
                        CMP SR_SCAN
                        BEQ SR_SCAN_DONE
                        INC SR_BANK
                        JMP SR_SCAN_BANK
SR_SCAN_DONE:           LDA     SR_OLD_BANK
                        STA     V2_SELECTED
                        BIT SR_ERROR
                        BMI SR_TABLE_PROMPT
                        LDA SR_INDEX
                        BEQ str8n_v2_sr_LONG_671
                        JMP SR_R_LOAD
str8n_v2_sr_LONG_671:
                        LDA #$05
                        JMP SR_CLI_ERROR
SR_R_DUPLICATE:         LDA SR_OLD_BANK
                        STA V2_SELECTED
                        LDA #$06
                        JMP SR_CLI_ERROR
SR_TABLE_PROMPT:
                        JMP     V2_PROMPT
SR_TABLE_ABORT:         LDA     SR_OLD_BANK
                        STA     V2_SELECTED
                        JMP     V2_CANCELLED
SR_TABLE_ROW:           LDA     SR_RECORD+1
                        JSR     V2_HEX_OUT
                        LDA     SR_RECORD
                        JSR     V2_HEX_OUT
                        JSR     SR_SPACE
                        LDA     SR_HEADER+5
                        JSR     V2_HEX_OUT
                        LDA     SR_HEADER+4
                        JSR     V2_HEX_OUT
                        LDA     #'-'
                        JSR     V2_PUTC
                        LDA     SR_HEADER+4
                        CLC
                        ADC     SR_HEADER+6
                        STA     V2_VALUE
                        LDA     SR_HEADER+5
                        ADC     SR_HEADER+7
                        STA     V2_VALUE+1
                        LDA     V2_VALUE
                        BNE SR_TABLE_END_DEC
                        DEC     V2_VALUE+1
SR_TABLE_END_DEC:       DEC     V2_VALUE
                        LDA     V2_VALUE+1
                        JSR     V2_HEX_OUT
                        LDA     V2_VALUE
                        JSR     V2_HEX_OUT
                        JSR     SR_SPACE
                        LDA     SR_HEADER+7
                        JSR     V2_HEX_OUT
                        LDA     SR_HEADER+6
                        JSR     V2_HEX_OUT
                        JSR     SR_SPACE
                        LDA     SR_HEADER+3
                        CMP     #SR_COMPLETE
                        BEQ SR_TABLE_COMPLETE
                        LDA     #'P'
                        JMP SR_TABLE_STATE
SR_TABLE_COMPLETE:      LDA     #'C'
SR_TABLE_STATE:         JSR     V2_PUTC
                        JSR     SR_SPACE
                        LDX     #$00
SR_TABLE_LABEL:         LDA     SR_HEADER+8,X
                        BEQ SR_TABLE_EOL
                        JSR     V2_PUTC
                        INX
                        CPX     #$10
                        BNE SR_TABLE_LABEL
SR_TABLE_EOL:           JMP     V2_NEWLINE
SR_SPACE:               LDA     #' '
                        JMP     V2_PUTC
SR_APPLICATION_LIMIT:
                        BIT SVC_ACTIVE
                        BEQ SR_UNRESERVED
                        CMP #$65
                        RTS
SR_UNRESERVED:          CMP #$67
                        RTS
SR_END:
                        ENDMOD
                        END
