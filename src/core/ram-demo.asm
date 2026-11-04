; Demonstrate only services supplied by the exact b15 F bootstrap.
; No MON, journal, VX1, flash, RTC, I2C or EEPROM dependency/write.
        MODULE F_USER_DEMO_B15
        INCLUDE "str8n-v2-public.inc"
DEMO_PTR EQU $E0
        CODE
DEMO_START:
        SEI
        CLD
        LDX #<DEMO_TITLE
        LDY #>DEMO_TITLE
        JSR DEMO_PRINT
        JSR STR8V2_RAM_BOARD_QUERY
        STX DEMO_CPU
        LDX #<DEMO_CPU_TEXT
        LDY #>DEMO_CPU_TEXT
        JSR DEMO_PRINT
        LDA DEMO_CPU
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        JSR STR8V2_RAM_CAPS_QUERY
        STX DEMO_CAPS
        LDX #<DEMO_CAPS_TEXT
        LDY #>DEMO_CAPS_TEXT
        JSR DEMO_PRINT
        LDA DEMO_CAPS
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        ; A small program can use RAM and compute without being installed.
        CLC
        LDA #$34
        ADC #1
        STA DEMO_SUM
        LDA #$12
        ADC #0
        STA DEMO_SUM+1
        LDX #<DEMO_SUM_TEXT
        LDY #>DEMO_SUM_TEXT
        JSR DEMO_PRINT
        LDA DEMO_SUM+1
        JSR STR8V2_RAM_HEX_OUT
        LDA DEMO_SUM
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        LDX #<DEMO_WAIT_TEXT
        LDY #>DEMO_WAIT_TEXT
        JSR DEMO_PRINT
        JSR STR8V2_RAM_GETC
        STA DEMO_KEY
        LDX #<DEMO_KEY_TEXT
        LDY #>DEMO_KEY_TEXT
        JSR DEMO_PRINT
        LDA DEMO_KEY
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        LDX #<DEMO_DONE_TEXT
        LDY #>DEMO_DONE_TEXT
        JSR DEMO_PRINT
        JMP STR8V2_RAM_RESET
DEMO_PRINT:
        STX DEMO_PTR
        STY DEMO_PTR+1
        LDY #0
DEMO_PRINT_NEXT:
        LDA (DEMO_PTR),Y
        BEQ DEMO_PRINT_DONE
        JSR STR8V2_RAM_PUTC
        INY
        BNE DEMO_PRINT_NEXT
        INC DEMO_PTR+1
        BRA DEMO_PRINT_NEXT
DEMO_PRINT_DONE:
        RTS
DEMO_TITLE:
        DB "STR8N-F BASE1 DEMO 0.3.0",13,10
        DB "This program runs in RAM using F only.",13,10
        DB "No journal, monitor or extension is required.",13,10,0
DEMO_CPU_TEXT: DB "CPU code (02=65C02, 16=65C816): ",0
DEMO_CAPS_TEXT: DB "F public capability flags: ",0
DEMO_SUM_TEXT: DB "RAM calculation, hex 1234 + 0001 = ",0
DEMO_WAIT_TEXT: DB "Press one key to test input> ",0
DEMO_KEY_TEXT: DB "Received key byte, hex: ",0
DEMO_DONE_TEXT:
        DB "Program complete. Returning through F to the saved boot choice.",13,10,0
DEMO_CPU: DB 0
DEMO_CAPS: DB 0
DEMO_SUM: DW 0
DEMO_KEY: DB 0
DEMO_END:
        ENDMOD
        END
