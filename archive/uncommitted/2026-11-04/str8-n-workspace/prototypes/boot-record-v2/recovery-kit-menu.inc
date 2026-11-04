; One text menu for the combined, F-dependent RAM application.
; BOOT_READ_LINE echoes input and normalizes lowercase; CR/LF/CRLF supported.
CK_MENU:
INSTALLER_MENU:
        LDX #<CK_PROMPT
        LDY #>CK_PROMPT
        JSR BOOT_PRINT
        JSR BOOT_READ_LINE
        BCC CK_COMMAND_BAD
        LDA V2_LINE+1
        BNE CK_COMMAND_BAD
        LDA V2_LINE
        CMP #'?'
        BEQ CK_HELP
        CMP #'Q'
        BEQ MA_QUIT
        CMP #'T'
        BEQ CK_RESTORE
        CMP #'X'
        BEQ CK_ERASE
        CMP #'I'
        BNE CK_COMMAND_BAD
        JSR CK_VERIFY
        JMP OI_PORT_CAPTURE
CK_RESTORE:
        JSR CK_VERIFY
        JMP MA_RESTORE
CK_ERASE:
        LDX #<CK_CONFIRM
        LDY #>CK_CONFIRM
        JSR BOOT_PRINT
        JSR BOOT_READ_LINE
        BCC CK_CANCELED
        LDX #0
CK_CONFIRM_BYTE:
        LDA V2_LINE,X
        CMP CK_ERASE_WORD,X
        BNE CK_CANCELED
        INX
        CPX #6
        BNE CK_CONFIRM_BYTE
        JSR CK_VERIFY
        JMP MA_DESTROY
CK_CANCELED:
        LDX #<CK_CANCEL_TEXT
        LDY #>CK_CANCEL_TEXT
        BRA CK_MESSAGE
CK_COMMAND_BAD:
        LDX #<CK_BAD_TEXT
        LDY #>CK_BAD_TEXT
        BRA CK_MESSAGE
CK_HELP:
        LDX #<CK_HELP_TEXT
        LDY #>CK_HELP_TEXT
CK_MESSAGE:
        ; F's short-string printer wraps Y at 256 bytes. The RAM printer
        ; advances the pointer across pages, including the complete help text.
        JSR OI_PRINT
        JMP CK_MENU
CK_PROMPT: DB "RAM KIT ? T I X Q> ",0
CK_CONFIRM: DB "Erase BOTH monitors: type ERASE then Enter> ",0
CK_ERASE_WORD: DB "ERASE",0
CK_CANCEL_TEXT: DB "CANCELED: MON erase",13,10,0
CK_BAD_TEXT: DB "REFUSED: command; ? for help",13,10,0
CK_HELP_TEXT:
        DB "?  Help (commands then Enter)",13,10
        DB "T  Restore embedded b14 MON A/B; verify; boot",13,10
        DB "I  OIP1 host transfer: read/write one 4096-byte sector + CRC",13,10
        DB "   Allowed B0-2:8-F, B3:8/9/E; protects B3:A/B/C/D/F",13,10
        DB "   Writes require current preimage CRC and durable wear reservation",13,10
        DB "X  Erase BOTH MON A/B (requires ERASE confirmation)",13,10
        DB "Q  Restart through F; use S for recovery",13,10
        DB "Raw app loads at 0200. Needs matching b14 F and valid journal to write.",13,10
        DB "Bad/partial binary transfer locks until reset; no RTC changes.",13,10,0
