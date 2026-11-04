; Dense S0/S1/S9 stream for complete B0/B1 sectors8000-DFFF.
; Parser validates each whole record before staging; only full sectors commit.
; Runtime-owned6100-63FF state/record;6700 journal;6800-77FF desired sector.
FI_NEXT EQU $6100
FI_END_PAGE EQU $6102
FI_INDEX EQU $6103
FI_COMPLETE EQU $6104
FI_STAGE EQU $E2
SL_ADDR EQU $61C0
SL_COUNT EQU $61C2
SL_TYPE EQU $61C3
SL_SUM EQU $61C4
SL_NIB EQU $61C5
SL_ERROR EQU $61C6
SL_RX_BAD EQU $F1
SL_RECORD EQU $6200
FI_COMMAND:
        LDA BQ_MAGIC
        CMP #BQ_ON
        BEQ FT_BAD
        LDA FT_BANK
        CMP #2
        BCS FT_BAD
        JSR FT_ADDRESS
        BCC FT_BAD
        LDA FT_ADDRESS_VALUE
        BNE FT_BAD
        STA FI_NEXT
        LDA FT_ADDRESS_VALUE+1
        AND #$0F
        BNE FT_BAD
        LDA FT_ADDRESS_VALUE+1
        STA FI_NEXT+1
        JSR BOOT_API_HEX_WORD
        BCC FT_BAD
        LDA V2_VALUE
        CMP #$FF
        BNE FT_BAD
        LDA V2_VALUE+1
        CMP #$E0
        BCS FT_BAD
        CMP FI_NEXT+1
        BCC FT_BAD
        STA FI_END_PAGE
        AND #$0F
        CMP #$0F
        BNE FT_BAD
        JSR FT_END
        BCC FT_BAD
        LDX #<FI_CONFIRM_TEXT
        LDY #>FI_CONFIRM_TEXT
        JSR CONFIG_PRINT
        LDA FT_BANK
        ORA #'0'
        JSR V2W_PUTC
        LDA #':'
        JSR V2W_PUTC
        LDA FI_NEXT+1
        JSR STR8V2_RAM_HEX_OUT
        LDA #0
        JSR STR8V2_RAM_HEX_OUT
        LDA #'-'
        JSR V2W_PUTC
        LDA FI_END_PAGE
        JSR STR8V2_RAM_HEX_OUT
        LDA #$FF
        JSR STR8V2_RAM_HEX_OUT
        JSR FT_CONFIRM
        BCC FT_CANCEL
        STZ FT_VALID
        STZ FI_COMPLETE
        STZ FI_STAGE
        LDA #$68
        STA FI_STAGE+1
        LDX #<FI_READY_TEXT
        LDY #>FI_READY_TEXT
        JSR CONFIG_PRINT
FI_RECORD:
        JSR SL_RECORD_READ
        BCC FI_FAILED
        LDA SL_TYPE
        BEQ FI_RECORD
        CMP #9
        BNE FI_DATA
        LDA FI_COMPLETE
        BEQ FI_FORMAT
        JSR SL_DRAIN
        JMP FT_OK
FI_DATA:
        LDA FI_COMPLETE
        BNE FI_FORMAT
        LDA SL_ADDR
        CMP FI_NEXT
        BNE FI_FORMAT
        LDA SL_ADDR+1
        CMP FI_NEXT+1
        BNE FI_FORMAT
        LDA SL_COUNT
        DEC A
        CLC
        ADC SL_ADDR
        LDA SL_ADDR+1
        ADC #0
        BCS FI_FORMAT
        CMP FI_END_PAGE
        BCC FI_COPY_BEGIN
        BNE FI_FORMAT
FI_COPY_BEGIN:
        STZ FI_INDEX
FI_COPY:
        LDX FI_INDEX
        LDA SL_RECORD,X
        STA (FI_STAGE)
        INC FI_NEXT
        BNE FI_NEXT_STAGE
        INC FI_NEXT+1
FI_NEXT_STAGE:
        INC FI_STAGE
        BNE FI_NEXT_BYTE
        INC FI_STAGE+1
        LDA FI_STAGE+1
        CMP #$78
        BNE FI_NEXT_BYTE
        JSR FI_COMMIT
        BCC FI_FAILED
        STZ FI_STAGE
        LDA #$68
        STA FI_STAGE+1
        LDA FI_NEXT+1
        DEC A
        CMP FI_END_PAGE
        BNE FI_NEXT_BYTE
        INC FI_COMPLETE
FI_NEXT_BYTE:
        INC FI_INDEX
        LDA FI_INDEX
        CMP SL_COUNT
        BCC FI_COPY
        BRA FI_RECORD
FI_FORMAT:
        LDA #1
FI_FAILED:
        STA SL_ERROR
        JSR SL_DRAIN
        LDX #<FI_ERROR_TEXT
        LDY #>FI_ERROR_TEXT
        JSR CONFIG_PRINT
        LDA SL_ERROR
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        JMP FT_MENU
FI_COMMIT:
        ; The final byte of this sector is NEXT-1, including a crossing record.
        LDA FI_NEXT+1
        DEC A
        AND #$F0
        STA V2_SECTOR
        LDA FT_BANK
        STA V2_SELECTED
        JSR V2W_ANALYZE
        LDA V2_ERASE
        BEQ FI_PROGRAM
        ; Durable reservation precedes erase. Never call frozen F's absent
        ; journal writer or permit an implicit C/D rotation in this helper.
        LDA #3
        JSR V2W_SELECT
        JSR FI_JOURNAL_ROOM
        BCC FI_JOURNAL_BAD
        LDA FT_BANK
        ASL A
        ASL A
        ASL A
        STA J_COUNTINDEX
        LDA V2_SECTOR
        LSR A
        LSR A
        LSR A
        LSR A
        SEC
        SBC #8
        ORA J_COUNTINDEX
        STA J_COUNTINDEX
        LDA #2
        JSR JE_ENTER
        BCC FI_JOURNAL_BAD
        JSR V2W_BEGIN
        LDA #1
        STA V2_NMI_HOLD
        JSR V2W_ERASE_RAW+2
        BCC FT_FATAL
FI_PROGRAM:
        STZ V2_ERASE
        STZ V2_FLASH_ERROR
        ; Same checked RAM worker as BANK MAINT; omit its optional BRK tag.
        JSR V2W_MUTATE+13
        BCS FT_FATAL
        SEC
        RTS
FI_JOURNAL_BAD:
        LDA #5
        CLC
        RTS
FI_JOURNAL_ROOM:
        ; Native JE can rotate. This transfer deliberately refuses unless a
        ; whole blank page exists before the final intent/rotation page.
        LDA #0
        JSR JE_ENTER
        BCC FI_NO_ROOM
        STZ V2_PTR
        LDA J_BEST+1
        INC A
        STA V2_PTR+1
FI_ROOM_PAGE:
        LDA V2_PTR+1
        AND #$0F
        CMP #$0F
        BCS FI_NO_ROOM
        LDY #0
FI_ROOM_BYTE:
        LDA (V2_PTR),Y
        CMP #$FF
        BNE FI_ROOM_NEXT
        INY
        BNE FI_ROOM_BYTE
        SEC
        RTS
FI_ROOM_NEXT:
        INC V2_PTR+1
        BRA FI_ROOM_PAGE
FI_NO_ROOM:
        CLC
        RTS
FI_WORD: DB "I",0
FI_CONFIRM_TEXT: DB "Dense S19 B",0
FI_READY_TEXT: DB "SEND S19; complete ascending sectors; Ctrl-C cancels",13,10,0
FI_ERROR_TEXT: DB "S19 stopped $",0
FI_HELP_TEXT: DB "I first last  Dense S19, complete sectors; B0/B1 8000-DFFF",13,10,0
        INCLUDE "flash-s19-parser.inc"
