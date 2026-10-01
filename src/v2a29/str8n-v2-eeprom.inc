; MCP79411 EEPROM, I2C $57. Two 12-byte records at $00/$0C.
; +0=$A1 commit/format, +1 generation, +2..7 config fields 1..6,
; +8..9 zero, +10..11 accumulated sums of +1..9 (modulo 256).
; Scratch overlaps S/R/T only during mutually exclusive command phases.
EE_BUF EQU $7DA0
EE_STATE EQU $7DB8           ; 0 unavailable, 1 empty, 2 invalid, 3 valid, 4 recovered
EE_SLOT EQU $7DB9
EE_FLAGS EQU $7DBA
EE_BASE EQU $7DBB
EE_SUM EQU $7DBC
EE_SUM2 EQU $7DBD
EE_INDEX EQU $7DBE
EE_VALUE EQU $7DBF
EE_WANT EQU $7DC0           ; desired 16-byte RAM config, survives scan
EE_GEN EQU $7DD0
EE_CFG EQU $7D80

EE_READ:
        JSR EE_SCAN
        BCC EE_READ_BAD
        LDX EE_SLOT
        JMP EE_UNPACK
EE_READ_BAD:
        STZ EE_CFG+1
        CLC
        RTS

EE_SCAN:
        STZ EE_STATE
        STZ EE_FLAGS
        JSR I2INIT
        BCS EE_LONG_31
        JMP EE_SCAN_EXIT
EE_LONG_31:
        JSR EE_FETCH
        BCS EE_LONG_33
        JMP EE_SCAN_EXIT
EE_LONG_33:
        LDX #0
        JSR EE_VALIDATE
        BCC EE_SCAN_B
        INC EE_FLAGS
EE_SCAN_B:
        LDX #12
        JSR EE_VALIDATE
        BCC EE_SELECT
        LDA EE_FLAGS
        ORA #2
        STA EE_FLAGS
EE_SELECT:
        LDA #2
        STA EE_STATE
        LDA EE_FLAGS
        BEQ EE_NONE
        LDA #3
        STA EE_STATE
        STZ EE_SLOT
        LDA EE_FLAGS
        CMP #3
        BEQ EE_BOTH
        CMP #1
        BEQ EE_ONLY_A
        LDA #12
        STA EE_SLOT
        LDX #0
        BRA EE_OTHER
EE_ONLY_A:
        LDX #12
EE_OTHER:
        JSR EE_ERASED
        BCS EE_SCAN_EXIT
        INC EE_STATE
        BRA EE_SCAN_EXIT
EE_BOTH:
        LDA EE_BUF+13
        SEC
        SBC EE_BUF+1
        BEQ EE_AMBIGUOUS
        CMP #$80
        BEQ EE_INVALID
        BCS EE_SCAN_EXIT
        LDA #12
        STA EE_SLOT
        BRA EE_SCAN_EXIT
EE_AMBIGUOUS:
; Equal generations are acceptable only for identical records.
        LDX #11
EE_EQUAL:
        LDA EE_BUF,X
        CMP EE_BUF+12,X
        BNE EE_INVALID
        DEX
        BPL EE_EQUAL
        BRA EE_SCAN_EXIT
EE_INVALID:
        LDA #2
        STA EE_STATE
        BRA EE_SCAN_EXIT
EE_NONE:
        LDX #0
        JSR EE_ERASED
        BCS EE_LONG_97
        JMP EE_SCAN_EXIT
EE_LONG_97:
        LDX #12
        JSR EE_ERASED
        BCS EE_LONG_100
        JMP EE_SCAN_EXIT
EE_LONG_100:
        DEC EE_STATE
EE_SCAN_EXIT:
        JSR I2REST
        LDA EE_STATE
        CMP #3
        RTS

EE_ERASED:
        LDY #12
EE_ERASE_LOOP:
        LDA EE_BUF,X
        CMP #$FF
        BNE EE_NO
        INX
        DEY
        BNE EE_ERASE_LOOP
        SEC
        RTS
EE_NO:  CLC
        RTS

EE_VALIDATE:
        STX EE_BASE
        LDA EE_BUF,X
        CMP #$A1
        BNE EE_NO
        LDA EE_BUF+8,X
        ORA EE_BUF+9,X
        BNE EE_NO
        JSR EE_CHECKSUM
        LDA EE_SUM
        CMP EE_BUF+10,X
        BNE EE_NO
        LDA EE_SUM2
        CMP EE_BUF+11,X
        BNE EE_NO
EE_UNPACK:
        STX EE_BASE
        LDY #15
EE_CLEAR:
        LDA #0
        STA EE_CFG,Y
        DEY
        BPL EE_CLEAR
        INC EE_CFG
        LDY #1
EE_FIELDS:
        LDA EE_BUF+2,X
        STA EE_CFG,Y
        INX
        INY
        CPY #7
        BNE EE_FIELDS
        JSR V2_CONFIG_SUM
        LDA $F6
        STA EE_CFG+14
        LDA $F7
        STA EE_CFG+15
        JMP V2_CONFIG_CHECK

EE_CHECKSUM:
        STZ EE_SUM
        STZ EE_SUM2
        LDY #9
EE_SUM_LOOP:
        LDA EE_BUF+1,X
        CLC
        ADC EE_SUM
        STA EE_SUM
        CLC
        ADC EE_SUM2
        STA EE_SUM2
        INX
        DEY
        BNE EE_SUM_LOOP
        LDX EE_BASE
        RTS

; Read all records in one random-read transaction. All paths release bus.
EE_FETCH:
        STZ BUSERR
        JSR I2START
        LDA #$AE
        JSR I2WRITE
        BCC EE_BUS_FAIL
        LDA #0
        JSR I2WRITE
        BCC EE_BUS_FAIL
        JSR I2START
        LDA #$AF
        JSR I2WRITE
        BCC EE_BUS_FAIL
        LDX #0
EE_FETCH_LOOP:
        LDY #0
        CPX #23
        BNE EE_FETCH_BYTE
        INY
EE_FETCH_BYTE:
        JSR I2READ
        STA EE_BUF,X
        INX
        CPX #24
        BNE EE_FETCH_LOOP
        JSR I2STOP
        LDA BUSERR
        BNE EE_FETCH_BAD
        SEC
        RTS
EE_BUS_FAIL:
        JSR I2STOP
EE_FETCH_BAD:
        CLC
        RTS

EE_SAVE:
        LDX #15
EE_SAVE_WANT:
        LDA EE_CFG,X
        STA EE_WANT,X
        DEX
        BPL EE_SAVE_WANT
        JSR EE_SCAN
        BCC EE_SAVE_NEW
        LDX EE_SLOT
        JSR EE_UNPACK
        LDX #6
EE_SAME:
        LDA EE_CFG,X
        CMP EE_WANT,X
        BNE EE_CHANGED
        DEX
        BNE EE_SAME
        SEC
        RTS
EE_CHANGED:
        LDX EE_SLOT
        LDA EE_BUF+1,X
        INC A
        STA EE_GEN
        LDA #12
        SEC
        SBC EE_SLOT
        BRA EE_DEST
EE_SAVE_NEW:
        LDA EE_STATE
        BNE EE_LONG_247
        JMP EE_SAVE_FAIL
EE_LONG_247:
        STZ EE_GEN
        LDA #0
EE_DEST:
        STA EE_SLOT
        JSR I2INIT
        BCS EE_LONG_253
        JMP EE_SAVE_EXIT_BAD
EE_LONG_253:
; Invalidate and verify before touching any payload byte.
        LDX EE_SLOT
        LDA #0
        JSR EE_PUT
        BCS EE_LONG_258
        JMP EE_SAVE_EXIT_BAD
EE_LONG_258:
        JSR EE_FETCH
        BCS EE_LONG_260
        JMP EE_SAVE_EXIT_BAD
EE_LONG_260:
        LDX EE_SLOT
        LDA EE_BUF,X
        BEQ EE_LONG_263
        JMP EE_SAVE_EXIT_BAD
EE_LONG_263:
        LDA EE_GEN
        STA EE_BUF+1,X
        LDY #1
EE_PACK:
        LDA EE_WANT,Y
        STA EE_BUF+2,X
        INX
        INY
        CPY #7
        BNE EE_PACK
        LDX EE_SLOT
        STZ EE_BUF+8,X
        STZ EE_BUF+9,X
        STX EE_BASE
        JSR EE_CHECKSUM
        LDA EE_SUM
        STA EE_BUF+10,X
        LDA EE_SUM2
        STA EE_BUF+11,X
        INX
EE_WRITE_LOOP:
        STX EE_INDEX
        LDA EE_BUF,X
        JSR EE_PUT
        BCS EE_LONG_288
        JMP EE_SAVE_EXIT_BAD
EE_LONG_288:
        LDX EE_INDEX
        INX
        TXA
        SEC
        SBC EE_SLOT
        CMP #12
        BNE EE_WRITE_LOOP
; Read back payload, compare all fields and generation, and check checksum.
        JSR EE_FETCH
        BCS EE_LONG_298
        JMP EE_SAVE_EXIT_BAD
EE_LONG_298:
        LDX EE_SLOT
        LDA EE_BUF+1,X
        CMP EE_GEN
        BEQ EE_LONG_302
        JMP EE_SAVE_EXIT_BAD
EE_LONG_302:
        LDA #$A1
        STA EE_BUF,X
        JSR EE_VALIDATE
        BCS EE_LONG_306
        JMP EE_SAVE_EXIT_BAD
EE_LONG_306:
        LDX #6
EE_VERIFY_FIELDS:
        LDA EE_CFG,X
        CMP EE_WANT,X
        BEQ EE_LONG_311
        JMP EE_SAVE_EXIT_BAD
EE_LONG_311:
        DEX
        BNE EE_VERIFY_FIELDS
; Commit marker is the final EEPROM write.
        LDX EE_SLOT
        LDA #$A1
        JSR EE_PUT
        BCS EE_LONG_318
        JMP EE_SAVE_EXIT_BAD
EE_LONG_318:
        JSR EE_FETCH
        BCS EE_LONG_320
        JMP EE_SAVE_EXIT_BAD
EE_LONG_320:
        LDX EE_SLOT
        JSR EE_VALIDATE
        PHP
        JSR I2REST
        PLP
        RTS
EE_SAVE_EXIT_BAD:
        JSR I2REST
EE_SAVE_FAIL:
        CLC
        RTS

; Byte writes avoid page-wrap hazards. Poll at most 256 times (>5 ms at 8 MHz).
; X=EEPROM address, A=value. Never accesses protected EEPROM or RTC registers.
EE_PUT:
        STA EE_VALUE
        STX EE_INDEX
        STZ BUSERR
        JSR I2START
        LDA #$AE
        JSR I2WRITE
        BCC EE_PUT_FAIL
        LDA EE_INDEX
        JSR I2WRITE
        BCC EE_PUT_FAIL
        LDA EE_VALUE
        JSR I2WRITE
        BCC EE_PUT_FAIL
        JSR I2STOP
        LDY #0
EE_POLL:
        JSR I2START
        LDA #$AE
        JSR I2WRITE
        PHP
        JSR I2STOP
        PLP
        BCS EE_READY
        DEY
        BNE EE_POLL
        CLC
        RTS
EE_READY:
        LDA BUSERR
        BNE EE_PUT_BAD
        SEC
        RTS

EE_PUT_FAIL:
        JSR I2STOP
EE_PUT_BAD:
        CLC
        RTS
