; RAM-only preserving host-controlled probe. All console outside timing.
        MODULE STORAGE_TIMING
        XDEF APP_END
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "timing-links.inc"
OP EQU $6200
SIZE EQU $6202
RESULT EQU $6210
STATUS EQU $6214
OLDACR EQU $6220
OLDT2 EQU $6221
LAST EQU $6223
NOW EQU $6225
DELTA EQU $6227
LEFT EQU $6229
PUTC EQU $7E6D
HOLD EQU $7E67
        CODE
START:  SEI
        CLD
        STZ STATUS
        LDA $7FCE
        AND #$7F
        BNE REFUSE
        LDA $7FCB
        STA OLDACR
        AND #$DF
        STA $7FCB
        LDA $7FC8
        STA OLDT2
        LDA $7FC9
        STA OLDT2+1
        LDA #2
        STA V2_SELECTED
        LDA #$D0
        STA V2_SECTOR
        LDA OP
        CMP #3
        BEQ ACCOUNT
        CMP #2
        BEQ FILL_BEGIN
        CMP #6
        BNE NOT_FILL
FILL_BEGIN:
        LDX #0
FILL:   LDA #$55
        STA $6800,X
        STA $6900,X
        STA $6A00,X
        STA $6B00,X
        STA $6C00,X
        STA $6D00,X
        STA $6E00,X
        STA $6F00,X
        STA $7000,X
        STA $7100,X
        STA $7200,X
        STA $7300,X
        STA $7400,X
        STA $7500,X
        STA $7600,X
        STA $7700,X
        INX
        BNE FILL
NOT_FILL:
        LDX #3
CLEAR:  STZ RESULT,X
        DEX
        BPL CLEAR
        LDA #$FF
        STA $7FC8
        STA $7FC9
        JSR COUNTER
        LDA NOW
        STA LAST
        LDA NOW+1
        STA LAST+1
        LDA OP
        BEQ SRAM
        CMP #5
        BEQ DONE
        CMP #6
        BEQ DONE
        CMP #4
        BEQ SRAM
        CMP #1
        BEQ ERASE
        CMP #2
        BNE REFUSE
        ; Full sector fresh programming + verification; no erase/accounting.
        STZ V2_ERASE
        STZ V2_SELF
        JSR V2W_MUTATE
        LDA V2_FLASH_ERROR
        STA STATUS
        BRA DONE
ERASE:  LDA V2_SELECTED
        JSR V2W_SELECT
        STZ V2_FLASH_PTR
        LDA #$D0
        STA V2_FLASH_PTR+1
        JSR V2W_ERASE_RAW
        LDA V2_FLASH_ERROR
        STA STATUS
        LDA V2_RESIDENT
        JSR V2W_SELECT
        BRA DONE
ACCOUNT:
        JSR V2W_ACCOUNT
        BCS UNTIMERED
        LDA #$E1
        STA STATUS
UNTIMERED:
        BRA RESTORE
SRAM:   LDA SIZE
        STA LEFT
        LDA SIZE+1
        STA LEFT+1
        STZ $6652
        LDA #$80
        STA $6653
        LDA #1
        STA $6654
        STZ $6655
        LDA #$40
        STA $6656
NEXT:   LDX #7
ZERO:   STZ $6658,X
        DEX
        BPL ZERO
        STZ $6651
        LDA #64
        LDX LEFT+1
        BNE CHUNK
        CMP LEFT
        BCC CHUNK
        LDA LEFT
CHUNK:  STA $6657
        LDA #2
        LDX OP
        BEQ WRITE
        LDA #1
WRITE:  STA $6650
        STZ $66AE
        JSR $66A6
        STA STATUS
        LDA #1
        STA $66AE
        JSR SAMPLE
        LDA STATUS
        BNE DONE
        SEC
        LDA LEFT
        SBC $6657
        STA LEFT
        LDA LEFT+1
        SBC #0
        STA LEFT+1
        ORA LEFT
        BEQ DONE
        CLC
        LDA $6652
        ADC $6657
        STA $6652
        BCC BUFFER
        INC $6653
BUFFER: CLC
        LDA $6655
        ADC $6657
        STA $6655
        BCC NEXT
        INC $6656
        BRA NEXT
DONE:   JSR SAMPLE
RESTORE:
        LDA OLDT2
        STA $7FC8
        LDA OLDT2+1
        STA $7FC9
        LDA OLDACR
        STA $7FCB
        LDA #'~'
        JSR PUTC
        JMP HOLD
REFUSE: LDA #$E0
        STA STATUS
        JMP HOLD
; Atomic high-low-high read, modulo-65536 delta sampled <65536 clocks apart.
COUNTER:
        LDA $7FC9
        STA NOW+1
        LDA $7FC8
        STA NOW
        LDA $7FC9
        CMP NOW+1
        BNE COUNTER
        RTS
SAMPLE: PHP
        PHA
        PHX
        PHY
        JSR COUNTER
        SEC
        LDA LAST
        SBC NOW
        STA DELTA
        LDA LAST+1
        SBC NOW+1
        STA DELTA+1
        CLC
        LDA RESULT
        ADC DELTA
        STA RESULT
        LDA RESULT+1
        ADC DELTA+1
        STA RESULT+1
        LDA RESULT+2
        ADC #0
        STA RESULT+2
        LDA RESULT+3
        ADC #0
        STA RESULT+3
        LDA NOW
        STA LAST
        LDA NOW+1
        STA LAST+1
        PLY
        PLX
        PLA
        PLP
        RTS
APP_END:
        ENDMOD
