; STR8-N 2.0a24 RAM bank maintenance. Load with L, then G 2000.
; M maps sector occupancy. C copies a whole bank to an erased B0-B2.
; E erases one B0-B2 sector. Every write requires Y confirmation.
; The resident B3 and its E/F firmware are never write targets.
                        MODULE  V2_BANK_MAINT
                        XDEF    START
                        XDEF    BM_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "bank-maint-worker.inc"

BM_SRC                  EQU     $7D70
BM_DST                  EQU     $7D71
BM_SAVE                 EQU     $7D72
BM_SEC                  EQU     $7D73
BM_PTR                  EQU     $C0

                        CODE
START:                  SEI
                        CLD
                        LDA     V2_RESIDENT
                        CMP     #$03
                        BNE     BM_EXIT
BM_MENU:                LDX     #<BM_TITLE
                        LDY     #>BM_TITLE
                        JSR     BM_PRINT
                        JSR     $F010
                        AND     #$DF
                        CMP     #'M'
                        BEQ     BM_MAP
                        CMP     #'C'
                        BEQ     BM_COPY
                        CMP     #'E'
                        BNE     BM_NOT_ERASE
                        JMP     BM_ERASE
BM_NOT_ERASE:
                        CMP     #'Q'
                        BEQ     BM_EXIT
                        BRA     BM_MENU
BM_EXIT:                JMP     $F007

; Map B0-B3, sectors 8-F. E means all FF; U means at least one used byte.
BM_MAP:                 STZ     BM_SRC
BM_MAP_BANK:            LDA     BM_SRC
                        CLC
                        ADC     #'0'
                        JSR     $F00D
                        LDA     #':'
                        JSR     $F00D
                        LDA     #$80
                        STA     BM_SEC
BM_MAP_SECTOR:          JSR     BM_SELECT_SOURCE
                        JSR     BM_SCAN_ERASED
                        PHP
                        LDA     V2_RESIDENT
                        JSR     V2W_SELECT
                        PLP
                        BCC     BM_MAP_USED
                        LDA     #'E'
                        BRA     BM_MAP_OUT
BM_MAP_USED:            LDA     #'U'
BM_MAP_OUT:             JSR     $F00D
                        LDA     BM_SEC
                        CLC
                        ADC     #$10
                        STA     BM_SEC
                        BNE     BM_MAP_SECTOR
                        JSR     BM_NEWLINE
                        INC     BM_SRC
                        LDA     BM_SRC
                        CMP     #$04
                        BNE     BM_MAP_BANK
                        JMP     BM_MENU

; C then source digit and destination digit. Whole destination is checked
; erased before confirmation, and again sector by sector before writing.
BM_COPY:                LDX     #<BM_COPY_Q
                        LDY     #>BM_COPY_Q
                        JSR     BM_PRINT
                        JSR     BM_READ_BANK
                        BCS     BM_COPY_SRC_OK
                        JMP     BM_BAD
BM_COPY_SRC_OK:
                        STA     BM_SRC
                        JSR     BM_READ_BANK
                        BCS     BM_COPY_DST_OK
                        JMP     BM_BAD
BM_COPY_DST_OK:
                        CMP     #$03
                        BCC     BM_COPY_DST_RANGE
                        JMP     BM_BAD
BM_COPY_DST_RANGE:
                        CMP     BM_SRC
                        BNE     BM_COPY_DISTINCT
                        JMP     BM_BAD
BM_COPY_DISTINCT:
                        STA     BM_DST
                        LDA     #$80
                        STA     BM_SEC
BM_COPY_CHECK:          LDA     BM_DST
                        STA     V2_SELECTED
                        LDA     BM_SEC
                        STA     V2_SECTOR
                        JSR     V2W_SNAPSHOT
                        JSR     BM_BUFFER_ERASED
                        BCS     BM_COPY_FREE
                        JMP     BM_OCCUPIED
BM_COPY_FREE:
                        JSR     BM_NEXT_SECTOR
                        BCC     BM_COPY_CHECK
                        JSR     BM_CONFIRM
                        BCS     BM_COPY_GO
                        JMP     BM_MENU
BM_COPY_GO:
                        LDA     #$80
                        STA     BM_SEC
BM_COPY_LOOP:           JSR     BM_SELECT_SOURCE
                        JSR     V2W_SNAPSHOT
                        LDA     BM_DST
                        STA     V2_SELECTED
                        LDA     BM_SEC
                        STA     V2_SECTOR
                        STZ     V2_SELF
                        STZ     V2_ERASE
                        JSR     V2W_MUTATE
                        BCS     BM_FAIL
                        JSR     BM_NEXT_SECTOR
                        BCC     BM_COPY_LOOP
                        BRA     BM_DONE

; E then bank 0-2 and sector 8-F. Never erases Bank 3.
BM_ERASE:               LDX     #<BM_ERASE_Q
                        LDY     #>BM_ERASE_Q
                        JSR     BM_PRINT
                        JSR     BM_READ_BANK
                        BCC     BM_BAD
                        CMP     #$03
                        BCS     BM_BAD
                        STA     BM_DST
                        JSR     $F010
                        CMP     #'8'
                        BCC     BM_BAD
                        CMP     #'9'+1
                        BCC     BM_DEC_SECTOR
                        CMP     #'A'
                        BCC     BM_BAD
                        CMP     #'F'+1
                        BCS     BM_BAD
                        SEC
                        SBC     #'A'-10
                        BRA     BM_SET_SECTOR
BM_DEC_SECTOR:          SEC
                        SBC     #'0'
BM_SET_SECTOR:          ASL     A
                        ASL     A
                        ASL     A
                        ASL     A
                        STA     BM_SEC
                        JSR     BM_CONFIRM
                        BCS     BM_ERASE_GO
                        JMP     BM_MENU
BM_ERASE_GO:
                        LDA     BM_DST
                        STA     V2_SELECTED
                        LDA     BM_SEC
                        STA     V2_SECTOR
                        LDX     #$10
                        LDY     #$00
                        STZ     BM_PTR
                        LDA     #$69
                        STA     BM_PTR+1
BM_FILL:                LDA     #$FF
                        STA     (BM_PTR),Y
                        INY
                        BNE     BM_FILL
                        INC     BM_PTR+1
                        DEX
                        BNE     BM_FILL
                        LDA     #$01
                        STA     V2_ERASE
                        STZ     V2_SELF
                        JSR     V2W_MUTATE
                        BCS     BM_FAIL
BM_DONE:                LDX     #<BM_OK
                        LDY     #>BM_OK
                        JSR     BM_PRINT
                        JMP     BM_MENU
BM_FAIL:                LDX     #<BM_FAILED
                        LDY     #>BM_FAILED
                        JSR     BM_PRINT
                        JMP     BM_MENU
BM_BAD:                 LDX     #<BM_INVALID
                        LDY     #>BM_INVALID
                        JSR     BM_PRINT
                        JMP     BM_MENU
BM_OCCUPIED:            LDX     #<BM_USED
                        LDY     #>BM_USED
                        JSR     BM_PRINT
                        JMP     BM_MENU

BM_SELECT_SOURCE:       LDA     BM_SRC
                        STA     V2_SELECTED
                        LDA     BM_SEC
                        STA     V2_SECTOR
                        RTS
BM_NEXT_SECTOR:         LDA     BM_SEC
                        CLC
                        ADC     #$10
                        STA     BM_SEC
                        RTS
BM_READ_BANK:           JSR     $F010
                        SEC
                        SBC     #'0'
                        CMP     #$04
                        BCS     BM_READ_BAD
                        SEC
                        RTS
BM_READ_BAD:            CLC
                        RTS
BM_CONFIRM:             LDX     #<BM_CONFIRM_Q
                        LDY     #>BM_CONFIRM_Q
                        JSR     BM_PRINT
                        JSR     $F010
                        AND     #$DF
                        CMP     #'Y'
                        BEQ     BM_YES
                        CLC
                        RTS
BM_YES:                 SEC
                        RTS
BM_SCAN_ERASED:         JSR     V2W_SNAPSHOT
BM_BUFFER_ERASED:       STZ     BM_PTR
                        LDA     #$69
                        STA     BM_PTR+1
                        LDX     #$10
                        LDY     #$00
BM_SCAN_BYTE:           LDA     (BM_PTR),Y
                        CMP     #$FF
                        BNE     BM_SCAN_USED
                        INY
                        BNE     BM_SCAN_BYTE
                        INC     BM_PTR+1
                        DEX
                        BNE     BM_SCAN_BYTE
                        SEC
                        RTS
BM_SCAN_USED:           CLC
                        RTS
BM_PRINT:               STX     BM_PTR
                        STY     BM_PTR+1
                        LDY     #$00
BM_PRINT_BYTE:          LDA     (BM_PTR),Y
                        BEQ     BM_PRINT_END
                        JSR     $F00D
                        INY
                        BNE     BM_PRINT_BYTE
BM_PRINT_END:           RTS
BM_NEWLINE:             LDA     #$0D
                        JSR     $F00D
                        LDA     #$0A
                        JMP     $F00D
BM_TITLE:               DB      $0D,$0A,"V2 BANK MAINT: M map, C copy, E erase, Q quit> ",0
BM_COPY_Q:              DB      $0D,$0A,"COPY source 0-3 then dest 0-2: ",0
BM_ERASE_Q:             DB      $0D,$0A,"ERASE bank 0-2 then sector 8-F: ",0
BM_CONFIRM_Q:           DB      $0D,$0A,"WRITE FLASH? Y: ",0
BM_OK:                  DB      $0D,$0A,"VERIFIED",$0D,$0A,0
BM_FAILED:              DB      $0D,$0A,"FLASH FAILED",$0D,$0A,0
BM_INVALID:             DB      $0D,$0A,"INVALID",$0D,$0A,0
BM_USED:                DB      $0D,$0A,"DESTINATION NOT ERASED",$0D,$0A,0
BM_END:
                        ENDMOD
                        END
