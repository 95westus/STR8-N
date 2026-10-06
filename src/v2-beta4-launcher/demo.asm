; A real flash-resident application, not an assembler implementation.
                       MODULE APP_DEMO
                       XDEF APP_END
                       INCLUDE "str8n-v2-public.inc"
                       CODE
                       DB "AP",$01,$01
                       DW $0000,$9010,$0000,$0000
                       DB $FF,$FF
                       DW $0000
APP_START:             LDX #$00
APP_MESSAGE:           LDA APP_TEXT,X
                       BEQ APP_QUIT
                       PHX
                       JSR STR8V2_RAM_PUTC
                       PLX
                       INX
                       BRA APP_MESSAGE
APP_QUIT:              JMP STR8V2_RAM_HOLD
APP_TEXT:              DB $0D,$0A,"FLASH APP DEMO",$0D,$0A,0
APP_END:
