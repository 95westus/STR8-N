; ROM-resident foreground W65C02 assembler, STR8-N named-app host ABI 1.
 MODULE ASM_APP
 XDEF APP_END
 INCLUDE "str8n-v2-public.inc"
 INCLUDE "layout.inc"
 CODE
 DB "AP",$01,$01
 DW $0000,APP_START,OUTPUT_START,STATE_END-1
 DB $00,$3F
 DW $0000
APP_START:
 SEI
 CLD
 LDA #>SOURCE_START
 STA SRC_END+1
 STZ SRC_END
 STZ RESULT_VALID
 STZ SKIP_LF
 STZ PASTE_MODE
 LDX #<BANNER
 LDY #>BANNER
 JSR PRINT
 JMP SHELL
 SHELL:
 LDX #<PROMPT
 LDY #>PROMPT
 JSR PRINT
 STZ ERROR
 STZ LINENO
 STZ LINENO+1
 JSR READ_LINE
 LDA ERROR
                        BEQ BM_LONG_32
                        JMP SHELL_ERROR
BM_LONG_32:
 LDX #$00
 JSR SPACES
                        BEQ SHELL
 CMP #'0'
                        BCC SHELL_COMMAND
 CMP #'9'+1
                        BCS SHELL_COMMAND
 JSR EDIT_LINE
 LDA ERROR
                        BEQ BM_LONG_42
                        JMP SHELL_ERROR
BM_LONG_42:
 JMP SHELL
SHELL_COMMAND:
 CMP #'?'
                        BNE SHELL_WORD
 INX
 JSR END_LINE
 LDA ERROR
                        BEQ BM_LONG_50
                        JMP SHELL_ERROR
BM_LONG_50:
 LDX #<HELP
 LDY #>HELP
 JSR PRINT
 JMP SHELL
SHELL_WORD:
 JSR READ_TOKEN
 JSR END_LINE
 LDA ERROR
                        BEQ BM_LONG_59
                        JMP SHELL_ERROR
BM_LONG_59:
 LDA TOKEN
 CMP #'N'
                        BNE SHELL_NOT_NEW
 LDX #<CMD_NEW
 LDY #>CMD_NEW
 JSR MATCH_TOKEN
                        BCS BM_LONG_66
                        JMP SHELL_BAD
BM_LONG_66:
 LDA #>SOURCE_START
 STA SRC_END+1
 STZ SRC_END
 STZ RESULT_VALID
 JMP SHELL
SHELL_NOT_NEW:
 CMP #'L'
                        BNE SHELL_NOT_LIST
 LDX #<CMD_LIST
 LDY #>CMD_LIST
 JSR MATCH_TOKEN
                        BCS BM_LONG_78
                        JMP SHELL_BAD
BM_LONG_78:
 JSR LIST_SOURCE
 JMP SHELL
SHELL_NOT_LIST:
 CMP #'A'
                        BNE SHELL_NOT_ASM
 LDX #<CMD_ASM
 LDY #>CMD_ASM
 JSR MATCH_TOKEN
                        BCS BM_LONG_87
                        JMP SHELL_BAD
BM_LONG_87:
 JSR ASM_ASSEMBLE
                        BCC BM_LONG_89
                        JMP SHELL_ERROR
BM_LONG_89:
 LDX #<OK_TEXT
 LDY #>OK_TEXT
 JSR PRINT
 LDA RESULT_LEN
 STA VAL
 LDA RESULT_LEN+1
 STA VAL+1
 JSR DECIMAL_OUT
 LDX #<ORIGIN_TEXT
 LDY #>ORIGIN_TEXT
 JSR PRINT
 LDA RESULT_ORIGIN+1
 JSR STR8V2_RAM_HEX_OUT
 LDA RESULT_ORIGIN
 JSR STR8V2_RAM_HEX_OUT
 LDX #<BUFFER_TEXT
 LDY #>BUFFER_TEXT
 JSR PRINT
 JSR SAVE_SUMMARY
 JMP SHELL
SHELL_NOT_ASM:
 CMP #'D'
                        BNE SHELL_NOT_DUMP
 LDX #<CMD_DUMP
 LDY #>CMD_DUMP
 JSR MATCH_TOKEN
                        BCC SHELL_BAD
 JSR REQUIRE_RESULT
                        BCC BM_LONG_118
                        JMP SHELL
BM_LONG_118:
 JSR DUMP_OUTPUT
 JMP SHELL
SHELL_NOT_DUMP:
 CMP #'S'
                        BNE SHELL_NOT_S19
 LDX #<CMD_S19
 LDY #>CMD_S19
 JSR MATCH_TOKEN
                        BCC SHELL_BAD
 JSR REQUIRE_RESULT
                        BCC BM_LONG_129
                        JMP SHELL
BM_LONG_129:
 JSR S19_OUTPUT
 JMP SHELL
SHELL_NOT_S19:
 CMP #'P'
                        BNE SHELL_NOT_PASTE
 LDX #<CMD_PASTE
 LDY #>CMD_PASTE
 JSR MATCH_TOKEN
                        BCC SHELL_BAD
 JSR PASTE_SOURCE
 LDA ERROR
                        BNE SHELL_ERROR
 JMP SHELL
SHELL_NOT_PASTE:
 CMP #'Q'
                        BNE SHELL_BAD
 LDX #<CMD_QUIT
 LDY #>CMD_QUIT
 JSR MATCH_TOKEN
                        BCC SHELL_BAD
 JMP STR8V2_RAM_HOLD
SHELL_BAD:
 LDA #E_SYNTAX
 STA ERROR
SHELL_ERROR:
 JSR REPORT_ERROR
 JMP SHELL

; Console routines preserve parser X/Y except READ_LINE and DECIMAL_OUT.
PUTC:
 PHX
 PHY
 JSR STR8V2_RAM_PUTC
 PLY
 PLX
 RTS
PRINT:
 STX TEMP
 STY TEMP+1
 LDY #$00
PRINT_LOOP:
 LDA (TEMP),Y
                        BEQ PRINT_END
 JSR PUTC
 INY
                        JMP PRINT_LOOP
PRINT_END:
 RTS
READ_LINE:
 LDX #$00
 STZ LINE_LEN
READ_CHAR:
 JSR STR8V2_RAM_GETC
 CMP #$03
                        BEQ READ_CANCEL
 CMP #$0A
                        BNE READ_NOT_LF
 LDA SKIP_LF
                        BNE READ_CHAR
 LDA #$0A
READ_NOT_LF:
 STZ SKIP_LF
 CMP #$0D
                        BEQ READ_CR
 CMP #$0A
                        BEQ READ_DONE
 CMP #$08
                        BEQ READ_BACK
 CMP #$7F
                        BEQ READ_BACK
 CMP #$09
                        BNE READ_PRINTABLE
 LDA #' '
READ_PRINTABLE:
 CMP #$20
                        BCC READ_CHAR
 CMP #$7F
                        BCS READ_CHAR
 CPX #LINE_MAX
                        BCS READ_OVERFLOW
 STA LINE,X
 INX
 LDY PASTE_MODE
                        BNE READ_CHAR
 JSR PUTC
                        JMP READ_CHAR
READ_OVERFLOW:
 LDA #E_LINE
 STA ERROR
                        JMP READ_CHAR
READ_BACK:
 CPX #$00
                        BEQ READ_CHAR
 DEX
 LDA PASTE_MODE
                        BNE READ_CHAR
 LDA #$08
 JSR PUTC
 LDA #' '
 JSR PUTC
 LDA #$08
 JSR PUTC
                        JMP READ_CHAR
READ_CR:
 INC SKIP_LF
READ_DONE:
 STX LINE_LEN
 STZ LINE,X
 LDA PASTE_MODE
                        BNE READ_PASTE_DONE
 JSR STR8V2_RAM_NEWLINE
READ_PASTE_DONE:
 RTS
READ_CANCEL:
 LDA #E_CANCEL
 STA ERROR
                        JMP READ_DONE

MATCH_TOKEN:
 STX TEMP
 STY TEMP+1
 LDY #$00
MATCH_LOOP:
 LDA (TEMP),Y
 CMP TOKEN,Y
                        BNE MATCH_FAIL
 CMP #$00
                        BEQ MATCH_OK
 INY
                        JMP MATCH_LOOP
MATCH_OK:
 SEC
 RTS
MATCH_FAIL:
 CLC
 RTS

DECIMAL_OUT:
 LDX #$00
 STZ SAVE
DECIMAL_DIGIT:
 STZ DIGIT
DECIMAL_SUB:
 SEC
 LDA VAL
 SBC DECIMAL_POWERS,X
 STA NUMBER
 LDA VAL+1
 SBC DECIMAL_POWERS+1,X
                        BCC DECIMAL_PRINT
 STA VAL+1
 LDA NUMBER
 STA VAL
 INC DIGIT
                        JMP DECIMAL_SUB
DECIMAL_PRINT:
 LDA DIGIT
                        BNE DECIMAL_NONZERO
 LDA SAVE
                        BNE DECIMAL_NONZERO
 CPX #$08
                        BNE DECIMAL_NEXT
DECIMAL_NONZERO:
 INC SAVE
 LDA DIGIT
 CLC
 ADC #'0'
 JSR PUTC
DECIMAL_NEXT:
 INX
 INX
 CPX #$0A
                        BNE DECIMAL_DIGIT
 RTS
DECIMAL_POWERS:
 DW 10000,1000,100,10,1

REPORT_ERROR:
 LDX #<ERROR_TEXT
 LDY #>ERROR_TEXT
 JSR PRINT
 LDA LINENO
 STA VAL
 LDA LINENO+1
 STA VAL+1
 JSR DECIMAL_OUT
 LDA #':'
 JSR PUTC
 LDA #' '
 JSR PUTC
 LDA ERROR
 DEC A
 ASL A
 TAX
 LDA ERROR_MESSAGES,X
 PHA
 LDY ERROR_MESSAGES+1,X
 PLX
 JSR PRINT
 JMP STR8V2_RAM_NEWLINE
REQUIRE_RESULT:
 LDA RESULT_VALID
                        BNE RESULT_OK
 LDX #<NO_RESULT
 LDY #>NO_RESULT
 JSR PRINT
 SEC
 RTS
RESULT_OK:
 CLC
 RTS
OUTPUT_SETUP:
 STZ PTR
 LDA #>OUTPUT_START
 STA PTR+1
 LDA RESULT_LEN
 STA ENDPTR
 CLC
 LDA RESULT_LEN+1
 ADC #>OUTPUT_START
 STA ENDPTR+1
 LDA RESULT_ORIGIN
 STA PC
 LDA RESULT_ORIGIN+1
 STA PC+1
 RTS
OUTPUT_MORE:
 LDA PTR+1
 CMP ENDPTR+1
                        BNE OUTPUT_MORE_YES
 LDA PTR
 CMP ENDPTR
OUTPUT_MORE_YES:
 RTS

; Report physical, inclusive RAM bounds. A runnable Store suggestion is
; only valid when the logical origin matches the physical output buffer.
; ENDPTR is scratch; OUTPUT_SETUP refreshes it for DUMP/S19.
SAVE_SUMMARY:
 LDA RESULT_LEN
 ORA RESULT_LEN+1
                        BEQ SAVE_EMPTY
 JSR OUTPUT_SETUP
 SEC
 LDA ENDPTR
 SBC #1
 STA ENDPTR
 LDA ENDPTR+1
 SBC #0
 STA ENDPTR+1
 LDX #<RAM_RANGE_TEXT
 LDY #>RAM_RANGE_TEXT
 JSR PRINT
 JSR SAVE_END_OUT
 JSR STR8V2_RAM_NEWLINE
 LDA RESULT_ORIGIN
 CMP #<OUTPUT_START
                        BNE SAVE_RELOCATED
 LDA RESULT_ORIGIN+1
 CMP #>OUTPUT_START
                        BNE SAVE_RELOCATED
 LDX #<SAVE_HINT_TEXT
 LDY #>SAVE_HINT_TEXT
 JSR PRINT
 LDX #<SAVE_COMMAND_TEXT
 LDY #>SAVE_COMMAND_TEXT
 JSR PRINT
 JSR SAVE_END_OUT
 LDX #<SAVE_NAME_TEXT
 LDY #>SAVE_NAME_TEXT
 JMP PRINT
SAVE_END_OUT:
 LDA ENDPTR+1
 JSR STR8V2_RAM_HEX_OUT
 LDA ENDPTR
 JMP STR8V2_RAM_HEX_OUT
SAVE_EMPTY:
 LDX #<EMPTY_TEXT
 LDY #>EMPTY_TEXT
 JMP PRINT
SAVE_RELOCATED:
 LDX #<RELOCATED_TEXT
 LDY #>RELOCATED_TEXT
 JMP PRINT

DUMP_OUTPUT:
 JSR OUTPUT_SETUP
DUMP_ROW:
 JSR OUTPUT_MORE
                        BEQ DUMP_DONE
 LDA PC+1
 JSR STR8V2_RAM_HEX_OUT
 LDA PC
 JSR STR8V2_RAM_HEX_OUT
 LDA #':'
 JSR PUTC
 LDX #$10
DUMP_BYTE:
 LDA #' '
 JSR PUTC
 LDA (PTR)
 PHX
 JSR STR8V2_RAM_HEX_OUT
 PLX
 JSR OUTPUT_ADVANCE
 JSR OUTPUT_MORE
                        BEQ DUMP_NEWLINE
 DEX
                        BNE DUMP_BYTE
DUMP_NEWLINE:
 JSR STR8V2_RAM_NEWLINE
 JSR STR8V2_RAM_CHECK_CANCEL
                        BCC DUMP_ROW
DUMP_DONE:
 RTS
OUTPUT_ADVANCE:
 INC PTR
                        BNE OUTPUT_PC
 INC PTR+1
OUTPUT_PC:
 INC PC
                        BNE OUTPUT_ADVANCE_DONE
 INC PC+1
OUTPUT_ADVANCE_DONE:
 RTS

S19_OUTPUT:
 JSR OUTPUT_SETUP
S19_ROW:
 JSR OUTPUT_MORE
                        BEQ S19_FINISH
 SEC
 LDA ENDPTR
 SBC PTR
 STA SREC_COUNT
 LDA ENDPTR+1
 SBC PTR+1
                        BNE S19_FULL
 LDA SREC_COUNT
 CMP #$11
                        BCC S19_COUNT
S19_FULL:
 LDA #$10
 STA SREC_COUNT
S19_COUNT:
 LDA #'S'
 JSR PUTC
 LDA #'1'
 JSR PUTC
 STZ SREC_SUM
 LDA SREC_COUNT
 CLC
 ADC #$03
 JSR S19_HEX
 LDA PC+1
 JSR S19_HEX
 LDA PC
 JSR S19_HEX
S19_DATA:
 LDA (PTR)
 JSR S19_HEX
 JSR OUTPUT_ADVANCE
 DEC SREC_COUNT
                        BNE S19_DATA
 JSR S19_CHECKSUM
 JSR STR8V2_RAM_CHECK_CANCEL
                        BCC S19_ROW
 RTS
S19_FINISH:
 LDA #'S'
 JSR PUTC
 LDA #'9'
 JSR PUTC
 STZ SREC_SUM
 LDA #$03
 JSR S19_HEX
 LDA RESULT_ORIGIN+1
 JSR S19_HEX
 LDA RESULT_ORIGIN
 JSR S19_HEX
S19_CHECKSUM:
 LDA SREC_SUM
 EOR #$FF
 JSR STR8V2_RAM_HEX_OUT
 JMP STR8V2_RAM_NEWLINE
S19_HEX:
 PHA
 CLC
 ADC SREC_SUM
 STA SREC_SUM
 PLA
 JMP STR8V2_RAM_HEX_OUT

BANNER: DB $0D,$0A,"STR8-N ASM 0.5 / 65C02",$0D,$0A,0
PROMPT: DB "ASM> ",0
HELP: DB "number text: insert/replace; number: delete",$0D,$0A
 DB "NEW PASTE LIST ASM DUMP S19 QUIT ?",$0D,$0A
 DB "Labels: name:  Constants: name = value",$0D,$0A
 DB "ORG BYTE WORD TEXT FILL END (optional dot)",$0D,$0A
 DB "ORG address[,fill] (default fill $00)",$0D,$0A
 DB "Local .name: belongs to preceding global label",$0D,$0A,0
CMD_NEW: DB "NEW",0
CMD_LIST: DB "LIST",0
CMD_ASM: DB "ASM",0
CMD_DUMP: DB "DUMP",0
CMD_S19: DB "S19",0
CMD_PASTE: DB "PASTE",0
CMD_QUIT: DB "QUIT",0
OK_TEXT: DB "OK ",0
ORIGIN_TEXT: DB " bytes, origin $",0
BUFFER_TEXT: DB ", buffer $0200",$0D,$0A,0
RAM_RANGE_TEXT: DB "RAM $0200-$",0
SAVE_HINT_TEXT: DB "After QUIT; change bank/name as needed:",$0D,$0A,0
SAVE_COMMAND_TEXT: DB "S 1 AUTO 0200 ",0
SAVE_NAME_TEXT: DB " PROGRAM",$0D,$0A,0
EMPTY_TEXT: DB "RAM empty; nothing to save.",$0D,$0A,0
RELOCATED_TEXT: DB "ORG differs; use S19/load at origin before Store.",$0D,$0A,0
ERROR_TEXT: DB "Error line ",0
NO_RESULT: DB "Assemble successfully first",$0D,$0A,0
ERROR_MESSAGES:
 DW ERR_SYNTAX,ERR_OPCODE,ERR_UNDEFINED,ERR_DUPLICATE,ERR_RANGE,ERR_BRANCH
 DW ERR_SOURCE,ERR_SYMBOLS,ERR_OUTPUT,ERR_PHASE,ERR_LINE,ERR_DEPTH,ERR_CANCEL,ERR_LAYOUT,ERR_SCOPE
ERR_SYNTAX: DB "Syntax",0
ERR_OPCODE: DB "Unknown instruction or mode",0
ERR_UNDEFINED: DB "Undefined symbol",0
ERR_DUPLICATE: DB "Duplicate symbol",0
ERR_RANGE: DB "Value out of range",0
ERR_BRANCH: DB "Branch out of range",0
ERR_SOURCE: DB "Source full",0
ERR_SYMBOLS: DB "Symbols full",0
ERR_OUTPUT: DB "Output full",0
ERR_PHASE: DB "Layout changed between passes",0
ERR_LINE: DB "Line too long",0
ERR_DEPTH: DB "Expression too deep",0
ERR_CANCEL: DB "Cancelled",0
ERR_LAYOUT: DB "Layout value must be defined earlier",0
ERR_SCOPE: DB "Local needs preceding global label",0

 ; Packed sorted records: decimal line number (word), text length, pass-1 mode,
; then text bytes. Header size is 4; no per-record terminator is stored.
EDIT_LINE:
 LDA #$0A
 STA RADIX
 JSR READ_NUMBER
 LDA ERROR
                        BEQ BM_LONG_575
                        JMP EDIT_RETURN
BM_LONG_575:
 LDA VAL
 STA LINENO
 LDA VAL+1
 STA LINENO+1
 ORA VAL
                        BNE BM_LONG_581
                        JMP EDIT_SYNTAX
BM_LONG_581:
 LDA LINE,X
                        BEQ EDIT_TEXT
 CMP #' '
                        BEQ BM_LONG_585
                        JMP EDIT_SYNTAX
BM_LONG_585:
EDIT_TEXT:
 JSR SPACES
EDIT_BUFFER:
 STX TEXT_POS
 SEC
 LDA LINE_LEN
 SBC TEXT_POS
                        BEQ EDIT_DELETE
 CLC
 ADC #$04
EDIT_DELETE:
 STA NEWLEN
 STZ OLDLEN
 STZ PTR
 LDA #>SOURCE_START
 STA PTR+1
EDIT_FIND:
 JSR PTR_AT_END
                        BEQ EDIT_CAPACITY
 LDY #$01
 LDA (PTR),Y
 CMP LINENO+1
                        BCC EDIT_NEXT
                        BNE EDIT_CAPACITY
 DEY
 LDA (PTR),Y
 CMP LINENO
                        BCC EDIT_NEXT
                        BNE EDIT_CAPACITY
 LDY #$02
 LDA (PTR),Y
 CLC
 ADC #$04
 STA OLDLEN
                        JMP EDIT_CAPACITY
EDIT_NEXT:
 LDY #$02
 LDA (PTR),Y
 CLC
 ADC #$04
 JSR PTR_ADD
                        JMP EDIT_FIND
EDIT_CAPACITY:
 SEC
 LDA SRC_END
 SBC OLDLEN
 STA TEMP
 LDA SRC_END+1
 SBC #$00
 STA TEMP+1
 CLC
 LDA TEMP
 ADC NEWLEN
 STA ENDPTR
 LDA TEMP+1
 ADC #$00
 STA ENDPTR+1
 CMP #>SOURCE_END
                        BCC EDIT_REMOVE
                        BEQ BM_LONG_645
                        JMP EDIT_FULL
BM_LONG_645:
 LDA ENDPTR
                        BEQ BM_LONG_647
                        JMP EDIT_FULL
BM_LONG_647:
EDIT_REMOVE:
 ; Nothing has changed until all capacity checks have passed.
 STZ RESULT_VALID
 LDA PTR
 STA NEXT
 LDA PTR+1
 STA NEXT+1
 CLC
 LDA NEXT
 ADC OLDLEN
 STA NEXT
                        BCC EDIT_REMOVE_PTR
 INC NEXT+1
EDIT_REMOVE_PTR:
 LDA PTR
 STA TEMP
 LDA PTR+1
 STA TEMP+1
EDIT_REMOVE_LOOP:
 LDA NEXT+1
 CMP SRC_END+1
                        BNE EDIT_COPY_DOWN
 LDA NEXT
 CMP SRC_END
                        BEQ EDIT_REMOVED
EDIT_COPY_DOWN:
 LDA (NEXT)
 STA (TEMP)
 INC NEXT
                        BNE EDIT_NEXT_UP
 INC NEXT+1
EDIT_NEXT_UP:
 INC TEMP
                        BNE EDIT_REMOVE_LOOP
 INC TEMP+1
                        JMP EDIT_REMOVE_LOOP
EDIT_REMOVED:
 LDA TEMP
 STA SRC_END
 LDA TEMP+1
 STA SRC_END+1
 LDA NEWLEN
                        BEQ EDIT_RETURN
 LDA ENDPTR
 STA NEXT
 LDA ENDPTR+1
 STA NEXT+1
EDIT_INSERT_LOOP:
 LDA TEMP+1
 CMP PTR+1
                        BNE EDIT_COPY_UP
 LDA TEMP
 CMP PTR
                        BEQ EDIT_INSERTED
EDIT_COPY_UP:
 JSR DEC_TEMP
 LDA NEXT
                        BNE EDIT_DEC_NEXT
 DEC NEXT+1
EDIT_DEC_NEXT:
 DEC NEXT
 LDA (TEMP)
 STA (NEXT)
                        JMP EDIT_INSERT_LOOP
EDIT_INSERTED:
 LDA ENDPTR
 STA SRC_END
 LDA ENDPTR+1
 STA SRC_END+1
 LDY #$00
 LDA LINENO
 STA (PTR),Y
 INY
 LDA LINENO+1
 STA (PTR),Y
 INY
 SEC
 LDA NEWLEN
 SBC #$04
 STA (PTR),Y
 INY
 LDA #$00
 STA (PTR),Y
 LDY #$04
 LDX TEXT_POS
EDIT_WRITE_TEXT:
 LDA LINE,X
 STA (PTR),Y
 INX
 INY
 CPX LINE_LEN
                        BNE EDIT_WRITE_TEXT
EDIT_RETURN:
 RTS
EDIT_SYNTAX:
 LDA #E_SYNTAX
 STA ERROR
 RTS
EDIT_FULL:
 LDA #E_SOURCE
 STA ERROR
 RTS
PTR_AT_END:
 LDA PTR+1
 CMP SRC_END+1
                        BNE PTR_END_RETURN
 LDA PTR
 CMP SRC_END
PTR_END_RETURN:
 RTS
PTR_ADD:
 CLC
 ADC PTR
 STA PTR
                        BCC PTR_ADD_RETURN
 INC PTR+1
PTR_ADD_RETURN:
 RTS
DEC_TEMP:
 LDA TEMP
                        BNE DEC_TEMP_LOW
 DEC TEMP+1
DEC_TEMP_LOW:
 DEC TEMP
 RTS

LIST_SOURCE:
 STZ REC
 LDA #>SOURCE_START
 STA REC+1
LIST_RECORD:
 JSR REC_AT_END
                        BEQ LIST_DONE
 JSR LOAD_RECORD
 LDA ERROR
                        BNE LIST_DONE
 LDA LINENO
 STA VAL
 LDA LINENO+1
 STA VAL+1
 JSR DECIMAL_OUT
 LDA #' '
 JSR PUTC
 LDX #$00
LIST_TEXT:
 LDA LINE,X
                        BEQ LIST_LINE_END
 JSR PUTC
 INX
                        JMP LIST_TEXT
LIST_LINE_END:
 JSR STR8V2_RAM_NEWLINE
 JSR NEXT_RECORD
 JSR STR8V2_RAM_CHECK_CANCEL
                        BCC LIST_RECORD
LIST_DONE:
 RTS
REC_AT_END:
 LDA REC+1
 CMP SRC_END+1
                        BNE REC_END_RETURN
 LDA REC
 CMP SRC_END
REC_END_RETURN:
 RTS
LOAD_RECORD:
 ; Validate a complete header and text span before any source fetch.
 CLC
 LDA REC
 ADC #$04
 STA NEXT
 LDA REC+1
 ADC #$00
 STA NEXT+1
 JSR CHECK_NEXT_BOUND
                        BCS RECORD_BAD
 LDY #$00
 LDA (REC),Y
 STA LINENO
 INY
 LDA (REC),Y
 STA LINENO+1
 INY
 LDA (REC),Y
 STA LINE_LEN
 CMP #LINE_MAX+1
                        BCS RECORD_BAD
 CLC
 ADC NEXT
 STA NEXT
                        BCC RECORD_NEXT_OK
 INC NEXT+1
RECORD_NEXT_OK:
 JSR CHECK_NEXT_BOUND
                        BCS RECORD_BAD
 LDX #$00
 LDY #$04
RECORD_COPY:
 CPX LINE_LEN
                        BEQ RECORD_COPIED
 LDA (REC),Y
 STA LINE,X
 INX
 INY
                        JMP RECORD_COPY
RECORD_COPIED:
 STZ LINE,X
 RTS
RECORD_BAD:
 LDA #E_SYNTAX
 STA ERROR
 RTS
CHECK_NEXT_BOUND:
 LDA NEXT+1
 CMP SRC_END+1
                        BCC NEXT_BOUND_OK
                        BNE NEXT_BOUND_BAD
 LDA NEXT
 CMP SRC_END
                        BCC NEXT_BOUND_OK
                        BEQ NEXT_BOUND_OK
NEXT_BOUND_BAD:
 SEC
 RTS
NEXT_BOUND_OK:
 CLC
 RTS
NEXT_RECORD:
 LDY #$02
 LDA (REC),Y
 CLC
 ADC #$04
 CLC
 ADC REC
 STA NEXT
 LDA REC+1
 ADC #$00
 STA NEXT+1
 LDA NEXT
 STA REC
 LDA NEXT+1
 STA REC+1
 RTS

; PASTE appends ordinary, unnumbered source in steps of ten. No per-character
; echo or per-line prompt: avoid filling the console RX queue during a paste.
PASTE_SOURCE:
 STZ REC
 LDA #>SOURCE_START
 STA REC+1
 STZ VAL
 STZ VAL+1
PASTE_FIND_LAST:
 JSR REC_AT_END
                        BEQ PASTE_NUMBER
 LDY #$00
 LDA (REC),Y
 STA VAL
 INY
 LDA (REC),Y
 STA VAL+1
 JSR NEXT_RECORD
                        JMP PASTE_FIND_LAST
PASTE_NUMBER:
 CLC
 LDA VAL
 ADC #$0A
 STA PASTE_NUM
 LDA VAL+1
 ADC #$00
 STA PASTE_NUM+1
                        BCC BM_LONG_919
                        JMP PASTE_NUMBER_BAD
BM_LONG_919:
 LDX #<PASTE_TEXT
 LDY #>PASTE_TEXT
 JSR PRINT
 INC PASTE_MODE
 STZ PASTE_ERROR
PASTE_LINE:
 STZ ERROR
 LDA PASTE_NUM
 STA LINENO
 LDA PASTE_NUM+1
 STA LINENO+1
 JSR READ_LINE
 LDA ERROR
 CMP #E_CANCEL
                        BEQ PASTE_CANCELLED
 LDA LINE
 CMP #'.'
                        BNE PASTE_STORE
 LDA LINE+1
                        BEQ PASTE_DONE
PASTE_STORE:
 LDA PASTE_ERROR
                        BNE PASTE_LINE
 LDA ERROR
                        BNE PASTE_SAVE_ERROR
 LDA LINE_LEN
                        BEQ PASTE_LINE
 LDX #$00
 JSR EDIT_BUFFER
 LDA ERROR
                        BNE PASTE_SAVE_ERROR
 CLC
 LDA PASTE_NUM
 ADC #$0A
 STA PASTE_NUM
 LDA PASTE_NUM+1
 ADC #$00
 STA PASTE_NUM+1
                        BCC PASTE_LINE
 LDA #E_RANGE
 STA ERROR
PASTE_SAVE_ERROR:
 STA PASTE_ERROR
 LDA LINENO
 STA PASTE_ERROR_LINE
 LDA LINENO+1
 STA PASTE_ERROR_LINE+1
                        JMP PASTE_LINE
PASTE_DONE:
 STZ PASTE_MODE
 JSR STR8V2_RAM_NEWLINE
 LDA PASTE_ERROR
 STA ERROR
                        BEQ PASTE_RETURN
 LDA PASTE_ERROR_LINE
 STA LINENO
 LDA PASTE_ERROR_LINE+1
 STA LINENO+1
PASTE_RETURN:
 RTS
PASTE_CANCELLED:
 STZ PASTE_MODE
 JSR STR8V2_RAM_NEWLINE
 LDA #E_CANCEL
 STA ERROR
 RTS
PASTE_NUMBER_BAD:
 LDA #E_RANGE
 STA ERROR
 RTS
PASTE_TEXT: DB "Paste source; . ends, Ctrl-C cancels",$0D,$0A,0

 ; Callable engine: source records in SOURCE_START..SRC_END, no console input.
; C=0 success (RESULT_VALID=1); C=1 error (ERROR, LINENO identify failure).
ASM_ASSEMBLE:
 STZ RESULT_VALID
 STZ RESULT_LEN
 STZ RESULT_LEN+1
 STZ ERROR
 STZ LINENO
 STZ LINENO+1
 STZ SYMTOP
 LDA #>SYMBOL_START
 STA SYMTOP+1
 LDA #$01
 STA PASS
 LDA SRC_END+1
 CMP #>SOURCE_START
                        BCC ASSEMBLE_SOURCE_BAD
 CMP #>SOURCE_END
                        BCC ASSEMBLE_PASS
                        BNE ASSEMBLE_SOURCE_BAD
 LDA SRC_END
                        BNE ASSEMBLE_SOURCE_BAD
ASSEMBLE_PASS:
 STZ SCOPE_ID
 STZ SCOPE_VALID
 STZ BASESET
 STZ PCFULL
 STZ ASSEMBLY_END
 STZ PC
 STZ OUTPTR
 LDA #>OUTPUT_START
 STA PC+1
 STA OUTPTR+1
 STZ REC
 LDA #>SOURCE_START
 STA REC+1
ASSEMBLE_RECORD:
 JSR REC_AT_END
                        BEQ ASSEMBLE_PASS_DONE
 JSR LOAD_RECORD
 LDA ERROR
                        BNE ASSEMBLE_FAILED
 JSR ASSEMBLE_LINE
 LDA ERROR
                        BNE ASSEMBLE_FAILED
 LDA ASSEMBLY_END
                        BNE ASSEMBLE_PASS_DONE
 JSR STR8V2_RAM_CHECK_CANCEL
                        BCS ASSEMBLE_CANCEL
 JSR NEXT_RECORD
                        JMP ASSEMBLE_RECORD
ASSEMBLE_PASS_DONE:
 LDA PASS
 CMP #$02
                        BEQ ASSEMBLE_SUCCESS
 INC PASS
                        JMP ASSEMBLE_PASS
ASSEMBLE_SUCCESS:
 LDA BASESET
                        BNE ASSEMBLE_RESULT
 LDA PC
 STA RESULT_ORIGIN
 LDA PC+1
 STA RESULT_ORIGIN+1
ASSEMBLE_RESULT:
 LDA OUTPTR
 STA RESULT_LEN
 SEC
 LDA OUTPTR+1
 SBC #>OUTPUT_START
 STA RESULT_LEN+1
 LDA #$01
 STA RESULT_VALID
 CLC
 RTS
ASSEMBLE_SOURCE_BAD:
 LDA #E_SOURCE
 STA ERROR
                        JMP ASSEMBLE_FAILED
ASSEMBLE_CANCEL:
 LDA #E_CANCEL
 STA ERROR
ASSEMBLE_FAILED:
 SEC
 RTS

ASSEMBLE_LINE:
 LDX #$00
 JSR SPACES
                        BNE BM_LONG_1081
                        JMP CORE_RETURN
BM_LONG_1081:
 CMP #';'
                        BNE BM_LONG_1083
                        JMP CORE_RETURN
BM_LONG_1083:
CORE_FIRST_TOKEN:
 JSR READ_SYMBOL_TOKEN
 LDA ERROR
                        BEQ BM_LONG_1087
                        JMP CORE_RETURN
BM_LONG_1087:
 JSR SPACES
 CMP #':'
                        BEQ CORE_LABEL
 CMP #'='
                        BEQ CORE_CONSTANT
                        JMP CORE_COMMAND
CORE_LABEL:
 JSR FIND_SYMBOL
 LDA ERROR
                        BEQ BM_LONG_1097
                        JMP CORE_RETURN
BM_LONG_1097:
 LDA PC
 STA VAL
 LDA PC+1
 STA VAL+1
 JSR DEFINE_SYMBOL
 LDA ERROR
                        BEQ BM_LONG_1104
                        JMP CORE_RETURN
BM_LONG_1104:
 LDA TOKEN_LOCAL
                        BNE CORE_LABEL_SCOPED
 LDA SYMBOL_INDEX
 STA SCOPE_ID
 LDA #$01
 STA SCOPE_VALID
CORE_LABEL_SCOPED:
 INX
 JSR SPACES
                        BNE BM_LONG_1114
                        JMP CORE_RETURN
BM_LONG_1114:
 CMP #';'
                        BNE BM_LONG_1116
                        JMP CORE_RETURN
BM_LONG_1116:
 CMP #'.'
                        BNE CORE_LABEL_COMMAND
 INX
CORE_LABEL_COMMAND:
 JSR READ_TOKEN
 LDA ERROR
                        BEQ BM_LONG_1123
                        JMP CORE_RETURN
BM_LONG_1123:
                        JMP CORE_COMMAND
CORE_CONSTANT:
 JSR FIND_SYMBOL
 LDA ERROR
                        BEQ BM_LONG_1128
                        JMP CORE_RETURN
BM_LONG_1128:
 LDA SYMPTR
 STA DEF_PTR
 LDA SYMPTR+1
 STA DEF_PTR+1
 INX
 JSR EXPRESSION
 LDA UNRES
                        BEQ BM_LONG_1136
                        JMP CORE_LAYOUT_BAD
BM_LONG_1136:
 JSR END_LINE
 LDA ERROR
                        BEQ BM_LONG_1139
                        JMP CORE_RETURN
BM_LONG_1139:
 LDA DEF_PTR
 STA SYMPTR
 LDA DEF_PTR+1
 STA SYMPTR+1
 JMP DEFINE_SYMBOL
CORE_COMMAND:
 STX OPPOS
 LDA TOKEN
 CMP #'O'
                        BNE CORE_NOT_ORG
 PHX
 LDX #<DIR_ORG
 LDY #>DIR_ORG
 JSR MATCH_TOKEN
 PLX
                        BCC BM_LONG_1155
                        JMP CORE_ORG
BM_LONG_1155:
CORE_NOT_ORG:
 LDA TOKEN
 CMP #'B'
                        BNE CORE_NOT_BYTE
 PHX
 LDX #<DIR_BYTE
 LDY #>DIR_BYTE
 JSR MATCH_TOKEN
 PLX
                        BCC BM_LONG_1165
                        JMP CORE_BYTE
BM_LONG_1165:
CORE_NOT_BYTE:
 LDA TOKEN
 CMP #'W'
                        BNE CORE_NOT_WORD
 PHX
 LDX #<DIR_WORD
 LDY #>DIR_WORD
 JSR MATCH_TOKEN
 PLX
                        BCC BM_LONG_1175
                        JMP CORE_WORD
BM_LONG_1175:
CORE_NOT_WORD:
 LDA TOKEN
 CMP #'T'
                        BNE CORE_NOT_TEXT
 PHX
 LDX #<DIR_TEXT
 LDY #>DIR_TEXT
 JSR MATCH_TOKEN
 PLX
                        BCC BM_LONG_1185
                        JMP CORE_BYTE
BM_LONG_1185:
CORE_NOT_TEXT:
 LDA TOKEN
 CMP #'F'
                        BNE CORE_NOT_FILL
 PHX
 LDX #<DIR_FILL
 LDY #>DIR_FILL
 JSR MATCH_TOKEN
 PLX
                        BCC BM_LONG_1195
                        JMP CORE_FILL
BM_LONG_1195:
CORE_NOT_FILL:
 LDA TOKEN
 CMP #'E'
                        BEQ BM_LONG_1199
                        JMP CORE_INSTRUCTION
BM_LONG_1199:
 PHX
 LDX #<DIR_END
 LDY #>DIR_END
 JSR MATCH_TOKEN
 PLX
                        BCS BM_LONG_1205
                        JMP CORE_INSTRUCTION
BM_LONG_1205:
 JSR END_LINE
 INC ASSEMBLY_END
CORE_RETURN:
 RTS
CORE_LAYOUT_BAD:
 LDA #E_LAYOUT
 STA ERROR
 RTS
CORE_SYNTAX:
 LDA #E_SYNTAX
 STA ERROR
 RTS
CORE_RANGE:
 LDA #E_RANGE
 STA ERROR
 RTS

DEFINE_SYMBOL:
 LDY #$12
 LDA PASS
 CMP #$02
                        BEQ DEFINE_COMPARE
 LDA (SYMPTR),Y
 AND #$01
                        BNE DEFINE_DUPLICATE
 LDA (SYMPTR),Y
 ORA #$01
 STA (SYMPTR),Y
 LDY #$10
 LDA VAL
 STA (SYMPTR),Y
 INY
 LDA VAL+1
 STA (SYMPTR),Y
 RTS
DEFINE_COMPARE:
 LDA (SYMPTR),Y
 AND #$01
                        BEQ DEFINE_PHASE
 LDY #$10
 LDA (SYMPTR),Y
 CMP VAL
                        BNE DEFINE_PHASE
 INY
 LDA (SYMPTR),Y
 CMP VAL+1
                        BNE DEFINE_PHASE
 RTS
DEFINE_DUPLICATE:
 LDA #E_DUPLICATE
 STA ERROR
 RTS
DEFINE_PHASE:
 LDA #E_PHASE
 STA ERROR
 RTS

CORE_ORG:
 JSR EXPRESSION
 LDA ERROR
                        BNE CORE_RETURN
 LDA UNRES
                        BNE CORE_LAYOUT_BAD
 ; Preserve the target while an optional byte expression uses VAL.
 LDA VAL
 STA COUNT
 LDA VAL+1
 STA COUNT+1
 STZ OPERAND
 JSR SPACES
 CMP #','
                        BNE ORG_END
 INX
 JSR EXPRESSION
 JSR BYTE_VALUE
 LDA ERROR
                        BNE CORE_RETURN
 LDA VAL
 STA OPERAND
ORG_END:
 JSR END_LINE
 LDA ERROR
                        BEQ BM_LONG_1288
                        JMP CORE_RETURN
BM_LONG_1288:
 LDA BASESET
                        BNE ORG_GAP
 LDA COUNT
 STA PC
 LDA COUNT+1
 STA PC+1
 RTS
ORG_GAP:
 LDA PCFULL
                        BEQ BM_LONG_1298
                        JMP CORE_RANGE
BM_LONG_1298:
 SEC
 LDA COUNT
 SBC PC
 STA COUNT
 LDA COUNT+1
 SBC PC+1
 STA COUNT+1
                        BCS BM_LONG_1306
                        JMP CORE_RANGE
BM_LONG_1306:
 JMP FILL_LOOP
CORE_FILL:
 JSR EXPRESSION
 LDA ERROR
                        BEQ BM_LONG_1311
                        JMP CORE_RETURN
BM_LONG_1311:
 LDA UNRES
                        BEQ BM_LONG_1313
                        JMP CORE_LAYOUT_BAD
BM_LONG_1313:
 LDA VAL
 STA COUNT
 LDA VAL+1
 STA COUNT+1
 JSR SPACES
 CMP #','
                        BEQ BM_LONG_1320
                        JMP CORE_SYNTAX
BM_LONG_1320:
 INX
 JSR EXPRESSION
 JSR END_LINE
 JSR BYTE_VALUE
 LDA ERROR
                        BEQ BM_LONG_1326
                        JMP CORE_RETURN
BM_LONG_1326:
 LDA VAL
 STA OPERAND
FILL_LOOP:
 LDA COUNT
 ORA COUNT+1
                        BNE BM_LONG_1332
                        JMP CORE_RETURN
BM_LONG_1332:
 LDA OPERAND
 JSR EMIT_BYTE
 LDA ERROR
                        BEQ BM_LONG_1336
                        JMP CORE_RETURN
BM_LONG_1336:
 LDA COUNT
                        BNE FILL_DEC
 DEC COUNT+1
FILL_DEC:
 DEC COUNT
                        JMP FILL_LOOP
CORE_BYTE:
 LDA #$01
                        JMP CORE_DATA
CORE_WORD:
 LDA #$02
CORE_DATA:
 STA DATA_KIND
DATA_ITEM:
 JSR SPACES
 CMP #'"'
                        BEQ DATA_STRING
 JSR EXPRESSION
 LDA DATA_KIND
 CMP #$01
                        BNE DATA_WORD
 JSR BYTE_VALUE
DATA_WORD:
 LDA ERROR
                        BEQ BM_LONG_1361
                        JMP CORE_RETURN
BM_LONG_1361:
 LDA VAL
 JSR EMIT_BYTE
 LDA DATA_KIND
 CMP #$02
                        BNE DATA_NEXT
 LDA VAL+1
 JSR EMIT_BYTE
DATA_NEXT:
 LDA ERROR
                        BEQ BM_LONG_1371
                        JMP CORE_RETURN
BM_LONG_1371:
 JSR SPACES
 CMP #','
                        BNE DATA_FINISH
 INX
                        JMP DATA_ITEM
DATA_FINISH:
 JMP END_LINE
DATA_STRING:
 LDA DATA_KIND
 CMP #$01
                        BEQ BM_LONG_1382
                        JMP CORE_SYNTAX
BM_LONG_1382:
 INX
DATA_STRING_CHAR:
 LDA LINE,X
                        BNE BM_LONG_1386
                        JMP CORE_SYNTAX
BM_LONG_1386:
 CMP #'"'
                        BEQ DATA_STRING_END
 CMP #$5C
                        BNE DATA_STRING_EMIT
 INX
 LDA LINE,X
 CMP #'n'
                        BEQ DATA_ESCAPE_LF
 CMP #'r'
                        BEQ DATA_ESCAPE_CR
 CMP #'t'
                        BEQ DATA_ESCAPE_TAB
 CMP #'0'
                        BEQ DATA_ESCAPE_ZERO
 CMP #'"'
                        BEQ DATA_STRING_EMIT
 CMP #$5C
                        BEQ BM_LONG_1404
                        JMP CORE_SYNTAX
BM_LONG_1404:
                        JMP DATA_STRING_EMIT
DATA_ESCAPE_LF:
 LDA #$0A
                        JMP DATA_STRING_EMIT
DATA_ESCAPE_CR:
 LDA #$0D
                        JMP DATA_STRING_EMIT
DATA_ESCAPE_TAB:
 LDA #$09
                        JMP DATA_STRING_EMIT
DATA_ESCAPE_ZERO:
 LDA #$00
DATA_STRING_EMIT:
 JSR EMIT_BYTE
 LDA ERROR
                        BEQ BM_LONG_1420
                        JMP CORE_RETURN
BM_LONG_1420:
 INX
                        JMP DATA_STRING_CHAR
DATA_STRING_END:
 INX
                        JMP DATA_NEXT

CORE_INSTRUCTION:
 LDA TOK_LEN
 CMP #$05
                        BCC BM_LONG_1430
                        JMP INSTRUCTION_BAD
BM_LONG_1430:
 LDY #$03
COPY_OPCODE_NAME:
 LDA TOKEN,Y
 STA OP_TOKEN,Y
 DEY
                        BPL COPY_OPCODE_NAME
 LDA #$FF
 STA WANT
 JSR LOOKUP_OPCODE
                        BCS BM_LONG_1440
                        JMP INSTRUCTION_BAD
BM_LONG_1440:
 LDA MODE
 CMP #$0E
                        BNE BM_LONG_1443
                        JMP INSTRUCTION_BRANCH
BM_LONG_1443:
 CMP #$0F
                        BNE BM_LONG_1445
                        JMP INSTRUCTION_BIT_BRANCH
BM_LONG_1445:
 JSR SPACES
                        BEQ INSTRUCTION_IMPLIED
 CMP #';'
                        BEQ INSTRUCTION_IMPLIED
 CMP #'A'
                        BNE INSTRUCTION_OPERAND
 LDA LINE+1,X
                        BEQ INSTRUCTION_ACC
 CMP #';'
                        BEQ INSTRUCTION_ACC
 CMP #' '
                        BNE INSTRUCTION_OPERAND
INSTRUCTION_ACC:
 LDA #$01
 STA WANT
 JSR LOOKUP_OPCODE
                        BCC INSTRUCTION_OPERAND
 INX
 JSR END_LINE
 JMP EMIT_INSTRUCTION
INSTRUCTION_IMPLIED:
 STZ WANT
 JSR LOOKUP_OPCODE
                        BCC BM_LONG_1469
                        JMP EMIT_INSTRUCTION
BM_LONG_1469:
 LDA #$01
 STA WANT
 JSR LOOKUP_OPCODE
                        BCS BM_LONG_1473
                        JMP INSTRUCTION_BAD
BM_LONG_1473:
 JMP EMIT_INSTRUCTION
INSTRUCTION_OPERAND:
 JSR SPACES
 CMP #'#'
                        BNE BM_LONG_1478
                        JMP INSTRUCTION_IMMEDIATE
BM_LONG_1478:
 CMP #'('
                        BNE BM_LONG_1480
                        JMP INSTRUCTION_INDIRECT
BM_LONG_1480:
 STZ FORCE_ZP
 CMP #'<'
                        BNE INSTRUCTION_DIRECT
 INC FORCE_ZP
INSTRUCTION_DIRECT:
 LDA #$06
 STA WANT
 JSR EXPRESSION
 JSR SPACES
 CMP #','
                        BNE INSTRUCTION_SELECT
 INX
 JSR SPACES
 CMP #'X'
                        BEQ INSTRUCTION_X
 CMP #'Y'
                        BEQ BM_LONG_1497
                        JMP CORE_SYNTAX
BM_LONG_1497:
 LDA #$08
                        JMP INSTRUCTION_INDEX
INSTRUCTION_X:
 LDA #$07
INSTRUCTION_INDEX:
 STA WANT
 INX
INSTRUCTION_SELECT:
 JSR END_LINE
 LDA ERROR
                        BEQ BM_LONG_1508
                        JMP CORE_RETURN
BM_LONG_1508:
 LDA PASS
 CMP #$02
                        BEQ INSTRUCTION_REUSE
 LDA VAL+1
                        BNE INSTRUCTION_LOOKUP
 LDA UNRES
                        BEQ INSTRUCTION_TRY_ZP
 LDA FORCE_ZP
                        BEQ INSTRUCTION_LOOKUP
INSTRUCTION_TRY_ZP:
 LDA WANT
 PHA
 SEC
 SBC #$03
 STA WANT
 JSR LOOKUP_OPCODE
                        BCC INSTRUCTION_NO_ZP
 PLA
                        JMP INSTRUCTION_SAVE
INSTRUCTION_NO_ZP:
 PLA
 STA WANT
INSTRUCTION_LOOKUP:
 JSR LOOKUP_OPCODE
                        BCS INSTRUCTION_SAVE
 ; Some forms exist only in zero page (RMB/SMB, STX zp,Y, STY zp,X).
 ; Reserve that fixed width for a forward reference, then range-check pass 2.
 LDA WANT
 CMP #$06
                        BCS BM_LONG_1538
                        JMP INSTRUCTION_BAD
BM_LONG_1538:
 CMP #$09
                        BCC BM_LONG_1540
                        JMP INSTRUCTION_BAD
BM_LONG_1540:
 SEC
 SBC #$03
 STA WANT
 JSR LOOKUP_OPCODE
                        BCS BM_LONG_1545
                        JMP INSTRUCTION_BAD
BM_LONG_1545:
                        JMP INSTRUCTION_SAVE
INSTRUCTION_REUSE:
 LDY #$03
 LDA (REC),Y
 STA WANT
 JSR LOOKUP_OPCODE
                        BCS BM_LONG_1552
                        JMP INSTRUCTION_BAD
BM_LONG_1552:
                        JMP INSTRUCTION_ENCODE
INSTRUCTION_SAVE:
 LDY #$03
 LDA MODE
 STA (REC),Y
INSTRUCTION_ENCODE:
 LDA MODE
 CMP #$06
                        BCC INSTRUCTION_BYTE
 CMP #$09
                        BCC INSTRUCTION_WORD
 CMP #$0C
                        BCC INSTRUCTION_ZP
                        JMP INSTRUCTION_WORD
INSTRUCTION_BYTE:
 CMP #$02
                        BNE INSTRUCTION_ZP
 JSR BYTE_VALUE
                        JMP INSTRUCTION_WORD
INSTRUCTION_ZP:
 LDA UNRES
                        BNE INSTRUCTION_WORD
 LDA VAL+1
                        BEQ BM_LONG_1576
                        JMP CORE_RANGE
BM_LONG_1576:
INSTRUCTION_WORD:
 LDA VAL
 STA OPERAND
 LDA VAL+1
 STA OPERAND+1
 JMP EMIT_INSTRUCTION
INSTRUCTION_IMMEDIATE:
 LDA #$02
 STA WANT
 INX
 JSR EXPRESSION
 JSR END_LINE
 JMP INSTRUCTION_LOOKUP
INSTRUCTION_INDIRECT:
 INX
 JSR EXPRESSION
 JSR SPACES
 CMP #','
                        BEQ INSTRUCTION_IND_X
 CMP #')'
                        BEQ BM_LONG_1597
                        JMP CORE_SYNTAX
BM_LONG_1597:
 INX
 JSR SPACES
 CMP #','
                        BEQ INSTRUCTION_IND_Y
 LDA #$0B
 STA WANT
 JSR LOOKUP_OPCODE
                        BCS INSTRUCTION_IND_DONE
 LDA #$0C
 STA WANT
                        JMP INSTRUCTION_IND_DONE
INSTRUCTION_IND_X:
 INX
 JSR SPACES
 CMP #'X'
                        BEQ BM_LONG_1613
                        JMP CORE_SYNTAX
BM_LONG_1613:
 INX
 JSR SPACES
 CMP #')'
                        BEQ BM_LONG_1617
                        JMP CORE_SYNTAX
BM_LONG_1617:
 INX
 LDA #$09
 STA WANT
 JSR LOOKUP_OPCODE
                        BCS INSTRUCTION_IND_DONE
 LDA #$0D
 STA WANT
                        JMP INSTRUCTION_IND_DONE
INSTRUCTION_IND_Y:
 INX
 JSR SPACES
 CMP #'Y'
                        BEQ BM_LONG_1630
                        JMP CORE_SYNTAX
BM_LONG_1630:
 INX
 LDA #$0A
 STA WANT
INSTRUCTION_IND_DONE:
 JSR END_LINE
 JMP INSTRUCTION_LOOKUP
INSTRUCTION_BRANCH:
 JSR EXPRESSION
 JSR END_LINE
 LDA #$0E
 STA WANT
 JSR LOOKUP_OPCODE
 LDA #$02
 JSR BRANCH_VALUE
 LDA VAL
 STA OPERAND
 JMP EMIT_INSTRUCTION
INSTRUCTION_BIT_BRANCH:
 JSR EXPRESSION
 LDA ERROR
                        BEQ BM_LONG_1651
                        JMP CORE_RETURN
BM_LONG_1651:
 LDA UNRES
                        BNE BIT_BRANCH_ZP_OK
 LDA VAL+1
                        BEQ BM_LONG_1655
                        JMP CORE_RANGE
BM_LONG_1655:
BIT_BRANCH_ZP_OK:
 LDA VAL
 STA BIT_ZP
 JSR SPACES
 CMP #','
                        BEQ BM_LONG_1661
                        JMP CORE_SYNTAX
BM_LONG_1661:
 INX
 JSR EXPRESSION
 JSR END_LINE
 LDA #$0F
 STA WANT
 JSR LOOKUP_OPCODE
 LDA #$03
 JSR BRANCH_VALUE
 LDA VAL
 STA OPERAND+1
 LDA BIT_ZP
 STA OPERAND
 JMP EMIT_INSTRUCTION
INSTRUCTION_BAD:
 LDA #E_OPCODE
 STA ERROR
 RTS
BRANCH_VALUE:
 LDY ERROR
                        BNE BRANCH_RETURN
 CLC
 ADC PC
 STA RIGHT
 LDA PC+1
 ADC #$00
 STA RIGHT+1
 SEC
 LDA VAL
 SBC RIGHT
 STA VAL
 LDA VAL+1
 SBC RIGHT+1
 STA VAL+1
 LDA PASS
 CMP #$01
                        BEQ BRANCH_RETURN
 LDA VAL+1
                        BEQ BRANCH_POSITIVE
 CMP #$FF
                        BNE BRANCH_BAD
 LDA VAL
 CMP #$80
                        BCS BRANCH_RETURN
                        JMP BRANCH_BAD
BRANCH_POSITIVE:
 LDA VAL
 CMP #$80
                        BCC BRANCH_RETURN
BRANCH_BAD:
 LDA #E_BRANCH
 STA ERROR
BRANCH_RETURN:
 RTS
BYTE_VALUE:
 LDA ERROR
                        BNE BYTE_VALUE_RETURN
 LDA UNRES
                        BNE BYTE_VALUE_RETURN
 LDA VAL+1
                        BEQ BYTE_VALUE_RETURN
 CMP #$FF
                        BEQ BM_LONG_1723
                        JMP CORE_RANGE
BM_LONG_1723:
 LDA VAL
 CMP #$80
                        BCS BM_LONG_1726
                        JMP CORE_RANGE
BM_LONG_1726:
BYTE_VALUE_RETURN:
 RTS

LOOKUP_OPCODE:
 PHX
 LDA #<OP_TABLE
 STA TABLEPTR
 LDA #>OP_TABLE
 STA TABLEPTR+1
LOOKUP_ROW:
 LDA TABLEPTR+1
 CMP #>OP_END
                        BNE LOOKUP_COMPARE
 LDA TABLEPTR
 CMP #<OP_END
                        BEQ LOOKUP_MISSING
LOOKUP_COMPARE:
 LDY #$00
LOOKUP_NAME:
 LDA (TABLEPTR),Y
 CMP OP_TOKEN,Y
                        BNE LOOKUP_NEXT
 INY
 CPY #$04
                        BNE LOOKUP_NAME
 LDA WANT
 CMP #$FF
                        BEQ LOOKUP_FOUND
 CMP (TABLEPTR),Y
                        BEQ LOOKUP_FOUND
LOOKUP_NEXT:
 CLC
 LDA TABLEPTR
 ADC #$06
 STA TABLEPTR
                        BCC LOOKUP_ROW
 INC TABLEPTR+1
                        JMP LOOKUP_ROW
LOOKUP_FOUND:
 LDA (TABLEPTR),Y
 STA MODE
 INY
 LDA (TABLEPTR),Y
 STA OPCODE
 PLX
 SEC
 RTS
LOOKUP_MISSING:
 PLX
 CLC
 RTS

EMIT_INSTRUCTION:
 LDA ERROR
                        BNE EMIT_RETURN
 LDA OPCODE
 JSR EMIT_BYTE
 LDA OPCODE
                        BNE EMIT_STANDARD_LENGTH
 ; BRK consumes its signature byte; bare BRK emits a zero signature.
 LDA #$00
 JMP EMIT_BYTE
EMIT_STANDARD_LENGTH:
 LDY MODE
 LDA MODE_LENGTHS,Y
 CMP #$01
                        BEQ EMIT_RETURN
 LDA OPERAND
 JSR EMIT_BYTE
 LDY MODE
 LDA MODE_LENGTHS,Y
 CMP #$03
                        BNE EMIT_RETURN
 LDA OPERAND+1
 JMP EMIT_BYTE
EMIT_BYTE:
 PHA
 LDA ERROR
                        BNE EMIT_POP
 LDA PCFULL
                        BNE EMIT_RANGE
 LDA OUTPTR+1
 CMP #>OUTPUT_END
                        BCS EMIT_FULL
 LDA BASESET
                        BNE EMIT_READY
 LDA PC
 STA RESULT_ORIGIN
 LDA PC+1
 STA RESULT_ORIGIN+1
 INC BASESET
EMIT_READY:
 PLA
 PHA
 LDY PASS
 CPY #$02
                        BNE EMIT_ADVANCE
 STA (OUTPTR)
EMIT_ADVANCE:
 INC OUTPTR
                        BNE EMIT_PC
 INC OUTPTR+1
EMIT_PC:
 INC PC
                        BNE EMIT_POP
 INC PC+1
                        BNE EMIT_POP
 INC PCFULL
EMIT_POP:
 PLA
EMIT_RETURN:
 RTS
EMIT_RANGE:
 LDA #E_RANGE
 STA ERROR
                        JMP EMIT_POP
EMIT_FULL:
 LDA #E_OUTPUT
 STA ERROR
                        JMP EMIT_POP
MODE_LENGTHS:
 DB 1,1,2,2,2,2,3,3,3,2,2,2,3,3,2,3
DIR_ORG: DB "ORG",0
DIR_BYTE: DB "BYTE",0
DIR_WORD: DB "WORD",0
DIR_TEXT: DB "TEXT",0
DIR_FILL: DB "FILL",0
DIR_END: DB "END",0

 ; Expressions: decimal/$hex/%binary/'c', symbols, current PC (*), parentheses,
; unary + - < > and binary + -. Arithmetic wraps at 16 bits; literals do not.
SPACES:
 LDA LINE,X
 CMP #' '
                        BNE CAPS
 INX
                        JMP SPACES
CAPS:
 CMP #'a'
                        BCC CAPS_DONE
 CMP #'z'+1
                        BCS CAPS_DONE
 AND #$DF
CAPS_DONE:
 ORA #$00
 RTS
END_LINE:
 LDA ERROR
                        BNE END_LINE_OK
 JSR SPACES
                        BEQ END_LINE_OK
 CMP #';'
                        BEQ END_LINE_OK
 LDA #E_SYNTAX
 STA ERROR
END_LINE_OK:
 RTS
READ_TOKEN:
 STZ TOKEN_LOCAL
 LDY #$0F
 LDA #$00
TOKEN_CLEAR:
 STA TOKEN,Y
 DEY
                        BPL TOKEN_CLEAR
 STZ TOK_LEN
 JSR SPACES
 JSR NAME_FIRST
                        BCC TOKEN_BAD
TOKEN_LOOP:
 JSR CAPS
 JSR NAME_CHAR
                        BCC TOKEN_DONE
 LDY TOK_LEN
 CPY #NAME_MAX
                        BCS TOKEN_BAD
 STA TOKEN,Y
 INC TOK_LEN
 INX
 LDA LINE,X
                        JMP TOKEN_LOOP
TOKEN_DONE:
 RTS
TOKEN_BAD:
 LDA #E_SYNTAX
 STA ERROR
 RTS
; The dot selects the current global-label scope. The stored name omits it,
; retaining the full 15-character name limit and 20-byte symbol rows.
READ_SYMBOL_TOKEN:
 JSR SPACES
 CMP #'.'
                        BNE READ_TOKEN
 INX
 JSR READ_TOKEN
 LDA #$01
 STA TOKEN_LOCAL
 RTS
NAME_FIRST:
 CMP #'_'
                        BEQ NAME_YES
 CMP #'A'
                        BCC NAME_NO
 CMP #'Z'+1
                        BCC NAME_YES
NAME_NO:
 CLC
 RTS
NAME_CHAR:
 CMP #'0'
                        BCC NAME_FIRST
 CMP #'9'+1
                        BCS NAME_FIRST
NAME_YES:
 SEC
 RTS

EXPRESSION:
 STZ UNRES
 STZ DEPTH
 JSR EXPR_SUM
 RTS
EXPR_SUM:
 JSR EXPR_UNARY
EXPR_SUM_NEXT:
 LDA ERROR
                        BNE EXPR_RETURN
 JSR SPACES
 CMP #'+'
                        BEQ EXPR_BINARY
 CMP #'-'
                        BNE EXPR_RETURN
EXPR_BINARY:
 PHA
 LDA VAL
 PHA
 LDA VAL+1
 PHA
 INX
 JSR EXPR_UNARY
 PLA
 STA LEFT+1
 PLA
 STA LEFT
 PLA
 CMP #'+'
                        BEQ EXPR_ADD
 SEC
 LDA LEFT
 SBC VAL
 STA VAL
 LDA LEFT+1
 SBC VAL+1
 STA VAL+1
                        JMP EXPR_SUM_NEXT
EXPR_ADD:
 CLC
 LDA LEFT
 ADC VAL
 STA VAL
 LDA LEFT+1
 ADC VAL+1
 STA VAL+1
                        JMP EXPR_SUM_NEXT
EXPR_RETURN:
 RTS
EXPR_UNARY:
 INC DEPTH
 LDA DEPTH
 CMP #$09
                        BCS EXPR_TOO_DEEP
 JSR SPACES
 CMP #'+'
                        BEQ EXPR_PREFIX
 CMP #'-'
                        BEQ EXPR_PREFIX
 CMP #'<'
                        BEQ EXPR_PREFIX
 CMP #'>'
                        BEQ EXPR_PREFIX
 CMP #'('
                        BEQ EXPR_GROUP
 JSR EXPR_PRIMARY
                        JMP EXPR_UNARY_DONE
EXPR_PREFIX:
 PHA
 INX
 JSR EXPR_UNARY
 PLA
 CMP #'+'
                        BEQ EXPR_UNARY_DONE
 CMP #'<'
                        BEQ EXPR_LOW
 CMP #'>'
                        BEQ EXPR_HIGH
 SEC
 LDA #$00
 SBC VAL
 STA VAL
 LDA #$00
 SBC VAL+1
 STA VAL+1
                        JMP EXPR_UNARY_DONE
EXPR_LOW:
 STZ VAL+1
                        JMP EXPR_UNARY_DONE
EXPR_HIGH:
 LDA VAL+1
 STA VAL
 STZ VAL+1
                        JMP EXPR_UNARY_DONE
EXPR_GROUP:
 INX
 JSR EXPR_SUM
 LDA ERROR
                        BNE EXPR_UNARY_DONE
 JSR SPACES
 CMP #')'
                        BNE EXPR_SYNTAX
 INX
EXPR_UNARY_DONE:
 DEC DEPTH
 RTS
EXPR_TOO_DEEP:
 LDA #E_DEPTH
 STA ERROR
                        JMP EXPR_UNARY_DONE
EXPR_SYNTAX:
 LDA #E_SYNTAX
 STA ERROR
                        JMP EXPR_UNARY_DONE
EXPR_PRIMARY:
 STZ VAL
 STZ VAL+1
 JSR SPACES
 CMP #'$'
                        BEQ EXPR_HEX
 CMP #'%'
                        BEQ EXPR_BINARY_NUMBER
 CMP #$27
                        BEQ EXPR_CHARACTER
 CMP #'*'
                        BEQ EXPR_PC
 CMP #'0'
                        BCC EXPR_SYMBOL
 CMP #'9'+1
                        BCS EXPR_SYMBOL
 LDA #$0A
 STA RADIX
 JMP READ_NUMBER
EXPR_HEX:
 LDA #$10
                        JMP EXPR_NUMBER_PREFIX
EXPR_BINARY_NUMBER:
 LDA #$02
EXPR_NUMBER_PREFIX:
 STA RADIX
 INX
 JMP READ_NUMBER
EXPR_CHARACTER:
 INX
 LDA LINE,X
                        BEQ EXPR_PRIMARY_BAD
 STA VAL
 INX
 LDA LINE,X
 CMP #$27
                        BNE EXPR_PRIMARY_BAD
 INX
 RTS
EXPR_PC:
 LDA PC
 STA VAL
 LDA PC+1
 STA VAL+1
 INX
 RTS
EXPR_SYMBOL:
 JSR READ_SYMBOL_TOKEN
 LDA ERROR
                        BNE EXPR_PRIMARY_RETURN
 JSR FIND_SYMBOL
 LDA ERROR
                        BNE EXPR_PRIMARY_RETURN
 LDY #$12
 LDA (SYMPTR),Y
 AND #$01
                        BEQ SYMBOL_UNDEFINED
 LDY #$10
 LDA (SYMPTR),Y
 STA VAL
 INY
 LDA (SYMPTR),Y
 STA VAL+1
EXPR_PRIMARY_RETURN:
 RTS
SYMBOL_UNDEFINED:
 INC UNRES
 LDA PASS
 CMP #$02
                        BNE EXPR_PRIMARY_RETURN
 LDA #E_UNDEFINED
 STA ERROR
 RTS
EXPR_PRIMARY_BAD:
 LDA #E_SYNTAX
 STA ERROR
 RTS

READ_NUMBER:
 STZ VAL
 STZ VAL+1
 STZ POS
NUMBER_LOOP:
 LDA LINE,X
 JSR CAPS
 JSR HEX_DIGIT
                        BCC NUMBER_DONE
 CMP RADIX
                        BCS NUMBER_DONE
 STA DIGIT
 LDA VAL
 STA NUMBER
 LDA VAL+1
 STA NUMBER+1
 STZ VAL
 STZ VAL+1
 LDY RADIX
NUMBER_MULTIPLY:
 CLC
 LDA VAL
 ADC NUMBER
 STA VAL
 LDA VAL+1
 ADC NUMBER+1
 STA VAL+1
                        BCS NUMBER_OVERFLOW
 DEY
                        BNE NUMBER_MULTIPLY
 CLC
 LDA VAL
 ADC DIGIT
 STA VAL
                        BCC NUMBER_DIGIT_OK
 INC VAL+1
                        BEQ NUMBER_OVERFLOW
NUMBER_DIGIT_OK:
 INX
 INC POS
                        JMP NUMBER_LOOP
NUMBER_DONE:
 LDA POS
                        BNE NUMBER_RETURN
 LDA #E_SYNTAX
 STA ERROR
NUMBER_RETURN:
 RTS
NUMBER_OVERFLOW:
 LDA #E_RANGE
 STA ERROR
 RTS
HEX_DIGIT:
 CMP #'0'
                        BCC HEX_NO
 CMP #'9'+1
                        BCC HEX_DECIMAL
 CMP #'A'
                        BCC HEX_NO
 CMP #'F'+1
                        BCS HEX_NO
 SEC
 SBC #'A'-10
 SEC
 RTS
HEX_DECIMAL:
 SEC
 SBC #'0'
 SEC
 RTS
HEX_NO:
 CLC
 RTS

; 256 records of 20 bytes: name[16], value[2], flags, parent symbol index.
; Flags bit 0=defined, bit 7=local. Globals and locals have distinct identities.
; References create an undefined entry in pass 1; pass 2 never creates one.
FIND_SYMBOL:
 LDA TOKEN_LOCAL
                        BEQ SYMBOL_SCOPE_OK
 LDA SCOPE_VALID
                        BNE SYMBOL_SCOPE_OK
 LDA #E_SCOPE
 STA ERROR
 RTS
SYMBOL_SCOPE_OK:
 STZ SYMBOL_INDEX
 STZ SYMPTR
 LDA #>SYMBOL_START
 STA SYMPTR+1
SYMBOL_SEARCH:
 LDA SYMPTR+1
 CMP SYMTOP+1
                        BNE SYMBOL_COMPARE
 LDA SYMPTR
 CMP SYMTOP
                        BEQ SYMBOL_CREATE
SYMBOL_COMPARE:
 LDY #$12
 LDA (SYMPTR),Y
 AND #$80
                        BEQ SYMBOL_GLOBAL
 LDA TOKEN_LOCAL
                        BEQ SYMBOL_NEXT
 INY
 LDA (SYMPTR),Y
 CMP SCOPE_ID
                        BNE SYMBOL_NEXT
                        JMP SYMBOL_NAME_START
SYMBOL_GLOBAL:
 LDA TOKEN_LOCAL
                        BNE SYMBOL_NEXT
SYMBOL_NAME_START:
 LDY #$00
SYMBOL_NAME_COMPARE:
 LDA (SYMPTR),Y
 CMP TOKEN,Y
                        BNE SYMBOL_NEXT
 CMP #$00
                        BEQ SYMBOL_FOUND
 INY
                        JMP SYMBOL_NAME_COMPARE
SYMBOL_NEXT:
 INC SYMBOL_INDEX
 CLC
 LDA SYMPTR
 ADC #$14
 STA SYMPTR
                        BCC SYMBOL_SEARCH
 INC SYMPTR+1
                        JMP SYMBOL_SEARCH
SYMBOL_CREATE:
 LDA PASS
 CMP #$02
                        BEQ SYMBOL_NOT_FOUND
 LDA SYMTOP+1
 CMP #>SYMBOL_END
                        BCS SYMBOL_FULL
 LDY #$13
 LDA #$00
SYMBOL_ZERO:
 STA (SYMPTR),Y
 DEY
                        BPL SYMBOL_ZERO
 LDA TOKEN_LOCAL
                        BEQ SYMBOL_COPY_GLOBAL
 LDY #$12
 LDA #$80
 STA (SYMPTR),Y
 INY
 LDA SCOPE_ID
 STA (SYMPTR),Y
SYMBOL_COPY_GLOBAL:
 LDY #$00
SYMBOL_COPY_NAME:
 LDA TOKEN,Y
 STA (SYMPTR),Y
                        BEQ SYMBOL_CREATED
 INY
                        JMP SYMBOL_COPY_NAME
SYMBOL_CREATED:
 CLC
 LDA SYMTOP
 ADC #$14
 STA SYMTOP
                        BCC SYMBOL_FOUND
 INC SYMTOP+1
SYMBOL_FOUND:
 RTS
SYMBOL_NOT_FOUND:
 LDA #E_UNDEFINED
 STA ERROR
 RTS
SYMBOL_FULL:
 LDA #E_SYMBOLS
 STA ERROR
 RTS

OP_TABLE:
  DB $41,$44,$43,$00,$06,$6D,$41,$44,$43,$00,$07,$7D
 DB $41,$44,$43,$00,$08,$79,$41,$44,$43,$00,$02,$69
 DB $41,$44,$43,$00,$09,$61,$41,$44,$43,$00,$0A,$71
 DB $41,$44,$43,$00,$03,$65,$41,$44,$43,$00,$0B,$72
 DB $41,$44,$43,$00,$04,$75,$41,$4E,$44,$00,$06,$2D
 DB $41,$4E,$44,$00,$07,$3D,$41,$4E,$44,$00,$08,$39
 DB $41,$4E,$44,$00,$02,$29,$41,$4E,$44,$00,$09,$21
 DB $41,$4E,$44,$00,$0A,$31,$41,$4E,$44,$00,$03,$25
 DB $41,$4E,$44,$00,$0B,$32,$41,$4E,$44,$00,$04,$35
 DB $41,$53,$4C,$00,$06,$0E,$41,$53,$4C,$00,$07,$1E
 DB $41,$53,$4C,$00,$01,$0A,$41,$53,$4C,$00,$03,$06
 DB $41,$53,$4C,$00,$04,$16,$42,$42,$52,$30,$0F,$0F
 DB $42,$42,$52,$31,$0F,$1F,$42,$42,$52,$32,$0F,$2F
 DB $42,$42,$52,$33,$0F,$3F,$42,$42,$52,$34,$0F,$4F
 DB $42,$42,$52,$35,$0F,$5F,$42,$42,$52,$36,$0F,$6F
 DB $42,$42,$52,$37,$0F,$7F,$42,$42,$53,$30,$0F,$8F
 DB $42,$42,$53,$31,$0F,$9F,$42,$42,$53,$32,$0F,$AF
 DB $42,$42,$53,$33,$0F,$BF,$42,$42,$53,$34,$0F,$CF
 DB $42,$42,$53,$35,$0F,$DF,$42,$42,$53,$36,$0F,$EF
 DB $42,$42,$53,$37,$0F,$FF,$42,$43,$43,$00,$0E,$90
 DB $42,$43,$53,$00,$0E,$B0,$42,$45,$51,$00,$0E,$F0
 DB $42,$49,$54,$00,$06,$2C,$42,$49,$54,$00,$07,$3C
 DB $42,$49,$54,$00,$02,$89,$42,$49,$54,$00,$03,$24
 DB $42,$49,$54,$00,$04,$34,$42,$4D,$49,$00,$0E,$30
 DB $42,$4E,$45,$00,$0E,$D0,$42,$50,$4C,$00,$0E,$10
 DB $42,$52,$41,$00,$0E,$80,$42,$52,$4B,$00,$00,$00
 DB $42,$56,$43,$00,$0E,$50,$42,$56,$53,$00,$0E,$70
 DB $43,$4C,$43,$00,$00,$18,$43,$4C,$44,$00,$00,$D8
 DB $43,$4C,$49,$00,$00,$58,$43,$4C,$56,$00,$00,$B8
 DB $43,$4D,$50,$00,$06,$CD,$43,$4D,$50,$00,$07,$DD
 DB $43,$4D,$50,$00,$08,$D9,$43,$4D,$50,$00,$02,$C9
 DB $43,$4D,$50,$00,$09,$C1,$43,$4D,$50,$00,$0A,$D1
 DB $43,$4D,$50,$00,$03,$C5,$43,$4D,$50,$00,$0B,$D2
 DB $43,$4D,$50,$00,$04,$D5,$43,$50,$58,$00,$06,$EC
 DB $43,$50,$58,$00,$02,$E0,$43,$50,$58,$00,$03,$E4
 DB $43,$50,$59,$00,$06,$CC,$43,$50,$59,$00,$02,$C0
 DB $43,$50,$59,$00,$03,$C4,$44,$45,$43,$00,$06,$CE
 DB $44,$45,$43,$00,$07,$DE,$44,$45,$43,$00,$01,$3A
 DB $44,$45,$43,$00,$03,$C6,$44,$45,$43,$00,$04,$D6
 DB $44,$45,$58,$00,$00,$CA,$44,$45,$59,$00,$00,$88
 DB $45,$4F,$52,$00,$06,$4D,$45,$4F,$52,$00,$07,$5D
 DB $45,$4F,$52,$00,$08,$59,$45,$4F,$52,$00,$02,$49
 DB $45,$4F,$52,$00,$09,$41,$45,$4F,$52,$00,$0A,$51
 DB $45,$4F,$52,$00,$03,$45,$45,$4F,$52,$00,$0B,$52
 DB $45,$4F,$52,$00,$04,$55,$49,$4E,$43,$00,$06,$EE
 DB $49,$4E,$43,$00,$07,$FE,$49,$4E,$43,$00,$01,$1A
 DB $49,$4E,$43,$00,$03,$E6,$49,$4E,$43,$00,$04,$F6
 DB $49,$4E,$58,$00,$00,$E8,$49,$4E,$59,$00,$00,$C8
 DB $4A,$4D,$50,$00,$06,$4C,$4A,$4D,$50,$00,$0D,$7C
 DB $4A,$4D,$50,$00,$0C,$6C,$4A,$53,$52,$00,$06,$20
 DB $4C,$44,$41,$00,$06,$AD,$4C,$44,$41,$00,$07,$BD
 DB $4C,$44,$41,$00,$08,$B9,$4C,$44,$41,$00,$02,$A9
 DB $4C,$44,$41,$00,$09,$A1,$4C,$44,$41,$00,$0A,$B1
 DB $4C,$44,$41,$00,$03,$A5,$4C,$44,$41,$00,$0B,$B2
 DB $4C,$44,$41,$00,$04,$B5,$4C,$44,$58,$00,$06,$AE
 DB $4C,$44,$58,$00,$08,$BE,$4C,$44,$58,$00,$02,$A2
 DB $4C,$44,$58,$00,$03,$A6,$4C,$44,$58,$00,$05,$B6
 DB $4C,$44,$59,$00,$06,$AC,$4C,$44,$59,$00,$07,$BC
 DB $4C,$44,$59,$00,$02,$A0,$4C,$44,$59,$00,$03,$A4
 DB $4C,$44,$59,$00,$04,$B4,$4C,$53,$52,$00,$06,$4E
 DB $4C,$53,$52,$00,$07,$5E,$4C,$53,$52,$00,$01,$4A
 DB $4C,$53,$52,$00,$03,$46,$4C,$53,$52,$00,$04,$56
 DB $4E,$4F,$50,$00,$00,$EA,$4F,$52,$41,$00,$06,$0D
 DB $4F,$52,$41,$00,$07,$1D,$4F,$52,$41,$00,$08,$19
 DB $4F,$52,$41,$00,$02,$09,$4F,$52,$41,$00,$09,$01
 DB $4F,$52,$41,$00,$0A,$11,$4F,$52,$41,$00,$03,$05
 DB $4F,$52,$41,$00,$0B,$12,$4F,$52,$41,$00,$04,$15
 DB $50,$48,$41,$00,$00,$48,$50,$48,$50,$00,$00,$08
 DB $50,$48,$58,$00,$00,$DA,$50,$48,$59,$00,$00,$5A
 DB $50,$4C,$41,$00,$00,$68,$50,$4C,$50,$00,$00,$28
 DB $50,$4C,$58,$00,$00,$FA,$50,$4C,$59,$00,$00,$7A
 DB $52,$4D,$42,$30,$03,$07,$52,$4D,$42,$31,$03,$17
 DB $52,$4D,$42,$32,$03,$27,$52,$4D,$42,$33,$03,$37
 DB $52,$4D,$42,$34,$03,$47,$52,$4D,$42,$35,$03,$57
 DB $52,$4D,$42,$36,$03,$67,$52,$4D,$42,$37,$03,$77
 DB $52,$4F,$4C,$00,$06,$2E,$52,$4F,$4C,$00,$07,$3E
 DB $52,$4F,$4C,$00,$01,$2A,$52,$4F,$4C,$00,$03,$26
 DB $52,$4F,$4C,$00,$04,$36,$52,$4F,$52,$00,$06,$6E
 DB $52,$4F,$52,$00,$07,$7E,$52,$4F,$52,$00,$01,$6A
 DB $52,$4F,$52,$00,$03,$66,$52,$4F,$52,$00,$04,$76
 DB $52,$54,$49,$00,$00,$40,$52,$54,$53,$00,$00,$60
 DB $53,$42,$43,$00,$06,$ED,$53,$42,$43,$00,$07,$FD
 DB $53,$42,$43,$00,$08,$F9,$53,$42,$43,$00,$02,$E9
 DB $53,$42,$43,$00,$09,$E1,$53,$42,$43,$00,$0A,$F1
 DB $53,$42,$43,$00,$03,$E5,$53,$42,$43,$00,$0B,$F2
 DB $53,$42,$43,$00,$04,$F5,$53,$45,$43,$00,$00,$38
 DB $53,$45,$44,$00,$00,$F8,$53,$45,$49,$00,$00,$78
 DB $53,$4D,$42,$30,$03,$87,$53,$4D,$42,$31,$03,$97
 DB $53,$4D,$42,$32,$03,$A7,$53,$4D,$42,$33,$03,$B7
 DB $53,$4D,$42,$34,$03,$C7,$53,$4D,$42,$35,$03,$D7
 DB $53,$4D,$42,$36,$03,$E7,$53,$4D,$42,$37,$03,$F7
 DB $53,$54,$41,$00,$06,$8D,$53,$54,$41,$00,$07,$9D
 DB $53,$54,$41,$00,$08,$99,$53,$54,$41,$00,$09,$81
 DB $53,$54,$41,$00,$0A,$91,$53,$54,$41,$00,$03,$85
 DB $53,$54,$41,$00,$0B,$92,$53,$54,$41,$00,$04,$95
 DB $53,$54,$50,$00,$00,$DB,$53,$54,$58,$00,$06,$8E
 DB $53,$54,$58,$00,$03,$86,$53,$54,$58,$00,$05,$96
 DB $53,$54,$59,$00,$06,$8C,$53,$54,$59,$00,$03,$84
 DB $53,$54,$59,$00,$04,$94,$53,$54,$5A,$00,$06,$9C
 DB $53,$54,$5A,$00,$07,$9E,$53,$54,$5A,$00,$03,$64
 DB $53,$54,$5A,$00,$04,$74,$54,$41,$58,$00,$00,$AA
 DB $54,$41,$59,$00,$00,$A8,$54,$52,$42,$00,$06,$1C
 DB $54,$52,$42,$00,$03,$14,$54,$53,$42,$00,$06,$0C
 DB $54,$53,$42,$00,$03,$04,$54,$53,$58,$00,$00,$BA
 DB $54,$58,$41,$00,$00,$8A,$54,$58,$53,$00,$00,$9A
 DB $54,$59,$41,$00,$00,$98,$57,$41,$49,$00,$00,$CB

OP_END:
APP_END:
