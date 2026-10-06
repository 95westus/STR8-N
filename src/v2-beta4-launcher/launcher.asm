; Named application extension, bank 3 E000-E7FF. Legacy SR stays at E800.
; No application RAM or application zero-page byte is modified during probing.
; Foreground, IRQ masked, decimal clear; 816 E=1 D=DBR=PBR=0.
                       MODULE NAMED_APPS
                       XDEF AP_END
                       INCLUDE "str8n-v2-eq.inc"
                       INCLUDE "str8n-v2-public.inc"
                       INCLUDE "vectors-symbols.inc"
                       INCLUDE "sr-monitor-symbols.inc"
                       INCLUDE "app-text-ids.inc"
                       INCLUDE "app-fixed-symbols.inc"
AP_DESC EQU $7D90
AP_HEADER EQU $7DB0
AP_ROW EQU $7DC0
AP_CURSOR EQU $7DC2
AP_LIMIT EQU $7DC4
AP_INDEX EQU $7DC6
AP_ROWS EQU $7DC7
AP_OLD EQU $7DC8
AP_TOKEN EQU $7DC9
AP_PROBE_STATUS EQU $7DC9
AP_PROBE_SLOT EQU $7DCA
AP_TABLE EQU $E6F0
                       CODE
                       DB "NA",$01,$3F,$00,$00,$00,$00
                       JMP AP_DISPATCH       ; E008: JSR contract, C=handled
                       JMP AP_LEGACY_SR      ; E00B: monitor tail dispatch
                       JMP AP_LEGACY_MAP     ; E00E: monitor tail dispatch
                       JMP AP_PROBE          ; E011: read-only slot probe

; A=slot 0..7, C=valid. AP_DESC contains a fully checked descriptor on success.
; Caller must verify the extension seal/capability first and map resident B3.
; Preserve monitor ZP so this can be called by the RAM maintenance utility.
AP_PROBE:              STA AP_PROBE_SLOT
                       STZ AP_PROBE_STATUS
                       LDX #$1F
AP_PROBE_SAVE:         LDA $E0,X
                       PHA
                       DEX
                       BPL AP_PROBE_SAVE
                       LDA AP_PROBE_SLOT
                       CMP #$08
                       BCS AP_PROBE_DONE
                       ASL A
                       ASL A
                       ASL A
                       ASL A
                       ASL A
                       CLC
                       ADC #$F4
                       STA V2_PTR
                       LDA #$E6
                       ADC #$00
                       STA V2_PTR+1
                       LDY #$1F
AP_PROBE_COPY:         LDA (V2_PTR),Y
                       STA AP_DESC,Y
                       DEY
                       BPL AP_PROBE_COPY
                       LDA AP_DESC+30
                       CMP #$3F
                       BNE AP_PROBE_DONE
                       LDA AP_DESC
                       BEQ AP_PROBE_DONE
                       STZ AP_PROBE_SLOT
                       LDX #$00
AP_PROBE_NAME:         LDA AP_DESC,X
                       BEQ AP_PROBE_PAD
                       LDY AP_PROBE_SLOT
                       BNE AP_PROBE_DONE
                       CPX #$0B
                       BEQ AP_PROBE_DONE
                       CMP #'A'
                       BCC AP_PROBE_DONE
                       CMP #'Z'+1
                       BCS AP_PROBE_DONE
                       BRA AP_PROBE_NAME_NEXT
AP_PROBE_PAD:          INC AP_PROBE_SLOT
AP_PROBE_NAME_NEXT:    INX
                       CPX #$0C
                       BNE AP_PROBE_NAME
                       JSR AP_VALIDATE
                       BCC AP_PROBE_DONE
                       JSR AP_LOAD_HEADER
                       BCC AP_PROBE_DONE
                       JSR AP_VERIFY_VECTORS
                       BCC AP_PROBE_DONE
                       JSR AP_VERIFY_IMAGE
                       BCC AP_PROBE_DONE
                       INC AP_PROBE_STATUS
AP_PROBE_DONE:         LDX #$00
AP_PROBE_RESTORE:      PLA
                       STA $E0,X
                       INX
                       CPX #$20
                       BNE AP_PROBE_RESTORE
                       CLC
                       LDA AP_PROBE_STATUS
                       BEQ AP_PROBE_RETURN
                       SEC
AP_PROBE_RETURN:       RTS

AP_DISPATCH:           LDA V2_LINE
                       CMP #'?'
                       BNE AP_DISPATCH_NAME
                       LDA V2_LINE+1
                       BNE AP_NO_MATCH
                       JSR AP_HELP_MONITOR
                       LDX #<AP_HELP_TEXT
                       LDY #>AP_HELP_TEXT
                       JSR AP_PRINT
                       SEC
                       RTS
; The immutable F router uses the active slot's printer/text table.
AP_HELP_MONITOR:       LDX #V2_HELP
                       PHX
                       LDX #$1E
                       JMP AP_SLOT_ROUTE
AP_DISPATCH_NAME:      LDX #$00
AP_TOKEN_LOOP:         LDA V2_LINE,X
                       BEQ AP_TOKEN_DONE
                       CMP #' '
                       BEQ AP_TOKEN_DONE
                       INX
                       CPX #$0C
                       BCC AP_TOKEN_LOOP
AP_NO_MATCH:           CLC
                       RTS
AP_TOKEN_DONE:         STX AP_TOKEN
                       CPX #$04
                       BNE AP_FIND
                       LDA V2_LINE
                       CMP #'A'
                       BNE AP_FIND
                       LDA V2_LINE+1
                       CMP #'P'
                       BNE AP_FIND
                       LDA V2_LINE+2
                       CMP #'P'
                       BNE AP_FIND
                       LDA V2_LINE+3
                       CMP #'S'
                       BEQ AP_LIST
AP_FIND:               LDA #$F4
                       STA AP_ROW
                       LDA #$E6
                       STA AP_ROW+1
                       LDA #$08
                       STA AP_ROWS
AP_FIND_ROW:           LDY #$00
                       LDA AP_ROW
                       STA V2_PTR
                       LDA AP_ROW+1
                       STA V2_PTR+1
AP_NAME_LOOP:          LDA (V2_PTR),Y
                       CMP V2_LINE,Y
                       BNE AP_NAME_END
                       INY
                       CPY AP_TOKEN
                       BCC AP_NAME_LOOP
                       LDA (V2_PTR),Y
                       BEQ AP_MATCH
AP_NAME_END:           JSR AP_NEXT_ROW
                       DEC AP_ROWS
                       BNE AP_FIND_ROW
                       BRA AP_NO_MATCH
AP_MATCH:              JSR AP_ARGUMENTS
                       BCC AP_ARGUMENT_ERROR
                       LDY #$1F
AP_COPY_DESC:          LDA (V2_PTR),Y
                       STA AP_DESC,Y
                       DEY
                       BPL AP_COPY_DESC
                       LDA AP_DESC+30
                       CMP #$3F
                       BNE AP_NOT_INSTALLED
                       JSR AP_VALIDATE
                       BCC AP_INVALID
                       JSR AP_LOAD_HEADER
                       BCC AP_INVALID
                       JSR AP_VERIFY_VECTORS
                       BCC AP_INVALID
                       JSR AP_VERIFY_IMAGE
                       BCC AP_INVALID
; Only a completed validation changes SELECTED permanently or transfers control.
                       LDA AP_DESC+12
                       STA V2_SELECTED
                       LDA AP_DESC+18
                       STA V2_VECTOR
                       LDA AP_DESC+19
                       STA V2_VECTOR+1
                       JMP V2W_EXECUTE
AP_NOT_INSTALLED:      LDX #<AP_MISSING_TEXT
                       LDY #>AP_MISSING_TEXT
                       BRA AP_REPORT
AP_ARGUMENT_ERROR:     LDX #<AP_ARGUMENT_TEXT
                       LDY #>AP_ARGUMENT_TEXT
                       BRA AP_REPORT
AP_INVALID:            LDX #<AP_INVALID_TEXT
                       LDY #>AP_INVALID_TEXT
AP_REPORT:             JSR AP_PRINT
                       SEC
                       RTS

AP_ARGUMENTS:          LDX AP_TOKEN
AP_ARGUMENT_LOOP:      LDA V2_LINE,X
                       BEQ AP_ARGUMENT_OK
                       CMP #' '
                       BNE AP_ARGUMENT_BAD
                       INX
                       BRA AP_ARGUMENT_LOOP
AP_ARGUMENT_OK:        SEC
                       RTS
AP_ARGUMENT_BAD:       CLC
                       RTS

AP_LIST:               JSR AP_ARGUMENTS
                       BCC AP_ARGUMENT_ERROR
                       LDA #$F4
                       STA AP_ROW
                       LDA #$E6
                       STA AP_ROW+1
                       LDA #$08
                       STA AP_ROWS
AP_LIST_ROW:           LDA AP_ROW
                       STA V2_PTR
                       LDA AP_ROW+1
                       STA V2_PTR+1
                       LDY #$00
                       LDA (V2_PTR),Y
                       BEQ AP_LIST_NEXT
                       JSR STR8V2_RAM_NEWLINE
                       STZ AP_INDEX
AP_LIST_NAME:          LDY AP_INDEX
                       LDA (V2_PTR),Y
                       BEQ AP_LIST_STATE
                       JSR STR8V2_RAM_PUTC
                       INC AP_INDEX
                       LDA AP_INDEX
                       CMP #$0C
                       BCC AP_LIST_NAME
AP_LIST_STATE:         LDY #$1E
                       LDA (V2_PTR),Y
                       CMP #$3F
                       BNE AP_LIST_MISSING
                       LDX #<AP_INSTALLED_TEXT
                       LDY #>AP_INSTALLED_TEXT
                       JSR AP_PRINT
                       LDY #$0C
                       LDA (V2_PTR),Y
                       ORA #'0'
                       JSR STR8V2_RAM_PUTC
                       LDA #':'
                       JSR STR8V2_RAM_PUTC
                       LDY #$0E
                       JSR AP_LIST_WORD
                       LDX #<AP_LENGTH_TEXT
                       LDY #>AP_LENGTH_TEXT
                       JSR AP_PRINT
                       LDY #$10
                       JSR AP_LIST_WORD
                       BRA AP_LIST_NEXT
AP_LIST_MISSING:       LDX #<AP_UNINSTALLED_TEXT
                       LDY #>AP_UNINSTALLED_TEXT
AP_LIST_PRINT:         JSR AP_PRINT
AP_LIST_NEXT:          JSR AP_NEXT_ROW
                       DEC AP_ROWS
                       BNE AP_LIST_ROW
                       SEC
                       RTS
; Print the descriptor's little-endian word at Y as four hexadecimal digits.
AP_LIST_WORD:          LDA (V2_PTR),Y
                       PHA
                       INY
                       LDA (V2_PTR),Y
                       JSR STR8V2_RAM_HEX_OUT
                       PLA
                       JMP STR8V2_RAM_HEX_OUT
AP_NEXT_ROW:           LDA AP_ROW
                       CLC
                       ADC #$20
                       STA AP_ROW
                       BCC AP_NEXT_DONE
                       INC AP_ROW+1
AP_NEXT_DONE:          RTS

; Descriptor CRC, ABI, address bounds and exclusive workspace declarations.
AP_VALIDATE:           LDA AP_DESC+31
                       BNE AP_VALIDATE_BAD
                       LDA AP_DESC+12
                       CMP #$04
                       BCS AP_VALIDATE_BAD
                       LDA AP_DESC+13
                       CMP #$01
                       BNE AP_VALIDATE_BAD
                       JSR AP_CRC_INIT
                       LDY #$00
AP_DESC_CRC:           LDA AP_DESC,Y
                       JSR AP_CRC_BYTE
                       INY
                       CPY #$1C
                       BNE AP_DESC_CRC
                       LDA AP_DESC+30
                       JSR AP_CRC_BYTE
                       LDA AP_DESC+31
                       JSR AP_CRC_BYTE
                       LDA AP_DESC+28
                       CMP J_CRC
                       BNE AP_VALIDATE_BAD
                       LDA AP_DESC+29
                       CMP J_CRC+1
                       BNE AP_VALIDATE_BAD
                       LDA AP_DESC+15
                       BPL AP_VALIDATE_BAD
; Image must contain a 16-byte header and stay below the hardware-vector area.
                       LDA AP_DESC+17
                       BNE AP_LENGTH_OK
                       LDA AP_DESC+16
                       CMP #$11
                       BCC AP_VALIDATE_BAD
AP_LENGTH_OK:          LDA AP_DESC+14
                       CLC
                       ADC AP_DESC+16
                       STA AP_LIMIT
                       LDA AP_DESC+15
                       ADC AP_DESC+17
                       STA AP_LIMIT+1
                       BCS AP_VALIDATE_BAD
                       CMP #$FF
                       BCC AP_LIMIT_OK
                       BNE AP_VALIDATE_BAD
                       LDA AP_LIMIT
                       CMP #$E1
                       BCS AP_VALIDATE_BAD
AP_LIMIT_OK:           LDA AP_DESC+12
                       CMP #$03
                       BNE AP_ENTRY_CHECK
                       LDA AP_LIMIT+1
                       CMP #$A0
                       BCC AP_ENTRY_CHECK
                       BNE AP_VALIDATE_BAD
                       LDA AP_LIMIT
                       BNE AP_VALIDATE_BAD
AP_ENTRY_CHECK:        LDA AP_DESC+14
                       CLC
                       ADC #$10
                       STA AP_CURSOR
                       LDA AP_DESC+15
                       ADC #$00
                       STA AP_CURSOR+1
                       LDA AP_DESC+18
                       CMP AP_CURSOR
                       LDA AP_DESC+19
                       SBC AP_CURSOR+1
                       BCC AP_VALIDATE_BAD
                       LDA AP_DESC+18
                       CMP AP_LIMIT
                       LDA AP_DESC+19
                       SBC AP_LIMIT+1
                       BCS AP_VALIDATE_BAD
; 0000/0000 means no application workspace. Otherwise use 0200-66FF.
                       LDA AP_DESC+20
                       ORA AP_DESC+21
                       ORA AP_DESC+22
                       ORA AP_DESC+23
                       BEQ AP_ZP_CHECK
                       LDA AP_DESC+21
                       CMP #$02
                       BCC AP_VALIDATE_BAD
                       LDA AP_DESC+23
                       CMP #$67
                       BCS AP_VALIDATE_BAD
                       LDA AP_DESC+22
                       CMP AP_DESC+20
                       LDA AP_DESC+23
                       SBC AP_DESC+21
                       BCC AP_VALIDATE_BAD
AP_ZP_CHECK:           LDA AP_DESC+24
                       CMP #$FF
                       BNE AP_ZP_PRESENT
                       LDA AP_DESC+25
                       CMP #$FF
                       BEQ AP_VALIDATE_OK
                       BRA AP_VALIDATE_BAD
AP_ZP_PRESENT:         LDA AP_DESC+24
                       CMP AP_DESC+25
                       BCC AP_ZP_RANGE
                       BNE AP_VALIDATE_BAD
AP_ZP_RANGE:           LDA AP_DESC+25
                       CMP #$E0
                       BCS AP_VALIDATE_BAD
AP_VALIDATE_OK:
                       SEC
                       RTS
AP_VALIDATE_BAD:       CLC
                       RTS

; Read while RAM worker temporarily selects the target bank and restores B3.
AP_READ:               LDA AP_CURSOR
                       STA V2_ADDR
                       LDA AP_CURSOR+1
                       STA V2_ADDR+1
                       LDA #$01
                       STA V2_COUNT
                       JSR V2W_READ
                       LDA V2_BYTES
                       INC AP_CURSOR
                       BNE AP_READ_DONE
                       INC AP_CURSOR+1
AP_READ_DONE:          RTS
AP_LOAD_HEADER:        LDA V2_SELECTED
                       STA AP_OLD
                       LDA AP_DESC+12
                       STA V2_SELECTED
                       LDA AP_DESC+14
                       STA AP_CURSOR
                       LDA AP_DESC+15
                       STA AP_CURSOR+1
                       STZ AP_INDEX
AP_HEADER_READ:        JSR AP_READ
                       LDX AP_INDEX
                       STA AP_HEADER,X
                       INC AP_INDEX
                       LDA AP_INDEX
                       CMP #$10
                       BNE AP_HEADER_READ
                       LDA AP_OLD
                       STA V2_SELECTED
                       LDA AP_HEADER
                       CMP #'A'
                       BNE AP_HEADER_BAD
                       LDA AP_HEADER+1
                       CMP #'P'
                       BNE AP_HEADER_BAD
                       LDA AP_HEADER+2
                       CMP #$01
                       BNE AP_HEADER_BAD
                       LDA AP_HEADER+3
                       CMP AP_DESC+13
                       BNE AP_HEADER_BAD
; Header duplicates length, entry, workspace and zero-page ownership.
                       LDX #$09
AP_HEADER_MATCH:       LDA AP_HEADER+4,X
                       CMP AP_DESC+16,X
                       BNE AP_HEADER_BAD
                       DEX
                       BPL AP_HEADER_MATCH
                       JSR AP_CRC_INIT
                       LDY #$00
AP_HEADER_CRC:         LDA AP_HEADER,Y
                       JSR AP_CRC_BYTE
                       INY
                       CPY #$0E
                       BNE AP_HEADER_CRC
                       LDA AP_HEADER+14
                       CMP J_CRC
                       BNE AP_HEADER_BAD
                       LDA AP_HEADER+15
                       CMP J_CRC+1
                       BNE AP_HEADER_BAD
                       SEC
                       RTS
AP_HEADER_BAD:         CLC
                       RTS

; Every bank must route hardware exceptions to the initialized RAM dispatchers.
; RESET is deliberately outside the launch contract; launch is through G's worker.
AP_VERIFY_VECTORS:     LDA V2_SELECTED
                       STA AP_OLD
                       LDA AP_DESC+12
                       STA V2_SELECTED
                       STZ AP_INDEX
AP_VECTOR_LOOP:        LDX AP_INDEX
                       LDA AP_VECTOR_OFFSETS,X
                       STA AP_CURSOR
                       LDA #$FF
                       STA AP_CURSOR+1
                       JSR AP_READ
                       LDX AP_INDEX
                       CMP AP_VECTOR_VALUES,X
                       BNE AP_VECTOR_BAD
                       INC AP_INDEX
                       LDA AP_INDEX
                       CMP #$12
                       BNE AP_VECTOR_LOOP
                       LDA AP_OLD
                       STA V2_SELECTED
                       SEC
                       RTS
AP_VECTOR_BAD:         LDA AP_OLD
                       STA V2_SELECTED
                       CLC
                       RTS
AP_VECTOR_OFFSETS:     DB $E4,$E5,$E6,$E7,$E8,$E9,$EA,$EB,$EE,$EF
                       DB $F4,$F5,$F8,$F9,$FA,$FB,$FE,$FF
AP_VECTOR_VALUES:      DW V2V_NATIVE_COP,V2V_NATIVE_BRK,V2V_NATIVE_ABORT
                       DW V2V_NATIVE_NMI,V2V_NATIVE_IRQ,V2V_COP,V2V_ABORT
                       DW V2V_NMI,V2V_IRQ_BRK

AP_VERIFY_IMAGE:       LDA AP_DESC+14
                       STA AP_CURSOR
                       LDA AP_DESC+15
                       STA AP_CURSOR+1
                       LDA V2_SELECTED
                       STA AP_OLD
                       LDA AP_DESC+12
                       STA V2_SELECTED
                       JSR AP_CRC_INIT
AP_IMAGE_CRC:          JSR AP_READ
                       JSR AP_CRC_BYTE
                       LDA AP_CURSOR
                       CMP AP_LIMIT
                       LDA AP_CURSOR+1
                       SBC AP_LIMIT+1
                       BCC AP_IMAGE_CRC
                       LDA AP_OLD
                       STA V2_SELECTED
                       LDA AP_DESC+26
                       CMP J_CRC
                       BNE AP_IMAGE_BAD
                       LDA AP_DESC+27
                       CMP J_CRC+1
                       BNE AP_IMAGE_BAD
                       SEC
                       RTS
AP_IMAGE_BAD:          CLC
                       RTS

; Independent console helper; shared monitor pointers may be clobbered by I/O.
AP_PRINT:              STX V2_BUF_PTR
                       STY V2_BUF_PTR+1
                       PHY
                       LDY #$00
AP_PRINT_LOOP:         LDA (V2_BUF_PTR),Y
                       BEQ AP_PRINT_DONE
                       PHY
                       JSR STR8V2_RAM_PUTC
                       PLY
                       INY
                       BRA AP_PRINT_LOOP
AP_PRINT_DONE:         PLY
                       RTS

AP_MISSING_TEXT:       DB $0D,$0A,"App not installed",0
AP_INVALID_TEXT:       DB $0D,$0A,"App invalid/incompatible",0
AP_ARGUMENT_TEXT:      DB $0D,$0A,"App takes no arguments",0
AP_INSTALLED_TEXT:     DB " installed B",0
AP_LENGTH_TEXT:        DB " LEN ",0
AP_UNINSTALLED_TEXT:   DB " not installed",0
                       INCLUDE "app-help.inc"

; Legacy dispatch/map code is moved here, retaining SR's original public slots.
                       INCLUDE "app-legacy-dispatch.inc"
AP_MAP_EDIT:           PHX
                       LDX #$26           ; Extra private slot-header service #19.
                       JMP AP_SLOT_ROUTE  ; Existing F router; F bytes unchanged.
AP_END:
