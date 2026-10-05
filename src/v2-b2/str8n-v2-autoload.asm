; Explicit resident-bank autoload policy. No arbitrary flash scan.
                        MODULE V2_AUTOLOAD
                        XDEF AL_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
                        INCLUDE "str8n-v2-config-public.inc"
                        INCLUDE "str8n-v2-autoload-public.inc"
                        INCLUDE "autoload-host-symbols.inc"
                        CODE
                        JMP AL_APPLY
                        JMP AL_COMMAND
                        JMP AL_LOAD
                        JMP AL_STAGE
; Carry=valid; AL_VALID=0 absent, 1 valid, 2 malformed. CF locator validates first.
AL_LOAD:                STZ AL_VALID
                        JSR CF_LOCATE
                        BCC AL_LOAD_DONE
                        LDA V2_SELECTED
                        STA AL_SAVED_SELECTED
                        LDA CF_BANK
                        STA V2_SELECTED
                        LDA #$10
                        STA V2_ADDR
                        LDA CF_SECTOR
                        STA V2_ADDR+1
                        LDA #$40
                        STA V2_COUNT
                        JSR V2W_READ
                        LDX #$3F
AL_LOAD_COPY:           LDA V2_BYTES,X
                        STA AL_BUFFER,X
                        DEX
                        BPL AL_LOAD_COPY
                        LDA AL_SAVED_SELECTED
                        STA V2_SELECTED
                        LDX #$3F
AL_EMPTY:               LDA AL_BUFFER,X
                        CMP #$FF
                        BNE AL_CHECK
                        DEX
                        BPL AL_EMPTY
                        LDA CF_HEADER+10
                        CMP #$A1
                        BNE AL_LOAD_DONE
                        LDA #$02
                        STA AL_VALID
AL_LOAD_DONE:           CLC
                        RTS
AL_CHECK:               LDA #$02
                        STA AL_VALID
                        LDA AL_BUFFER
                        CMP #'A'
                        BNE AL_LOAD_DONE
                        LDA AL_BUFFER+1
                        CMP #'L'
                        BNE AL_LOAD_DONE
                        LDA AL_BUFFER+2
                        CMP #$01
                        BNE AL_LOAD_DONE
                        LDA AL_BUFFER+3
                        CMP #$3F
                        BNE AL_LOAD_DONE
                        LDA AL_BUFFER+4
                        CMP #$02
                        BCS AL_LOAD_DONE
                        JSR AL_SUM
                        LDA AL_SUM1
                        CMP AL_BUFFER+62
                        BNE AL_LOAD_DONE
                        LDA AL_SUM2
                        CMP AL_BUFFER+63
                        BNE AL_LOAD_DONE
                        LDX #$05
AL_RESERVED_HEAD:      LDA AL_BUFFER,X
                        BNE AL_LOAD_DONE
                        INX
                        CPX #$08
                        BNE AL_RESERVED_HEAD
                        LDX #$28
AL_RESERVED_TAIL:      LDA AL_BUFFER,X
                        BNE AL_LOAD_DONE
                        INX
                        CPX #$3E
                        BNE AL_RESERVED_TAIL
                        LDX #$08
AL_RECORD_CHECK:       LDA AL_BUFFER,X
                        BEQ AL_RECORD_EMPTY
                        STA AL_KEY
                        STX AL_SLOT
                        JSR AL_KEY_CHECK
                        BCC AL_LOAD_DONE
                        LDX AL_SLOT
                        LDA AL_BUFFER+1,X
                        CMP #$02
                        BCS AL_LOAD_DONE
                        LDA AL_BUFFER+2,X
                        STA AL_ENTRY
                        LDA AL_BUFFER+3,X
                        STA AL_ENTRY+1
                        JSR AL_ADDRESS_CHECK
                        BCC AL_LOAD_DONE
                        LDX #$08
AL_DUP_CHECK:          CPX AL_SLOT
                        BEQ AL_RECORD_NEXT
                        LDA AL_BUFFER,X
                        CMP AL_KEY
                        BEQ AL_LOAD_DONE
                        INX
                        INX
                        INX
                        INX
                        BRA AL_DUP_CHECK
AL_RECORD_EMPTY:       LDA AL_BUFFER+1,X
                        ORA AL_BUFFER+2,X
                        ORA AL_BUFFER+3,X
                        BNE AL_LOAD_DONE
                        STX AL_SLOT
AL_RECORD_NEXT:        LDX AL_SLOT
                        INX
                        INX
                        INX
                        INX
                        CPX #$28
                        BNE AL_RECORD_CHECK
                        LDA #$01
                        STA AL_VALID
                        SEC
                        RTS
AL_SUM:                 STZ AL_SUM1
                        STZ AL_SUM2
                        LDX #$00
AL_SUM_BYTE:            LDA AL_BUFFER,X
                        CLC
                        ADC AL_SUM1
                        STA AL_SUM1
                        CLC
                        ADC AL_SUM2
                        STA AL_SUM2
                        INX
                        CPX #$3E
                        BNE AL_SUM_BYTE
                        RTS
AL_KEY_CHECK:           LDA AL_KEY
                        CMP #'A'
                        BCC AL_BAD
                        CMP #'Z'+1
                        BCS AL_BAD
                        LDX #$09
AL_CORE_KEY:            CMP V2_COMMAND_KEYS,X
                        BEQ AL_BAD
                        DEX
                        BPL AL_CORE_KEY
                        CMP #'K'
                        BEQ AL_BAD
                        SEC
                        RTS
AL_ADDRESS_CHECK:       LDA AL_ENTRY
                        ORA AL_ENTRY+1
                        BNE AL_ROM_ADDRESS
                        LDA AL_KEY
                        CMP #'R'
                        BEQ AL_GOOD
                        CMP #'S'
                        BEQ AL_GOOD
                        CMP #'T'
                        BEQ AL_GOOD
AL_BAD:                 CLC
                        RTS
AL_ROM_ADDRESS:         LDA AL_ENTRY+1
                        CMP #$B0
                        BCC AL_BAD
                        CMP #$E0
                        BCS AL_BAD
                        CMP #$DF
                        BNE AL_GOOD
                        LDA AL_ENTRY
                        CMP #$FA
                        BCS AL_BAD
AL_GOOD:                SEC
                        RTS
; Providers: JMP init; "EX",1,key. Init is RTS-returning, C=success.
AL_PROVIDER_CHECK:      JSR AL_ADDRESS_CHECK
                        BCC AL_BAD
                        LDA AL_ENTRY
                        STA V2_PTR
                        LDA AL_ENTRY+1
                        STA V2_PTR+1
                        LDY #$00
                        LDA (V2_PTR),Y
                        CMP #$4C
                        BNE AL_BAD
                        LDY #$02
                        LDA (V2_PTR),Y
                        CMP #$B0
                        BCC AL_BAD
                        CMP #$E0
                        BCS AL_BAD
                        LDY #$03
                        LDA (V2_PTR),Y
                        CMP #'E'
                        BNE AL_BAD
                        INY
                        LDA (V2_PTR),Y
                        CMP #'X'
                        BNE AL_BAD
                        INY
                        LDA (V2_PTR),Y
                        CMP #$01
                        BNE AL_BAD
                        INY
                        LDA (V2_PTR),Y
                        CMP AL_KEY
                        BNE AL_BAD
                        SEC
                        RTS
AL_STAGE:               LDA AL_VALID
                        BEQ AL_STAGE_END
; Tag CF so an erased/torn AL block cannot fall back to legacy defaults.
                        LDA #$A1
                        STA CF_DESIRED+10
                        LDA #<CF_DESIRED
                        STA V2_PTR
                        JSR CF_SUM
                        LDA CF_SUM1
                        STA CF_DESIRED+14
                        LDA CF_SUM2
                        STA CF_DESIRED+15
                        LDX #$3F
AL_STAGE_BYTE:          LDA AL_BUFFER,X
                        STA $6110,X
                        DEX
                        BPL AL_STAGE_BYTE
AL_STAGE_END:           RTS
; Fresh manager already has K,S,R,T. Explicit/malformed AL withdraws S/R/T.
AL_APPLY:               JSR AL_LOAD
                        LDA AL_VALID
                        BEQ AL_APPLY_END
                        LDA #$03
                        STA MG_COUNT
                        LDA V2_CONSOLE
                        INC A
                        BNE AL_CONSOLE_READY
                        LDA #$20
                        BIT V2_CTRL
                        BNE AL_CONSOLE_READY
                        JSR STR8V2_RAM_CON_INIT
AL_CONSOLE_READY:       LDA AL_VALID
                        CMP #$01
                        BEQ AL_APPLY_START
                        LDX #<AL_INVALID_TEXT
                        LDY #>AL_INVALID_TEXT
                        JMP AL_PRINT
AL_APPLY_START:         LDA AL_BUFFER+4
                        BNE AL_APPLY_LOOP_START
                        LDA #'K'
                        STA AL_KEY
                        JSR AL_REGISTERED
AL_APPLY_LOOP_START:    LDA #$08
                        STA AL_INDEX
AL_APPLY_LOOP:          LDX AL_INDEX
                        LDA AL_BUFFER,X
                        BEQ AL_APPLY_NEXT
                        STA AL_KEY
                        LDA AL_BUFFER+1,X
                        BEQ AL_APPLY_NEXT
                        LDA AL_BUFFER+2,X
                        STA AL_ENTRY
                        LDA AL_BUFFER+3,X
                        STA AL_ENTRY+1
                        LDA MG_COUNT
                        STA AL_OLD_COUNT
                        LDA MG_DYNAMIC_COUNT
                        STA AL_OLD_DYNAMIC
                        LDA MG_NAMED_COUNT
                        STA MG_NAMED_ROLLBACK
                        LDA AL_ENTRY
                        ORA AL_ENTRY+1
                        BNE AL_APPLY_ROM
                        LDA AL_KEY
                        LDX #<SR_COMMAND_RESTORE
                        LDY #>SR_COMMAND_RESTORE
                        CMP #'R'
                        BEQ AL_APPLY_BUILTIN
                        LDX #<SR_COMMAND_SAVE
                        LDY #>SR_COMMAND_SAVE
                        CMP #'S'
                        BEQ AL_APPLY_BUILTIN
                        LDX #<SR_COMMAND_TABLE
                        LDY #>SR_COMMAND_TABLE
AL_APPLY_BUILTIN:       JSR RTS_REGISTER
                        BRA AL_APPLY_RESULT
AL_APPLY_ROM:           JSR AL_PROVIDER_CHECK
                        BCC AL_APPLY_FAILED
                        LDA AL_ENTRY
                        STA AL_CALL
                        LDA AL_ENTRY+1
                        STA AL_CALL+1
                        JSR AL_CALL_PROVIDER
AL_APPLY_RESULT:        BCC AL_APPLY_FAILED
                        LDX AL_OLD_COUNT
                        LDA MG_TABLE,X
                        CMP AL_KEY
                        BNE AL_APPLY_FAILED
                        TXA
                        CLC
                        ADC #$03
                        CMP MG_COUNT
                        BNE AL_APPLY_FAILED
                        LDA AL_BUFFER+4
                        BNE AL_APPLY_NEXT
                        JSR AL_REGISTERED
                        BRA AL_APPLY_NEXT
AL_APPLY_FAILED:        LDA AL_OLD_COUNT
                        STA MG_COUNT
                        LDA AL_OLD_DYNAMIC
                        STA MG_DYNAMIC_COUNT
                        LDA MG_NAMED_ROLLBACK
                        STA MG_NAMED_COUNT
                        JSR AL_PRINT_KEY
                        LDX #<AL_FAILED_TEXT
                        LDY #>AL_FAILED_TEXT
                        JSR AL_PRINT
AL_APPLY_NEXT:          LDA AL_INDEX
                        CLC
                        ADC #$04
                        STA AL_INDEX
                        CMP #$28
                        BNE AL_APPLY_LOOP
AL_APPLY_END:           RTS
AL_CALL_PROVIDER:       JMP (AL_CALL)
AL_REGISTERED:          JSR AL_PRINT_KEY
                        LDX #<AL_REGISTERED_TEXT
                        LDY #>AL_REGISTERED_TEXT
                        JMP AL_PRINT
AL_PRINT_KEY:           LDA V2_CONSOLE
                        INC A
                        BEQ AL_PRINT_KEY_END
                        LDA AL_KEY
                        JSR STR8V2_RAM_PUTC
AL_PRINT_KEY_END:       RTS
AL_PRINT:               STX V2_ADDR
                        STY V2_ADDR+1
                        LDA V2_CONSOLE
                        INC A
                        BEQ AL_PRINT_END
                        LDY #$00
AL_PRINT_BYTE:          LDA (V2_ADDR),Y
                        BEQ AL_PRINT_END
                        JSR STR8V2_RAM_PUTC
                        INY
                        BRA AL_PRINT_BYTE
AL_PRINT_END:           RTS
; K AUTO [+key [entry]|-key|QUIET 0|1|?]. Changes take effect at reset.
AL_COMMAND:             INX
                        LDA V2_LINE,X
                        CMP #'U'
                        BNE AL_COMMAND_BAD
                        INX
                        LDA V2_LINE,X
                        CMP #'T'
                        BNE AL_COMMAND_BAD
                        INX
                        LDA V2_LINE,X
                        CMP #'O'
                        BNE AL_COMMAND_BAD
                        INX
                        LDA V2_LINE,X
                        BEQ AL_COMMAND_LIST
                        CMP #' '
                        BNE AL_COMMAND_BAD
                        JSR V2_SKIP_SPACES
                        BEQ AL_COMMAND_LIST
                        CMP #'?'
                        BNE AL_COMMAND_EDIT
                        INX
                        JSR V2_SKIP_SPACES
                        BNE AL_COMMAND_BAD
AL_COMMAND_LIST:        JSR AL_LOAD
                        LDA AL_VALID
                        CMP #$01
                        BEQ AL_SHOW
                        CMP #$02
                        BEQ AL_COMMAND_INVALID
                        LDX #<AL_DEFAULT_TEXT
                        LDY #>AL_DEFAULT_TEXT
                        JMP AL_PRINT
AL_COMMAND_INVALID:     LDX #<AL_INVALID_TEXT
                        LDY #>AL_INVALID_TEXT
                        JMP AL_PRINT
AL_COMMAND_BAD:         LDX #<AL_BAD_TEXT
                        LDY #>AL_BAD_TEXT
                        JMP AL_PRINT
AL_COMMAND_EDIT:        STX AL_PARSE
                        JSR CF_LOCATE
                        BCC AL_COMMAND_NO_CONFIG
                        JSR AL_LOAD
                        BCS AL_EDIT_VALID
                        LDA AL_VALID
                        BEQ AL_EDIT_DEFAULT
                        LDX AL_PARSE
                        LDA V2_LINE,X
                        CMP #'R'
                        BEQ AL_RESET_POLICY
                        CMP #'C'
                        BEQ AL_CLEAR_POLICY
                        JMP AL_COMMAND_INVALID
AL_EDIT_DEFAULT:
                        JSR AL_DEFAULT
AL_EDIT_VALID:          LDX AL_PARSE
                        LDA V2_LINE,X
                        CMP #'R'
                        BEQ AL_RESET_POLICY
                        CMP #'C'
                        BEQ AL_CLEAR_POLICY
                        CMP #'Q'
                        BEQ AL_QUIET
                        CMP #'+'
                        BEQ AL_ENABLE
                        CMP #'-'
                        BNE AL_COMMAND_BAD
                        STZ AL_ACTION
                        BRA AL_PARSE_KEY
AL_ENABLE:              LDA #$01
                        STA AL_ACTION
AL_PARSE_KEY:           INX
                        LDA V2_LINE,X
                        STA AL_KEY
                        PHX
                        JSR AL_KEY_CHECK
                        PLX
                        BCC AL_COMMAND_BAD
                        INX
                        LDA V2_LINE,X
                        BEQ AL_NO_ADDRESS
                        CMP #' '
                        BNE AL_COMMAND_BAD
                        JSR V2_SKIP_SPACES
                        BEQ AL_NO_ADDRESS
                        LDA AL_ACTION
                        BEQ AL_COMMAND_BAD
                        JSR V2_HEX_WORD
                        BCC AL_COMMAND_BAD
                        LDA V2_VALUE
                        STA AL_ENTRY
                        LDA V2_VALUE+1
                        STA AL_ENTRY+1
                        JSR V2_SKIP_SPACES
                        BNE AL_COMMAND_BAD
                        JSR AL_PROVIDER_CHECK
                        BCC AL_COMMAND_BAD
                        BRA AL_FIND_SLOT
AL_NO_ADDRESS:          STZ AL_ENTRY
                        STZ AL_ENTRY+1
                        BRA AL_FIND_SLOT
AL_DEFAULT_ADDRESS:
                        LDA AL_KEY
                        CMP #'H'
                        BNE AL_DEFAULT_X
                        LDA #$0A
                        STA AL_ENTRY
                        LDA #$C0
                        STA AL_ENTRY+1
AL_DEFAULT_X:           CMP #'X'
                        BNE AL_DEFAULT_ADDRESS_END
                        LDA #$0A
                        STA AL_ENTRY
                        LDA #$C7
                        STA AL_ENTRY+1
AL_DEFAULT_ADDRESS_END: RTS
AL_FIND_SLOT:           LDX #$08
                        LDA #$FF
                        STA AL_SLOT
AL_FIND_NEXT:           LDA AL_BUFFER,X
                        CMP AL_KEY
                        BEQ AL_EXISTING_SLOT
                        BNE AL_FIND_EMPTY
AL_FIND_EMPTY:          CMP #$00
                        BNE AL_FIND_ADVANCE
                        LDA AL_SLOT
                        CMP #$FF
                        BNE AL_FIND_ADVANCE
                        STX AL_SLOT
AL_FIND_ADVANCE:        INX
                        INX
                        INX
                        INX
                        CPX #$28
                        BNE AL_FIND_NEXT
                        LDX AL_SLOT
                        CPX #$FF
                        BEQ AL_COMMAND_FULL
                        LDA AL_ACTION
                        BEQ AL_COMMAND_BAD
                        BRA AL_SET_SLOT
AL_EXISTING_SLOT:       LDA AL_ENTRY
                        ORA AL_ENTRY+1
                        BNE AL_SET_SLOT
                        LDA AL_BUFFER+2,X
                        STA AL_ENTRY
                        LDA AL_BUFFER+3,X
                        STA AL_ENTRY+1
AL_SET_SLOT:            STX AL_SLOT
                        LDA AL_ENTRY
                        ORA AL_ENTRY+1
                        BNE AL_CHECK_SLOT_ADDRESS
                        JSR AL_DEFAULT_ADDRESS
AL_CHECK_SLOT_ADDRESS:
                        JSR AL_ADDRESS_CHECK
                        BCC AL_COMMAND_BAD
                        LDA AL_ACTION
                        BEQ AL_WRITE_SLOT
                        LDA AL_ENTRY
                        ORA AL_ENTRY+1
                        BEQ AL_WRITE_SLOT
                        JSR AL_PROVIDER_CHECK
                        BCC AL_COMMAND_BAD
AL_WRITE_SLOT:          LDX AL_SLOT
                        LDA AL_KEY
                        STA AL_BUFFER,X
                        LDA AL_ACTION
                        STA AL_BUFFER+1,X
                        LDA AL_ENTRY
                        STA AL_BUFFER+2,X
                        LDA AL_ENTRY+1
                        STA AL_BUFFER+3,X
                        BRA AL_WRITE
AL_RESET_POLICY:        LDA #<AL_RESET_WORD
                        STA V2_PTR
                        LDA #>AL_RESET_WORD
                        STA V2_PTR+1
                        JSR AL_MATCH_WORD
                        BCC AL_COMMAND_BAD
                        JSR AL_DEFAULT
                        JMP AL_WRITE
AL_CLEAR_POLICY:        LDA #<AL_CLEAR_WORD
                        STA V2_PTR
                        LDA #>AL_CLEAR_WORD
                        STA V2_PTR+1
                        JSR AL_MATCH_WORD
                        BCC AL_COMMAND_BAD
                        JSR AL_DEFAULT
                        LDX #$1F
                        LDA #$00
AL_CLEAR_RECORDS:       STA AL_BUFFER+8,X
                        DEX
                        BPL AL_CLEAR_RECORDS
                        JMP AL_WRITE
AL_MATCH_WORD:          LDY #$00
AL_MATCH_BYTE:          LDA (V2_PTR),Y
                        BEQ AL_MATCH_END
                        CMP V2_LINE,X
                        BNE AL_MATCH_BAD
                        INX
                        INY
                        BRA AL_MATCH_BYTE
AL_MATCH_END:           JSR V2_SKIP_SPACES
                        BNE AL_MATCH_BAD
                        SEC
                        RTS
AL_MATCH_BAD:           CLC
                        RTS
AL_QUIET:               INX
                        LDA V2_LINE,X
                        CMP #'U'
                        BNE AL_COMMAND_BAD
                        INX
                        LDA V2_LINE,X
                        CMP #'I'
                        BNE AL_COMMAND_BAD
                        INX
                        LDA V2_LINE,X
                        CMP #'E'
                        BNE AL_COMMAND_BAD
                        INX
                        LDA V2_LINE,X
                        CMP #'T'
                        BNE AL_COMMAND_BAD
                        INX
                        LDA V2_LINE,X
                        CMP #' '
                        BNE AL_COMMAND_BAD
                        JSR V2_HEX_BYTE
                        BCC AL_COMMAND_BAD
                        LDA V2_VALUE
                        CMP #$02
                        BCS AL_COMMAND_BAD
                        STA AL_BUFFER+4
                        JSR V2_SKIP_SPACES
                        BNE AL_COMMAND_BAD
AL_WRITE:               JSR AL_SUM
                        LDA AL_SUM1
                        STA AL_BUFFER+62
                        LDA AL_SUM2
                        STA AL_BUFFER+63
                        LDA CF_BANK
                        STA V2_SELECTED
                        LDA CF_SECTOR
                        STA V2_SECTOR
                        STZ V2_SELF
                        JSR V2W_SNAPSHOT
                        LDX #$0F
AL_COPY_CF:             LDA $6100,X
                        STA CF_DESIRED,X
                        DEX
                        BPL AL_COPY_CF
                        JSR AL_STAGE
                        LDX #$0F
AL_STAGE_CF:            LDA CF_DESIRED,X
                        STA $6100,X
                        DEX
                        BPL AL_STAGE_CF
; Marker pending until checksum/data are fully written and verified.
                        LDA #$7F
                        STA $6113
                        JSR V2W_ANALYZE
                        JSR AL_SHOW
                        JSR V2_FLASH_MODE
                        JSR V2_CONFIRM
                        BCC AL_COMMAND_CANCEL
                        JSR V2W_MUTATE
                        BCS AL_COMMAND_FLASH_FAIL
                        LDA #$3F
                        STA $6113
                        STZ V2_ERASE
                        JSR V2W_MUTATE
                        BCS AL_COMMAND_FLASH_FAIL
                        LDX #<AL_DONE_TEXT
                        LDY #>AL_DONE_TEXT
                        JMP AL_PRINT
AL_COMMAND_NO_CONFIG:   LDX #<AL_NO_CONFIG_TEXT
                        LDY #>AL_NO_CONFIG_TEXT
                        JMP AL_PRINT
AL_COMMAND_CANCEL:      LDX #<AL_CANCEL_TEXT
                        LDY #>AL_CANCEL_TEXT
                        JMP AL_PRINT
AL_COMMAND_FLASH_FAIL:  LDX #<AL_FLASH_TEXT
                        LDY #>AL_FLASH_TEXT
                        JMP AL_PRINT
AL_COMMAND_FULL:        LDX #<AL_FULL_TEXT
                        LDY #>AL_FULL_TEXT
                        JMP AL_PRINT
AL_DEFAULT:             LDX #$3F
                        LDA #$00
AL_DEFAULT_CLEAR:       STA AL_BUFFER,X
                        DEX
                        BPL AL_DEFAULT_CLEAR
                        LDA #'A'
                        STA AL_BUFFER
                        LDA #'L'
                        STA AL_BUFFER+1
                        LDA #$01
                        STA AL_BUFFER+2
                        STA AL_VALID
                        STA AL_BUFFER+9
                        STA AL_BUFFER+13
                        STA AL_BUFFER+17
                        LDA #$3F
                        STA AL_BUFFER+3
                        LDA #'R'
                        STA AL_BUFFER+8
                        LDA #'S'
                        STA AL_BUFFER+12
                        LDA #'T'
                        STA AL_BUFFER+16
                        RTS
AL_SHOW:                LDX #<AL_QUIET_TEXT
                        LDY #>AL_QUIET_TEXT
                        JSR AL_PRINT
                        LDA AL_BUFFER+4
                        JSR STR8V2_RAM_HEX_OUT
                        JSR STR8V2_RAM_NEWLINE
                        LDA #$08
                        STA AL_INDEX
AL_SHOW_NEXT:           LDX AL_INDEX
                        LDA AL_BUFFER,X
                        BEQ AL_SHOW_ADVANCE
                        STA AL_KEY
                        JSR AL_PRINT_KEY
                        LDX AL_INDEX
                        LDA AL_BUFFER+1,X
                        BEQ AL_SHOW_OFF
                        LDX #<AL_ON_TEXT
                        LDY #>AL_ON_TEXT
                        BRA AL_SHOW_STATE
AL_SHOW_OFF:            LDX #<AL_OFF_TEXT
                        LDY #>AL_OFF_TEXT
AL_SHOW_STATE:          JSR AL_PRINT
                        LDX AL_INDEX
                        LDA AL_BUFFER+3,X
                        JSR STR8V2_RAM_HEX_OUT
                        LDX AL_INDEX
                        LDA AL_BUFFER+2,X
                        JSR STR8V2_RAM_HEX_OUT
                        JSR STR8V2_RAM_NEWLINE
AL_SHOW_ADVANCE:        LDA AL_INDEX
                        CLC
                        ADC #$04
                        STA AL_INDEX
                        CMP #$28
                        BNE AL_SHOW_NEXT
                        RTS
AL_REGISTERED_TEXT:     DB " registered",$0D,$0A,0
AL_FAILED_TEXT:         DB " registration failed",$0D,$0A,0
AL_INVALID_TEXT:        DB "Autoload invalid",$0D,$0A,0
AL_DEFAULT_TEXT:        DB "AUTO legacy R S T; H/X off",$0D,$0A,0
AL_BAD_TEXT:            DB "Bad AUTO",0
AL_NO_CONFIG_TEXT:      DB "AUTO needs valid K config",0
AL_CANCEL_TEXT:         DB "Canceled",0
AL_FLASH_TEXT:          DB "AUTO flash fail",0
AL_FULL_TEXT:           DB "AUTO list full",0
AL_DONE_TEXT:           DB "Done; reset to apply",0
AL_QUIET_TEXT:          DB "AUTO QUIET ",0
AL_ON_TEXT:             DB " ON B3 ",0
AL_OFF_TEXT:            DB " OFF B3 ",0
AL_RESET_WORD:          DB "RESET",0
AL_CLEAR_WORD:          DB "CLEAR",0
AL_END:
                        ENDMOD
                        END
