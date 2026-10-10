; Read 16 external SRAM bytes at 10000 into CPU 3100. No PROBE or WRITE.
; Entry G 2000. Copied request/result at 3000-300F; final status at 3030.
        MODULE READ_SPISRAM
        XDEF START
        XDEF APP_END
RESULT_COPY EQU $3000
STATUS EQU $3030
BUFFER EQU $3100
        CODE
START:  SEI
        CLD
        JSR EX_CHECK_RA
        BCC EX_NO_ABI
        LDA #8
        JSR EX_CHECK_SV
        BCC FAILED
        LDX #3
CHECK_SM:
        LDA $66A2,X
        CMP EXPECTED_SM,X
        BNE ABSENT
        DEX
        BPL CHECK_SM
        LDX #15
PREPARE:
        LDA REQUEST,X
        STA $6650,X
        DEX
        BPL PREPARE
        JSR $66A6
        BCC FAILED
        CMP #0
        BNE FAILED
        LDA $6659
        CMP #16
        BNE SHORT_READ
        LDX #15
COPY_RESULT:
        LDA $6650,X
        STA RESULT_COPY,X
        DEX
        BPL COPY_RESULT
        LDA #0
        STA STATUS
        JSR REPORT
        LDX #<DATA_TEXT
        LDY #>DATA_TEXT
        JSR EX_PRINT
        LDX #0
PRINT_DATA:
        LDA BUFFER,X
        JSR HEX
        LDA #' '
        JSR PUTC
        INX
        CPX #16
        BNE PRINT_DATA
        JSR NL
        JMP HOLD
SHORT_READ:
        LDA #7
        BRA FAILED
ABSENT: LDA #$80
FAILED: STA STATUS
        JSR REPORT
        JMP HOLD
REPORT: LDX #<STATUS_TEXT
        LDY #>STATUS_TEXT
        JSR EX_PRINT
        LDA STATUS
        JSR HEX
        JSR NL
        RTS
EXPECTED_SM DB "SM",1,1
REQUEST DB 1,0,0,0,1,0,$31,16,0,0,0,0,0,0,0,0
STATUS_TEXT DB "SRAM READ: ",0
DATA_TEXT DB "DATA: ",0
        INCLUDE "example-abi.inc"
APP_END:
        ENDMOD
        END
