; STR8-N v2 RAM-only W65C816 native BRK/NMI acceptance probe.
; Load with L, start with G 2000, then press NMI once. No flash writes.
; Pointer publication/restoration occurs in emulation mode under the NMI gate.
                        CHIP    65816
                        LONGA   OFF
                        LONGI   OFF
                        INCLUDE "str8n-v2-public.inc"

START:                  SEI
                        CLD
                        LDX     #$FF
                        TXS
                        LDA     STR8V2_NMI_GATE
                        BEQ     SAFE
                        JMP     REFUSE
SAFE:                   LDX     #$05
SAVE_POINTERS:          LDA     STR8V2_NATIVE_BRK_PTR,X
                        STA     SAVED_POINTERS,X
                        DEX
                        BPL     SAVE_POINTERS
                        INC     STR8V2_NMI_GATE
                        LDA     #<NATIVE_NMI_HANDLER
                        STA     STR8V2_NATIVE_NMI_PTR
                        LDA     #>NATIVE_NMI_HANDLER
                        STA     STR8V2_NATIVE_NMI_PTR+1
                        STZ     STR8V2_NMI_GATE
                        LDA     #<NATIVE_BRK_HANDLER
                        STA     STR8V2_NATIVE_BRK_PTR
                        LDA     #>NATIVE_BRK_HANDLER
                        STA     STR8V2_NATIVE_BRK_PTR+1
                        STZ     BRK_SEEN
                        STZ     NMI_SEEN
                        STZ     RESULT
                        STZ     TIME0
                        STZ     TIME1
                        STZ     TIME2
                        LDX     #<MSG_PRESS
                        LDY     #>MSG_PRESS
                        JSR     PRINT_TEXT

; Native mode with 8-bit A/X/Y, D=0, DBR=0, PBR=0 and stack $01FF.
ENTER_NATIVE:           CLC
                        XCE
                        SEP     #$30
                        LDA     #$55
                        LDX     #$5A
                        LDY     #$A5
                        BRK
                        NOP
AFTER_BRK:              CMP     #$55
                        BNE     NATIVE_DONE
                        CPX     #$5A
                        BNE     NATIVE_DONE
                        CPY     #$A5
                        BNE     NATIVE_DONE
                        TSX
                        CPX     #$FF
                        BNE     NATIVE_DONE
                        LDA     BRK_SEEN
                        CMP     #$01
                        BNE     NATIVE_DONE
                        LDA     BRK_SP
                        CMP     #$FB
                        BNE     NATIVE_DONE
                        LDA     BRK_PBR
                        BNE     NATIVE_DONE
                        INC     RESULT

                        LDA     #$55
                        LDX     #$5A
                        LDY     #$A5
WAIT_NMI:               BIT     NMI_SEEN
                        BNE     GOT_NMI
                        INC     TIME0
                        BNE     WAIT_NMI
                        INC     TIME1
                        BNE     WAIT_NMI
                        INC     TIME2
                        BNE     WAIT_NMI
                        BRA     NATIVE_DONE
GOT_NMI:                CMP     #$55
                        BNE     NATIVE_DONE
                        CPX     #$5A
                        BNE     NATIVE_DONE
                        CPY     #$A5
                        BNE     NATIVE_DONE
                        TSX
                        CPX     #$FF
                        BNE     NATIVE_DONE
                        LDA     NMI_SP
                        CMP     #$FB
                        BNE     NATIVE_DONE
                        LDA     NMI_PBR
                        BNE     NATIVE_DONE
                        INC     RESULT

; Monitor services are emulation-only. Return to E=1 before cleanup/reporting.
NATIVE_DONE:            SEI
                        SEC
                        XCE
CLEANUP:                INC     STR8V2_NMI_GATE
                        LDX     #$05
RESTORE_POINTERS:       LDA     SAVED_POINTERS,X
                        STA     STR8V2_NATIVE_BRK_PTR,X
                        DEX
                        BPL     RESTORE_POINTERS
                        STZ     STR8V2_NMI_GATE
                        LDX     #<MSG_FAIL
                        LDY     #>MSG_FAIL
                        LDA     RESULT
                        CMP     #$02
                        BNE     REPORT
                        LDX     #<MSG_PASS
                        LDY     #>MSG_PASS
                        BRA     REPORT
REFUSE:                 LDX     #<MSG_BUSY
                        LDY     #>MSG_BUSY
REPORT:                 JSR     PRINT_TEXT
                        JMP     STR8V2_HOLD

PRINT_TEXT:             STX     $80
                        STY     $81
                        LDY     #$00
PRINT_NEXT:             LDA     ($80),Y
                        BEQ     PRINT_DONE
                        JSR     STR8V2_PUTC
                        INY
                        BRA     PRINT_NEXT
PRINT_DONE:             RTS

; Native BRK/NMI stack: P at +1, PC at +2/+3, PBR at +4 from entry SP.
NATIVE_BRK_HANDLER:     STA     BRK_A
                        STX     BRK_X
                        STY     BRK_Y
                        TSX
                        STX     BRK_SP
                        LDA     $0104,X
                        STA     BRK_PBR
                        INC     BRK_SEEN
                        LDY     BRK_Y
                        LDX     BRK_X
                        LDA     BRK_A
                        RTI

NATIVE_NMI_HANDLER:     STA     NMI_A
                        STX     NMI_X
                        STY     NMI_Y
                        TSX
                        STX     NMI_SP
                        LDA     $0104,X
                        STA     NMI_PBR
                        INC     NMI_SEEN
                        LDY     NMI_Y
                        LDX     NMI_X
                        LDA     NMI_A
                        RTI

SAVED_POINTERS:         DS      6
BRK_SEEN:               DB      $00
NMI_SEEN:               DB      $00
RESULT:                 DB      $00
TIME0:                  DB      $00
TIME1:                  DB      $00
TIME2:                  DB      $00
BRK_A:                  DB      $00
BRK_X:                  DB      $00
BRK_Y:                  DB      $00
BRK_SP:                 DB      $00
BRK_PBR:                DB      $00
NMI_A:                  DB      $00
NMI_X:                  DB      $00
NMI_Y:                  DB      $00
NMI_SP:                 DB      $00
NMI_PBR:                DB      $00
MSG_PRESS:              DB      $0D,$0A,"816N: PRESS NMI",$0D,$0A,$00
MSG_PASS:               DB      "V2 816N BRK/NMI / A-X-Y / FRAME / RTI: PASS",$0D,$0A,$00
MSG_FAIL:               DB      "V2 816N BRK/NMI PROBE: FAIL/TIMEOUT",$0D,$0A,$00
MSG_BUSY:               DB      $0D,$0A,"REFUSE: NMI POINTER UPDATE BUSY",$0D,$0A,$00
PROBE_END:
                        END
