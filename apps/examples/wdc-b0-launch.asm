; Project-authored opaque B0:$8000 launcher, 65C02 only.
; Requires the exact retained vendor B0:F sector admitted by the host:
; SHA256 ce5415f4e5032e44a19a2ab801ca9090fd81434355421d1913fca86a62f5a44b
; The fingerprints below are compatibility checks, not a portable WDC ABI.
; No vendor firmware is bundled. Foundation F and its journal stay separate.
; Link at $8000; pad to a complete 4096-byte sector for OPAQUE installation.
        MODULE WDC_B0_LAUNCH
        INCLUDE "str8n-v2-public.inc"
        XDEF LAUNCH_START,LAUNCH_END
        CODE
LAUNCH_START:
        SEI
        CLD
        LDX #$FF
        TXS
        LDX #11
CHECK_ID:
        LDA $F80C,X
        CMP EXPECT_ID,X
        BNE REJECT
        DEX
        BPL CHECK_ID
        LDX #11
CHECK_SERIAL:
        LDA $F800,X
        CMP EXPECT_SERIAL,X
        BNE REJECT
        DEX
        BPL CHECK_SERIAL
        LDX #10
CHECK_MAIN:
        LDA $F8A6,X
        CMP EXPECT_MAIN,X
        BNE REJECT
        DEX
        BPL CHECK_MAIN
        JSR $F800                ; Pinned FT245 initializer; no EDU init.
        LDX #0
PRINT_BANNER:
        LDA BANNER,X
        BEQ ENTER_WDC
        JSR $F803                ; Pinned FT245 byte output, X preserved.
        INX
        BRA PRINT_BANNER
ENTER_WDC:
        JMP $F8A6                ; Main has no auto-application timeout.
REJECT:
        JMP STR8V2_RAM_RESET     ; Select golden B3 and reopen the chooser.
                                 ; S selects recovery if a guard ever rejects.
EXPECT_ID:
        DB "SXB2",$2C,$01,$00,$00,$C8,$00,$00,$00
EXPECT_SERIAL:
        DB $4C,$C2,$F9,$4C,$D0,$F9,$4C,$F4,$F9,$4C,$10,$FA
EXPECT_MAIN:
        DB $78,$D8,$A2,$FF,$9A,$20,$F4,$F9,$C9,$55,$D0
BANNER:
        DB 13,10,"WDC B0 / BASE1 DEFAULT BOOT",13,10,0
LAUNCH_END:
        ENDMOD
        END
