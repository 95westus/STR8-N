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
START:                  SEC
                        DB $FB
                        SEI
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
                        JSR MIG_IDENTIFY
                        BCS STORE_MIG_LONG_32
                        JMP RTC_MIG_LONG_32
STORE_MIG_LONG_32:
                        JMP BASE_LONG_32
RTC_MIG_LONG_32:
                        JMP MIG_FAIL
BASE_LONG_32:
                        STZ MIG_INDEX
                        STZ MIG_TABLE_INDEX
                        LDX #<MIG_TITLE
                        LDY #>MIG_TITLE
                        JSR MIG_PRINT
                        JSR V2W_GETC
                        CMP #'Y'
                        BEQ STORE_MIG_LONG_44
                        JMP RTC_MIG_LONG_42
STORE_MIG_LONG_44:
                        JMP BASE_LONG_40
RTC_MIG_LONG_42:
                        JMP MIG_FAIL
BASE_LONG_40:
                        JSR V2W_GETC
                        CMP #$0D
                        BEQ STORE_MIG_LONG_51
                        JMP RTC_MIG_LONG_47
STORE_MIG_LONG_51:
                        JMP BASE_LONG_43
RTC_MIG_LONG_47:
                        JMP MIG_FAIL
BASE_LONG_43:
MIG_NEXT:
                        LDX MIG_INDEX
                        LDA MIG_BANKS,X
                        STA V2_SELECTED
                        JSR V2W_SELECT
                        JSR MIG_GUARD
                        BCS STORE_MIG_LONG_62
                        JMP RTC_MIG_LONG_56
STORE_MIG_LONG_62:
                        JMP BASE_LONG_45
RTC_MIG_LONG_56:
                        JMP MIG_FAIL
BASE_LONG_45:
                        LDX MIG_TABLE_INDEX
                        LDA MIG_TABLE,X
                        STA V2_SECTOR
                        LDX #<MIG_SEND
                        LDY #>MIG_SEND
                        JSR MIG_PRINT
                        LDA V2_SELECTED
                        CLC
                        ADC #'0'
                        JSR V2W_PUTC
                        LDA #':'
                        JSR V2W_PUTC
                        LDA V2_SECTOR
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        CLC
                        ADC #'0'
                        CMP #'9'+1
                        BCS STORE_MIG_LONG_87
                        JMP RTC_MIG_LONG_79
STORE_MIG_LONG_87:
                        JMP BASE_LONG_60
RTC_MIG_LONG_79:
                        JMP MIG_DIGIT
BASE_LONG_60:
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
                        BCS STORE_MIG_LONG_102
                        JMP RTC_MIG_LONG_92
STORE_MIG_LONG_102:
                        JMP BASE_LONG_71
RTC_MIG_LONG_92:
                        JMP MIG_RECEIVE
BASE_LONG_71:
                        STA (V2_BUF_PTR)
                        INC V2_BUF_PTR
                        BEQ STORE_MIG_LONG_109
                        JMP RTC_MIG_LONG_97
STORE_MIG_LONG_109:
                        JMP BASE_LONG_74
RTC_MIG_LONG_97:
                        JMP MIG_RECEIVE
BASE_LONG_74:
                        INC V2_BUF_PTR+1
                        LDA V2_BUF_PTR+1
                        CMP #$78
                        BEQ STORE_MIG_LONG_117
                        JMP RTC_MIG_LONG_103
STORE_MIG_LONG_117:
                        JMP BASE_LONG_78
RTC_MIG_LONG_103:
                        JMP MIG_RECEIVE
BASE_LONG_78:
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
                        BCS STORE_MIG_LONG_133
                        JMP RTC_MIG_LONG_117
STORE_MIG_LONG_133:
                        JMP BASE_LONG_90
RTC_MIG_LONG_117:
                        JMP MIG_FAIL
BASE_LONG_90:
                        JSR MIG_GUARD
                        BCS STORE_MIG_LONG_139
                        JMP RTC_MIG_LONG_121
STORE_MIG_LONG_139:
                        JMP BASE_LONG_92
RTC_MIG_LONG_121:
                        JMP MIG_FAIL
BASE_LONG_92:
                        LDA #$01
                        STA V2_ERASE
                        STZ V2_SELF
                        JSR V2W_MUTATE
                        BCC STORE_MIG_LONG_148
                        JMP RTC_MIG_LONG_128
STORE_MIG_LONG_148:
                        JMP BASE_LONG_97
RTC_MIG_LONG_128:
                        JMP MIG_FAIL
BASE_LONG_97:
                        INC MIG_INDEX
                        LDX MIG_INDEX
                        LDA MIG_COMMITS-1,X
                        BEQ STORE_MIG_LONG_156
                        JMP RTC_MIG_LONG_134
STORE_MIG_LONG_156:
                        JMP MIG_STORAGE_READY
RTC_MIG_LONG_134:
                        DEC A
                        STA V2_SELECTED
                        JSR V2W_SELECT
                        LDA MIG_INDEX
                        DEC A
                        ASL A
                        ASL A
                        STA $6230
                        TAX
                        JSR MIG_RECORD_COMMIT
                        BCS STORE_MIG_LONG_169
                        JMP MIG_FAIL
STORE_MIG_LONG_169:
                        LDA $6230
                        CLC
                        ADC #2
                        TAX
                        JSR MIG_RECORD_COMMIT
                        BCS STORE_MIG_LONG_175
                        JMP MIG_FAIL
STORE_MIG_LONG_175:
MIG_STORAGE_READY:
                        LDA MIG_TABLE_INDEX
                        CLC
                        ADC #$09
                        STA MIG_TABLE_INDEX
                        LDA MIG_INDEX
                        CMP MIG_PLAN_COUNT
                        BEQ STORE_MIG_LONG_183
                        JMP RTC_MIG_LONG_155
STORE_MIG_LONG_183:
                        JMP BASE_LONG_118
RTC_MIG_LONG_155:
                        JMP MIG_NEXT
BASE_LONG_118:
                        LDX #<MIG_DONE
                        LDY #>MIG_DONE
                        JSR MIG_PRINT
MIG_HALT:               JMP MIG_HALT
MIG_FAIL:               LDX #<MIG_BAD
                        LDY #>MIG_BAD
                        JSR MIG_PRINT
                        JMP MIG_HALT

MIG_GUARD:
                        LDA V2_SELECTED
                        JSR V2W_SELECT
                        STZ V2_PTR
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
                        BEQ STORE_MIG_LONG_212
                        JMP RTC_MIG_LONG_182
STORE_MIG_LONG_212:
                        JMP BASE_LONG_140
RTC_MIG_LONG_182:
                        JMP MIG_MISMATCH
BASE_LONG_140:
                        INX
                        INY
                        CPY #$04
                        BEQ STORE_MIG_LONG_220
                        JMP RTC_MIG_LONG_188
STORE_MIG_LONG_220:
                        JMP BASE_LONG_144
RTC_MIG_LONG_188:
                        JMP MIG_COMPARE_BYTE
BASE_LONG_144:
                        SEC
                        RTS
MIG_MISMATCH:           CLC
                        RTS
MIG_HASH_RANGE:         LDX #$03
MIG_HASH_INIT:          LDA MIG_OFFSET,X
                        STA MIG_HASH,X
                        DEX
                        BMI STORE_MIG_LONG_233
                        JMP RTC_MIG_LONG_199
STORE_MIG_LONG_233:
                        JMP BASE_LONG_153
RTC_MIG_LONG_199:
                        JMP MIG_HASH_INIT
BASE_LONG_153:
MIG_HASH_BYTE:          LDA (V2_PTR)
                        JSR MIG_FNV_BYTE
                        INC V2_PTR
                        BEQ STORE_MIG_LONG_241
                        JMP RTC_MIG_LONG_205
STORE_MIG_LONG_241:
                        JMP BASE_LONG_157
RTC_MIG_LONG_205:
                        JMP MIG_HASH_BYTE
BASE_LONG_157:
                        INC V2_PTR+1
                        LDA V2_PTR+1
                        CMP MIG_STOP
                        BEQ STORE_MIG_LONG_249
                        JMP RTC_MIG_LONG_211
STORE_MIG_LONG_249:
                        JMP BASE_LONG_161
RTC_MIG_LONG_211:
                        JMP MIG_HASH_BYTE
BASE_LONG_161:
                        RTS
; FNV-1a update, same byte order/multiply as the qualified beta1 installer.
MIG_FNV_BYTE:           EOR MIG_HASH
                        STA MIG_HASH
                        LDX #$03
MIG_FNV_COPY:           LDA MIG_HASH,X
                        STA MIG_TERM,X
                        DEX
                        BMI STORE_MIG_LONG_262
                        JMP RTC_MIG_LONG_222
STORE_MIG_LONG_262:
                        JMP BASE_LONG_170
RTC_MIG_LONG_222:
                        JMP MIG_FNV_COPY
BASE_LONG_170:
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
                        BEQ STORE_MIG_LONG_285
                        JMP RTC_MIG_LONG_243
STORE_MIG_LONG_285:
                        JMP BASE_LONG_189
RTC_MIG_LONG_243:
                        JMP MIG_SHIFT_ADD
BASE_LONG_189:
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
                        BNE STORE_MIG_LONG_308
                        JMP RTC_MIG_LONG_264
STORE_MIG_LONG_308:
                        JMP BASE_LONG_208
RTC_MIG_LONG_264:
                        JMP MIG_PRINT_END
BASE_LONG_208:
                        JSR V2W_PUTC
                        INY
                        JMP MIG_PRINT_BYTE
MIG_PRINT_END:          RTS
MIG_TITLE:             DB "STR8-N 2.0b27 RTC/I2C MIGRATOR; MAINT B1, SYSTEM B3. KEEP POWER STABLE UNTIL VERIFIED.",$0D,$0A,"Y then Enter> ",0
MIG_SEND:              DB "SEND 4096 BYTES FOR B",0
MIG_DONE:              DB "MIGRATION VERIFIED; PRESS PHYSICAL RESET",$0D,$0A,0
MIG_BAD:               DB "MIGRATION REFUSED/FAILED; HALTED IN RAM",$0D,$0A,0
MIG_OFFSET:            DB $C5,$9D,$1C,$81
; Host patches the verified plan and count before loading this RAM image.
MIG_PLAN_COUNT:        DB $00
MIG_COMMIT_AFTER:      DB $00
MIG_RECORD_COMMIT:
                        LDA MIG_COMMIT_ADDRS+1,X
                        BNE STORE_MIG_LONG_327
                        JMP MIG_COMMIT_SKIP
STORE_MIG_LONG_327:
                        STA V2_FLASH_PTR+1
                        LDA MIG_COMMIT_ADDRS,X
                        STA V2_FLASH_PTR
                        LDA #$3F
                        LDY V2_FLASH_PTR
                        CPY #$1F
                        BNE MIG_COMMIT_VALUE_READY
                        LDA #$00
MIG_COMMIT_VALUE_READY:  STA V2_FLASH_DATA
                        JMP V2W_BYTE
MIG_COMMIT_SKIP:        SEC
                        RTS
MIG_COMMIT_ADDRS:       DS 64
MIG_IDENTIFY:          LDA #$AA
                        STA $D555
                        LDA #$55
                        STA $AAAA
                        LDA #$90
                        STA $D555
                        LDA $8000
                        STA $620D
                        LDA $8001
                        STA $620E
                        LDA #$F0
                        STA $8000
                        LDA $620D
                        CMP #$BF
                        BEQ STORE_MIG_LONG_351
                        JMP RTC_MIG_LONG_293
STORE_MIG_LONG_351:
                        JMP BASE_LONG_235
RTC_MIG_LONG_293:
                        JMP MIG_ID_BAD
BASE_LONG_235:
                        LDA $620E
                        CMP #$B5
                        BEQ STORE_MIG_LONG_358
                        JMP RTC_MIG_LONG_298
STORE_MIG_LONG_358:
                        JMP BASE_LONG_238
RTC_MIG_LONG_298:
                        JMP MIG_ID_BAD
BASE_LONG_238:
                        LDA MIG_PLAN_COUNT
                        BNE STORE_MIG_LONG_364
                        JMP RTC_MIG_LONG_302
STORE_MIG_LONG_364:
                        JMP BASE_LONG_240
RTC_MIG_LONG_302:
                        JMP MIG_ID_BAD
BASE_LONG_240:
                        CMP #$11
                        BCC STORE_MIG_LONG_370
                        JMP RTC_MIG_LONG_306
STORE_MIG_LONG_370:
                        JMP BASE_LONG_242
RTC_MIG_LONG_306:
                        JMP MIG_ID_BAD
BASE_LONG_242:
                        SEC
                        RTS
MIG_ID_BAD:            CLC
                        RTS
MIG_COMMITS:           DS 16
MIG_BANKS:             DS 16
MIG_TABLE:             INCLUDE "migration-table.inc"
MIG_WORKER:            INCLUDE "migration-worker-image.inc"
MIG_END:
                        ENDMOD
                        END
