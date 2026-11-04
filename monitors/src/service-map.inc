; Two-character sector tags describe observed formats, not execution admission.
S_MAP:
        LDX #<SM_TITLE
        LDY #>SM_TITLE
        JSR S_PUTS
        STZ S_ROW_BANK
SM_BANK:
        STZ S_CONT_END
        STZ S_CONT_END+1
        STZ S_HAVE_WB
        LDA #'B'
        JSR STR8V2_RAM_PUTC
        LDA S_ROW_BANK
        ORA #'0'
        JSR STR8V2_RAM_PUTC
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA #$80
        STA S_ROW_PAGE
SM_SECTOR:
        LDA S_ROW_BANK
        STA S_READ_BANK
        STZ S_ADDR
        LDA S_ROW_PAGE
        STA S_ADDR+1
        LDA #$FF
        STA S_ERASED
        LDA #64
        STA S_CHUNKS
        LDA #$C5
        STA S_FNV
        LDA #$9D
        STA S_FNV+1
        LDA #$1C
        STA S_FNV+2
        LDA #$81
        STA S_FNV+3
        LDA #$FF
        STA S_CRC
        STA S_CRC+1
        STZ S_WDC_CPU
SM_READ:
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS SM_CANCELED
        JSR S_READ64
        LDA S_CHUNKS
        CMP #64
        BNE SM_BYTE_START
        LDX #23
SM_HEADER_COPY:
        LDA S_BUFFER,X
        STA S_HEADER,X
        DEX
        BPL SM_HEADER_COPY
SM_BYTE_START:
        LDY #0
SM_BYTE:
        LDA S_ERASED
        AND S_BUFFER,Y
        STA S_ERASED
        LDA S_ROW_PAGE
        CMP #$F0
        BNE SM_BYTE_NEXT
        LDA S_ADDR+1
        CMP #$F8
        BCC SM_BYTE_NEXT
        LDA S_BUFFER,Y
        JSR S_CRC_BYTE
        LDA S_BUFFER,Y
        JSR SM_FNV_BYTE
SM_BYTE_NEXT:
        INY
        CPY #64
        BCC SM_BYTE
        LDA S_ADDR+1
        CMP #$F8
        BNE SM_NOT_SIGNATURE
        LDA S_ADDR
        BNE SM_NOT_SIGNATURE
        LDA S_BUFFER+12
        CMP #'S'
        BNE SM_NOT_SIGNATURE
        LDA S_BUFFER+13
        CMP #'X'
        BNE SM_NOT_SIGNATURE
        LDA S_BUFFER+14
        CMP #'B'
        BNE SM_NOT_SIGNATURE
        LDA S_BUFFER+15
        CMP #'2'
        BEQ SM_CPU02
        CMP #'6'
        BNE SM_NOT_SIGNATURE
        LDA #$16
        BRA SM_CPU_SAVE
SM_CPU02:
        LDA #2
SM_CPU_SAVE:
        STA S_WDC_CPU
SM_NOT_SIGNATURE:
        LDA S_CHUNKS
        CMP #1
        BNE SM_ADVANCE
        LDA S_BUFFER+60
        STA S_WDC_RESET
        LDA S_BUFFER+61
        STA S_WDC_RESET+1
SM_ADVANCE:
        CLC
        LDA S_ADDR
        ADC #64
        STA S_ADDR
        BCC SM_DEC
        INC S_ADDR+1
SM_DEC:
        DEC S_CHUNKS
        BNE SM_READ
        JSR SM_CLASSIFY
        JSR S_PUTS
        LDA #' '
        JSR STR8V2_RAM_PUTC
        CLC
        LDA S_ROW_PAGE
        ADC #$10
        STA S_ROW_PAGE
        BNE SM_SECTOR
        JSR STR8V2_RAM_NEWLINE
        INC S_ROW_BANK
        LDA S_ROW_BANK
        CMP #4
        BCC SM_BANK
        LDX #<SM_LEGEND
        LDY #>SM_LEGEND
        JMP S_MESSAGE
SM_CANCELED:
        LDX #<SM_CANCELED_TEXT
        LDY #>SM_CANCELED_TEXT
        JMP S_MESSAGE
SM_CLASSIFY:
        LDA S_ROW_BANK
        CMP #3
        BNE SM_NOT_B3
        LDA S_ROW_PAGE
        CMP #$F0
        BEQ SM_NF
        CMP #$E0
        BEQ SM_SERVICE
        CMP #$C0
        BEQ SM_JOURNAL
        CMP #$D0
        BEQ SM_JOURNAL
SM_NOT_B3:
        ; Erased payload bytes can still belong to a continued record.
        LDA S_ROW_PAGE
        CMP S_CONT_END+1
        BCC SM_CONT
        BNE SM_NOT_CONTINUED
        LDA S_CONT_END
        BNE SM_CONT
SM_NOT_CONTINUED:
        LDA S_ERASED
        CMP #$FF
        BEQ SM_EMPTY
        LDA S_ROW_PAGE
        CMP #$F0
        BNE SM_NOT_WDC
        LDA S_WDC_CPU
        BEQ SM_NOT_WDC
        LDA S_WDC_RESET+1
        CMP #$F8
        BCC SM_NOT_WDC
        LDX #<SM_WDC_POSSIBLE
        LDY #>SM_WDC_POSSIBLE
        LDA S_WDC_RESET
        CMP #$18
        BNE SM_CLASS_RETURN
        LDA S_WDC_RESET+1
        CMP #$F8
        BNE SM_CLASS_RETURN
        LDX #0
        LDA S_WDC_CPU
        CMP #2
        BEQ SM_PROFILE
        LDX #11
SM_PROFILE:
        LDA MAP_WDC_CATALOG+3,X
        CMP S_CRC
        BNE SM_WDC_UNKNOWN
        LDA MAP_WDC_CATALOG+4,X
        CMP S_CRC+1
        BNE SM_WDC_UNKNOWN
        LDY #0
SM_FNV_COMPARE:
        LDA MAP_WDC_CATALOG+5,X
        CMP S_FNV,Y
        BNE SM_WDC_UNKNOWN
        INX
        INY
        CPY #4
        BCC SM_FNV_COMPARE
        LDX #<SM_WDC_KNOWN
        LDY #>SM_WDC_KNOWN
        RTS
SM_WDC_UNKNOWN:
        LDX #<SM_WDC_POSSIBLE
        LDY #>SM_WDC_POSSIBLE
        RTS
SM_NOT_WDC:
        LDA S_ROW_BANK
        CMP #2
        BNE SM_NOT_BUNDLE
        LDA S_ROW_PAGE
        CMP #$80
        BNE SM_BUNDLE_NEXT
        LDA S_HEADER+3
        CMP #'W'
        BNE SM_NOT_BUNDLE
        LDA S_HEADER+4
        CMP #'F'
        BNE SM_NOT_BUNDLE
        LDA S_HEADER+5
        CMP #2
        BEQ SM_BUNDLE_V2
        CMP #3
        BNE SM_NOT_BUNDLE
        LDA #$B0
        BRA SM_BUNDLE_END
SM_BUNDLE_V2:
        LDA #$A0
SM_BUNDLE_END:
        STA S_HAVE_WB
SM_BUNDLE_NEXT:
        LDA S_HAVE_WB
        BEQ SM_NOT_BUNDLE
        LDA S_ROW_PAGE
        CMP S_HAVE_WB
        BCS SM_NOT_BUNDLE
        LDX #<SM_BUNDLE_TAG
        LDY #>SM_BUNDLE_TAG
        RTS
SM_NOT_BUNDLE:
        LDA S_ROW_PAGE
        CMP S_CONT_END+1
        BCC SM_CONT
        BNE SM_HEADERS
        LDA S_CONT_END
        BNE SM_CONT
SM_HEADERS:
        LDA S_HEADER
        CMP #'S'
        BNE SM_NOT_RECORD
        LDA S_HEADER+1
        CMP #'R'
        BNE SM_NOT_RECORD
        LDA S_HEADER+2
        CMP #1
        BNE SM_NOT_RECORD
        LDA S_HEADER+3
        CMP #$3F
        BEQ SM_RECORD_STATE_OK
        CMP #$FF
        BNE SM_NOT_RECORD
SM_RECORD_STATE_OK:
        LDA S_HEADER+6
        ORA S_HEADER+7
        BEQ SM_NOT_RECORD
        CLC
        LDA S_HEADER+6
        ADC #24
        STA S_CONT_END
        LDA S_HEADER+7
        ADC S_ROW_PAGE
        BCS SM_NOT_RECORD
        CMP #$E0
        BCC SM_RECORD_END_OK
        BNE SM_NOT_RECORD
        LDX S_CONT_END
        BNE SM_NOT_RECORD
SM_RECORD_END_OK:
        STA S_CONT_END+1
        LDX #<SM_RECORD_TAG
        LDY #>SM_RECORD_TAG
        RTS
SM_NOT_RECORD:
        LDA S_HEADER
        CMP #'M'
        BNE SM_NOT_MI
        LDA S_HEADER+1
        CMP #'I'
        BNE SM_NOT_MI
        LDX #<SM_MON_TAG
        LDY #>SM_MON_TAG
        RTS
SM_NOT_MI:
        LDA S_HEADER
        CMP #'A'
        BNE SM_UNKNOWN
        LDA S_HEADER+1
        CMP #'P'
        BNE SM_UNKNOWN
        LDX #<SM_APP_TAG
        LDY #>SM_APP_TAG
        RTS
SM_UNKNOWN:
        LDX #<SM_UNKNOWN_TAG
        LDY #>SM_UNKNOWN_TAG
        RTS
SM_CONT:
        LDX #<SM_CONT_TAG
        LDY #>SM_CONT_TAG
        RTS
SM_NF:
        LDX #<SM_NF_TAG
        LDY #>SM_NF_TAG
        RTS
SM_SERVICE:
        LDX #7
SM_SERVICE_HEADER:
        LDA S_HEADER,X
        CMP SM_SERVICE_MAGIC,X
        BNE SM_UNKNOWN
        DEX
        BPL SM_SERVICE_HEADER
        LDX #<SM_SERVICE_TAG
        LDY #>SM_SERVICE_TAG
        RTS
SM_JOURNAL:
        LDX #<SM_JOURNAL_TAG
        LDY #>SM_JOURNAL_TAG
        RTS
SM_EMPTY:
        LDX #<SM_EMPTY_TAG
        LDY #>SM_EMPTY_TAG
SM_CLASS_RETURN:
        RTS
; FNV-1a multiplication by 01000193, using shifts/adds on a saved value.
SM_FNV_BYTE:
        PHX
        PHY
        EOR S_FNV
        STA S_FNV
        LDX #3
SM_FNV_SAVE:
        LDA S_FNV,X
        STA S_FNV_TEMP,X
        DEX
        BPL SM_FNV_SAVE
        JSR SM_FNV_SHIFT
        JSR SM_FNV_ADD
        LDX #3
        JSR SM_FNV_SHIFTS
        JSR SM_FNV_ADD
        LDX #3
        JSR SM_FNV_SHIFTS
        JSR SM_FNV_ADD
        JSR SM_FNV_SHIFT
        JSR SM_FNV_ADD
        LDX #16
        JSR SM_FNV_SHIFTS
        JSR SM_FNV_ADD
        PLY
        PLX
        RTS
SM_FNV_SHIFTS:
        JSR SM_FNV_SHIFT
        DEX
        BNE SM_FNV_SHIFTS
        RTS
SM_FNV_SHIFT:
        ASL S_FNV_TEMP
        ROL S_FNV_TEMP+1
        ROL S_FNV_TEMP+2
        ROL S_FNV_TEMP+3
        RTS
SM_FNV_ADD:
        CLC
        LDA S_FNV
        ADC S_FNV_TEMP
        STA S_FNV
        LDA S_FNV+1
        ADC S_FNV_TEMP+1
        STA S_FNV+1
        LDA S_FNV+2
        ADC S_FNV_TEMP+2
        STA S_FNV+2
        LDA S_FNV+3
        ADC S_FNV_TEMP+3
        STA S_FNV+3
        RTS
SM_TITLE: DB "     8  9  A  B  C  D  E  F",13,10,0
SM_LEGEND: DB "MI MON SR record ++ next AP app WB bundle MS svc JJ journal NF F",13,10
        DB "W+/W? WDC known/tag; .. erased; ?? other",13,10
        DB "Tags != code; erased != free.",13,10,0
SM_CANCELED_TEXT: DB "Map canceled",13,10,0
SM_NF_TAG: DB "NF",0
SM_SERVICE_TAG: DB "MS",0
SM_SERVICE_MAGIC: DB "MS",SB_FORMAT,SB_PAGES,"PR05"
SM_JOURNAL_TAG: DB "JJ",0
SM_EMPTY_TAG: DB "..",0
SM_WDC_POSSIBLE: DB "W?",0
SM_WDC_KNOWN: DB "W+",0
SM_BUNDLE_TAG: DB "WB",0
SM_RECORD_TAG: DB "SR",0
SM_MON_TAG: DB "MI",0
SM_APP_TAG: DB "AP",0
SM_UNKNOWN_TAG: DB "??",0
SM_CONT_TAG: DB "++",0
        INCLUDE "map-wdc-catalog.inc"
