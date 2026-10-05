; Board probe: publish callable/data versions, test duplicate protection.
; Temporary ownership: 7700-7808. Reset withdraws records; RESTORE then
; restores these bytes from the saved board snapshot before app RAM reload.
                        MODULE B2_SERVICES_TEST
                        XDEF START,RESTORE,APP_END
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
PTR                     EQU $E0
DST                     EQU $E2
                        CODE
START:                  SEI
                        CLD
                        LDA MG_DYNAMIC_COUNT
                        BNE FAIL
                        JSR $E008
                        BCC FAIL
                        LDA #<REGISTER_NAME
                        LDX #>REGISTER_NAME
                        LDY #$01
                        JSR STR8MGR_LOOKUP
                        BCC FAIL
                        CPY #$01
                        BNE FAIL
                        STA REGISTER_PTR
                        STX REGISTER_PTR+1
                        LDX #$00
COPY_NAME:              LDA PROVIDER_NAME,X
                        STA $7700,X
                        INX
                        CPX #$0C
                        BNE COPY_NAME
                        LDX #$00
COPY_BUILTIN:           LDA BUILTIN_NAME,X
                        STA $7720,X
                        INX
                        CPX #$0D
                        BNE COPY_BUILTIN
                        LDA #$A9
                        STA $7800
                        LDA #$42
                        STA $7801
                        LDA #$60
                        STA $7802
                        LDA #$A5
                        STA $7808
                        LDA #<DESC_ONE
                        LDX #>DESC_ONE
                        LDY #$00
                        JSR REGISTER
                        BCC FAIL
                        CMP #$00
                        BNE FAIL
                        LDA #<DESC_TWO
                        LDX #>DESC_TWO
                        LDY #$00
                        JSR REGISTER
                        BCC FAIL
                        LDA #<DESC_ONE
                        LDX #>DESC_ONE
                        LDY #$00
                        JSR REGISTER
                        BCS FAIL
                        CMP #$02
                        BNE FAIL
                        LDA #<DESC_CORE
                        LDX #>DESC_CORE
                        LDY #$00
                        JSR REGISTER
                        BCS FAIL
                        CMP #$02
                        BNE FAIL
; Prove that the manager copied the descriptor, not its address.
                        LDX #$05
CLEAR_DESCRIPTOR:       STZ DESC_ONE,X
                        DEX
                        BPL CLEAR_DESCRIPTOR
                        LDA #$00
                        LDX #$77
                        LDY #$01
                        JSR STR8MGR_LOOKUP
                        BCC FAIL
                        CMP #$00
                        BNE FAIL
                        CPX #$78
                        BNE FAIL
                        CPY #$01
                        BNE FAIL
                        STA PROVIDER_PTR
                        STX PROVIDER_PTR+1
                        JSR CALL_PROVIDER
                        CMP #$42
                        BNE FAIL
                        LDA #$00
                        LDX #$77
                        LDY #$02
                        JSR STR8MGR_LOOKUP
                        BCC FAIL
                        CMP #$08
                        BNE FAIL
                        CPX #$78
                        BNE FAIL
                        CPY #$00
                        BNE FAIL
                        LDA $7808
                        CMP #$A5
                        BNE FAIL
                        LDA #$00
                        LDX #$77
                        LDY #$03
                        JSR STR8MGR_LOOKUP
                        BCS FAIL
                        CMP #$02
                        BNE FAIL
                        LDA MG_DYNAMIC_COUNT
                        CMP #$0C
                        BNE FAIL
                        LDA MG_COUNT
                        CMP #$12
                        BNE FAIL
                        LDX #<PASS_TEXT
                        LDY #>PASS_TEXT
                        BRA FINISH
RESTORE:                SEI
                        CLD
                        LDA MG_DYNAMIC_COUNT
                        BNE FAIL
                        LDA #<ORIGINAL_MODULE_BYTES
                        STA PTR
                        LDA #>ORIGINAL_MODULE_BYTES
                        STA PTR+1
                        STZ DST
                        LDA #$77
                        STA DST+1
                        LDY #$00
RESTORE_BYTE:           LDA (PTR),Y
                        STA (DST),Y
                        INC PTR
                        BNE RESTORE_DEST
                        INC PTR+1
RESTORE_DEST:           INC DST
                        BNE RESTORE_CHECK
                        INC DST+1
RESTORE_CHECK:          LDA DST
                        CMP #$09
                        BNE RESTORE_BYTE
                        LDA DST+1
                        CMP #$78
                        BNE RESTORE_BYTE
                        LDX #<RESTORED_TEXT
                        LDY #>RESTORED_TEXT
                        BRA FINISH
FAIL:                   LDX #<FAIL_TEXT
                        LDY #>FAIL_TEXT
FINISH:                 JSR PRINT
                        JMP STR8V2_RAM_HOLD
REGISTER:               JMP (REGISTER_PTR)
CALL_PROVIDER:          JMP (PROVIDER_PTR)
PRINT:                  STX PTR
                        STY PTR+1
                        LDY #$00
PRINT_BYTE:             LDA (PTR),Y
                        BEQ PRINT_END
                        JSR STR8V2_RAM_PUTC
                        INY
                        BRA PRINT_BYTE
PRINT_END:              RTS
REGISTER_PTR:           DW $0000
PROVIDER_PTR:           DW $0000
DESC_ONE:               DB $00,$77,$01,$01,$00,$78
DESC_TWO:               DB $00,$77,$02,$00,$08,$78
DESC_CORE:              DB $20,$77,$01,$01,$00,$78
REGISTER_NAME:          DB "SERVICE.REGISTER",0
PROVIDER_NAME:          DB "BOARD.VALUE",0
BUILTIN_NAME:           DB "CONSOLE.PUTC",0
PASS_TEXT:              DB "SERVICE REGISTER / CALLABLE / DATA / VERSION / DUPLICATE PASS",$0D,$0A,0
RESTORED_TEXT:          DB "TEMP PROVIDER RAM RESTORED",$0D,$0A,0
FAIL_TEXT:              DB "SERVICE PROBE FAIL",$0D,$0A,0
ORIGINAL_MODULE_BYTES:  INCLUDE "original-service-ram.inc"
APP_END:
                        ENDMOD
                        END
