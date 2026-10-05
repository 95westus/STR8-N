; Independent pinned command/service probe for the b2 C02 board acceptance.
; Leaves an X handler in the reserved overlay; RESET withdraws registration.
                        MODULE B2_MANAGER_TEST
                        XDEF START
                        XDEF APP_END
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
CALL_PTR                EQU $C0
TEXT_PTR                EQU $C2
SAVED_PCR               EQU $C4
TEST_BANK               EQU $C5
                        CODE
START:                  SEI
                        CLD
                        JSR $E008
                        BCC FAIL
                        LDA #<PUTC_NAME
                        LDX #>PUTC_NAME
                        LDY #$01
                        JSR STR8MGR_LOOKUP
                        BCC FAIL
                        CMP #<STR8V2_RAM_PUTC
                        BNE FAIL
                        CPX #>STR8V2_RAM_PUTC
                        BNE FAIL
                        CPY #$01
                        BNE FAIL
                        STA CALL_PTR
                        STX CALL_PTR+1
                        LDA $7FEC
                        STA SAVED_PCR
                        STZ TEST_BANK
NEXT_BANK:              LDX TEST_BANK
                        LDA SAVED_PCR
                        AND #$11
                        ORA BANK_BITS,X
                        STA $7FEC
                        LDA TEST_BANK
                        ORA #'0'
                        JSR CALL_ENTRY
                        LDX TEST_BANK
                        LDA SAVED_PCR
                        AND #$11
                        ORA BANK_BITS,X
                        CMP $7FEC
                        BNE FAIL_RESTORE_BANK
                        INC TEST_BANK
                        LDA TEST_BANK
                        CMP #$04
                        BNE NEXT_BANK
                        LDA SAVED_PCR
                        STA $7FEC
                        LDA #<PUTC_NAME
                        LDX #>PUTC_NAME
                        LDY #$02
                        JSR STR8MGR_LOOKUP
                        BCS FAIL
                        CMP #$02
                        BNE FAIL
                        LDA #<MISSING_NAME
                        LDX #>MISSING_NAME
                        LDY #$01
                        JSR STR8MGR_LOOKUP
                        BCS FAIL
                        CMP #$01
                        BNE FAIL
                        LDX #<LOOKUP_PASS
                        LDY #>LOOKUP_PASS
                        JSR PRINT
                        LDA #<CONFIG_NAME
                        LDX #>CONFIG_NAME
                        LDY #$01
                        JSR STR8MGR_LOOKUP
                        BCC FAIL
                        STA CALL_PTR
                        STX CALL_PTR+1
                        JSR CALL_ENTRY
                        BCS FAIL
                        CMP #$00
                        BNE FAIL
                        LDX #<CONFIG_PASS
                        LDY #>CONFIG_PASS
                        JSR PRINT
                        LDX #$00
COPY_X:                 LDA X_CODE,X
                        STA $5800,X
                        INX
                        CPX #X_END-X_CODE
                        BNE COPY_X
                        LDA #<REGISTER_NAME
                        LDX #>REGISTER_NAME
                        LDY #$01
                        JSR STR8MGR_LOOKUP
                        BCC FAIL
                        STA CALL_PTR
                        STX CALL_PTR+1
                        LDA #'X'
                        LDX #$00
                        LDY #$58
                        JSR CALL_ENTRY
                        BCC FAIL
                        LDA #'X'
                        STA $7C00
                        STZ $7C01
                        JSR STR8MGR_DISPATCH
                        CMP #$01
                        BNE FAIL
                        LDA #'Y'
                        STA $7C01
                        STZ $7C02
                        JSR STR8MGR_DISPATCH
                        CMP #$00
                        BNE FAIL
                        LDX #<REGISTER_PASS
                        LDY #>REGISTER_PASS
                        JSR PRINT
                        JMP STR8V2_RAM_HOLD
FAIL_RESTORE_BANK:      LDA SAVED_PCR
                        STA $7FEC
FAIL:                   LDX #<FAIL_TEXT
                        LDY #>FAIL_TEXT
                        JSR PRINT
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
X_CODE:                 LDA #'X'
                        JSR STR8V2_RAM_PUTC
                        LDA #$01
                        RTS
X_END:
BANK_BITS:              DB $CC,$CE,$EC,$EE
PUTC_NAME:              DB "CONSOLE.PUTC",0
MISSING_NAME:           DB "NO.SUCH.SERVICE",0
CONFIG_NAME:            DB "CONFIG.LOCATE",0
REGISTER_NAME:          DB "COMMAND.REGISTER",0
LOOKUP_PASS:            DB $0D,$0A,"LOOKUP / VERSION / FOUR-BANK CONSOLE PASS",$0D,$0A,0
CONFIG_PASS:            DB "CONFIG UNASSIGNED PASS",$0D,$0A,0
REGISTER_PASS:          DB $0D,$0A,"REGISTER / EXACT DISPATCH PASS",$0D,$0A,0
FAIL_TEXT:              DB $0D,$0A,"MANAGER PROBE FAIL",$0D,$0A,0
APP_END:
                        ENDMOD
                        END
