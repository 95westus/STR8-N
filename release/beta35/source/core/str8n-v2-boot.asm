; Immutable Bank-3 F bootstrap and independent binary recovery console.
; B3:A/B separately linked monitor slots; B3:C/D config/wear journal.
; No routine firmware operation writes F. Flash busy execution stays in RAM.
                        MODULE V2_BOOT
                        XDEF BOOT_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "vectors-symbols.inc"
                        CODE
                        DB "SN",$02,$00
                        JMP BOOT_RESET             ; F004 RESET
                        JMP BOOT_HOLD              ; F007 HOLD
                        JMP V2W_CON_INIT
                        JMP V2W_PUTC
                        JMP V2W_GETC
                        JMP V2W_RAW_POLL
                        JMP V2W_CHECK_CANCEL
                        JMP V2W_RX_RESET
                        JMP BOOT_RESERVED
                        JMP V2V_RAM_HEX_OUT
                        JMP V2V_RAM_NEWLINE
                        JMP V2V_RAM_HEX_NIBBLE
                        JMP V2V_RAM_CAPS_QUERY
                        JMP V2V_RAM_BOARD_QUERY
                        JMP BOOT_RESERVED
                        JMP BOOT_RESERVED
BOOT_RESERVED:          RTS
                        DB "CA",$01,$17             ; F035
BOOT_API_PROMOTE:       JMP BOOT_META_PROMOTE       ; F038, config including preference
                        DB $FF,$FF,$FF,$FF
                        INCLUDE "sr-stubs.inc"      ; F040, 19 six-byte stubs
BOOT_API_READ:          JMP BOOT_META_READ           ; F0B2
BOOT_API_CFG:           JMP BOOT_META_CFG            ; F0B5
BOOT_ERASE_ENTRY:       JMP BOOT_META_ERASE          ; F0B8
BOOT_API_W:             JMP BOOT_REPORT              ; F0BB
BOOT_API_UPDATE:        JMP BOOT_UPDATE              ; F0BE
BOOT_WEAR_DESCRIPTOR:   DB "WR",$01,$01

BOOT_RESET:             SEI
                        CLD
                        LDX #$FF
                        TXS
; Reset on either supported CPU. XCE is a one-byte unused NOP on W65C02.
                        LDA #$02
                        CLC
BOOT_XCE:               DB $FB,$EA
                        BCC BOOT_CPU_READY
                        LDA #$16
                        SEC
BOOT_XCE_RESTORE:       DB $FB,$EA
BOOT_CPU_READY:         STA V2_CPU
                        LDX #$03
BOOT_CLEAR:             STZ V2_RESIDENT,X
                        INX
                        BNE BOOT_CLEAR
                        LDA #$03
                        STA V2_RESIDENT
                        STA V2_SELECTED
                        STA V2_TARGET
                        STZ V2_NMI_HOLD
                        STZ V2_SKIP_LF
                        INCLUDE "worker-copy.inc"
                        LDX #$00
BOOT_COPY_VECTORS:      LDA BOOT_VECTOR_IMAGE,X
                        STA V2_VECTOR_CODE,X
                        INX
                        CPX #V2_VECTOR_SIZE
                        BNE BOOT_COPY_VECTORS
                        LDX #$08
BOOT_POINTERS:          LDA #<V2V_DEFAULT
                        STA V2_POINTERS,X
                        STA V2_NATIVE_POINTERS,X
                        LDA #>V2V_DEFAULT
                        STA V2_POINTERS+1,X
                        STA V2_NATIVE_POINTERS+1,X
                        DEX
                        DEX
                        BPL BOOT_POINTERS
                        JSR V2W_CON_INIT
                        JSR V2W_RX_RESET
                        LDA #$03
                        JSR V2W_SELECT
                        LDA #$30
                        STA V2_PIA_CRA
                        LDA #$FF
                        STA V2_LED
                        LDA #$34
                        STA V2_PIA_CRA
                        LDA #V2_LED_RUNNING
                        STA V2_LED
                        JSR BOOT_SELECT
                        LDA BOOT_BEST
                        STA BOOT_ACTIVE
; One bounded startup delay, before the selection prompt. Never block on USB.
                        JSR BOOT_FIFO_DRAIN
                        LDY #$A0
BOOT_STARTUP_DOTS:      JSR V2W_RAW_POLL
                        BCC BOOT_DOT_WAIT
                        AND #$DF
                        CMP #'A'
                        BEQ BOOT_WINDOW_A
                        CMP #'B'
                        BEQ BOOT_WINDOW_B
                        JMP BOOT_SHOW_CHOICES
BOOT_DOT_WAIT:          JSR V2W_BOOT_DELAY
                        LDA #'.'
                        JSR BOOT_CHOICE_PUTC
                        DEY
                        BNE BOOT_STARTUP_DOTS
; Any non-A/B byte skips only the dots; slot selection remains validated.
BOOT_SHOW_CHOICES:
                        LDA BOOT_ACTIVE
                        BNE KEY_LONG_112
                        JMP BOOT_RECOVERY
KEY_LONG_112:
                        LDA #$A0
                        JSR BOOT_CHOICE_SLOT
                        LDA #$B0
                        JSR BOOT_CHOICE_SLOT
                        LDX #<BOOT_CHOICE_TEXT
                        LDY #>BOOT_CHOICE_TEXT
                        JSR BOOT_CHOICE_PRINT
                        LDA #$48
                        STA $7DF8
BOOT_RECOVERY_WINDOW:   JSR V2W_RAW_POLL
                        BCC BOOT_WINDOW_NEXT
                        AND #$DF
                        CMP #'S'
                        BNE KEY_LONG_126
                        JMP BOOT_RECOVERY
KEY_LONG_126:
                        CMP #$03
                        BNE KEY_LONG_128
                        JMP BOOT_RECOVERY
KEY_LONG_128:
                        CMP #$0D
                        BEQ BOOT_WINDOW_DEFAULT
                        CMP #'A'
                        BEQ BOOT_WINDOW_A
                        CMP #'B'
                        BNE BOOT_WINDOW_NEXT
BOOT_WINDOW_B:          LDA #$B0
                        JMP BOOT_WINDOW_SLOT
BOOT_WINDOW_A:          LDA #$A0
BOOT_WINDOW_SLOT:       STA BOOT_DEST
                        STA V2_PTR+1
                        STZ V2_PTR
                        JSR BOOT_SLOT_CHECK
                        BCC BOOT_SHOW_CHOICES
                        LDA BOOT_DEST
                        STA BOOT_ACTIVE
                        JMP BOOT_LAUNCH
BOOT_WINDOW_NEXT:       JSR V2W_BOOT_DELAY
                        DEC $7DF8
                        BNE BOOT_RECOVERY_WINDOW
BOOT_WINDOW_DEFAULT:
                        LDA BOOT_ACTIVE
                        BNE KEY_LONG_151
                        JMP BOOT_RECOVERY
KEY_LONG_151:
                        JMP BOOT_LAUNCH

BOOT_CHOICE_SLOT:       STA BOOT_DEST
                        LDX #<BOOT_CHOICE_MONITOR
                        LDY #>BOOT_CHOICE_MONITOR
                        JSR BOOT_CHOICE_PRINT
                        LDA BOOT_DEST
                        CMP #$B0
                        BNE BOOT_CHOICE_A_NAME
                        LDA #'B'
                        JMP BOOT_CHOICE_NAME
BOOT_CHOICE_A_NAME:     LDA #'A'
BOOT_CHOICE_NAME:       JSR BOOT_CHOICE_PUTC
                        STZ V2_PTR
                        LDA BOOT_DEST
                        STA V2_PTR+1
                        JSR BOOT_SLOT_CHECK
                        BCC BOOT_CHOICE_BAD
                        LDX #<BOOT_CHOICE_GEN
                        LDY #>BOOT_CHOICE_GEN
                        JSR BOOT_CHOICE_PRINT
                        LDY #$0B
BOOT_CHOICE_GENERATION: LDA (V2_PTR),Y
                        PHA
                        LSR A
                        LSR A
                        LSR A
                        LSR A
                        JSR BOOT_CHOICE_NIBBLE
                        PLA
                        AND #$0F
                        JSR BOOT_CHOICE_NIBBLE
                        DEY
                        CPY #$07
                        BNE BOOT_CHOICE_GENERATION
                        LDX #<BOOT_CHOICE_VALID
                        LDY #>BOOT_CHOICE_VALID
                        JSR BOOT_CHOICE_PRINT
                        LDA BOOT_DEST
                        CMP BOOT_ACTIVE
                        BNE BOOT_CHOICE_RETURN
                        LDX #<BOOT_CHOICE_DEFAULT
                        LDY #>BOOT_CHOICE_DEFAULT
                        JMP BOOT_CHOICE_PRINT
BOOT_CHOICE_BAD:        LDX #<BOOT_CHOICE_INVALID
                        LDY #>BOOT_CHOICE_INVALID
                        JMP BOOT_CHOICE_PRINT
BOOT_CHOICE_RETURN:     RTS
BOOT_CHOICE_NIBBLE:     CMP #$0A
                        BCC BOOT_CHOICE_DIGIT
                        ADC #$06
BOOT_CHOICE_DIGIT:      CLC
                        ADC #'0'
BOOT_CHOICE_PUTC:       PHA
                        LDA V2_CONSOLE
                        BNE BOOT_CHOICE_DROP
                        LDA #$21
                        BIT V2_CTRL
                        BNE BOOT_CHOICE_DROP
                        PLA
                        JMP V2W_SEND
BOOT_CHOICE_DROP:       PLA
                        RTS
BOOT_CHOICE_PRINT:      STX V2_ADDR
                        STY V2_ADDR+1
                        PHY
                        LDY #$00
BOOT_CHOICE_CHAR:       LDA (V2_ADDR),Y
                        BEQ BOOT_CHOICE_END
                        JSR BOOT_CHOICE_PUTC
                        INY
                        JMP BOOT_CHOICE_CHAR
BOOT_CHOICE_END:        PLY
                        RTS

BOOT_HOLD:              SEI
                        CLD
                        LDX #$FF
                        TXS
                        LDA BOOT_ACTIVE
                        BNE KEY_LONG_232
                        JMP BOOT_RECOVERY
KEY_LONG_232:
                        STA BOOT_DEST
                        STZ V2_PTR
                        STA V2_PTR+1
                        JSR BOOT_SLOT_CHECK
                        BCS KEY_LONG_237
                        JMP BOOT_RESET
KEY_LONG_237:
                        LDA #$87
                        STA BOOT_CALL_PTR
                        LDA BOOT_ACTIVE
                        STA BOOT_CALL_PTR+1
                        JMP (BOOT_CALL_PTR)

BOOT_SELECT:            STZ BOOT_BEST
                        JSR BOOT_META_READ
                        LDA #$A0
                        STA BOOT_SLOT
BOOT_SELECT_NEXT:       LDA BOOT_SLOT
                        STA BOOT_DEST
                        STZ V2_PTR
                        STA V2_PTR+1
                        JSR BOOT_SLOT_CHECK
                        BCC BOOT_SELECT_SKIP
; A journal preference identifies one exact, validated generation. A stale or
; corrupt preference leaves the ordinary newest-valid fallback in force.
                        LDA V2_CONFIG+7
                        CMP #'P'
                        BNE BOOT_SELECT_GENERATION
                        LDA V2_CONFIG+8
                        CMP BOOT_SLOT
                        BNE BOOT_SELECT_GENERATION
                        LDY #$0B
BOOT_PREFERRED_GEN:     LDA (V2_PTR),Y
                        CMP V2_CONFIG+1,Y
                        BNE BOOT_SELECT_GENERATION
                        DEY
                        CPY #$07
                        BNE BOOT_PREFERRED_GEN
                        LDA BOOT_SLOT
                        STA BOOT_BEST
                        RTS
BOOT_SELECT_GENERATION:
                        LDA BOOT_BEST
                        BEQ BOOT_SELECT_NEW
                        LDY #$0B
BOOT_GEN_COMPARE:       LDA (V2_PTR),Y
                        CMP BOOT_GENERATION-8,Y
                        BCC BOOT_SELECT_SKIP
                        BNE BOOT_SELECT_NEW
                        DEY
                        CPY #$07
                        BNE BOOT_GEN_COMPARE
                        BRA BOOT_SELECT_SKIP
BOOT_SELECT_NEW:        LDA BOOT_SLOT
                        STA BOOT_BEST
                        LDY #$08
BOOT_GEN_COPY:          LDA (V2_PTR),Y
                        STA BOOT_GENERATION-8,Y
                        INY
                        CPY #$0C
                        BNE BOOT_GEN_COPY
BOOT_SELECT_SKIP:       JMP BOOT_SELECT_SKIP_OUT

; PTR is a sector-aligned flash slot or the 6800 staging buffer. DEST is A0/B0.
; All header execution addresses are fixed and constrained, independently of CRC.
BOOT_SLOT_CHECK:        LDA V2_PTR+1
                        STA BOOT_IO_PAGE
                        LDY #$00
                        LDA (V2_PTR),Y
                        CMP #'M'
                        BEQ KEY_LONG_307
                        JMP BOOT_SLOT_BAD
KEY_LONG_307:
                        INY
                        LDA (V2_PTR),Y
                        CMP #'I'
                        BEQ KEY_LONG_311
                        JMP BOOT_SLOT_BAD
KEY_LONG_311:
                        INY
                        LDA (V2_PTR),Y
                        CMP #$01
                        BEQ KEY_LONG_315
                        JMP BOOT_SLOT_BAD
KEY_LONG_315:
                        INY
                        LDA (V2_PTR),Y
                        CMP BOOT_DEST
                        BEQ KEY_LONG_319
                        JMP BOOT_SLOT_BAD
KEY_LONG_319:
                        INY
                        LDA (V2_PTR),Y
                        CMP #$03
                        BEQ KEY_LONG_323
                        JMP BOOT_SLOT_BAD
KEY_LONG_323:
                        INY
                        LDA (V2_PTR),Y
                        CMP #$01
                        BEQ KEY_LONG_327
                        JMP BOOT_SLOT_BAD
KEY_LONG_327:
                        LDY #$0D
                        LDA (V2_PTR),Y
                        CMP #$0F
                        BCC BOOT_LENGTH_OK
                        BEQ KEY_LONG_332
                        JMP BOOT_SLOT_BAD
KEY_LONG_332:
                        DEY
                        LDA (V2_PTR),Y
                        CMP #$81
                        BCC KEY_LONG_336
                        JMP BOOT_SLOT_BAD
KEY_LONG_336:
BOOT_LENGTH_OK:         LDY #$0C
                        LDA (V2_PTR),Y
                        STA BOOT_LENGTH
                        INY
                        LDA (V2_PTR),Y
                        ORA BOOT_LENGTH
                        BNE KEY_LONG_343
                        JMP BOOT_SLOT_BAD
KEY_LONG_343:
                        INY
                        LDA (V2_PTR),Y
                        CMP #$84
                        BEQ KEY_LONG_347
                        JMP BOOT_SLOT_BAD
KEY_LONG_347:
                        INY
                        LDA (V2_PTR),Y
                        CMP BOOT_DEST
                        BNE BOOT_SLOT_BAD
                        INY
                        LDA (V2_PTR),Y
                        CMP #$87
                        BNE BOOT_SLOT_BAD
                        INY
                        LDA (V2_PTR),Y
                        CMP BOOT_DEST
                        BNE BOOT_SLOT_BAD
                        LDY #$1F
                        LDA (V2_PTR),Y
                        BNE BOOT_SLOT_BAD
; Require the exact installed bootstrap contract, including worker addresses.
                        LDY #$14
BOOT_COMPAT_CHECK:      LDA (V2_PTR),Y
                        CMP BOOT_COMPAT_DATA-$14,Y
                        BNE BOOT_SLOT_BAD
                        INY
                        CPY #$18
                        BNE BOOT_COMPAT_CHECK
                        LDY #$80
                        LDA (V2_PTR),Y
                        CMP #'S'
                        BNE BOOT_SLOT_BAD
                        INY
                        LDA (V2_PTR),Y
                        CMP #'N'
                        BNE BOOT_SLOT_BAD
                        JSR J_CRC_INIT
                        LDY #$00
BOOT_HEADER_CRC:        LDA (V2_PTR),Y
                        JSR J_CRC_BYTE
                        INY
                        CPY #$12
                        BNE BOOT_HEADER_CRC
                        LDA BOOT_IO_PAGE
                        CLC
                        ADC #$10
                        STA BOOT_END_PAGE
                        LDY #$20
BOOT_PAYLOAD_CRC:       LDA (V2_PTR),Y
                        JSR J_CRC_BYTE
                        INY
                        BNE BOOT_PAYLOAD_CRC
                        INC V2_PTR+1
                        LDA V2_PTR+1
                        CMP BOOT_END_PAGE
                        BNE BOOT_PAYLOAD_CRC
                        LDA BOOT_IO_PAGE
                        STA V2_PTR+1
                        LDY #$12
                        LDA (V2_PTR),Y
                        CMP J_CRC
                        BNE BOOT_SLOT_BAD
                        INY
                        LDA (V2_PTR),Y
                        CMP J_CRC+1
                        BNE BOOT_SLOT_BAD
                        SEC
                        RTS
BOOT_SLOT_BAD:          CLC
                        RTS


; Returning private services shared by S/R/T. Preserve monitor parser pointers.
BOOT_SELECT_SKIP_OUT:   LDA #$10
                        TSB BOOT_SLOT
                        BNE BOOT_SELECT_DONE_OUT
                        JMP BOOT_SELECT_NEXT
BOOT_SELECT_DONE_OUT:   RTS
                        DB $FF,$FF,$FF
BOOT_SR_ROUTE:          PHA
                        PHY
                        LDA V2_PTR
                        PHA
                        LDA V2_PTR+1
                        PHA
                        STZ V2_PTR
                        LDA BOOT_ACTIVE
                        STA V2_PTR+1
                        TXA
                        CLC
                        ADC #$20
                        TAY
                        LDA (V2_PTR),Y
                        STA BOOT_CALL_PTR
                        INY
                        LDA (V2_PTR),Y
                        STA BOOT_CALL_PTR+1
                        PLA
                        STA V2_PTR+1
                        PLA
                        STA V2_PTR
                        PLY
                        PLA
                        PLX
                        JMP (BOOT_CALL_PTR)

BOOT_LAUNCH:            STA BOOT_CALL_PTR+1
                        LDA #$84
                        STA BOOT_CALL_PTR
                        JMP (BOOT_CALL_PTR)

BOOT_RECOVERY:          JSR V2W_RX_RESET
                        LDX #<BOOT_RECOVERY_TEXT
                        LDY #>BOOT_RECOVERY_TEXT
                        JSR BOOT_PRINT
BOOT_MENU:              STZ V2_CANCEL_REQUEST
                        LDX #<BOOT_PROMPT_TEXT
                        LDY #>BOOT_PROMPT_TEXT
                        JSR BOOT_PRINT
                        LDX #$00
BOOT_LINE:              JSR V2W_GETC
                        CMP #$0D
                        BEQ BOOT_LINE_END
                        CMP #$0A
                        BEQ BOOT_LINE_END
                        CMP #$03
                        BEQ BOOT_MENU
                        CMP #'a'
                        BCC BOOT_LINE_STORE
                        CMP #'z'+1
                        BCS BOOT_LINE_STORE
                        AND #$DF
BOOT_LINE_STORE:
                        CPX #$04
                        BCS BOOT_LINE
                        STA V2_LINE,X
                        INX
                        JMP BOOT_LINE
BOOT_LINE_END:          STZ V2_LINE,X
                        JSR V2V_RAM_NEWLINE
                        LDA V2_LINE
                        CMP #'U'
                        BEQ BOOT_UPDATE
                        LDA V2_LINE+1
                        BNE BOOT_MENU
                        LDA V2_LINE
                        CMP #'W'
                        BEQ BOOT_MENU_W
                        CMP #'A'
                        BEQ BOOT_MENU_A
                        CMP #'B'
                        BNE BOOT_MENU
                        LDA #$B0
                        JMP BOOT_MENU_SLOT
BOOT_MENU_A:            LDA #$A0
BOOT_MENU_SLOT:         STA BOOT_DEST
                        STZ V2_PTR
                        STA V2_PTR+1
                        JSR BOOT_SLOT_CHECK
                        BCC BOOT_MENU
                        LDA BOOT_DEST
                        STA BOOT_ACTIVE
                        JMP BOOT_HOLD
BOOT_MENU_W:            JSR BOOT_REPORT
                        JMP BOOT_MENU

; U A|B -> Y -> exact 4096 binary bytes. This path is usable with BOTH slots
; corrupt; it depends only on fixed F and the copied RAM services.
BOOT_UPDATE:            LDA V2_LINE+1
                        CMP #' '
                        BEQ KEY_LONG_507
                        JMP BOOT_UPDATE_BAD
KEY_LONG_507:
                        LDA V2_LINE+3
                        BEQ KEY_LONG_509
                        JMP BOOT_UPDATE_BAD
KEY_LONG_509:
                        LDA V2_LINE+2
                        CMP #'A'
                        BEQ BOOT_UPDATE_A
                        CMP #'B'
                        BEQ KEY_LONG_514
                        JMP BOOT_UPDATE_BAD
KEY_LONG_514:
                        LDA #$B0
                        JMP BOOT_UPDATE_SLOT
BOOT_UPDATE_A:          LDA #$A0
BOOT_UPDATE_SLOT:       STA BOOT_DEST
                        CMP BOOT_ACTIVE
                        BNE KEY_LONG_520
                        JMP BOOT_UPDATE_BAD
KEY_LONG_520:
; Never replace the proven preference from a one-time candidate session.
; Independent recovery (no active monitor) can repair either corrupt slot.
                        LDA BOOT_ACTIVE
                        BEQ BOOT_UPDATE_ALLOWED
                        JSR BOOT_META_READ
                        LDA V2_CONFIG+7
                        CMP #'P'
                        BNE BOOT_UPDATE_ALLOWED
                        LDA V2_CONFIG+8
                        CMP BOOT_DEST
                        BNE KEY_LONG_531
                        JMP BOOT_UPDATE_BAD
KEY_LONG_531:
BOOT_UPDATE_ALLOWED:
                        LDX #<BOOT_CONFIRM_TEXT
                        LDY #>BOOT_CONFIRM_TEXT
                        JSR BOOT_PRINT
                        JSR V2W_GETC
                        CMP #'Y'
                        BEQ KEY_LONG_538
                        JMP BOOT_UPDATE_BAD
KEY_LONG_538:
                        JSR V2W_GETC
                        CMP #$0D
                        BEQ KEY_LONG_541
                        JMP BOOT_UPDATE_BAD
KEY_LONG_541:
                        LDX #<BOOT_BINARY_TEXT
                        LDY #>BOOT_BINARY_TEXT
                        JSR BOOT_PRINT
; Binary data bypasses text queue/Ctrl-C semantics: every byte value is valid.
                        STZ V2_BUF_PTR
                        LDA #$68
                        STA V2_BUF_PTR+1
BOOT_RECEIVE:           JSR V2W_RAW_POLL
                        BCC BOOT_RECEIVE
                        STA (V2_BUF_PTR)
                        INC V2_BUF_PTR
                        BNE BOOT_RECEIVE
                        INC V2_BUF_PTR+1
                        LDA V2_BUF_PTR+1
                        CMP #$78
                        BNE BOOT_RECEIVE
                        STZ V2_PTR
                        LDA #$68
                        STA V2_PTR+1
                        JSR BOOT_SLOT_CHECK
                        BCC BOOT_UPDATE_BAD
; Reject stale/equal generations while a valid active monitor exists.
                        LDA BOOT_ACTIVE
                        BEQ BOOT_UPDATE_NEW
                        STA V2_ADDR+1
                        STZ V2_ADDR
                        LDY #$0B
BOOT_UPDATE_GEN:        LDA (V2_PTR),Y
                        CMP (V2_ADDR),Y
                        BCC BOOT_UPDATE_BAD
                        BNE BOOT_UPDATE_NEW
                        DEY
                        CPY #$07
                        BNE BOOT_UPDATE_GEN
                        JMP BOOT_UPDATE_BAD
BOOT_UPDATE_NEW:        LDA #$FF
                        STA $681F
                        LDA #$03
                        STA V2_SELECTED
                        LDA BOOT_DEST
                        STA V2_SECTOR
                        JSR BOOT_UPDATE_WRITE
                        NOP
                        NOP
                        NOP
                        NOP
                        NOP
                        NOP
                        BCS BOOT_UPDATE_BAD
                        STZ V2_FLASH_PTR
                        LDA BOOT_DEST
                        STA V2_FLASH_PTR+1
                        LDA #$1F
                        STA V2_FLASH_PTR
                        STZ V2_FLASH_DATA
                        JSR V2W_BYTE
                        BCC BOOT_UPDATE_BAD
                        STZ V2_PTR
                        LDA BOOT_DEST
                        STA V2_PTR+1
                        JSR BOOT_SLOT_CHECK
                        BCC BOOT_UPDATE_BAD
                        LDX #<BOOT_DONE_TEXT
                        LDY #>BOOT_DONE_TEXT
                        JSR BOOT_PRINT
                        JMP BOOT_RESET
BOOT_UPDATE_BAD:        LDX #<BOOT_FAILED_TEXT
                        LDY #>BOOT_FAILED_TEXT
                        JSR BOOT_PRINT
                        JMP BOOT_MENU

BOOT_PRINT:             STX V2_PTR
                        STY V2_PTR+1
                        LDY #$00
BOOT_PRINT_BYTE:        LDA (V2_PTR),Y
                        BEQ BOOT_PRINT_END
                        JSR V2W_PUTC
                        INY
                        JMP BOOT_PRINT_BYTE
BOOT_PRINT_END:         RTS
BOOT_RECOVERY_TEXT:     DB $0D,$0A,"FIXED F RECOVERY",$0D,$0A,"A/B U A|B W",$0D,$0A,0
BOOT_PROMPT_TEXT:       DB "REC> ",0
BOOT_CONFIRM_TEXT:     DB "Y then Enter> ",0
BOOT_BINARY_TEXT:      DB "SEND 4096 BIN",$0D,$0A,0
BOOT_DONE_TEXT:        DB "COMMITTED",$0D,$0A,0
BOOT_FAILED_TEXT:      DB "REFUSED",$0D,$0A,0
BOOT_CHOICE_MONITOR:    DB $0D,$0A,"MONITOR ",0
BOOT_CHOICE_GEN:        DB " gen ",0
BOOT_CHOICE_VALID:      DB " VALID",0
BOOT_CHOICE_DEFAULT:    DB " default",0
BOOT_CHOICE_INVALID:    DB " INVALID",0
BOOT_CHOICE_TEXT:       DB $0D,$0A,"A/B/S,Enter default [3s]: ",0
; Patched by the builder with CRC32 of the complete canonical F sector with
; this field zeroed. Slot updates cannot silently change the bootstrap ABI.
                        DB $FF,$FF
; Read at most 4*256 pending FTDI bytes, stopping at the first empty poll.
; No wait for more input; reset software buffering once, before input opens.
BOOT_FIFO_DRAIN:        LDY #$04
                        LDX #$00
BOOT_FIFO_DRAIN_NEXT:   JSR V2W_RAW_POLL
                        BCC BOOT_FIFO_DRAIN_DONE
                        DEX
                        BNE BOOT_FIFO_DRAIN_NEXT
                        DEY
                        BNE BOOT_FIFO_DRAIN_NEXT
BOOT_FIFO_DRAIN_DONE:   JMP V2W_RX_RESET
BOOT_COMPAT_DATA:       DB $00,$00,$00,$00
                        INCLUDE "str8n-v2-journal.inc"
; A missing/invalid journal never permits an erase. Only completely blank
; C/D permits bootstrap programming of bytes which are FF or already equal.
; A torn matching upload resumes without programming any byte twice.
BOOT_UPDATE_WRITE:      JSR BOOT_META_READ
                        BCS BOOT_UPDATE_ACCOUNTED
                        STZ V2_PTR
                        LDA #$C0
                        STA V2_PTR+1
                        LDA #$E0
                        STA BOOT_END_PAGE
                        LDY #$00
                        JSR J_SECTOR_BYTE
                        BCC BOOT_BOOTSTRAP_REFUSE
                        JSR V2W_ANALYZE
                        LDA V2_ERASE
                        BNE BOOT_BOOTSTRAP_REFUSE
                        STZ V2_SELF
                        STZ V2_FLASH_ERROR
                        LDA #$01
                        STA V2_NMI_HOLD
                        JSR V2W_BEGIN
                        JMP V2W_PROGRAM
BOOT_UPDATE_ACCOUNTED:  LDA #$01
                        STA V2_ERASE
                        STZ V2_SELF
                        JMP V2W_MUTATE
BOOT_BOOTSTRAP_REFUSE:  SEC
                        RTS
BOOT_WORKER_IMAGE:      INCLUDE "worker-image.inc"
BOOT_VECTOR_IMAGE:      INCLUDE "vectors-image.inc"
BOOT_END:
                        ENDMOD
                        END
