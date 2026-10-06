; Board-specific one-time migration, all code/constants/I/O in RAM.
; Six exact raw sector transfers; whole-bank FNV guard before each write,
; payload FNV before mutation, full sector comparison, fixed F installed LAST.
; No automatic retry: failure halts in RAM, preserving the staged image.
                        MODULE MIGRATION
                        XDEF MIG_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "migration-symbols.inc"
MIG_INDEX EQU $6200
MIG_TABLE_INDEX EQU $6201
MIG_HASH EQU $6204
MIG_TERM EQU $6208
MIG_STOP EQU $620C
                        CODE
START:                  SEI
                        CLD
                        LDX #$FF
                        TXS
                        LDA #$03
                        STA V2_RESIDENT
                        STA V2_SELECTED
                        STA V2_TARGET
                        STZ V2_NMI_HOLD
                        STZ V2_SELF
                        INCLUDE "migration-copy.inc"
                        LDA #$03
                        JSR V2W_SELECT
                        JSR V2W_CON_INIT
                        JSR V2W_RX_RESET
                        STZ MIG_INDEX
                        STZ MIG_TABLE_INDEX
                        LDX #<MIG_TITLE
                        LDY #>MIG_TITLE
                        JSR MIG_PRINT
                        JSR V2W_GETC
                        CMP #'Y'
                        BNE MIG_FAIL
                        JSR V2W_GETC
                        CMP #$0D
                        BNE MIG_FAIL
MIG_NEXT:               JSR MIG_GUARD
                        BCC MIG_FAIL
                        LDX MIG_TABLE_INDEX
                        LDA MIG_TABLE,X
                        STA V2_SECTOR
                        LDX #<MIG_SEND
                        LDY #>MIG_SEND
                        JSR MIG_PRINT
                        LDA V2_SECTOR
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        CLC
                        ADC #'0'
                        CMP #'9'+1
                        BCC MIG_DIGIT
                        ADC #$06
MIG_DIGIT:              JSR V2W_PUTC
                        LDA #$0D
                        JSR V2W_PUTC
                        LDA #$0A
                        JSR V2W_PUTC
                        STZ V2_BUF_PTR
                        LDA #$68
                        STA V2_BUF_PTR+1
MIG_RECEIVE:            JSR V2W_RAW_POLL
                        BCC MIG_RECEIVE
                        STA (V2_BUF_PTR)
                        INC V2_BUF_PTR
                        BNE MIG_RECEIVE
                        INC V2_BUF_PTR+1
                        LDA V2_BUF_PTR+1
                        CMP #$78
                        BNE MIG_RECEIVE
                        STZ V2_PTR
                        LDA #$68
                        STA V2_PTR+1
                        LDA #$78
                        STA MIG_STOP
                        JSR MIG_HASH_RANGE
                        LDA MIG_TABLE_INDEX
                        CLC
                        ADC #$05
                        TAX
                        JSR MIG_HASH_COMPARE
                        BCC MIG_FAIL
                        JSR MIG_GUARD
                        BCC MIG_FAIL
                        LDA #$01
                        STA V2_ERASE
                        STZ V2_SELF
                        JSR V2W_MUTATE
                        BCS MIG_FAIL
                        INC MIG_INDEX
                        LDA MIG_TABLE_INDEX
                        CLC
                        ADC #$09
                        STA MIG_TABLE_INDEX
                        LDA MIG_INDEX
                        CMP #$06
                        BNE MIG_NEXT
                        LDX #<MIG_DONE
                        LDY #>MIG_DONE
                        JSR MIG_PRINT
MIG_HALT:               JMP MIG_HALT
MIG_FAIL:               LDX #<MIG_BAD
                        LDY #>MIG_BAD
                        JSR MIG_PRINT
                        BRA MIG_HALT

MIG_GUARD:              STZ V2_PTR
                        LDA #$80
                        STA V2_PTR+1
                        STZ MIG_STOP
                        JSR MIG_HASH_RANGE
                        LDA MIG_TABLE_INDEX
                        INC A
                        TAX
                        JMP MIG_HASH_COMPARE
MIG_HASH_COMPARE:       LDY #$00
MIG_COMPARE_BYTE:       LDA MIG_TABLE,X
                        CMP MIG_HASH,Y
                        BNE MIG_MISMATCH
                        INX
                        INY
                        CPY #$04
                        BNE MIG_COMPARE_BYTE
                        SEC
                        RTS
MIG_MISMATCH:           CLC
                        RTS
MIG_HASH_RANGE:         LDX #$03
MIG_HASH_INIT:          LDA MIG_OFFSET,X
                        STA MIG_HASH,X
                        DEX
                        BPL MIG_HASH_INIT
MIG_HASH_BYTE:          LDA (V2_PTR)
                        JSR MIG_FNV_BYTE
                        INC V2_PTR
                        BNE MIG_HASH_BYTE
                        INC V2_PTR+1
                        LDA V2_PTR+1
                        CMP MIG_STOP
                        BNE MIG_HASH_BYTE
                        RTS
; FNV-1a update, same byte order/multiply as the qualified beta1 installer.
MIG_FNV_BYTE:           EOR MIG_HASH
                        STA MIG_HASH
                        LDX #$03
MIG_FNV_COPY:           LDA MIG_HASH,X
                        STA MIG_TERM,X
                        DEX
                        BPL MIG_FNV_COPY
                        LDX #$01
                        JSR MIG_SHIFT_ADD
                        LDX #$03
                        JSR MIG_SHIFT_ADD
                        LDX #$03
                        JSR MIG_SHIFT_ADD
                        LDX #$01
                        JSR MIG_SHIFT_ADD
                        LDA MIG_HASH+3
                        CLC
                        ADC MIG_TERM+1
                        STA MIG_HASH+3
                        RTS
MIG_SHIFT_ADD:          ASL MIG_TERM
                        ROL MIG_TERM+1
                        ROL MIG_TERM+2
                        ROL MIG_TERM+3
                        DEX
                        BNE MIG_SHIFT_ADD
                        CLC
                        LDA MIG_HASH
                        ADC MIG_TERM
                        STA MIG_HASH
                        LDA MIG_HASH+1
                        ADC MIG_TERM+1
                        STA MIG_HASH+1
                        LDA MIG_HASH+2
                        ADC MIG_TERM+2
                        STA MIG_HASH+2
                        LDA MIG_HASH+3
                        ADC MIG_TERM+3
                        STA MIG_HASH+3
                        RTS
MIG_PRINT:              STX V2_ADDR
                        STY V2_ADDR+1
                        LDY #$00
MIG_PRINT_BYTE:         LDA (V2_ADDR),Y
                        BEQ MIG_PRINT_END
                        JSR V2W_PUTC
                        INY
                        BRA MIG_PRINT_BYTE
MIG_PRINT_END:          RTS
MIG_TITLE:             DB "BETA1 -> RECOVERY; REPLACES B3:A-F. INITIAL F WRITE IS NOT POWER-LOSS SAFE.",$0D,$0A,"Y then Enter> ",0
MIG_SEND:              DB "SEND 4096 BYTES FOR B3:",0
MIG_DONE:              DB "MIGRATION VERIFIED; PRESS PHYSICAL RESET",$0D,$0A,0
MIG_BAD:               DB "MIGRATION REFUSED/FAILED; HALTED IN RAM",$0D,$0A,0
MIG_OFFSET:            DB $C5,$9D,$1C,$81
MIG_TABLE:             INCLUDE "migration-table.inc"
MIG_WORKER:            INCLUDE "migration-worker-image.inc"
MIG_END:
                        ENDMOD
                        END
