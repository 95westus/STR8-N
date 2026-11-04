; BASE1 acceptance fixture, execute in flash B0:9000.
; Only public bank-independent RAM ABI calls; never calls ROM/private F.
; All mutable data is in borrowed owner RAM 6100-6103, NOT this flash image.
; Q resets through F; the host catches S/recovery before a saved default boots.
        MODULE BASE1_B0_ACCEPT
        INCLUDE "str8n-v2-public.inc"
PTR EQU $E0
CPU EQU $6100
KEY EQU $6101
SUM EQU $6102
        CODE
START:
        SEI
        CLD
        LDX #3
SIGNATURE:
        LDA STR8V2_RAM_SIGNATURE,X
        CMP EXPECTED,X
        BNE BAD_ABI
        DEX
        BPL SIGNATURE
        JSR STR8V2_RAM_BOARD_QUERY
        STX CPU
        LDX #<TITLE
        LDY #>TITLE
        JSR PRINT
        LDA CPU
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        CLC
        LDA #$34
        ADC #1
        STA SUM
        LDA #$12
        ADC #0
        STA SUM+1
        LDX #<MATH
        LDY #>MATH
        JSR PRINT
        LDA SUM+1
        JSR STR8V2_RAM_HEX_OUT
        LDA SUM
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
WAIT_KEY:
        LDX #<PROMPT
        LDY #>PROMPT
        JSR PRINT
        JSR STR8V2_RAM_GETC
        STA KEY
        CMP #'Q'
        BEQ RETURN
        CMP #'q'
        BEQ RETURN
        CMP #3
        BNE WAIT_KEY
RETURN:
        LDX #<RETURN_TEXT
        LDY #>RETURN_TEXT
        JSR PRINT
        JMP STR8V2_RAM_RESET
BAD_ABI:
        JMP BAD_ABI
PRINT:
        STX PTR
        STY PTR+1
        LDY #0
PRINT_NEXT:
        LDA (PTR),Y
        BEQ PRINT_DONE
        JSR STR8V2_RAM_PUTC
        INY
        BNE PRINT_NEXT
        INC PTR+1
        BRA PRINT_NEXT
PRINT_DONE:
        RTS
EXPECTED: DB "RA",1,$0D
TITLE: DB "STR8N-F BASE1 OPAQUE B0:9000",13,10,"CPU code: ",0
MATH: DB "Flash-bank calculation 1234 + 0001 = ",0
PROMPT: DB "B0:9 Q> ",0
RETURN_TEXT: DB "Returning through F; select S for recovery.",13,10,0
IMAGE_END:
        ENDMOD
        END
