; BASE1 read-only WDC resident identification. No vendor code is included.
; Caller has selected MA_MB. Only F800-FFFF plus the reset vector are read.
; W+ means a known resident fingerprint, never a complete bank/boot guarantee.
MAP_RECOGNIZE:
        STZ MAP_PROFILE
        STZ MAP_CPU
        LDA #'.'
        STA MAP_MARK
        LDA MA_STATUS
        CMP #'E'
        BEQ MAP_LONG_1
        JMP MAP_PROGRAMMED
MAP_LONG_1:
        LDA #'.'
        STA MA_STATUS
        RTS
MAP_PROGRAMMED:
        LDA #'+'
        STA MAP_MARK
        LDA MA_MS
        CMP #$F0
        BEQ MAP_LONG_2
        JMP MAP_RETURN
MAP_LONG_2:
        LDA MA_MB
        CMP #3
        BEQ MAP_LONG_3
        JMP MAP_WDC_PROBE
MAP_LONG_3:
        ; The current B3 F already passed the tool's exact F/ABI guards.
        LDA #'F'
        STA MA_STATUS
        RTS
MAP_WDC_PROBE:
        LDA $FFFC
        STA MAP_RESET
        LDA $FFFD
        STA MAP_RESET+1
        CMP #$F8
        BCS MAP_LONG_4
        JMP MAP_RETURN
MAP_LONG_4:
        CMP #$FF
        BEQ MAP_LONG_5
        JMP MAP_VECTOR_OK
MAP_LONG_5:
        LDA MAP_RESET
        CMP #$E0
        BCC MAP_LONG_6
        JMP MAP_RETURN
MAP_LONG_6:
MAP_VECTOR_OK:
        LDA $F80C
        CMP #'S'
        BEQ MAP_LONG_7
        JMP MAP_RETURN
MAP_LONG_7:
        LDA $F80D
        CMP #'X'
        BEQ MAP_LONG_8
        JMP MAP_RETURN
MAP_LONG_8:
        LDA $F80E
        CMP #'B'
        BEQ MAP_LONG_9
        JMP MAP_RETURN
MAP_LONG_9:
        LDA $F80F
        CMP #'2'
        BNE MAP_LONG_10
        JMP MAP_CPU_02
MAP_LONG_10:
        CMP #'6'
        BEQ MAP_LONG_11
        JMP MAP_RETURN
MAP_LONG_11:
        LDA #$16
        JMP MAP_CPU_SET
MAP_CPU_02:
        LDA #2
MAP_CPU_SET:
        STA MAP_CPU
        LDA #'W'
        STA MA_STATUS
        LDA #'?'
        STA MAP_MARK
        STZ MA_PTR
        LDA #$F8
        STA MA_PTR+1
        STZ MA_COUNT
        LDA #8
        STA MA_COUNT+1
        JSR MA_CRC_AT_PTR
        JSR MAP_FNV_RESIDENT
        LDX #0
        LDA MAP_CPU
        CMP #2
        BNE MAP_LONG_12
        JMP MAP_COMPARE_PROFILE
MAP_LONG_12:
        LDX #11
MAP_COMPARE_PROFILE:
        STX MAP_CATALOG_INDEX
        LDA MAP_RESET
        CMP MAP_WDC_CATALOG+1,X
        BEQ MAP_LONG_13
        JMP MAP_RETURN
MAP_LONG_13:
        LDA MAP_RESET+1
        CMP MAP_WDC_CATALOG+2,X
        BEQ MAP_LONG_14
        JMP MAP_RETURN
MAP_LONG_14:
        LDA MA_CRC
        CMP MAP_WDC_CATALOG+3,X
        BEQ MAP_LONG_15
        JMP MAP_RETURN
MAP_LONG_15:
        LDA MA_CRC+1
        CMP MAP_WDC_CATALOG+4,X
        BEQ MAP_LONG_16
        JMP MAP_RETURN
MAP_LONG_16:
        LDY #0
MAP_MATCH_FNV:
        LDA MAP_HASH,Y
        CMP MAP_WDC_CATALOG+5,X
        BEQ MAP_LONG_17
        JMP MAP_RETURN
MAP_LONG_17:
        INX
        INY
        CPY #4
        BEQ MAP_LONG_18
        JMP MAP_MATCH_FNV
MAP_LONG_18:
        LDX MAP_CATALOG_INDEX
        LDA MAP_WDC_CATALOG+9,X
        STA MAP_NAME
        LDA MAP_WDC_CATALOG+10,X
        STA MAP_NAME+1
        LDA #1
        STA MAP_PROFILE
        LDA #'+'
        STA MAP_MARK
MAP_RETURN:
        RTS

; A numeric nibble must be encoded for output, not sent to HEX_NIBBLE,
; which is the public ASCII-to-value parser.
MAP_PRINT_NIBBLE:
        CMP #10
        BCC MAP_PRINT_DIGIT
        CLC
        ADC #7
MAP_PRINT_DIGIT:
        CLC
        ADC #'0'
        JMP STR8V2_RAM_PUTC

MAP_PRINT_CELL:
        LDA MA_STATUS
        JSR STR8V2_RAM_PUTC
        LDA MAP_MARK
        JMP STR8V2_RAM_PUTC

MAP_DETAIL:
        LDA MA_STATUS
        CMP #'W'
        BEQ MAP_LONG_19
        JMP MAP_DETAIL_DONE
MAP_LONG_19:
        LDX #<MAP_DETAIL_PREFIX
        LDY #>MAP_DETAIL_PREFIX
        JSR MA_PRINT
        LDA MAP_PROFILE
        BNE MAP_LONG_20
        JMP MAP_DETAIL_POSSIBLE
MAP_LONG_20:
        LDX MAP_NAME
        LDY MAP_NAME+1
        JSR MA_PRINT
        LDX #<MAP_MATCHED_TEXT
        LDY #>MAP_MATCHED_TEXT
        JSR MA_PRINT
        JMP MAP_DETAIL_ENTRY
MAP_DETAIL_POSSIBLE:
        LDX #<MAP_POSSIBLE_TEXT
        LDY #>MAP_POSSIBLE_TEXT
        JSR MA_PRINT
        LDX #<MAP_CPU_816_TEXT
        LDY #>MAP_CPU_816_TEXT
        LDA MAP_CPU
        CMP #2
        BEQ MAP_LONG_21
        JMP MAP_DETAIL_CPU
MAP_LONG_21:
        LDX #<MAP_CPU_02_TEXT
        LDY #>MAP_CPU_02_TEXT
MAP_DETAIL_CPU:
        JSR MA_PRINT
        LDX #<MAP_UNCONFIRMED_TEXT
        LDY #>MAP_UNCONFIRMED_TEXT
        JSR MA_PRINT
MAP_DETAIL_ENTRY:
        LDX #<MAP_ENTRY_TEXT
        LDY #>MAP_ENTRY_TEXT
        JSR MA_PRINT
        LDA MAP_RESET+1
        JSR STR8V2_RAM_HEX_OUT
        LDA MAP_RESET
        JSR STR8V2_RAM_HEX_OUT
        LDX #<MAP_SCOPE_TEXT
        LDY #>MAP_SCOPE_TEXT
        JSR MA_PRINT
MAP_DETAIL_DONE:
        RTS

; FNV-1a32 multiply by 01000193; project-authored RAM algorithm.
MAP_FNV_RESIDENT:
        LDX #3
MAP_HASH_INIT:
        LDA MAP_FNV_OFFSET,X
        STA MAP_HASH,X
        DEX
        BMI MAP_LONG_22
        JMP MAP_HASH_INIT
MAP_LONG_22:
        STZ MA_PTR
        LDA #$F8
        STA MA_PTR+1
MAP_HASH_NEXT:
        LDA (MA_PTR)
        JSR MAP_FNV_BYTE
        INC MA_PTR
        BEQ MAP_LONG_23
        JMP MAP_HASH_NEXT
MAP_LONG_23:
        INC MA_PTR+1
        BEQ MAP_LONG_24
        JMP MAP_HASH_NEXT
MAP_LONG_24:
        RTS
MAP_FNV_BYTE:
        EOR MAP_HASH
        STA MAP_HASH
        LDX #3
MAP_FNV_COPY:
        LDA MAP_HASH,X
        STA MAP_TERM,X
        DEX
        BMI MAP_LONG_25
        JMP MAP_FNV_COPY
MAP_LONG_25:
        LDX #1
        JSR MAP_FNV_SHIFT_ADD
        LDX #3
        JSR MAP_FNV_SHIFT_ADD
        LDX #3
        JSR MAP_FNV_SHIFT_ADD
        LDX #1
        JSR MAP_FNV_SHIFT_ADD
        LDA MAP_HASH+3
        CLC
        ADC MAP_TERM+1
        STA MAP_HASH+3
        RTS
MAP_FNV_SHIFT_ADD:
        ASL MAP_TERM
        ROL MAP_TERM+1
        ROL MAP_TERM+2
        ROL MAP_TERM+3
        DEX
        BEQ MAP_LONG_26
        JMP MAP_FNV_SHIFT_ADD
MAP_LONG_26:
        CLC
        LDA MAP_HASH
        ADC MAP_TERM
        STA MAP_HASH
        LDA MAP_HASH+1
        ADC MAP_TERM+1
        STA MAP_HASH+1
        LDA MAP_HASH+2
        ADC MAP_TERM+2
        STA MAP_HASH+2
        LDA MAP_HASH+3
        ADC MAP_TERM+3
        STA MAP_HASH+3
        RTS
MAP_FNV_OFFSET: DB $C5,$9D,$1C,$81
MAP_DETAIL_PREFIX: DB " | ",0
MAP_MATCHED_TEXT: DB "; resident CRC16+FNV32 matched",0
MAP_POSSIBLE_TEXT: DB "possible WDCMON / ",0
MAP_CPU_02_TEXT: DB "65C02",0
MAP_CPU_816_TEXT: DB "65C816",0
MAP_UNCONFIRMED_TEXT: DB "; version unknown; signature/vector only",0
MAP_ENTRY_TEXT: DB "; entry ",0
MAP_SCOPE_TEXT: DB "; resident F800-FFFF; gen --; rest of bank unclassified",0
        INCLUDE "map-wdc-catalog.inc"
