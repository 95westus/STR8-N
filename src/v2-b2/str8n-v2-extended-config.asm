; K: persistent policy in an explicitly selected reserved flash sector.
; Code is resident B ROM, authenticated by the optional E carrier.
                        MODULE V2_EXTENDED_CONFIG
                        XDEF CF_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
                        INCLUDE "str8n-v2-config-public.inc"
                        INCLUDE "config-host-symbols.inc"
                        INCLUDE "str8n-v2-autoload-public.inc"
                        CODE
; CONFIG.LOCATE v1: refresh/validate selected configuration.
; C=1: A=bank, X=sector high byte, Y=1. C=0: A=0 unassigned,
; A=1 invalid pocket/locator, A=2 invalid sector. Scratch/AXY volatile.
CF_LOCATE:              JSR CF_LOAD
                        BCC CF_LOCATE_END
                        LDA CF_BANK
                        LDX CF_SECTOR
                        LDY #$01
                        SEC
CF_LOCATE_END:          RTS

; Clear policy first: no stale writable pool after validation failure.
CF_LOAD:                LDA V2_SELECTED
                        STA CF_OLD_SELECTED
                        STZ CF_HEADER
                        LDX #$03
CF_POLICY_CLEAR:        STZ CF_POLICY,X
                        DEX
                        BPL CF_POLICY_CLEAR
                        JSR V2_CONFIG_READ
                        BCC CF_INVALID_LOCATOR
                        LDA V2_CONFIG+7
                        ORA V2_CONFIG+8
                        ORA V2_CONFIG+9
                        BEQ CF_UNASSIGNED
                        LDA V2_CONFIG+7
                        CMP #CF_LOCATOR_TAG
                        BNE CF_INVALID_LOCATOR
                        LDA V2_CONFIG+8
                        STA CF_BANK
                        LDA V2_CONFIG+9
                        STA CF_SECTOR
                        JSR CF_LOCATION_CHECK
                        BCC CF_INVALID_LOCATOR
                        LDA CF_BANK
                        STA V2_SELECTED
                        STZ V2_ADDR
                        LDA CF_SECTOR
                        STA V2_ADDR+1
                        LDA #$10
                        STA V2_COUNT
                        JSR V2W_READ
                        LDX #$0F
CF_READ_HEADER:         LDA V2_BYTES,X
                        STA CF_HEADER,X
                        DEX
                        BPL CF_READ_HEADER
                        JSR CF_HEADER_CHECK
                        BCC CF_INVALID_SECTOR
                        LDX #$03
CF_POLICY_COPY:         LDA CF_HEADER+4,X
                        STA CF_POLICY,X
                        DEX
                        BPL CF_POLICY_COPY
; The configuration sector is reserved even if its requested mask included it.
                        LDA CF_SECTOR
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        SEC
                        SBC #$08
                        TAX
                        LDA CF_SECTOR_BITS,X
                        EOR #$FF
                        LDX CF_BANK
                        AND CF_POLICY,X
                        STA CF_POLICY,X
                        LDA #$00
                        SEC
                        BRA CF_LOAD_RETURN
CF_UNASSIGNED:          LDA #$00
                        BRA CF_LOAD_FAIL
CF_INVALID_LOCATOR:     LDA #$01
                        BRA CF_LOAD_FAIL
CF_INVALID_SECTOR:      LDA #$02
CF_LOAD_FAIL:           CLC
CF_LOAD_RETURN:         STA CF_STATUS
                        PHP
                        LDA CF_OLD_SELECTED
                        STA V2_SELECTED
                        PLP
                        LDA CF_STATUS
                        RTS
CF_LOCATION_CHECK:      LDA CF_BANK
                        CMP #$04
                        BCS CF_CHECK_BAD
                        LDA CF_SECTOR
                        CMP #$80
                        BCC CF_CHECK_BAD
                        CMP #$E0
                        BCS CF_CHECK_BAD
                        AND #$0F
                        BNE CF_CHECK_BAD
                        SEC
                        RTS
CF_CHECK_BAD:           CLC
                        RTS
CF_HEADER_CHECK:        LDA CF_HEADER
                        CMP #'C'
                        BNE CF_CHECK_BAD
                        LDA CF_HEADER+1
                        CMP #'F'
                        BNE CF_CHECK_BAD
                        LDA CF_HEADER+2
                        CMP #$01
                        BNE CF_CHECK_BAD
                        LDA CF_HEADER+3
                        CMP #$3F
                        BNE CF_CHECK_BAD
                        LDA CF_HEADER+8
                        CMP CF_BANK
                        BNE CF_CHECK_BAD
                        LDA CF_HEADER+9
                        CMP CF_SECTOR
                        BNE CF_CHECK_BAD
                        LDA CF_HEADER+4
                        ORA CF_HEADER+5
                        ORA CF_HEADER+6
                        ORA CF_HEADER+7
                        AND #$C0
                        BNE CF_CHECK_BAD
                        LDA #<CF_HEADER
                        STA V2_PTR
                        JSR CF_SUM
                        LDA CF_SUM1
                        CMP CF_HEADER+14
                        BNE CF_CHECK_BAD
                        LDA CF_SUM2
                        CMP CF_HEADER+15
                        BNE CF_CHECK_BAD
                        SEC
                        RTS
; PTR points into private page 75; sum the first fourteen bytes.
CF_SUM:                 LDA #>CF_HEADER
                        STA V2_PTR+1
                        STZ CF_SUM1
                        STZ CF_SUM2
                        LDY #$00
CF_SUM_BYTE:            LDA (V2_PTR),Y
                        CLC
                        ADC CF_SUM1
                        STA CF_SUM1
                        CLC
                        ADC CF_SUM2
                        STA CF_SUM2
                        INY
                        CPY #$0E
                        BNE CF_SUM_BYTE
                        RTS

CF_COMMAND:             LDA V2_SELECTED
                        STA CF_COMMAND_SELECTED
                        STZ CF_OFF
                        LDX #$01
                        JSR V2_SKIP_SPACES
                        BNE CF_COMMAND_SET
                        JSR CF_LOAD
                        JSR CF_SHOW
                        JMP CF_COMMAND_RETURN
CF_COMMAND_SET:         CMP #'A'
                        BNE CF_COMMAND_NORMAL
                        JSR AL_COMMAND_ENTRY
                        JMP CF_COMMAND_RETURN
CF_COMMAND_NORMAL:      CMP #'O'
                        BNE CF_PARSE_LOCATION
                        INX
                        LDA V2_LINE,X
                        CMP #'F'
                        BNE CF_COMMAND_BAD
                        INX
                        LDA V2_LINE,X
                        CMP #'F'
                        BNE CF_COMMAND_BAD
                        INX
                        JSR V2_SKIP_SPACES
                        BNE CF_COMMAND_BAD
                        INC CF_OFF
                        BRA CF_CONFIRM_OFF
CF_PARSE_LOCATION:      CMP #'B'
                        BNE CF_COMMAND_BAD
                        INX
                        LDA V2_LINE,X
                        SEC
                        SBC #'0'
                        CMP #$04
                        BCS CF_COMMAND_BAD
                        STA CF_NEW_BANK
                        INX
                        LDA V2_LINE,X
                        CMP #' '
                        BNE CF_COMMAND_BAD
                        JSR V2_HEX_BYTE
                        BCC CF_COMMAND_BAD
                        LDA V2_VALUE
                        CMP #$08
                        BCC CF_COMMAND_BAD
                        CMP #$0E
                        BCS CF_COMMAND_BAD
                        ASL A
                        ASL A
                        ASL A
                        ASL A
                        STA CF_NEW_SECTOR
                        JSR CF_PARSE_MASKS
                        BCC CF_COMMAND_BAD
                        JMP CF_PREPARE_SECTOR
CF_COMMAND_BAD:         LDX #<CF_BAD_TEXT
                        LDY #>CF_BAD_TEXT
                        BRA CF_COMMAND_MESSAGE
CF_CONFIRM_OFF:         JSR V2_CONFIRM
                        BCC CF_COMMAND_CANCELED
                        JSR CF_WRITE_LOCATOR
                        BRA CF_COMMAND_DONE
CF_COMMAND_CANCELED:    LDX #<CF_CANCEL_TEXT
                        LDY #>CF_CANCEL_TEXT
                        BRA CF_COMMAND_MESSAGE
CF_COMMAND_ERROR:       LDX #<CF_FAIL_TEXT
                        LDY #>CF_FAIL_TEXT
                        JSR CF_PRINT
                        BRA CF_COMMAND_RELOAD
CF_COMMAND_DONE:        LDX #<CF_DONE_TEXT
                        LDY #>CF_DONE_TEXT
CF_COMMAND_MESSAGE:     JSR CF_PRINT
CF_COMMAND_RELOAD:      JSR CF_LOAD
CF_COMMAND_RETURN:      LDA CF_COMMAND_SELECTED
                        STA V2_SELECTED
                        LDA #$01
                        RTS

CF_PARSE_MASKS:         LDY #$0F
                        LDA #$00
CF_DESIRED_CLEAR:       STA CF_DESIRED,Y
                        DEY
                        BPL CF_DESIRED_CLEAR
                        STZ CF_INDEX
CF_PARSE_MASK:          JSR V2_HEX_BYTE
                        BCC CF_PARSE_FAIL
                        LDA V2_VALUE
                        CMP #$40
                        BCS CF_PARSE_FAIL
                        LDY CF_INDEX
                        STA CF_DESIRED+4,Y
                        INC CF_INDEX
                        LDA CF_INDEX
                        CMP #$04
                        BNE CF_PARSE_MASK
                        JSR V2_SKIP_SPACES
                        BNE CF_PARSE_FAIL
                        LDA #'C'
                        STA CF_DESIRED
                        LDA #'F'
                        STA CF_DESIRED+1
                        LDA #$01
                        STA CF_DESIRED+2
                        LDA #$3F
                        STA CF_DESIRED+3
                        LDA CF_NEW_BANK
                        STA CF_DESIRED+8
                        LDA CF_NEW_SECTOR
                        STA CF_DESIRED+9
                        LDA #<CF_DESIRED
                        STA V2_PTR
                        JSR CF_SUM
                        LDA CF_SUM1
                        STA CF_DESIRED+14
                        LDA CF_SUM2
                        STA CF_DESIRED+15
                        SEC
                        RTS
CF_PARSE_FAIL:          CLC
                        RTS

CF_PREPARE_SECTOR:      JSR AL_PRESERVE_ENTRY
                        LDA CF_NEW_BANK
                        STA CF_BANK
                        STA V2_SELECTED
                        LDA CF_NEW_SECTOR
                        STA CF_SECTOR
                        STA V2_SECTOR
                        STZ V2_SELF
                        JSR V2W_SNAPSHOT
                        LDX #$0F
CF_EXISTING_HEADER:     LDA $6100,X
                        STA CF_HEADER,X
                        DEX
                        BPL CF_EXISTING_HEADER
                        JSR CF_HEADER_CHECK
                        BCS CF_STAGE_HEADER
; Never claim opaque contents: new destinations must be wholly erased.
                        STZ V2_PTR
                        LDA #$61
                        STA V2_PTR+1
CF_ERASED_BYTE:         LDA (V2_PTR)
                        CMP #$FF
                        BNE CF_DEST_OCCUPIED
                        INC V2_PTR
                        BNE CF_ERASED_BYTE
                        INC V2_PTR+1
                        LDA V2_PTR+1
                        CMP #$71
                        BNE CF_ERASED_BYTE
CF_STAGE_HEADER:        JSR AL_STAGE_ENTRY
                        LDX #$0F
CF_STAGE_BYTE:          LDA CF_DESIRED,X
                        STA $6100,X
                        STA CF_HEADER,X
                        DEX
                        BPL CF_STAGE_BYTE
                        LDA #$7F
                        STA $6103
                        JSR V2W_ANALYZE
                        STZ CF_STATUS
                        JSR CF_SHOW
                        JSR V2_FLASH_MODE
                        JSR V2_CONFIRM
                        BCC CF_SECTOR_CANCEL
                        JSR V2W_MUTATE
                        BCS CF_SECTOR_FAIL
; Complete header before switching locator. No erase on this second pass.
                        LDA #$3F
                        STA $6103
                        STZ V2_ERASE
                        JSR V2W_MUTATE
                        BCS CF_SECTOR_FAIL
                        JSR CF_WRITE_LOCATOR
                        JMP CF_COMMAND_DONE
CF_DEST_OCCUPIED:       LDX #<CF_OCCUPIED_TEXT
                        LDY #>CF_OCCUPIED_TEXT
                        JMP CF_COMMAND_MESSAGE
CF_SECTOR_CANCEL:       JMP CF_COMMAND_CANCELED
CF_SECTOR_FAIL:         JMP CF_COMMAND_ERROR

; Rewrite only the locator/checksum in the resident F snapshot. Boot settings
; survive valid pockets; an invalid pocket is initialized to monitor-only.
CF_WRITE_LOCATOR:       JSR V2_CONFIG_READ
                        BCS CF_POCKET_VALID
                        LDX #$0F
CF_POCKET_CLEAR:        STZ V2_CONFIG,X
                        DEX
                        BPL CF_POCKET_CLEAR
                        INC V2_CONFIG
                        LDA V2_RESIDENT
                        STA V2_CONFIG+2
                        LDA #$F0
                        STA V2_CONFIG+4
                        LDA #$0A
                        STA V2_CONFIG+5
CF_POCKET_VALID:        LDX #$06
CF_LOCATOR_CLEAR:       STZ V2_CONFIG+7,X
                        DEX
                        BPL CF_LOCATOR_CLEAR
                        LDA CF_OFF
                        BNE CF_POCKET_SUM
                        LDA #CF_LOCATOR_TAG
                        STA V2_CONFIG+7
                        LDA CF_NEW_BANK
                        STA V2_CONFIG+8
                        LDA CF_NEW_SECTOR
                        STA V2_CONFIG+9
CF_POCKET_SUM:          JSR V2_CONFIG_SUM
                        LDA V2_CFG_SUM
                        STA V2_CONFIG+14
                        LDA V2_CFG_SUM2
                        STA V2_CONFIG+15
                        LDA V2_RESIDENT
                        STA V2_SELECTED
                        LDA #$F0
                        STA V2_SECTOR
                        LDA #$02
                        STA V2_SELF
                        JSR V2W_SNAPSHOT
                        LDX #$0F
CF_POCKET_STAGE:        LDA V2_CONFIG,X
                        STA $70D0,X
                        DEX
                        BPL CF_POCKET_STAGE
                        JSR V2W_ANALYZE
                        JMP V2W_MUTATE

CF_SHOW:                LDA #'K'
                        JSR STR8V2_RAM_PUTC
                        JSR CF_SPACE
                        LDA CF_STATUS
                        JSR STR8V2_RAM_HEX_OUT
                        LDA CF_STATUS
                        BNE CF_SHOW_END
                        LDA CF_HEADER
                        CMP #'C'
                        BNE CF_SHOW_END
                        JSR CF_SPACE
                        LDA #'B'
                        JSR STR8V2_RAM_PUTC
                        LDA CF_BANK
                        ORA #'0'
                        JSR STR8V2_RAM_PUTC
                        JSR CF_SPACE
                        LDA CF_SECTOR
                        JSR STR8V2_RAM_HEX_OUT
                        STZ CF_INDEX
CF_SHOW_MASK:           JSR CF_SPACE
                        LDX CF_INDEX
                        LDA CF_HEADER+4,X
                        JSR STR8V2_RAM_HEX_OUT
                        INC CF_INDEX
                        LDA CF_INDEX
                        CMP #$04
                        BNE CF_SHOW_MASK
CF_SHOW_END:            JMP STR8V2_RAM_NEWLINE
CF_SPACE:               LDA #' '
                        JMP STR8V2_RAM_PUTC
CF_PRINT:               STX V2_ADDR
                        STY V2_ADDR+1
                        LDY #$00
CF_PRINT_BYTE:          LDA (V2_ADDR),Y
                        BEQ CF_PRINT_END
                        JSR STR8V2_RAM_PUTC
                        INY
                        BRA CF_PRINT_BYTE
CF_PRINT_END:           RTS
CF_SECTOR_BITS:         DB $01,$02,$04,$08,$10,$20
CF_BAD_TEXT:            DB "Bad config",$00
CF_CANCEL_TEXT:         DB "Canceled",$00
CF_FAIL_TEXT:           DB "Config flash fail",$00
CF_DONE_TEXT:           DB "Done",$00
CF_OCCUPIED_TEXT:       DB "Config sector occupied",$00
CF_END:
                        ENDMOD
                        END
