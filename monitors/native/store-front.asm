; STORE P frontend before WB borrows4800-66FF. Loaded with SL at6B00.
; Code6D00-70FD; request69D0, line67C0; no WORKSPACE staging or SPI format.
; Large flash Store remains a separate backend; this component is PROGRAM.
        MODULE STORE_FRONT
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "store-tail.inc"
        INCLUDE "s19-pins.inc"
        CODE
SF_START:
        DB "WS",1,4,"PR05"
        JMP SF_COMMAND
SF_PTR EQU $E0
SF_LINE EQU $67C0
SF_REQ EQU $69D0
SF_VALUE EQU $69F0
SF_DIGITS EQU $69F2
SF_COMMAND:
        STX SF_PTR
        STY SF_PTR+1
        LDY #0
SF_LINE_COPY:
        LDA (SF_PTR),Y
        STA SF_LINE,Y
        BEQ SF_CLEAR
        INY
        CPY #41
        BCC SF_LINE_COPY
        BRA SF_BAD
SF_CLEAR:
        LDY #31
        LDA #0
SF_REQ_CLEAR:
        STA SF_REQ,Y
        DEY
        BPL SF_REQ_CLEAR
        LDX #0
        JSR SF_SKIP
SF_VERB:
        LDA SF_LINE,X
        BEQ SF_BAD
        INX
        CMP #' '
        BNE SF_VERB
        JSR SF_SKIP
        CMP #'P'
        BNE SF_BAD
        INX
        LDA SF_LINE,X
        CMP #' '
        BNE SF_BAD
        JSR SF_SKIP
        CMP #'A'
        BNE SF_EXPLICIT
        LDA SF_LINE+1,X
        CMP #'U'
        BNE SF_BAD
        LDA SF_LINE+2,X
        CMP #'T'
        BNE SF_BAD
        LDA SF_LINE+3,X
        CMP #'O'
        BNE SF_BAD
        LDA SF_LINE+4,X
        CMP #' '
        BNE SF_BAD
        INX
        INX
        INX
        INX
        BRA SF_SOURCE
SF_EXPLICIT:
        JSR SF_WORD
        BCC SF_BAD
        LDA SF_VALUE
        BNE SF_BAD
        LDA SF_VALUE+1
        CMP #8
        BCC SF_BAD
        STA SF_REQ+25
SF_SOURCE:
        JSR SF_WORD
        BCC SF_BAD
        LDA SF_VALUE
        STA SF_REQ+2
        STA SF_REQ+6
        LDA SF_VALUE+1
        STA SF_REQ+3
        STA SF_REQ+7
        CMP #2
        BCC SF_BAD
        JSR SF_WORD
        BCC SF_BAD
        LDA SF_VALUE
        STA SF_REQ+4
        LDA SF_VALUE+1
        STA SF_REQ+5
        CMP #$67
        BCS SF_BAD
        LDA SF_REQ+4
        CMP SF_REQ+2
        LDA SF_REQ+5
        SBC SF_REQ+3
        BCC SF_BAD
        JSR SF_SKIP
        LDY #0
SF_NAME:
        LDA SF_LINE,X
        BEQ SF_NAME_END
        CMP #' '
        BEQ SF_NAME_END
        CPY #16
        BCS SF_BAD
        STA SF_REQ+8,Y
        INX
        INY
        BRA SF_NAME
SF_NAME_END:
        CPY #0
        BEQ SF_BAD
        JSR SF_SKIP
        BNE SF_BAD
        LDA $6A20
        BEQ SF_NO_EDU
        LDX #<SF_CONFIRM_TEXT
        LDY #>SF_CONFIRM_TEXT
        JSR SF_PRINT
        JSR BOOT_READ_LINE
        BCC SF_CANCEL
        LDA $7C00
        CMP #'Y'
        BNE SF_CANCEL
        LDA $7C01
        CMP #'E'
        BNE SF_CANCEL
        LDA $7C02
        CMP #'S'
        BNE SF_CANCEL
        LDA $7C03
        BNE SF_CANCEL
        JSR STORE_S19_DRAIN
        LDA #8
        STA SF_REQ
        LDX #<SF_RESULT_TEXT
        LDY #>SF_RESULT_TEXT
        JSR SF_PRINT
        LDX #0
SF_TAIL_COPY:
        LDA SF_TAIL_IMAGE,X
        STA $6A30,X
        INX
        CPX #STORE_TAIL_BYTES
        BCC SF_TAIL_COPY
        JMP $6A30
SF_CANCEL:
        JSR STORE_S19_DRAIN
        LDX #<SF_CANCEL_TEXT
        LDY #>SF_CANCEL_TEXT
        BRA SF_MESSAGE
SF_NO_EDU:
        LDX #<SF_EDU_TEXT
        LDY #>SF_EDU_TEXT
        BRA SF_MESSAGE
SF_BAD:
        LDX #<SF_BAD_TEXT
        LDY #>SF_BAD_TEXT
SF_MESSAGE:
        JSR SF_PRINT
        CLC
        RTS
SF_SKIP:
        LDA SF_LINE,X
        CMP #' '
        BNE SF_SKIP_END
        INX
        BRA SF_SKIP
SF_SKIP_END:
        CMP #0
        RTS
SF_WORD:
        JSR SF_SKIP
        STZ SF_VALUE
        STZ SF_VALUE+1
        STZ SF_DIGITS
SF_HEX_CHAR:
        LDA SF_LINE,X
        BEQ SF_WORD_END
        CMP #' '
        BEQ SF_WORD_END
        CMP #'0'
        BCC SF_WORD_BAD
        CMP #':'
        BCC SF_HEX_DECIMAL
        CMP #'A'
        BCC SF_WORD_BAD
        CMP #'G'
        BCS SF_WORD_BAD
        SEC
        SBC #('A'-10)
        BRA SF_HEX_VALUE
SF_HEX_DECIMAL:
        SEC
        SBC #'0'
SF_HEX_VALUE:
        PHA
        LDY #4
SF_SHIFT:
        ASL SF_VALUE
        ROL SF_VALUE+1
        DEY
        BNE SF_SHIFT
        PLA
        ORA SF_VALUE
        STA SF_VALUE
        INX
        INC SF_DIGITS
        LDA SF_DIGITS
        CMP #5
        BCC SF_HEX_CHAR
SF_WORD_BAD:
        CLC
        RTS
SF_WORD_END:
        LDA SF_DIGITS
        BEQ SF_WORD_BAD
        SEC
        RTS
SF_PRINT:
        STX SF_PTR
        STY SF_PTR+1
        LDY #0
SF_PRINT_BYTE:
        LDA (SF_PTR),Y
        BEQ SF_PRINT_END
        JSR STR8V2_RAM_PUTC
        INY
        BRA SF_PRINT_BYTE
SF_PRINT_END:
        RTS
SF_CONFIRM_TEXT: DB "STORE PROGRAM from original RAM; type YES: ",0
SF_RESULT_TEXT: DB "STORE status $",0
SF_CANCEL_TEXT: DB "Canceled; no Store.",13,10,0
SF_EDU_TEXT: DB "REFUSED: EDU OFF",13,10,0
SF_BAD_TEXT: DB "Use STORE P AUTO|addr start end name",13,10,0
SF_TAIL_IMAGE:
        INCLUDE "store-tail-bytes.inc"
SF_END:
        ENDMOD
        END
