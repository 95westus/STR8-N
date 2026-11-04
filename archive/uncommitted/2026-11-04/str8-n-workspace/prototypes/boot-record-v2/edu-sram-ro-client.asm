; Matching ES1 inspection client. RAM only; USB qualification target.
        MODULE EDU_SRAM_RO_CLIENT
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "edu-client-params.inc"
EC_PTR EQU $E0
        CODE
EC_START:
        SEI
        CLD
        STZ EC_ERROR
        LDA $7E60
        CMP #'R'
        BNE EC_BAD_GUARD
        LDA $7E61
        CMP #'A'
        BNE EC_BAD_GUARD
        LDA $7E62
        CMP #1
        BNE EC_BAD_GUARD
        LDA $7E63
        CMP #$0D
        BNE EC_BAD_GUARD
        LDA #<EC_START
        STA EC_SRC
        LDA #>EC_START
        STA EC_SRC+1
        LDA #<(EC_IMM_END-EC_START)
        STA EC_COUNT
        LDA #>(EC_IMM_END-EC_START)
        STA EC_COUNT+1
        JSR EC_RAW_CRC
        LDA EC_CRC
        ORA EC_CRC+1
        BNE EC_BAD_GUARD
        STZ EC_SRC
        LDA #$F0
        STA EC_SRC+1
        STZ EC_COUNT
        LDA #$10
        STA EC_COUNT+1
        JSR EC_RAW_CRC
        LDA EC_CRC
        CMP #EC_F_CRC_LO
        BNE EC_BAD_GUARD
        LDA EC_CRC+1
        CMP #EC_F_CRC_HI
        BNE EC_BAD_GUARD
        LDX #0
EC_RAM_GUARD:
        LDA EC_GUARDS,X
        STA EC_SRC
        LDA EC_GUARDS+1,X
        STA EC_SRC+1
        LDA EC_GUARDS+2,X
        STA EC_COUNT
        LDA EC_GUARDS+3,X
        STA EC_COUNT+1
        STX EC_INDEX
        JSR EC_RAW_CRC
        LDX EC_INDEX
        LDA EC_CRC
        CMP EC_GUARDS+4,X
        BNE EC_BAD_GUARD
        LDA EC_CRC+1
        CMP EC_GUARDS+5,X
        BNE EC_BAD_GUARD
        TXA
        CLC
        ADC #6
        TAX
        CPX #12
        BNE EC_RAM_GUARD
        LDX #63
EC_HEADER:
        LDA $8000,X
        CMP EC_EXPECTED_HEADER,X
        BNE EC_UNAVAILABLE
        DEX
        BPL EC_HEADER
        STZ EC_SRC
        LDA #$80
        STA EC_SRC+1
        STZ EC_COUNT
        LDA #$10
        STA EC_COUNT+1
        JSR EC_RAW_CRC
        LDA EC_CRC
        ORA EC_CRC+1
        BNE EC_UNAVAILABLE
        JSR $8004
        BCC EC_UNAVAILABLE
        LDX #<EC_TITLE
        LDY #>EC_TITLE
        JSR EC_PRINT
EC_MENU:
        LDX #<EC_PROMPT
        LDY #>EC_PROMPT
        JSR EC_PRINT
        JSR BOOT_API_LINE
        BCC EC_BAD
        LDA STR8V2_LINE
        CMP #'R'
        BEQ EC_READ
        LDA STR8V2_LINE+1
        BNE EC_BAD
        LDA STR8V2_LINE
        CMP #'S'
        BEQ EC_QUERY
        CMP #'V'
        BEQ EC_VIA
        CMP #'A'
        BEQ EC_PREP
        CMP #'?'
        BEQ EC_HELP
        CMP #'Q'
        BNE EC_BAD
        JMP STR8V2_RAM_RESET
EC_HELP:
        LDX #<EC_HELP_TEXT
        LDY #>EC_HELP_TEXT
        BRA EC_MESSAGE
EC_BAD:
        LDX #<EC_BAD_TEXT
        LDY #>EC_BAD_TEXT
EC_MESSAGE:
        JSR EC_PRINT
        JMP EC_MENU
EC_UNAVAILABLE:
        LDX #<EC_MISSING_TEXT
        LDY #>EC_MISSING_TEXT
        JSR EC_PRINT
        JMP STR8V2_RAM_RESET
EC_BAD_GUARD:
        LDA #1
        STA EC_ERROR
EC_HALT:
        JMP EC_HALT
EC_QUERY:
        JSR $8007
        JSR EC_STATUS
        LDX #<EC_QUERY_TEXT
        LDY #>EC_QUERY_TEXT
        BRA EC_MESSAGE
EC_PREP:
        JSR $800D
        JSR EC_STATUS
        JMP EC_MENU
EC_VIA:
        LDX #<EC_VIA_TEXT
        LDY #>EC_VIA_TEXT
        JSR EC_PRINT
        LDA $7FC2
        JSR STR8V2_RAM_HEX_OUT
        LDA $7FCC
        JSR EC_HEX_SPACE
        LDA $7FCB
        JSR EC_HEX_SPACE
        LDA $7FCD
        JSR EC_HEX_SPACE
        LDA $7FCE
        JSR EC_HEX_SPACE
        JSR STR8V2_RAM_NEWLINE
        JMP EC_MENU
EC_READ:
        LDA STR8V2_LINE+1
        CMP #' '
        BNE EC_BAD
        LDA STR8V2_LINE+7
        CMP #' '
        BNE EC_BAD
        LDA STR8V2_LINE+10
        BNE EC_BAD
        STZ EC_VALUE
        STZ EC_VALUE+1
        STZ EC_VALUE+2
        LDA #2
        STA EC_INDEX
EC_ADDR_DIGIT:
        LDX EC_INDEX
        LDA STR8V2_LINE,X
        JSR EC_NIBBLE
        BCC EC_BAD
        PHA
        LDX #4
EC_SHIFT:
        ASL EC_VALUE
        ROL EC_VALUE+1
        ROL EC_VALUE+2
        DEX
        BNE EC_SHIFT
        PLA
        ORA EC_VALUE
        STA EC_VALUE
        INC EC_INDEX
        LDA EC_INDEX
        CMP #7
        BNE EC_ADDR_DIGIT
        LDA STR8V2_LINE+8
        JSR EC_NIBBLE
        BCC EC_BAD
        ASL A
        ASL A
        ASL A
        ASL A
        STA EC_LENGTH
        LDA STR8V2_LINE+9
        JSR EC_NIBBLE
        BCC EC_BAD
        ORA EC_LENGTH
        STA $6004
        LDA #1
        STA $6000
        LDA EC_VALUE
        STA $6001
        LDA EC_VALUE+1
        STA $6002
        LDA EC_VALUE+2
        STA $6003
        STZ $6005
        LDA #$61
        STA $6006
        STZ $6007
        JSR $800A
        JSR EC_STATUS
        LDA $6008
        BNE EC_MENU
        LDA $6009
        STA EC_LENGTH
        STZ EC_INDEX
EC_DUMP:
        LDX EC_INDEX
        LDA $6100,X
        JSR STR8V2_RAM_HEX_OUT
        LDA #' '
        JSR STR8V2_RAM_PUTC
        INC EC_INDEX
        LDA EC_INDEX
        CMP EC_LENGTH
        BNE EC_DUMP
        JSR STR8V2_RAM_NEWLINE
        JMP EC_MENU
EC_STATUS:
        STA EC_RESULT
        LDX #<EC_STATUS_TEXT
        LDY #>EC_STATUS_TEXT
        JSR EC_PRINT
        LDA EC_RESULT
        JSR STR8V2_RAM_HEX_OUT
        LDA #' '
        JSR STR8V2_RAM_PUTC
        LDA $6009
        JSR STR8V2_RAM_HEX_OUT
        LDA $600A
        JSR EC_HEX_SPACE
        JSR STR8V2_RAM_NEWLINE
        RTS
EC_NIBBLE:
        CMP #'0'
        BCC EC_NOT_HEX
        CMP #('9'+1)
        BCC EC_DECIMAL
        CMP #'A'
        BCC EC_NOT_HEX
        CMP #('F'+1)
        BCS EC_NOT_HEX
        SEC
        SBC #('A'-10)
        SEC
        RTS
EC_DECIMAL:
        SEC
        SBC #'0'
        SEC
        RTS
EC_NOT_HEX:
        CLC
        RTS
EC_HEX_SPACE:
        PHA
        LDA #' '
        JSR STR8V2_RAM_PUTC
        PLA
        JMP STR8V2_RAM_HEX_OUT
EC_PRINT:
        STX EC_PTR
        STY EC_PTR+1
        LDY #0
EC_PRINT_NEXT:
        LDA (EC_PTR),Y
        BEQ EC_PRINT_DONE
        JSR STR8V2_RAM_PUTC
        INY
        BNE EC_PRINT_NEXT
        INC EC_PTR+1
        BRA EC_PRINT_NEXT
EC_PRINT_DONE:
        RTS
        INCLUDE "edu-client-crc.inc"
EC_GUARDS:
        INCLUDE "edu-client-guards.inc"
EC_EXPECTED_HEADER:
        INCLUDE "edu-client-header.inc"
EC_TITLE: DB "ES1 EDU/SRAM READ ONLY / 2609 b15",13,10,0
EC_PROMPT: DB "EDU RO> ",0
EC_HELP_TEXT:
        DB "S software info; V VIA inputs; A acknowledge disabled CB flags",13,10
        DB "R aaaaa nn read 01..40 hex bytes; Q REC",13,10
        DB "No SRAM write, mode change, probe, format or saved EDU switch.",13,10,0
EC_QUERY_TEXT: DB "Configured capacity 00020000; physical presence UNPROVEN; read only",13,10,0
EC_VIA_TEXT: DB "DDR PCR ACR IFR IER: ",0
EC_STATUS_TEXT: DB "STATUS COMPLETED MODE: ",0
EC_BAD_TEXT: DB "REFUSED",13,10,0
EC_MISSING_TEXT: DB "ES1 unavailable or incompatible; returning REC",13,10,0
EC_IMAGE_CRC: DW 0
EC_IMM_END:
EC_SRC: DW 0
EC_COUNT: DW 0
EC_CRC: DW 0
EC_VALUE: DB 0,0,0
EC_INDEX: DB 0
EC_LENGTH: DB 0
EC_RESULT: DB 0
EC_ERROR: DB 0
EC_END:
        ENDMOD
        END
