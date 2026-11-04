; BASE1 RAM map/maintenance: read-only image recognition and owner data inspection.
; Matching PR05 private bindings; no flash/config writer or execution entry.
        MODULE RAM_MAINT_RO_B15
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "worker-public-symbols.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "maint-ro-params.inc"
MA_PTR EQU $E0
MA_BP EQU $E2
MA_BUF EQU $5000
        CODE
MA_START:
        SEI
        CLD
        STZ MA_HAVE
        STZ MA_ERROR
        ; No F/private call until exact immutable image, F and RAM guards pass.
        LDA $7E60
        CMP #'R'
        BEQ MRO_LONG_1
        JMP MA_GUARD_BAD
MRO_LONG_1:
        LDA $7E61
        CMP #'A'
        BEQ MRO_LONG_2
        JMP MA_GUARD_BAD
MRO_LONG_2:
        LDA $7E62
        CMP #1
        BEQ MRO_LONG_3
        JMP MA_GUARD_BAD
MRO_LONG_3:
        LDA $7E63
        CMP #$0D
        BEQ MRO_LONG_4
        JMP MA_GUARD_BAD
MRO_LONG_4:
        LDA #<MA_START
        STA MA_SRC
        LDA #>MA_START
        STA MA_SRC+1
        LDA #<(MA_IMM_END-MA_START)
        STA MA_COUNT
        LDA #>(MA_IMM_END-MA_START)
        STA MA_COUNT+1
        JSR MA_RAW_CRC
        LDA MA_CRC
        ORA MA_CRC+1
        BEQ MRO_LONG_5
        JMP MA_GUARD_BAD
MRO_LONG_5:
        LDA #$F0
        STA MA_SRC+1
        STZ MA_SRC
        LDA #$10
        STA MA_COUNT+1
        STZ MA_COUNT
        JSR MA_RAW_CRC
        LDA MA_CRC
        CMP #MA_F_CRC_LO
        BEQ MRO_LONG_6
        JMP MA_GUARD_BAD
MRO_LONG_6:
        LDA MA_CRC+1
        CMP #MA_F_CRC_HI
        BEQ MRO_LONG_7
        JMP MA_GUARD_BAD
MRO_LONG_7:
        LDX #0
MA_RAM_GUARD:
        LDA MA_GUARD_TABLE,X
        STA MA_SRC
        LDA MA_GUARD_TABLE+1,X
        STA MA_SRC+1
        LDA MA_GUARD_TABLE+2,X
        STA MA_COUNT
        LDA MA_GUARD_TABLE+3,X
        STA MA_COUNT+1
        STX MA_TABLE_INDEX
        JSR MA_RAW_CRC
        LDX MA_TABLE_INDEX
        LDA MA_CRC
        CMP MA_GUARD_TABLE+4,X
        BEQ MRO_LONG_8
        JMP MA_GUARD_BAD
MRO_LONG_8:
        LDA MA_CRC+1
        CMP MA_GUARD_TABLE+5,X
        BEQ MRO_LONG_9
        JMP MA_GUARD_BAD
MRO_LONG_9:
        TXA
        CLC
        ADC #6
        TAX
        CPX #12
        BEQ MRO_LONG_10
        JMP MA_RAM_GUARD
MRO_LONG_10:
        LDX #<MA_TITLE
        LDY #>MA_TITLE
        JSR MA_PRINT
MA_MENU:
        LDX #<MA_PROMPT
        LDY #>MA_PROMPT
        JSR MA_PRINT
        JSR BOOT_API_LINE
        BCS MRO_LONG_11
        JMP MA_BAD
MRO_LONG_11:
        LDA #1
        STA MA_POS
        LDA STR8V2_LINE
        CMP #'M'
        BNE MRO_LONG_12
        JMP MA_MAP
MRO_LONG_12:
        CMP #'R'
        BNE MRO_LONG_13
        JMP MA_READ
MRO_LONG_13:
        CMP #'D'
        BNE MRO_LONG_14
        JMP MA_DUMP
MRO_LONG_14:
        CMP #'V'
        BNE MRO_LONG_15
        JMP MA_COMPARE
MRO_LONG_15:
        CMP #'K'
        BNE MRO_LONG_16
        JMP MA_CHECKSUM
MRO_LONG_16:
        JSR MA_ENDLINE
        BCS MRO_LONG_17
        JMP MA_BAD
MRO_LONG_17:
        LDA STR8V2_LINE
        CMP #'?'
        BNE MRO_LONG_18
        JMP MA_HELP
MRO_LONG_18:
        CMP #'Q'
        BEQ MRO_LONG_19
        JMP MA_BAD
MRO_LONG_19:
        JMP STR8V2_RAM_RESET
MA_HELP:
        LDX #<MA_HELP_TEXT
        LDY #>MA_HELP_TEXT
        JMP MA_MESSAGE
MA_BAD:
        LDX #<MA_BAD_TEXT
        LDY #>MA_BAD_TEXT
MA_MESSAGE:
        JSR MA_PRINT
        JMP MA_MENU
MA_GUARD_BAD:
        LDA #1
        STA MA_ERROR
MA_HALT:
        JMP MA_HALT

; Tokens: exactly one bank character or four hex digits, space separated.
MA_NEED_SPACE:
        LDX MA_POS
        LDA STR8V2_LINE,X
        CMP #' '
        BEQ MRO_LONG_20
        JMP MA_PARSE_BAD
MRO_LONG_20:
MA_SKIP_SPACE:
        INX
        LDA STR8V2_LINE,X
        CMP #' '
        BNE MRO_LONG_21
        JMP MA_SKIP_SPACE
MRO_LONG_21:
        STX MA_POS
        CMP #0
        BNE MRO_LONG_22
        JMP MA_PARSE_BAD
MRO_LONG_22:
        SEC
        RTS
MA_ENDLINE:
        LDX MA_POS
MA_END_SKIP:
        LDA STR8V2_LINE,X
        BNE MRO_LONG_23
        JMP MA_PARSE_OK
MRO_LONG_23:
        CMP #' '
        BEQ MRO_LONG_24
        JMP MA_PARSE_BAD
MRO_LONG_24:
        INX
        JMP MA_END_SKIP
MA_BANK_TOKEN:
        JSR MA_NEED_SPACE
        BCS MRO_LONG_25
        JMP MA_PARSE_BAD
MRO_LONG_25:
        LDA STR8V2_LINE,X
        CMP #'R'
        BEQ MRO_LONG_26
        JMP MA_BANK_DIGIT
MRO_LONG_26:
        LDA #4
        JMP MA_BANK_SAVE
MA_BANK_DIGIT:
        CMP #'0'
        BCS MRO_LONG_27
        JMP MA_PARSE_BAD
MRO_LONG_27:
        CMP #'4'
        BCC MRO_LONG_28
        JMP MA_PARSE_BAD
MRO_LONG_28:
        SEC
        SBC #'0'
MA_BANK_SAVE:
        PHA
        INX
        STX MA_POS
        LDA STR8V2_LINE,X
        BNE MRO_LONG_29
        JMP MA_BANK_OK
MRO_LONG_29:
        CMP #' '
        BEQ MRO_LONG_30
        JMP MA_BANK_ERROR
MRO_LONG_30:
MA_BANK_OK:
        PLA
        SEC
        RTS
MA_BANK_ERROR:
        PLA
MA_PARSE_BAD:
        CLC
        RTS
MA_PARSE_OK:
        SEC
        RTS
MA_WORD_TOKEN:
        JSR MA_NEED_SPACE
        BCS MRO_LONG_31
        JMP MA_PARSE_BAD
MRO_LONG_31:
        STZ MA_VALUE
        STZ MA_VALUE+1
        LDA #4
        STA MA_DIGITS
MA_WORD_DIGIT:
        LDA STR8V2_LINE,X
        CMP #'0'
        BCS MRO_LONG_32
        JMP MA_PARSE_BAD
MRO_LONG_32:
        CMP #'9'+1
        BCS MRO_LONG_33
        JMP MA_WORD_NUMBER
MRO_LONG_33:
        CMP #'A'
        BCS MRO_LONG_34
        JMP MA_PARSE_BAD
MRO_LONG_34:
        CMP #'F'+1
        BCC MRO_LONG_35
        JMP MA_PARSE_BAD
MRO_LONG_35:
        SEC
        SBC #'A'-10
        JMP MA_WORD_NIBBLE
MA_WORD_NUMBER:
        SEC
        SBC #'0'
MA_WORD_NIBBLE:
        PHA
        ASL MA_VALUE
        ROL MA_VALUE+1
        ASL MA_VALUE
        ROL MA_VALUE+1
        ASL MA_VALUE
        ROL MA_VALUE+1
        ASL MA_VALUE
        ROL MA_VALUE+1
        PLA
        ORA MA_VALUE
        STA MA_VALUE
        INX
        DEC MA_DIGITS
        BEQ MRO_LONG_36
        JMP MA_WORD_DIGIT
MRO_LONG_36:
        STX MA_POS
        LDA STR8V2_LINE,X
        BNE MRO_LONG_37
        JMP MA_PARSE_OK
MRO_LONG_37:
        CMP #' '
        BNE MRO_LONG_38
        JMP MA_PARSE_OK
MRO_LONG_38:
        CLC
        RTS
MA_PARSE_RANGE:
        JSR MA_BANK_TOKEN
        BCS MRO_LONG_39
        JMP MA_PARSE_BAD
MRO_LONG_39:
        STA MA_SB
        JSR MA_WORD_TOKEN
        BCS MRO_LONG_40
        JMP MA_PARSE_BAD
MRO_LONG_40:
        LDA MA_VALUE
        STA MA_SRC
        LDA MA_VALUE+1
        STA MA_SRC+1
        JSR MA_WORD_TOKEN
        BCS MRO_LONG_41
        JMP MA_PARSE_BAD
MRO_LONG_41:
        LDA MA_VALUE
        STA MA_LAST
        LDA MA_VALUE+1
        STA MA_LAST+1
        JSR MA_RANGE
        BCS MRO_LONG_42
        JMP MA_PARSE_BAD
MRO_LONG_42:
        SEC
        LDA MA_LAST
        SBC MA_SRC
        STA MA_COUNT
        LDA MA_LAST+1
        SBC MA_SRC+1
        STA MA_COUNT+1
        INC MA_COUNT
        BEQ MRO_LONG_43
        JMP MA_PARSE_OK
MRO_LONG_43:
        INC MA_COUNT+1
        SEC
        RTS
MA_RANGE:
        LDA MA_LAST
        CMP MA_SRC
        LDA MA_LAST+1
        SBC MA_SRC+1
        BCS MRO_LONG_44
        JMP MA_PARSE_BAD
MRO_LONG_44:
        LDA MA_SB
        CMP #4
        BNE MRO_LONG_45
        JMP MA_RANGE_RAM
MRO_LONG_45:
        LDA MA_SRC+1
        CMP #$80
        BCS MRO_LONG_46
        JMP MA_PARSE_BAD
MRO_LONG_46:
        SEC
        RTS
MA_RANGE_RAM:
        LDA MA_SRC+1
        CMP #$20
        BCS MRO_LONG_47
        JMP MA_PARSE_BAD
MRO_LONG_47:
        LDA MA_LAST+1
        CMP #$65
        BCC MRO_LONG_48
        JMP MA_PARSE_BAD
MRO_LONG_48:
        SEC
        RTS

; Read-only bank selection: source reads happen in RAM; ROM calls see B3.
MA_SELECT_SOURCE:
        LDA MA_SB
        CMP #4
        BNE MRO_LONG_49
        JMP MA_SELECTED
MRO_LONG_49:
        JSR V2W_SELECT
MA_SELECTED:
        LDA MA_SRC
        STA MA_PTR
        LDA MA_SRC+1
        STA MA_PTR+1
        RTS
MA_HOME:
        LDA #3
        JMP V2W_SELECT
MA_NEXT_PTR:
        INC MA_PTR
        BEQ MRO_LONG_50
        JMP MA_NEXT_DONE
MRO_LONG_50:
        INC MA_PTR+1
MA_NEXT_DONE:
        RTS
MA_DEC_COUNT:
        LDA MA_COUNT
        BEQ MRO_LONG_51
        JMP MA_DEC_LOW
MRO_LONG_51:
        DEC MA_COUNT+1
MA_DEC_LOW:
        DEC MA_COUNT
        LDA MA_COUNT
        ORA MA_COUNT+1
        RTS

MA_READ:
        JSR MA_PARSE_RANGE
        BCS MRO_LONG_52
        JMP MA_BAD
MRO_LONG_52:
        JSR MA_ENDLINE
        BCS MRO_LONG_53
        JMP MA_BAD
MRO_LONG_53:
        LDA MA_COUNT+1
        CMP #$10
        BCS MRO_LONG_54
        JMP MA_READ_LENGTH_OK
MRO_LONG_54:
        BEQ MRO_LONG_55
        JMP MA_BAD
MRO_LONG_55:
        LDA MA_COUNT
        BEQ MRO_LONG_56
        JMP MA_BAD
MRO_LONG_56:
MA_READ_LENGTH_OK:
        ; A read-to-buffer must not overlap and overwrite its own RAM source.
        LDA MA_SB
        CMP #4
        BEQ MRO_LONG_57
        JMP MA_READ_READY
MRO_LONG_57:
        LDA MA_SRC+1
        CMP #$60
        BCC MRO_LONG_58
        JMP MA_READ_READY
MRO_LONG_58:
        LDA MA_LAST+1
        CMP #$50
        BCC MRO_LONG_59
        JMP MA_BAD
MRO_LONG_59:
MA_READ_READY:
        LDA MA_COUNT
        STA MA_LENGTH
        LDA MA_COUNT+1
        STA MA_LENGTH+1
        STZ MA_BP
        LDA #$50
        STA MA_BP+1
        JSR MA_SELECT_SOURCE
MA_READ_BYTE:
        LDA (MA_PTR)
        STA (MA_BP)
        INC MA_BP
        BEQ MRO_LONG_60
        JMP MA_READ_ADVANCE
MRO_LONG_60:
        INC MA_BP+1
MA_READ_ADVANCE:
        JSR MA_NEXT_PTR
        JSR MA_DEC_COUNT
        BEQ MRO_LONG_61
        JMP MA_READ_BYTE
MRO_LONG_61:
        JSR MA_HOME
        LDA #1
        STA MA_HAVE
        LDX #<MA_BUFFER_TEXT
        LDY #>MA_BUFFER_TEXT
        JMP MA_MESSAGE

MA_DUMP:
        LDA MA_HAVE
        BNE MRO_LONG_62
        JMP MA_BAD
MRO_LONG_62:
        JSR MA_ENDLINE
        BCS MRO_LONG_63
        JMP MA_DUMP_ARGUMENTS
MRO_LONG_63:
        STZ MA_OFFSET
        STZ MA_OFFSET+1
        LDA #15
        STA MA_LAST
        STZ MA_LAST+1
        LDA MA_LENGTH+1
        BEQ MRO_LONG_64
        JMP MA_DUMP_GO
MRO_LONG_64:
        LDA MA_LENGTH
        CMP #16
        BCC MRO_LONG_65
        JMP MA_DUMP_GO
MRO_LONG_65:
        DEC A
        STA MA_LAST
        JMP MA_DUMP_GO
MA_DUMP_ARGUMENTS:
        JSR MA_WORD_TOKEN
        BCS MRO_LONG_66
        JMP MA_BAD
MRO_LONG_66:
        LDA MA_VALUE
        STA MA_OFFSET
        LDA MA_VALUE+1
        STA MA_OFFSET+1
        JSR MA_ENDLINE
        BCS MRO_LONG_67
        JMP MA_DUMP_END
MRO_LONG_67:
        LDA MA_OFFSET
        STA MA_LAST
        LDA MA_OFFSET+1
        STA MA_LAST+1
        JMP MA_DUMP_VALIDATE
MA_DUMP_END:
        JSR MA_WORD_TOKEN
        BCS MRO_LONG_68
        JMP MA_BAD
MRO_LONG_68:
        LDA MA_VALUE
        STA MA_LAST
        LDA MA_VALUE+1
        STA MA_LAST+1
        JSR MA_ENDLINE
        BCS MRO_LONG_69
        JMP MA_BAD
MRO_LONG_69:
MA_DUMP_VALIDATE:
        LDA MA_LAST
        CMP MA_OFFSET
        LDA MA_LAST+1
        SBC MA_OFFSET+1
        BCS MRO_LONG_70
        JMP MA_BAD
MRO_LONG_70:
        LDA MA_LAST
        CMP MA_LENGTH
        LDA MA_LAST+1
        SBC MA_LENGTH+1
        BCC MRO_LONG_71
        JMP MA_BAD
MRO_LONG_71:
MA_DUMP_GO:
        STZ MA_COLUMN
MA_DUMP_BYTE:
        LDA MA_COLUMN
        BEQ MRO_LONG_72
        JMP MA_DUMP_VALUE
MRO_LONG_72:
        LDA MA_OFFSET+1
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_OFFSET
        JSR STR8V2_RAM_HEX_OUT
        LDA #':'
        JSR STR8V2_RAM_PUTC
MA_DUMP_VALUE:
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA MA_OFFSET
        STA MA_PTR
        LDA MA_OFFSET+1
        CLC
        ADC #$50
        STA MA_PTR+1
        LDA (MA_PTR)
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_OFFSET
        CMP MA_LAST
        BEQ MRO_LONG_73
        JMP MA_DUMP_MORE
MRO_LONG_73:
        LDA MA_OFFSET+1
        CMP MA_LAST+1
        BNE MRO_LONG_74
        JMP MA_DUMP_DONE
MRO_LONG_74:
MA_DUMP_MORE:
        INC MA_OFFSET
        BEQ MRO_LONG_75
        JMP MA_DUMP_COL
MRO_LONG_75:
        INC MA_OFFSET+1
MA_DUMP_COL:
        INC MA_COLUMN
        LDA MA_COLUMN
        AND #15
        STA MA_COLUMN
        BEQ MRO_LONG_76
        JMP MA_DUMP_BYTE
MRO_LONG_76:
        JSR STR8V2_RAM_NEWLINE
        JMP MA_DUMP_BYTE
MA_DUMP_DONE:
        JSR STR8V2_RAM_NEWLINE
        JMP MA_MENU

MA_CHECKSUM:
        JSR MA_ENDLINE
        BCS MRO_LONG_77
        JMP MA_CHECKSUM_RANGE
MRO_LONG_77:
        LDA MA_HAVE
        BNE MRO_LONG_78
        JMP MA_BAD
MRO_LONG_78:
        LDA #4
        STA MA_SB
        STZ MA_SRC
        LDA #$50
        STA MA_SRC+1
        LDA MA_LENGTH
        STA MA_COUNT
        LDA MA_LENGTH+1
        STA MA_COUNT+1
        JMP MA_CHECKSUM_GO
MA_CHECKSUM_RANGE:
        JSR MA_PARSE_RANGE
        BCS MRO_LONG_79
        JMP MA_BAD
MRO_LONG_79:
        JSR MA_ENDLINE
        BCS MRO_LONG_80
        JMP MA_BAD
MRO_LONG_80:
MA_CHECKSUM_GO:
        JSR MA_SELECT_SOURCE
        JSR MA_CRC_AT_PTR
        JSR MA_HOME
        LDX #<MA_CRC_TEXT
        LDY #>MA_CRC_TEXT
        JSR MA_PRINT
        LDA MA_CRC+1
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_CRC
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        JMP MA_MENU

MA_COMPARE:
        JSR MA_PARSE_RANGE
        BCS MRO_LONG_81
        JMP MA_BAD
MRO_LONG_81:
        JSR MA_BANK_TOKEN
        BCS MRO_LONG_82
        JMP MA_BAD
MRO_LONG_82:
        STA MA_DB
        JSR MA_WORD_TOKEN
        BCS MRO_LONG_83
        JMP MA_BAD
MRO_LONG_83:
        LDA MA_VALUE
        STA MA_DST
        LDA MA_VALUE+1
        STA MA_DST+1
        JSR MA_ENDLINE
        BCS MRO_LONG_84
        JMP MA_BAD
MRO_LONG_84:
        ; Check the complete destination span before performing any read.
        SEC
        LDA MA_COUNT
        SBC #1
        STA MA_VALUE
        LDA MA_COUNT+1
        SBC #0
        STA MA_VALUE+1
        CLC
        LDA MA_DST
        ADC MA_VALUE
        STA MA_VALUE
        LDA MA_DST+1
        ADC MA_VALUE+1
        BCC MRO_LONG_85
        JMP MA_BAD
MRO_LONG_85:
        STA MA_VALUE+1
        LDA MA_DB
        CMP #4
        BNE MRO_LONG_86
        JMP MA_COMPARE_RAM
MRO_LONG_86:
        LDA MA_DST+1
        CMP #$80
        BCS MRO_LONG_87
        JMP MA_BAD
MRO_LONG_87:
        JMP MA_COMPARE_LOOP
MA_COMPARE_RAM:
        LDA MA_DST+1
        CMP #$20
        BCS MRO_LONG_88
        JMP MA_BAD
MRO_LONG_88:
        LDA MA_VALUE+1
        CMP #$65
        BCC MRO_LONG_89
        JMP MA_BAD
MRO_LONG_89:
MA_COMPARE_LOOP:
        JSR MA_SELECT_SOURCE
        LDA (MA_PTR)
        STA MA_BYTE
        JSR MA_HOME
        LDA MA_DB
        CMP #4
        BNE MRO_LONG_90
        JMP MA_COMPARE_DST
MRO_LONG_90:
        JSR V2W_SELECT
MA_COMPARE_DST:
        LDA MA_DST
        STA MA_PTR
        LDA MA_DST+1
        STA MA_PTR+1
        LDA (MA_PTR)
        CMP MA_BYTE
        PHP
        JSR MA_HOME
        PLP
        BEQ MRO_LONG_91
        JMP MA_DIFFERENT
MRO_LONG_91:
        INC MA_SRC
        BEQ MRO_LONG_92
        JMP MA_COMPARE_SRC_NEXT
MRO_LONG_92:
        INC MA_SRC+1
MA_COMPARE_SRC_NEXT:
        INC MA_DST
        BEQ MRO_LONG_93
        JMP MA_COMPARE_DST_NEXT
MRO_LONG_93:
        INC MA_DST+1
MA_COMPARE_DST_NEXT:
        JSR MA_DEC_COUNT
        BEQ MRO_LONG_94
        JMP MA_COMPARE_LOOP
MRO_LONG_94:
        LDX #<MA_MATCH_TEXT
        LDY #>MA_MATCH_TEXT
        JMP MA_MESSAGE
MA_DIFFERENT:
        LDX #<MA_DIFFERENT_TEXT
        LDY #>MA_DIFFERENT_TEXT
        JSR MA_PRINT
        LDA MA_DB
        JSR MA_SPACE_NAME
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA MA_DST+1
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_DST
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        JMP MA_MENU

; Local CRC16-CCITT-FALSE: seed FFFF, polynomial 1021, no final XOR.
MA_RAW_CRC:
        LDA MA_SRC
        STA MA_PTR
        LDA MA_SRC+1
        STA MA_PTR+1
MA_CRC_AT_PTR:
        LDA #$FF
        STA MA_CRC
        STA MA_CRC+1
MA_CRC_LOOP:
        LDA (MA_PTR)
        JSR MA_CRC_BYTE
        JSR MA_NEXT_PTR
        JSR MA_DEC_COUNT
        BEQ MRO_LONG_95
        JMP MA_CRC_LOOP
MRO_LONG_95:
        RTS
MA_CRC_BYTE:
        EOR MA_CRC+1
        STA MA_CRC+1
        LDX #8
MA_CRC_BIT:
        ASL MA_CRC
        ROL MA_CRC+1
        BCS MRO_LONG_96
        JMP MA_CRC_NO_XOR
MRO_LONG_96:
        LDA MA_CRC
        EOR #$21
        STA MA_CRC
        LDA MA_CRC+1
        EOR #$10
        STA MA_CRC+1
MA_CRC_NO_XOR:
        DEX
        BEQ MRO_LONG_97
        JMP MA_CRC_BIT
MRO_LONG_97:
        RTS

MA_MAP:
        LDA #2
        STA MA_VIEW
        JSR MA_ENDLINE
        BCC MRO_LONG_98
        JMP MA_MAP_READY
MRO_LONG_98:
        ; Preserve familiar M1/M2/M3 as well as spaced M 1/2/3.
        LDX MA_POS
        LDA STR8V2_LINE,X
        CMP #' '
        BNE MRO_LONG_99
        JSR MA_NEED_SPACE
        BCS MRO_LONG_99
        JMP MA_BAD
MRO_LONG_99:
        LDA STR8V2_LINE,X
        CMP #'1'
        BCS MRO_LONG_100
        JMP MA_BAD
MRO_LONG_100:
        CMP #'4'
        BCC MRO_LONG_101
        JMP MA_BAD
MRO_LONG_101:
        SEC
        SBC #'0'
        STA MA_VIEW
        INC MA_POS
        JSR MA_ENDLINE
        BCS MRO_LONG_102
        JMP MA_BAD
MRO_LONG_102:
MA_MAP_READY:
        JSR MA_READ_JOURNAL
        STZ MA_MAP_INDEX
        STZ MA_MB
        LDA #$80
        STA MA_MS
        LDA MA_VIEW
        CMP #1
        BEQ MRO_LONG_103
        JMP MA_MAP_ROW
MRO_LONG_103:
        LDX #<MA_GRID_TITLE
        LDY #>MA_GRID_TITLE
        JSR MA_PRINT
MA_MAP_ROW:
        LDA MA_MB
        JSR V2W_SELECT
        STZ MA_PTR
        LDA MA_MS
        STA MA_PTR+1
        STZ MA_COUNT
        LDA #$10
        STA MA_COUNT+1
        LDA #'E'
        STA MA_STATUS
MA_SCAN:
        LDA (MA_PTR)
        CMP #$FF
        BEQ MRO_LONG_104
        JMP MA_USED
MRO_LONG_104:
        JSR MA_NEXT_PTR
        JSR MA_DEC_COUNT
        BEQ MRO_LONG_105
        JMP MA_SCAN
MRO_LONG_105:
        JMP MA_SCAN_DONE
MA_USED:
        LDA #'U'
        STA MA_STATUS
MA_SCAN_DONE:
        JSR MAP_RECOGNIZE
        JSR MA_HOME
        LDA MA_VIEW
        CMP #1
        BEQ MRO_LONG_106
        JMP MA_MAP_DETAIL
MRO_LONG_106:
        LDA MA_MS
        CMP #$80
        BEQ MRO_LONG_107
        JMP MA_GRID_CELL
MRO_LONG_107:
        LDA MA_MB
        JSR MA_SPACE_NAME
MA_GRID_CELL:
        JSR MA_SPACE
        JSR MAP_PRINT_CELL
        LDA MA_MS
        CMP #$F0
        BEQ MRO_LONG_108
        JMP MA_MAP_NEXT
MRO_LONG_108:
        JSR STR8V2_RAM_NEWLINE
        JMP MA_MAP_NEXT
MA_MAP_DETAIL:
        LDA MA_MB
        JSR MA_SPACE_NAME
        LDA #':'
        JSR STR8V2_RAM_PUTC
        LDA MA_MS
        LSR A
        LSR A
        LSR A
        LSR A
        JSR MAP_PRINT_NIBBLE
        JSR MA_SPACE
        JSR MAP_PRINT_CELL
        JSR MA_SPACE
        LDA MA_VIEW
        CMP #3
        BEQ MRO_LONG_109
        JMP MA_MAP_ROLE
MRO_LONG_109:
        JSR MA_MAP_COUNT
        JSR MA_SPACE
MA_MAP_ROLE:
        JSR MA_ROLE
        JSR MA_PRINT
        JSR MAP_DETAIL
        JSR STR8V2_RAM_NEWLINE
MA_MAP_NEXT:
        INC MA_MAP_INDEX
        CLC
        LDA MA_MS
        ADC #$10
        STA MA_MS
        BEQ MRO_LONG_110
        JMP MA_MAP_ROW
MRO_LONG_110:
        LDA #$80
        STA MA_MS
        INC MA_MB
        LDA MA_MB
        CMP #4
        BEQ MRO_LONG_111
        JMP MA_MAP_ROW
MRO_LONG_111:
        LDX #<MA_MAP_LEGEND
        LDY #>MA_MAP_LEGEND
        JSR MA_PRINT
        LDA MA_JVALID
        BNE MRO_LONG_112
        JMP MA_MAP_NO_JOURNAL
MRO_LONG_112:
        LDX #<MA_SEQUENCE_TEXT
        LDY #>MA_SEQUENCE_TEXT
        JSR MA_PRINT
        LDX #11
MA_SEQ_BYTE:
        LDA MA_JOURNAL,X
        PHX
        JSR STR8V2_RAM_HEX_OUT
        PLX
        DEX
        CPX #7
        BEQ MRO_LONG_113
        JMP MA_SEQ_BYTE
MRO_LONG_113:
        LDX #<MA_DEFAULT_TEXT
        LDY #>MA_DEFAULT_TEXT
        JSR MA_PRINT
        LDA MA_JOURNAL+7
        JSR STR8V2_RAM_PUTC
        LDX #<MA_MASK_TEXT
        LDY #>MA_MASK_TEXT
        JSR MA_PRINT
        LDA MA_JOURNAL+13
        JSR STR8V2_RAM_HEX_OUT
        LDX #<MA_UNKNOWN_TEXT
        LDY #>MA_UNKNOWN_TEXT
        JSR MA_PRINT
        LDX #163
MA_UNKNOWN_BYTE:
        LDA MA_JOURNAL,X
        PHX
        JSR STR8V2_RAM_HEX_OUT
        PLX
        DEX
        CPX #159
        BEQ MRO_LONG_114
        JMP MA_UNKNOWN_BYTE
MRO_LONG_114:
        JSR STR8V2_RAM_NEWLINE
        JMP MA_MENU
MA_MAP_NO_JOURNAL:
        LDX #<MA_NO_JOURNAL_TEXT
        LDY #>MA_NO_JOURNAL_TEXT
        JMP MA_MESSAGE
MA_MAP_COUNT:
        LDA MA_JVALID
        BEQ MRO_LONG_115
        JMP MA_MAP_COUNT_VALID
MRO_LONG_115:
        LDX #<MA_UNKNOWN_COUNT
        LDY #>MA_UNKNOWN_COUNT
        JMP MA_PRINT
MA_MAP_COUNT_VALID:
        LDA MA_MAP_INDEX
        ASL A
        CLC
        ADC MA_MAP_INDEX
        TAX
        LDA MA_JOURNAL+66,X
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_MAP_INDEX
        ASL A
        CLC
        ADC MA_MAP_INDEX
        TAX
        LDA MA_JOURNAL+65,X
        JSR STR8V2_RAM_HEX_OUT
        LDA MA_MAP_INDEX
        ASL A
        CLC
        ADC MA_MAP_INDEX
        TAX
        LDA MA_JOURNAL+64,X
        JMP STR8V2_RAM_HEX_OUT
MA_ROLE:
        LDA MA_MB
        CMP #3
        BNE MA_ROLE_OWNER
        LDA MA_MS
        CMP #$C0
        BEQ MA_ROLE_JOURNAL
        CMP #$D0
        BEQ MA_ROLE_JOURNAL
        CMP #$F0
        BEQ MA_ROLE_F
MA_ROLE_OWNER:
        LDX #<MA_ROLE_OWNER_TEXT
        LDY #>MA_ROLE_OWNER_TEXT
        RTS
MA_ROLE_JOURNAL:
        LDX #<MA_ROLE_JOURNAL_TEXT
        LDY #>MA_ROLE_JOURNAL_TEXT
        RTS
MA_ROLE_F:
        LDX #<MA_ROLE_F_TEXT
        LDY #>MA_ROLE_F_TEXT
        RTS

; Copy and admit the current snapshot without linking any journal writer.
MA_READ_JOURNAL:
        STZ MA_JVALID
        JSR BOOT_READ_RECORD
        BCS MRO_LONG_122
        JMP MA_JOURNAL_DONE
MRO_LONG_122:
        STZ MA_PTR
        LDA J_BEST+1
        STA MA_PTR+1
        LDY #0
MA_JCOPY:
        LDA (MA_PTR),Y
        STA MA_JOURNAL,Y
        INY
        BEQ MRO_LONG_123
        JMP MA_JCOPY
MRO_LONG_123:
        LDA #<MA_JOURNAL
        STA MA_SRC
        LDA #>MA_JOURNAL
        STA MA_SRC+1
        LDA #252
        STA MA_COUNT
        STZ MA_COUNT+1
        JSR MA_RAW_CRC
        LDA MA_CRC
        CMP MA_JOURNAL+252
        BEQ MRO_LONG_124
        JMP MA_JOURNAL_DONE
MRO_LONG_124:
        LDA MA_CRC+1
        CMP MA_JOURNAL+253
        BEQ MRO_LONG_125
        JMP MA_JOURNAL_DONE
MRO_LONG_125:
        LDA MA_JOURNAL+254
        CMP #$FF
        BEQ MRO_LONG_126
        JMP MA_JOURNAL_DONE
MRO_LONG_126:
        JSR MA_CHECK_DUPLICATES
        BCS MRO_LONG_127
        JMP MA_JOURNAL_DONE
MRO_LONG_127:
        INC MA_JVALID
MA_JOURNAL_DONE:
        RTS
        INCLUDE "maint-ro-duplicates.inc"

MA_SPACE:
        LDA #' '
        JMP STR8V2_RAM_PUTC
MA_SPACE_NAME:
        CMP #4
        BNE MRO_LONG_128
        JMP MA_NAME_RAM
MRO_LONG_128:
        PHA
        LDA #'B'
        JSR STR8V2_RAM_PUTC
        PLA
        ORA #'0'
        JMP STR8V2_RAM_PUTC
MA_NAME_RAM:
        LDA #'R'
        JMP STR8V2_RAM_PUTC
MA_PRINT:
        STX MA_PTR
        STY MA_PTR+1
        LDY #0
MA_PRINT_NEXT:
        LDA (MA_PTR),Y
        BNE MRO_LONG_129
        JMP MA_PRINT_DONE
MRO_LONG_129:
        JSR STR8V2_RAM_PUTC
        INY
        BEQ MRO_LONG_130
        JMP MA_PRINT_NEXT
MRO_LONG_130:
        INC MA_PTR+1
        JMP MA_PRINT_NEXT
MA_PRINT_DONE:
        RTS
MA_TITLE: DB "STR8N-F MAP 0.3.0 / BASE1 / PR05 / READ ONLY",13,10,0
MA_PROMPT: DB "MAINT RO> ",0
MA_HELP_TEXT:
        DB "M [1|2|3] grid / sectors (default) / wear",13,10
        DB "R src first last  Read 1-4096 bytes into buffer 5000-5FFF",13,10
        DB "D [offset [end]]  Display valid buffer bytes",13,10
        DB "K [src first last]  CRC16 of buffer or range",13,10
        DB "V src first last dst start  Compare; no copy/write",13,10
        DB "Q Restart F; ? Help. src/dst=R or bank 0-3; hex addresses.",13,10
        DB "RAM 2000-64FF; flash 8000-FFFF. R rejects buffer overlap.",13,10
        DB "No write, erase, edit, init, CONFIG-save or execution commands.",13,10,0
MA_BAD_TEXT: DB "REFUSED: command/range/buffer; ? for help",13,10,0
MA_BUFFER_TEXT: DB "BUFFER LOADED; D displays; K CRC; no write command",13,10,0
MA_CRC_TEXT: DB "CRC16=",0
MA_MATCH_TEXT: DB "MATCH",13,10,0
MA_DIFFERENT_TEXT: DB "DIFFERENT AT DEST ",0
MA_GRID_TITLE: DB "   8  9  A  B  C  D  E  F",13,10,0
MA_MAP_LEGEND: DB ".. erased; U+ unknown; W+ known WDC resident; W? possible; F+ running F.",13,10,"WDC marks cover F800-FFFF only, not the whole bank or a tested boot.",13,10,"BASE1: C/D journal, F recovery; all other sectors owner-assigned. READ ONLY.",13,10,0
MA_SEQUENCE_TEXT: DB "SNBT SEQ=",0
MA_DEFAULT_TEXT: DB " DEFAULT=",0
MA_MASK_TEXT: DB " BANKS=",0
MA_UNKNOWN_TEXT: DB " UNKNOWN=",0
MA_NO_JOURNAL_TEXT: DB "SNBT unavailable/ambiguous; wear counts unknown",13,10,0
MA_UNKNOWN_COUNT: DB "??????",0
MA_ROLE_OWNER_TEXT: DB "OWNER IMAGE SPACE",0
MA_ROLE_JOURNAL_TEXT: DB "JOURNAL PROTECTED",0
MA_ROLE_F_TEXT: DB "BOOT-F PROTECTED",0
        INCLUDE "map-recognition.inc"
MA_GUARD_TABLE:
        INCLUDE "maint-ro-ram-guards.inc"
MA_IMAGE_CRC: DW 0
MA_IMM_END:
; Disposable app-owned state, excluded from its immutable-code CRC.
MA_STATE_BEGIN:
MA_HAVE: DB 0
MA_ERROR: DB 0
MA_POS: DB 0
MA_DIGITS: DB 0
MA_SB: DB 0
MA_DB: DB 0
MA_SRC: DW 0
MA_LAST: DW 0
MA_DST: DW 0
MA_COUNT: DW 0
MA_VALUE: DW 0
MA_OFFSET: DW 0
MA_LENGTH: DW 0
MA_CRC: DW 0
MA_COLUMN: DB 0
MA_BYTE: DB 0
MA_VIEW: DB 0
MA_MB: DB 0
MA_MS: DB 0
MA_STATUS: DB 0
MA_MAP_INDEX: DB 0
MA_TABLE_INDEX: DB 0
MA_JVALID: DB 0
MAP_MARK: DB 0
MAP_PROFILE: DB 0
MAP_CPU: DB 0
MAP_RESET: DW 0
MAP_NAME: DW 0
MAP_CATALOG_INDEX: DB 0
MAP_HASH: DS 4
MAP_TERM: DS 4
MA_JOURNAL: DS 256
MA_END:
        ENDMOD
        END
