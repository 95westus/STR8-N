; STR8-N v2 RAM-only physical NMI probe. Load with L, start with G 2000,
; then press the board's NMI button once. No flash writes. The monitor's NMI
; gate protects both publication and restoration of the two-byte pointer.
                        INCLUDE "str8n-v2-public.inc"

NMI_GATE                EQU     $F4
NMI_POINTER             EQU     $7E00

START:                  SEI
                        CLD
                        LDX     #$FF
                        TXS
                        LDA     NMI_GATE
                        BEQ     NMI_READY
                        JMP     REFUSE
NMI_READY:
                        LDA     NMI_POINTER
                        STA     SAVED_NMI
                        LDA     NMI_POINTER+1
                        STA     SAVED_NMI+1
                        INC     NMI_GATE
                        LDA     #<NMI_HANDLER
                        STA     NMI_POINTER
                        LDA     #>NMI_HANDLER
                        STA     NMI_POINTER+1
                        STZ     NMI_GATE
                        STZ     NMI_SEEN
                        STZ     RESULT
                        STZ     TIME0
                        STZ     TIME1
                        STZ     TIME2
                        LDX     #<MSG_PRESS
                        LDY     #>MSG_PRESS
                        JSR     PRINT_TEXT
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
                        BRA     CLEANUP
GOT_NMI:                CMP     #$55
                        BNE     CLEANUP
                        CPX     #$5A
                        BNE     CLEANUP
                        CPY     #$A5
                        BNE     CLEANUP
                        TSX
                        CPX     #$FF
                        BNE     CLEANUP
                        LDA     OBS_A
                        CMP     #$55
                        BNE     CLEANUP
                        LDA     OBS_X
                        CMP     #$5A
                        BNE     CLEANUP
                        LDA     OBS_Y
                        CMP     #$A5
                        BNE     CLEANUP
                        LDA     OBS_P
                        AND     #$18
                        BNE     CLEANUP
                        INC     RESULT
CLEANUP:                SEI
                        INC     NMI_GATE
                        LDA     SAVED_NMI
                        STA     NMI_POINTER
                        LDA     SAVED_NMI+1
                        STA     NMI_POINTER+1
                        STZ     NMI_GATE
                        LDX     #<MSG_TIMEOUT
                        LDY     #>MSG_TIMEOUT
                        LDA     RESULT
                        BEQ     REPORT
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

NMI_HANDLER:            STA     OBS_A
                        STX     OBS_X
                        STY     OBS_Y
                        TSX
                        LDA     $0101,X
                        STA     OBS_P
                        INC     NMI_SEEN
                        LDY     OBS_Y
                        LDX     OBS_X
                        LDA     OBS_A
                        RTI

SAVED_NMI:              DW      $0000
NMI_SEEN:               DB      $00
RESULT:                 DB      $00
TIME0:                  DB      $00
TIME1:                  DB      $00
TIME2:                  DB      $00
OBS_A:                  DB      $00
OBS_X:                  DB      $00
OBS_Y:                  DB      $00
OBS_P:                  DB      $00
MSG_PRESS:              DB      $0D,$0A,"PRESS NMI",$0D,$0A,$00
MSG_PASS:               DB      "V2 NMI / A-X-Y / STACK / RTI: PASS",$0D,$0A,$00
MSG_TIMEOUT:            DB      "V2 NMI PROBE: TIMEOUT",$0D,$0A,$00
MSG_BUSY:               DB      $0D,$0A,"REFUSE: NMI POINTER UPDATE BUSY",$0D,$0A,$00
PROBE_END:
                        END
