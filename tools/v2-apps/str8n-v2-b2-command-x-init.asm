; Example X initializer at C700; registers X, then chains existing H at C000.
; Owns only 7403-7405 in manager RAM. No application/overlay RAM allocation.
                        MODULE B2_X_FLASH
                        XDEF START
                        XDEF FLASH_INIT_END
                        XDEF AUTO_ENTRY
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
                        INCLUDE "command-x-addresses.inc"
CALL_PTR                EQU $E0
TEXT_PTR                EQU $E2
                        CODE
START:                  JMP LEGACY_START
                        DB "XC",$01
                        DW FLASH_HANDLER,FLASH_STUB
AUTO_ENTRY:             JMP INITIALIZE
                        DB "EX",$01,'X'
LEGACY_START:           JSR INITIALIZE
                        BCS LEGACY_DONE
                        CMP #$01
                        BNE LEGACY_BUSY
                        LDX #<UNAVAILABLE_TEXT
                        LDY #>UNAVAILABLE_TEXT
                        BRA LEGACY_PRINT
LEGACY_BUSY:
                        LDX #<BUSY_TEXT
                        LDY #>BUSY_TEXT
LEGACY_PRINT:
                        JSR PRINT
                        JMP STR8V2_RAM_HOLD
LEGACY_DONE:            JMP $C000
INITIALIZE:             SEI
                        CLD
                        LDA $7D00
                        CMP #$03
                        BNE UNAVAILABLE
                        LDA $7FEC
                        AND #$EE
                        CMP #$EE
                        BNE UNAVAILABLE
                        LDX #$03
CHECK_DESCRIPTOR:       LDA $E000,X
                        CMP DESCRIPTOR,X
                        BNE UNAVAILABLE
                        DEX
                        BPL CHECK_DESCRIPTOR
                        JSR $E008
                        BCC UNAVAILABLE
                        LDA #<REGISTER_NAME
                        LDX #>REGISTER_NAME
                        LDY #$01
                        JSR STR8MGR_LOOKUP
                        BCC UNAVAILABLE
                        CPY #$01
                        BNE UNAVAILABLE
                        STA CALL_PTR
                        STX CALL_PTR+1
                        LDX #$00
SCAN_REGISTRY:          CPX MG_COUNT
                        BEQ CHECK_SPACE
                        CPX #MG_CAPACITY*3
                        BCS BUSY
                        LDA MG_TABLE,X
                        CMP #'X'
                        BEQ CHECK_EXISTING_X
                        LDA MG_TABLE+2,X
                        CMP #>FLASH_STUB
                        BNE SCAN_NEXT
                        LDA MG_TABLE+1,X
                        CMP #<FLASH_STUB
                        BCC SCAN_NEXT
                        CMP #<(FLASH_STUB+3)
                        BCC BUSY
SCAN_NEXT:              INX
                        INX
                        INX
                        BRA SCAN_REGISTRY
CHECK_EXISTING_X:       LDA MG_TABLE+1,X
                        CMP #<FLASH_STUB
                        BNE BUSY
                        LDA MG_TABLE+2,X
                        CMP #>FLASH_STUB
                        BNE BUSY
                        LDX #$02
CHECK_STUB:             LDA FLASH_STUB,X
                        CMP STUB_CODE,X
                        BNE BUSY
                        DEX
                        BPL CHECK_STUB
                        BRA READY
CHECK_SPACE:            CPX #MG_CAPACITY*3
                        BCS BUSY
                        LDX #$02
COPY_STUB:              LDA STUB_CODE,X
                        STA FLASH_STUB,X
                        DEX
                        BPL COPY_STUB
                        LDA #'X'
                        LDX #<FLASH_STUB
                        LDY #>FLASH_STUB
                        JSR CALL_ENTRY
                        BCC UNAVAILABLE
READY:                  LDA #<HELLO_DESCRIPTOR
                        LDX #>HELLO_DESCRIPTOR
                        JSR REGISTER_NAMED
                        BCC BUSY
                        LDA #<ECHO_DESCRIPTOR
                        LDX #>ECHO_DESCRIPTOR
                        JSR REGISTER_NAMED
                        BCC BUSY
                        LDA #$00
                        SEC
                        RTS
; Discover v2 separately; older managers retain the legacy X command.
REGISTER_NAMED:         PHX
                        PHA
                        LDA #<REGISTER_NAME
                        LDX #>REGISTER_NAME
                        LDY #$02
                        JSR STR8MGR_LOOKUP
                        BCC NAMED_UNAVAILABLE
                        STA CALL_PTR
                        STX CALL_PTR+1
                        PLA
                        PLX
                        PHA
                        PHX
                        LDY #$00
                        JSR CALL_ENTRY
                        STA $E9
                        PLX
                        PLA
                        STA TEXT_PTR
                        STX TEXT_PTR+1
                        LDA $E9
                        BEQ NAMED_READY
                        CMP #$02
                        BNE NAMED_BUSY
; A duplicate is idempotent only when all four stored descriptor bytes match.
                        LDX #$00
NAMED_EXISTING:         CPX MG_NAMED_COUNT
                        BEQ NAMED_BUSY
                        CPX #$20
                        BCS NAMED_BUSY
                        STX $EA
                        LDY #$00
NAMED_EXISTING_BYTE:    LDA (TEXT_PTR),Y
                        CMP MG_NAMED_TABLE,X
                        BNE NAMED_EXISTING_NEXT
                        INX
                        INY
                        CPY #$04
                        BNE NAMED_EXISTING_BYTE
                        BRA NAMED_READY
NAMED_EXISTING_NEXT:    LDA $EA
                        CLC
                        ADC #$04
                        TAX
                        BRA NAMED_EXISTING
NAMED_UNAVAILABLE:      PLA
                        PLX
NAMED_READY:            SEC
                        RTS
NAMED_BUSY:             CLC
                        RTS
BUSY:                   LDA #$02
                        CLC
                        RTS
UNAVAILABLE:            LDA #$01
                        CLC
                        RTS
CALL_ENTRY:             JMP (CALL_PTR)
PRINT:                  STX TEXT_PTR
                        STY TEXT_PTR+1
                        LDY #$00
PRINT_BYTE:             LDA (TEXT_PTR),Y
                        BEQ PRINT_DONE
                        JSR STR8V2_RAM_PUTC
                        INY
                        BRA PRINT_BYTE
PRINT_DONE:             RTS
STUB_CODE:              JMP FLASH_HANDLER
DESCRIPTOR:             DB "EM",$01,$01
REGISTER_NAME:          DB "COMMAND.REGISTER",0
HELLO_DESCRIPTOR:       DW HELLO_NAME,NAMED_HELLO
ECHO_DESCRIPTOR:        DW ECHO_NAME,NAMED_ECHO
HELLO_NAME:             DB "HELLO",0
ECHO_NAME:              DB "ECHO",0
BUSY_TEXT:              DB $0D,$0A,"X/stub conflict or registry full",$0D,$0A,0
UNAVAILABLE_TEXT:       DB $0D,$0A,"X requires a valid bank-3 b2 manager",$0D,$0A,0
FLASH_INIT_END:
                        ENDMOD
                        END
