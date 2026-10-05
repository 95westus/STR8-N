; Load at 2000 with L, run G 2000, pin H at 5800 and register it.
; This first loader reserves the entire overlay area while H is installed.
                        MODULE B2_HELP_LOADER
                        XDEF START
                        XDEF APP_END
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
                        INCLUDE "help-image.inc"
CALL_PTR                EQU $C0
SOURCE_PTR              EQU $C2
DEST_PTR                EQU $C4
TEXT_PTR                EQU $C6
                        CODE
START:                  SEI
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
                        BEQ BUSY
                        LDA MG_TABLE+2,X
                        CMP #$58
                        BCC SCAN_NEXT
                        CMP #$60
                        BCC BUSY
SCAN_NEXT:              INX
                        INX
                        INX
                        BRA SCAN_REGISTRY
CHECK_SPACE:            CPX #MG_CAPACITY*3
                        BCS BUSY
                        LDA #<HELP_IMAGE
                        STA SOURCE_PTR
                        LDA #>HELP_IMAGE
                        STA SOURCE_PTR+1
                        STZ DEST_PTR
                        LDA #$58
                        STA DEST_PTR+1
                        LDY #$00
COPY_BYTE:              LDA (SOURCE_PTR),Y
                        STA (DEST_PTR),Y
                        INC SOURCE_PTR
                        BNE COPY_DEST
                        INC SOURCE_PTR+1
COPY_DEST:              INC DEST_PTR
                        BNE COPY_CHECK
                        INC DEST_PTR+1
COPY_CHECK:             LDA DEST_PTR
                        CMP #<PINNED_END
                        BNE COPY_BYTE
                        LDA DEST_PTR+1
                        CMP #>PINNED_END
                        BNE COPY_BYTE
                        LDA #'H'
                        LDX #<PINNED_ENTRY
                        LDY #>PINNED_ENTRY
                        JSR CALL_ENTRY
                        BCC UNAVAILABLE
                        LDX #<SUCCESS_TEXT
                        LDY #>SUCCESS_TEXT
                        BRA FINISH
BUSY:                   LDX #<BUSY_TEXT
                        LDY #>BUSY_TEXT
                        BRA FINISH
UNAVAILABLE:            LDX #<UNAVAILABLE_TEXT
                        LDY #>UNAVAILABLE_TEXT
FINISH:                 JSR PRINT
                        JMP STR8V2_RAM_HOLD
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
DESCRIPTOR:             DB "EM",$01,$01
REGISTER_NAME:          DB "COMMAND.REGISTER",0
SUCCESS_TEXT:           DB $0D,$0A,"H registered",$0D,$0A,0
BUSY_TEXT:              DB $0D,$0A,"H already registered, overlay busy or registry full",$0D,$0A,0
UNAVAILABLE_TEXT:       DB $0D,$0A,"H requires a valid bank-3 b2 manager",$0D,$0A,0
HELP_IMAGE:
                        INCLUDE "help-bytes.inc"
APP_END:
                        ENDMOD
                        END
