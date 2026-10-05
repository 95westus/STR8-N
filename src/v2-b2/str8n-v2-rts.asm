; Basic RTS module: named, automatic S; named R; configured T.
; Stored SR/01 records remain byte-compatible; execution ABI is separate.
                        MODULE V2_RTS
                        XDEF SR_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
                        INCLUDE "config-module-symbols.inc"
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
SR_PENDING              EQU     $7F
SR_COMPLETE             EQU     $3F

                        CODE
RTS_DESCRIPTOR:        DB "RTS",$01,$01,$10
                        DW SR_END-RTS_DESCRIPTOR
SR_COMMAND_SAVE:        JMP SR_CLI_SAVE
SR_COMMAND_RESTORE:     JMP SR_CLI_RESTORE
SR_COMMAND_TABLE:       JMP SR_CLI_TABLE
SR_ENTRY_SAVE:          JMP SR_API_SAVE
SR_ENTRY_RESTORE:       JMP SR_API_RESTORE
RTS_INIT_ENTRY:         JMP RTS_INIT
; RTS.SAVE / RTS.RESTORE v1: A/X points to a readable 23-byte request:
; bank, flash address LE16, RAM start LE16, inclusive end LE16, label[16].
; Save uses all fields; restore uses bank/address and stored metadata.
; C=1,A=0 success; C=0,A=error. Scratch/AXY volatile, selected bank restored.
SR_API_SAVE:            JSR     SR_COPY_REQUEST
                        LDA     SR_REQUEST
                        CMP     #$04
                        BCS     SR_SAVE_BAD
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
                        BCC     SR_SAVE_BAD
                        STA     SR_HEADER+7
                        INC     SR_HEADER+6
                        BNE     SR_SAVE_LENGTH
                        INC     SR_HEADER+7
                        BEQ     SR_SAVE_BAD
                        BRA     SR_SAVE_LENGTH
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
                        BPL     SR_SAVE_LABEL
                        JSR     SR_VALIDATE
                        BCC     SR_SAVE_BAD
                        LDA     SR_BANK
                        STA     RTS_BANK
                        JSR     RTS_EXTENT_ALLOWED
                        BCC     SR_SAVE_BAD
                        LDA     V2_SELECTED
                        STA     SR_OLD_BANK
                        LDA     SR_BANK
                        STA     V2_SELECTED
                        JSR     SR_PREFLIGHT
                        BCC     SR_SAVE_EXIT
                        JSR     SR_WRITE_RECORD
                        BCC     SR_SAVE_EXIT
                        JSR     SR_COMMIT_MARKER
SR_SAVE_EXIT:           JMP     SR_RETURN_BANK

SR_API_RESTORE:         JSR     SR_COPY_REQUEST
                        LDA     SR_REQUEST
                        CMP     #$04
                        BCC     SR_RESTORE_BANK
                        JMP     SR_ARGUMENT
SR_RESTORE_BANK:
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
                        BCC     SR_RECORD_ERROR
                        LDA     SR_BANK
                        STA     RTS_BANK
                        LDA     SR_RECORD
                        CLC
                        ADC     #SR_HEADER_SIZE
                        STA     SR_LIMIT
                        LDA     SR_RECORD+1
                        ADC     #$00
                        STA     SR_LIMIT+1
                        JSR     RTS_EXTENT_ALLOWED
                        BCC     SR_RECORD_ERROR
                        JSR     SR_LOAD_HEADER
                        JSR     SR_VALIDATE
                        BCC     SR_RECORD_ERROR
                        LDA     SR_BANK
                        STA     RTS_BANK
                        JSR     RTS_EXTENT_ALLOWED
                        BCC     SR_RECORD_ERROR
                        LDA     SR_HEADER+3
                        CMP     #SR_COMPLETE
                        BNE     SR_RECORD_ERROR
                        LDA     SR_HEADER+4
                        STA     V2_PTR
                        LDA     SR_HEADER+5
                        STA     V2_PTR+1
                        JSR     SR_SET_BODY_CURSOR
SR_RESTORE_BYTE:        JSR     SR_READ
                        STA     (V2_PTR)
                        INC     V2_PTR
                        BNE     SR_RESTORE_NEXT
                        INC     V2_PTR+1
SR_RESTORE_NEXT:        JSR     SR_NEXT
                        JSR     SR_AT_LIMIT
                        BNE     SR_RESTORE_BYTE
                        JSR     SR_SUCCESS
                        BRA     SR_RETURN_BANK
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

; Refresh persistent policy even for direct service callers, before copying
; their request. The locator service uses disjoint private buffers.
SR_COPY_REQUEST:        PHA
                        PHX
                        JSR     RTS_CONFIG_LOCATE
                        PLX
                        PLA
                        STA     V2_PTR
                        STX     V2_PTR+1
                        LDY     #$16
SR_COPY_REQ_BYTE:       LDA     (V2_PTR),Y
                        STA     SR_REQUEST,Y
                        DEY
                        BPL     SR_COPY_REQ_BYTE
                        RTS

; Validate fixed metadata and calculate the exclusive flash limit. No checksum.
; Both pending and complete headers are accepted here; restore checks complete.
SR_VALIDATE:            LDA     SR_HEADER
                        CMP     #'S'
                        BNE     SR_BAD_HEAD
                        LDA     SR_HEADER+1
                        CMP     #'R'
                        BNE     SR_BAD_HEAD
                        LDA     SR_HEADER+2
                        CMP     #$01
                        BNE     SR_BAD_HEAD
                        LDA     SR_HEADER+3
                        CMP     #SR_PENDING
                        BEQ     SR_VALID_STATE
                        CMP     #SR_COMPLETE
                        BEQ     SR_VALID_STATE
SR_BAD_HEAD:            JMP     SR_INVALID
SR_VALID_STATE:         LDA     SR_HEADER+6
                        ORA     SR_HEADER+7
                        BEQ     SR_BAD_HEAD
                        LDA     SR_HEADER+5
                        CMP     #$02
                        BCC     SR_BAD_HEAD
                        CMP     #$58
                        BCS     SR_BAD_HEAD
                        LDA     SR_HEADER+4
                        CLC
                        ADC     SR_HEADER+6
                        LDA     SR_HEADER+5
                        ADC     SR_HEADER+7
                        BCS     SR_INVALID
                        CMP     #$58
                        BCC     SR_VALID_RAM
                        BNE     SR_INVALID
                        LDA     SR_HEADER+4
                        CLC
                        ADC     SR_HEADER+6
                        BNE     SR_INVALID
SR_VALID_RAM:           LDA     SR_RECORD+1
                        CMP     #$80
                        BCC     SR_INVALID
                        CMP     #$E0
                        BCS     SR_INVALID
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
                        BCS     SR_INVALID
                        STA     SR_LIMIT+1
                        CMP     #$E0
                        BCC     SR_VALID_EXTENT
                        BNE     SR_INVALID
                        LDA     SR_LIMIT
                        BNE     SR_INVALID
SR_VALID_EXTENT:        LDX     #$00
SR_LABEL_CHAR:          LDA     SR_HEADER+8,X
                        BEQ     SR_LABEL_PAD
                        CMP     #$21
                        BCC     SR_LABEL_BAD
                        CMP     #$7F
                        BCS     SR_LABEL_BAD
                        INX
                        CPX     #$10
                        BNE     SR_LABEL_CHAR
                        BRA     SR_VALID
SR_LABEL_PAD:           LDA     SR_HEADER+8,X
                        BNE     SR_LABEL_BAD
                        INX
                        CPX     #$10
                        BNE     SR_LABEL_PAD
                        BRA     SR_VALID
SR_LABEL_BAD:           CLC
                        RTS
SR_VALID:               SEC
                        RTS
SR_INVALID:             CLC
                        RTS

; Do not read beyond the designated storage range while fetching a header.
SR_HEADER_FITS:         LDA     SR_RECORD+1
                        CMP     #$80
                        BCC     SR_INVALID
                        CMP     #$DF
                        BCC     SR_VALID
                        BNE     SR_INVALID
                        LDA     SR_RECORD
                        CMP     #$E9
                        BCS     SR_INVALID
                        BRA     SR_VALID

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
                        BNE     SR_LOAD_BYTE
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
                        BNE     SR_NEXT_DONE
                        INC     SR_CURSOR+1
SR_NEXT_DONE:           RTS
SR_AT_LIMIT:            LDA     SR_CURSOR
                        CMP     SR_LIMIT
                        BNE     SR_NOT_LIMIT
                        LDA     SR_CURSOR+1
                        CMP     SR_LIMIT+1
SR_NOT_LIMIT:           RTS

SR_PREFLIGHT:           LDA     SR_RECORD
                        STA     SR_CURSOR
                        LDA     SR_RECORD+1
                        STA     SR_CURSOR+1
SR_PREFLIGHT_BYTE:      JSR     SR_READ
                        CMP     #$FF
                        BNE     SR_OCCUPIED
                        JSR     SR_NEXT
                        JSR     SR_AT_LIMIT
                        BNE     SR_PREFLIGHT_BYTE
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
                        BCS     SR_STAGE_BODY
                        LDA     SR_HEADER,X
                        INC     SR_INDEX
                        BRA     SR_STAGE_STORE
SR_STAGE_BODY:          LDA     (V2_PTR)
                        INC     V2_PTR
                        BNE     SR_STAGE_STORE
                        INC     V2_PTR+1
SR_STAGE_STORE:         STA     (V2_BUF_PTR)
                        INC     V2_BUF_PTR
                        BNE     SR_STAGE_ADVANCE
                        INC     V2_BUF_PTR+1
SR_STAGE_ADVANCE:       JSR     SR_NEXT
                        JSR     SR_AT_LIMIT
                        BEQ     SR_STAGE_FINAL
                        LDA     SR_CURSOR+1
                        AND     #$F0
                        CMP     V2_SECTOR
                        BEQ     SR_STAGE_BYTE
                        JSR     SR_WRITE_SECTOR
                        BCC     SR_STAGE_FAIL
                        JSR     SR_SNAPSHOT
                        BRA     SR_STAGE_BYTE
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
                        ADC     #$61
                        STA     V2_BUF_PTR+1
                        RTS
SR_WRITE_SECTOR:        STZ     V2_ERASE
                        STZ     V2_SELF
                        JSR     V2W_MUTATE
                        BCC     SR_SECTOR_OK
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
                        BCC     SR_MARK_DONE
                        JMP     SR_SUCCESS
SR_MARK_DONE:           RTS

                        INCLUDE "str8n-v2-rts-commands.inc"
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
                        BNE     SR_TABLE_END_DEC
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
                        BEQ     SR_TABLE_COMPLETE
                        LDA     #'P'
                        BRA     SR_TABLE_STATE
SR_TABLE_COMPLETE:      LDA     #'C'
SR_TABLE_STATE:         JSR     V2_PUTC
                        JSR     SR_SPACE
                        LDX     #$00
SR_TABLE_LABEL:         LDA     SR_HEADER+8,X
                        BEQ     SR_TABLE_EOL
                        JSR     V2_PUTC
                        INX
                        CPX     #$10
                        BNE     SR_TABLE_LABEL
SR_TABLE_EOL:           JMP     V2_NEWLINE
SR_SPACE:               LDA     #' '
                        JMP     V2_PUTC
                        INCLUDE "str8n-v2-rts-imports.inc"
SR_END:
                        ENDMOD
                        END
