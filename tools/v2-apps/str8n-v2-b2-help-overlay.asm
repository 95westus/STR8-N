; Optional pinned H command. No changes to core or E carrier.
; Uses monitor foreground scratch and the format-1 registry's public layout.
                        MODULE B2_HELP_OVERLAY
                        XDEF HELP_ENTRY
                        XDEF HELP_END
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "str8n-v2-manager-public.inc"
TEXT_PTR                EQU $E0
                        CODE
HELP_ENTRY:             LDY #$01
HELP_ARGS:              LDA STR8V2_LINE,Y
                        BEQ HELP_SHOW
                        CMP #' '
                        BNE HELP_BAD_ARGS
                        INY
                        CPY #STR8V2_LINE_LIMIT
                        BCC HELP_ARGS
HELP_BAD_ARGS:          LDX #<USAGE_TEXT
                        LDY #>USAGE_TEXT
                        JSR PRINT
                        BRA HELP_DONE
HELP_SHOW:              LDX #<HELP_TEXT
                        LDY #>HELP_TEXT
                        JSR PRINT
                        LDX #$00
HELP_KEYS:              CPX MG_COUNT
                        BCS HELP_NEWLINE
                        CPX #MG_CAPACITY*3
                        BCS HELP_NEWLINE
                        LDA MG_TABLE,X
                        JSR STR8V2_RAM_PUTC
                        LDA #' '
                        JSR STR8V2_RAM_PUTC
                        INX
                        INX
                        INX
                        BRA HELP_KEYS
HELP_NEWLINE:           JSR STR8V2_RAM_NEWLINE
                        LDA #<NAMED_SERVICE
                        LDX #>NAMED_SERVICE
                        LDY #$02
                        JSR STR8MGR_LOOKUP
                        BCC HELP_DONE
                        LDA MG_NAMED_COUNT
                        BEQ HELP_DONE
                        LDX #<NAMED_TEXT
                        LDY #>NAMED_TEXT
                        JSR PRINT
                        LDX #$00
HELP_NAMES:             CPX MG_NAMED_COUNT
                        BCS HELP_NAMES_DONE
                        CPX #$20
                        BCS HELP_NAMES_DONE
                        PHX
                        LDA MG_NAMED_TABLE+1,X
                        TAY
                        LDA MG_NAMED_TABLE,X
                        TAX
                        JSR PRINT
                        LDA #' '
                        JSR STR8V2_RAM_PUTC
                        PLX
                        INX
                        INX
                        INX
                        INX
                        BRA HELP_NAMES
HELP_NAMES_DONE:        JSR STR8V2_RAM_NEWLINE
HELP_DONE:              LDA #$01
                        RTS
PRINT:                  STX TEXT_PTR
                        STY TEXT_PTR+1
                        LDY #$00
PRINT_BYTE:             LDA (TEXT_PTR),Y
                        BEQ PRINT_DONE
                        JSR STR8V2_RAM_PUTC
                        INC TEXT_PTR
                        BNE PRINT_BYTE
                        INC TEXT_PTR+1
                        BRA PRINT_BYTE
PRINT_DONE:             RTS
USAGE_TEXT:             DB "Use H",$0D,$0A,0
HELP_TEXT:              DB $0D,$0A,"B0-3                 Select flash bank",$0D,$0A
                        DB "D addr [end]         Dump memory",$0D,$0A
                        DB "M addr bytes         Modify RAM",$0D,$0A
                        DB "F addr bytes         Program flash",$0D,$0A
                        DB "G addr               Run application",$0D,$0A
                        DB "L                    Load S19 application",$0D,$0A
                        DB "I start end          Install monitor",$0D,$0A
                        DB "C 0|1 0-3 addr|V delay  Set boot options",$0D,$0A
                        DB "J0-3                 Boot selected bank",$0D,$0A
                        DB "?                    Core syntax summary",$0D,$0A
                        DB "H                    This optional help",$0D,$0A
                        DB "K [Bn 8-D m0 m1 m2 m3|OFF]  Extended config",$0D,$0A
                        DB "K AUTO [+key [entry]|-key|?]  Startup commands",$0D,$0A
                        DB "K AUTO QUIET 0|1     Startup messages on|off",$0D,$0A
                        DB "S start end name [Bn]  Save named RAM",$0D,$0A
                        DB "R name [Bn]          Restore named RAM",$0D,$0A
                        DB "T [Bn]               List saved records",$0D,$0A
                        DB "Bn=B0-B3; masks m0-m3 select sectors 8-D.",$0D,$0A
                        DB "K/S/R/T require the optional modules.",$0D,$0A
                        DB "Registered: ",0
NAMED_SERVICE:          DB "COMMAND.REGISTER",0
NAMED_TEXT:             DB "Named: ",0
HELP_END:
                        ENDMOD
                        END
