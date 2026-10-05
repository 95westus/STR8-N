; Permanent resident-bank command provider. Entry C000, H code in this sector.
; Owns only 7400-7402 in manager RAM. No application/overlay RAM allocation.
                        MODULE B2_HELP_FLASH
                        XDEF START
                        XDEF FLASH_INIT_END
                        XDEF AUTO_ENTRY
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
                        INCLUDE "help-flash-addresses.inc"
CALL_PTR                EQU $E0
TEXT_PTR                EQU $E2
                        CODE
START:                  JMP LEGACY_START
                        DB "HC",$01
                        DW FLASH_HANDLER,FLASH_STUB
AUTO_ENTRY:             JMP INITIALIZE
                        DB "EX",$01,'H'
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
LEGACY_DONE:            JMP STR8V2_RAM_HOLD
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
                        CMP #'H'
                        BEQ CHECK_EXISTING_H
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
CHECK_EXISTING_H:       LDA MG_TABLE+1,X
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
                        LDA #'H'
                        LDX #<FLASH_STUB
                        LDY #>FLASH_STUB
                        JSR CALL_ENTRY
                        BCC UNAVAILABLE
READY:                  LDA #$00
                        SEC
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
BUSY_TEXT:              DB $0D,$0A,"H/stub conflict or registry full",$0D,$0A,0
UNAVAILABLE_TEXT:       DB $0D,$0A,"H requires a valid bank-3 b2 manager",$0D,$0A,0
FLASH_INIT_END:
                        ENDMOD
                        END
