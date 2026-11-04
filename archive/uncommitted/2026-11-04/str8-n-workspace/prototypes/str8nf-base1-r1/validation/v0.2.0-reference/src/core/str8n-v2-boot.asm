; Immutable Bank-3 F bootstrap and independent binary recovery console.
; B3:A/B separately linked monitor slots; B3:C/D config/wear journal.
; No routine firmware operation writes F. Flash busy execution stays in RAM.
                        MODULE V2_BOOT
                        XDEF BOOT_END
                        INCLUDE "str8n-v2-eq.inc"
                        INCLUDE "str8n-v2-public.inc"
                        INCLUDE "vectors-symbols.inc"
B14_TICKS EQU $7C68
B14_PENDING EQU $7C69
B14_PENDING_BYTE EQU $7C6A
B14_FT_LO EQU 240
B14_FT_MID EQU 69
B14_FT_HI EQU 4
B14_AC_LO EQU 99
B14_AC_MID EQU 27
B14_AC_HI EQU 4
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
BOOT_API_LINE: JMP FC_READ_LINE
                        JMP V2V_RAM_HEX_OUT
                        JMP V2V_RAM_NEWLINE
                        JMP V2V_RAM_HEX_NIBBLE
                        JMP V2V_RAM_CAPS_QUERY
                        JMP V2V_RAM_BOARD_QUERY
BOOT_API_HEX_WORD: JMP FC_HEX_WORD
BOOT_API_HEX_BYTE: JMP FC_HEX_BYTE
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
        BCS P_LONG_1
        JMP BOOT_CPU_READY
P_LONG_1:
                        LDA #$16
                        SEC
BOOT_XCE_RESTORE:       DB $FB,$EA
BOOT_CPU_READY:         STA V2_CPU
                        LDX #$03
BOOT_CLEAR:             STZ V2_RESIDENT,X
                        INX
        BEQ P_LONG_2
        JMP BOOT_CLEAR
P_LONG_2:
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
        BEQ P_LONG_3
        JMP BOOT_COPY_VECTORS
P_LONG_3:
                        LDX #$08
BOOT_POINTERS:          LDA #<V2V_DEFAULT
                        STA V2_POINTERS,X
                        STA V2_NATIVE_POINTERS,X
                        LDA #>V2V_DEFAULT
                        STA V2_POINTERS+1,X
                        STA V2_NATIVE_POINTERS+1,X
                        DEX
                        DEX
        BMI P_LONG_4
        JMP BOOT_POINTERS
P_LONG_4:
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
        DB $EA,$EA,$EA
        LDA #<BOOT_NO_SERVICE
        STA JE_HANDLER
        LDA #>BOOT_NO_SERVICE
        STA JE_HANDLER+1
        JMP BOOT_START_CHOICES
; Read-only boot/config consumer. Never emits a flash command.
JE_FRAME EQU $6700
JE_HANDLER EQU $7C60
BR_TARGET EQU $7C64
BR_VALID EQU $7C65
BR_TICKS EQU $7C66
BR_CONFLICT EQU $7C67
RL_PTR EQU $E2
BOOT_SELECT:
        JSR BOOT_READ_RECORD
        LDA #'S'
        BCS P_LONG_5
        JMP BR_USE_DEFAULT
P_LONG_5:
        LDA JE_FRAME+7
BR_USE_DEFAULT:
        STA BR_TARGET
        RTS
; Optional fixed three-second startup UI. Replaces BOOT_START_CHOICES through
; the instruction immediately before BR_DEFAULT; no journal writes occur here.
; The saved default still comes from BOOT_SELECT. The legacy timeout byte is
; preserved in the record but this UI deliberately uses a fixed three seconds.
BR_SLICES EQU $7C7D             ; BR_BANK scratch, before an opaque handoff
BOOT_START_CHOICES:
        JMP BOOT_STARTUP
        LDX #<B07_CHOICES
        LDY #>B07_CHOICES
        JSR B07_PRINT_CHOICES
        LDA #6
        STA BR_TICKS
BR_COUNTDOWN:
        LDA BR_TICKS
        ORA #'0'
        JSR V2W_PUTC
        LDA BR_TICKS
        BNE P_LONG_6
        JMP BR_COUNTDOWN_DONE
P_LONG_6:
        LDA #' '
        JSR V2W_PUTC
        LDA #100
        STA BR_SLICES
BR_WINDOW:
        JSR V2W_RAW_POLL
        BCC P_LONG_7
        JMP BR_KEY
P_LONG_7:
BR_NO_KEY:
        LDA BR_TICKS
        BNE P_LONG_8
        JMP BR_COUNTDOWN_DEFAULT
P_LONG_8:
        ; One ~10 ms slice, including polling/loop overhead at 8 MHz.
        ; Poll between slices so a key never waits for a full second.
        LDX #62
        JSR V2W_BOOT_DELAY_OUTER
        DEC BR_SLICES
        BEQ P_LONG_9
        JMP BR_WINDOW
P_LONG_9:
        DEC BR_TICKS
        JMP BR_COUNTDOWN
BR_COUNTDOWN_DONE:
        ; Include keys received during the final delay slice.
        JSR V2W_RAW_POLL
        BCC P_LONG_10
        JMP BR_KEY
P_LONG_10:
BR_COUNTDOWN_DEFAULT:
        JSR V2V_RAM_NEWLINE

BR_DEFAULT:
        LDA BR_TARGET
        CMP #'A'
        BNE P_LONG_11
        JMP BR_DEFAULT_MON
P_LONG_11:
        CMP #'B'
        BEQ P_LONG_12
        JMP BR_DISPATCH
P_LONG_12:
BR_DEFAULT_MON:
        PHA
        CMP #'A'
        BNE P_LONG_13
        JMP BR_DEFAULT_A
P_LONG_13:
        LDA #$B0
        JMP BR_DEFAULT_GEN
BR_DEFAULT_A:
        LDA #$A0
BR_DEFAULT_GEN:
        STA V2_PTR+1
        STZ V2_PTR
        LDY #8
BR_GEN:
        LDA (V2_PTR),Y
        CMP JE_FRAME+10,Y
        BEQ P_LONG_14
        JMP BR_GEN_BAD
P_LONG_14:
        INY
        CPY #12
        BEQ P_LONG_15
        JMP BR_GEN
P_LONG_15:
        PLA
        JMP BR_DISPATCH
BR_GEN_BAD:
        PLA
        JMP BOOT_RECOVERY
BR_KEY:
        CMP #13
        BNE P_LONG_16
        JMP BR_NO_KEY
P_LONG_16:
        CMP #10
        BNE P_LONG_17
        JMP BR_NO_KEY
P_LONG_17:
        AND #$DF
BR_DISPATCH:
        CMP #'S'
        BNE P_LONG_18
        JMP BOOT_RECOVERY
P_LONG_18:
        CMP #3
        BNE P_LONG_19
        JMP BOOT_RECOVERY
P_LONG_19:
        CMP #'A'
        BNE P_LONG_20
        JMP BR_A
P_LONG_20:
        CMP #'B'
        BNE P_LONG_21
        JMP BR_B
P_LONG_21:
        ; AND #DF changes ASCII digits: accept both normalized and raw values.
        ORA #$20
        CMP #'0'
        BCS P_LONG_22
        JMP BR_NO_KEY
P_LONG_22:
        CMP #'4'
        BCC P_LONG_23
        JMP BR_NO_KEY
P_LONG_23:
        SEC
        SBC #'0'
        TAX
        STX BR_BANK
        LDA BR_VALID
        BNE P_LONG_24
        JMP BR_BAD
P_LONG_24:
        LDA #1
BR_MASK:
        CPX #0
        BNE P_LONG_25
        JMP BR_MASK_READY
P_LONG_25:
        ASL A
        DEX
        JMP BR_MASK
BR_MASK_READY:
        AND JE_FRAME+13
        BNE P_LONG_26
        JMP BR_BAD
P_LONG_26:
        LDX BR_BANK
        STX V2_SELECTED
        LDA JE_FRAME+14,X
        ASL A
        ASL A
        ASL A
        ASL A
        STA V2_VECTOR+1
        STZ V2_VECTOR
        JMP B08_BANK_LINE
BR_A:   LDA #$A0
        JMP BR_MON
BR_B:   LDA #$B0
BR_MON: STA BOOT_DEST
        STA V2_PTR+1
        STZ V2_PTR
        JSR BOOT_SLOT_CHECK
        BCS P_LONG_27
        JMP BR_BAD
P_LONG_27:
        LDA BOOT_DEST
        STA BOOT_ACTIVE
        JMP BOOT_LAUNCH
BR_BAD: JMP BOOT_RECOVERY
BR_BANK EQU $7C7D
; About 799,934 cycles including the caller JSR: nominal 0.1 s at 8 MHz.
BR_TENTH:
        JSR V2W_BOOT_DELAY
        JSR V2W_BOOT_DELAY
        LDX #110
        JMP V2W_BOOT_DELAY_OUTER

BOOT_RECOVERY:
        JSR B08_RECOVERY_LINE
        STZ V2_SKIP_LF
        LDX #<BR_RECOVERY
        LDY #>BR_RECOVERY
        JSR BOOT_PRINT
BOOT_MENU:
        STZ DC_BINARY
        LDX #<BR_PROMPT
        LDY #>BR_PROMPT
        JSR BOOT_PRINT
        JSR BOOT_B08_READ_LINE
        BCC BR_SYNTAX
        LDA V2_LINE
        CMP #'C'
        BEQ DC_MODE_COMMAND
        LDA V2_LINE+1
        BNE BR_SYNTAX
        LDA V2_LINE
        BEQ BOOT_MENU
        CMP #'?'
        BNE B11_NOT_HELP
        JMP B12_HELP
B11_NOT_HELP:
        CMP #'L'
        BNE B14_NOT_LOAD
        JMP RL_LOAD
B14_NOT_LOAD:
B14_FREE_DISPATCH:
        DB $EA,$EA,$EA,$EA,$EA,$EA,$EA,$EA,$EA,$EA,$EA,$EA,$EA,$EA,$EA
        CMP #'A'
        BNE P_LONG_36
        JMP BR_A
P_LONG_36:
        CMP #'B'
        BNE P_LONG_37
        JMP BR_B
P_LONG_37:
DC_MODE_COMMAND:
        LDA V2_LINE+2
        BNE BR_SYNTAX
        LDA V2_LINE+1
        SEC
        SBC #'0'
        JSR BOOT_CON_SELECT
        BCC BR_SYNTAX
        JMP BOOT_MENU
BR_SYNTAX:
        LDX #<BR_USAGE
        LDY #>BR_USAGE
        JMP BR_MESSAGE
BR_ERROR:
        LDX #<BR_REFUSED
        LDY #>BR_REFUSED
BR_MESSAGE:
        ; Builder replaces this compact message helper with explicit pointers.
        JSR BOOT_PRINT
        JMP BOOT_MENU

BOOT_VECTOR_IMAGE: INCLUDE "vectors-image.inc"
B14_MAIN_BASE:
; Raw BIN receiver. Empty polls count nominal CPU cycles; no frame/CRC/length.
; Main fits the tail of the old 302-byte RLP1 region after relocated vectors.
RL_LOAD_BYTE:
        PHA
        LDA V2_RX_BAD
        BNE B14_RX_BAD_POP
        LDA RL_PTR+1
        CMP #$65
        BCS B14_RANGE_POP
        PLA
        STA (RL_PTR)
        INC RL_PTR
        BNE B14_RELOAD
        INC RL_PTR+1
B14_RELOAD:
        LDA DC_LAST
        STA DC_BINARY
        ; DC_NEXT always equals the selected port after a successful poll.
        CMP #1
        BNE B14_ACIA_TIMER
        LDX #B14_FT_LO
        LDY #B14_FT_MID
        LDA #B14_FT_HI
        BRA B14_TIMER_SET
B14_ACIA_TIMER:
        LDX #B14_AC_LO
        LDY #B14_AC_MID
        LDA #B14_AC_HI
B14_TIMER_SET:
        STA B14_TICKS
B14_IDLE:
        JSR V2W_RAW_POLL
        BCS RL_LOAD_BYTE
        LDA V2_RX_BAD
        BNE B14_RX_BAD
        DEX
        BNE B14_IDLE
        DEY
        BNE B14_IDLE
        DEC B14_TICKS
        BNE B14_IDLE
B14_RUN:
        STZ DC_BINARY
        JSR V2W_RX_RESET
        JMP $0200
B14_RX_BAD_POP:
        PLA
B14_RX_BAD:
        LDX #<B14_RX_TEXT
        LDY #>B14_RX_TEXT
        JMP BR_MESSAGE
B14_RANGE_POP:
        PLA
        LDX #<BR_REFUSED
        LDY #>BR_REFUSED
        JMP BR_MESSAGE
B14_MAIN_END:
        DS B14_MAIN_BASE+106-B14_MAIN_END,$FF
BOOT_USB_WAIT_DONE:
        STZ DC_BINARY
        JSR V2W_RX_RESET
        LDX #<BOOT_CONSUMING
        LDY #>BOOT_CONSUMING
        JSR BOOT_PRINT
        STZ V2_DDRA
        LDA #126
        STA BR_TICKS
        LDY #0
        JMP BOOT_DRAIN_BEGIN
B13_FREE_B12_FREE_TX_ERROR:
        DB $FF,$FF,$FF,$FF,$FF,$FF
B14_INIT_BASE:
RL_LOAD:
        STZ B14_PENDING
        LDA DC_LAST
        STA DC_BINARY
        ; Consume the optional LF belonging to the command before SEND BIN.
        ; Raw bytes start after that ready message; no control decoding then.
        JSR V2W_BOOT_DELAY
        LDA DC_SKIP
        AND DC_BINARY
        BEQ B14_READY
        JSR V2W_RAW_POLL
        BCC B14_READY
        CMP #10
        BEQ B14_READY
        STA B14_PENDING_BYTE
        INC B14_PENDING
B14_READY:
        ; Preserve a receive error detected during the optional-LF probe.
        LDA V2_RX_BAD
        PHA
        JSR V2W_RX_RESET
        PLA
        STA V2_RX_BAD
        STZ DC_BINARY
        STZ RL_PTR
        LDA #2
        STA RL_PTR+1
        LDX #<RL_SEND
        LDY #>RL_SEND
        JSR BOOT_PRINT
        LDA B14_PENDING
        BEQ B14_FIRST
        LDA B14_PENDING_BYTE
        JMP B14_FIRST_GOT
B14_FIRST:
        JSR V2W_RAW_POLL
        BCS B14_FIRST_GOT
        LDA V2_RX_BAD
        BNE B14_FIRST_BAD
        BRA B14_FIRST
B14_FIRST_GOT:
        CMP #3
        BEQ B15_CANCEL
        JMP RL_LOAD_BYTE
B14_FIRST_BAD:
        JMP B14_RX_BAD
B14_INIT_END:
        DS B14_INIT_BASE+99-B14_INIT_END,$FF
BOOT_CONSUMING: DB 13,10,"WAIT...",13,10,0


; b07 append-only display code: keep every prior PR04 private call fixed.
B07_PRINT_CHOICES:
        JSR BOOT_PRINT
        LDX #<B07_PREFIX
        LDY #>B07_PREFIX
        JMP BOOT_PRINT
B07_PREFIX: DB "Boot : ",0
B07_CHOICES: DB "S=Recovery  A/B=Monitor  0-3=Bank",13,10,0

; Twelve append-only bytes. Existing monitor banner already starts with CRLF.
B08_RECOVERY_LINE:
        JSR V2W_RX_RESET
        JMP V2V_RAM_NEWLINE
B08_BANK_LINE:
        JSR V2V_RAM_NEWLINE
        JMP V2W_EXECUTE

BOOT_STARTUP:
        JMP B13_USB_START
B15_CANCEL:
        LDA V2_RX_BAD
        BEQ B15_CANCEL_OK
        JMP B14_RX_BAD
B15_CANCEL_OK:
        STZ DC_BINARY
        JMP BOOT_RECOVERY
B14_FREE_FIRST:
        DB $FF,$FF,$FF,$FF
BOOT_READ_RECORD:
        STZ BR_VALID
        STZ BR_CONFLICT
        STZ J_BEST+1
        STZ J_SCAN
        LDA #$C0
        STA J_SCAN+1
BR_SCAN:
        STZ V2_PTR
        LDA J_SCAN+1
        STA V2_PTR+1
        LDY #$FF
        LDA (V2_PTR),Y
        BEQ P_LONG_74
        JMP BR_NEXT
P_LONG_74:
        LDY #5
BR_RECORD_MAGIC:
        LDA (V2_PTR),Y
        CMP BR_SIGNATURE,Y
        BEQ P_LONG_75
        JMP BR_NEXT
P_LONG_75:
        DEY
        BPL BR_RECORD_MAGIC
        JSR J_CRC_INIT
        LDY #0
BR_CRC:
        LDA (V2_PTR),Y
        JSR J_CRC_BYTE
        INY
        CPY #30
        BNE BR_CRC
        LDA (V2_PTR),Y
        CMP J_CRC
        BEQ P_LONG_78
        JMP BR_NEXT
P_LONG_78:
        INY
        LDA (V2_PTR),Y
        CMP J_CRC+1
        BNE BR_NEXT
        LDA BR_VALID
        BEQ BR_NEW
        LDY #11
BR_SEQUENCE:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BCC BR_NEXT
        BNE BR_NEW
        DEY
        CPY #7
        BNE BR_SEQUENCE
        LDY #31
BR_EQUAL:
        LDA (V2_PTR),Y
        CMP JE_FRAME,Y
        BNE BR_CONFLICTING
        DEY
        BPL BR_EQUAL
        JMP BR_NEXT
BR_CONFLICTING:
        INC BR_CONFLICT
        JMP BR_NEXT
BR_NEW:
        LDY #31
BR_COPY:
        LDA (V2_PTR),Y
        STA JE_FRAME,Y
        DEY
        BPL BR_COPY
        JSR BOOT_CHECK_FIELDS
        BCS BR_NEW_VALID
        LDA BR_VALID
        BEQ BR_NEXT
        LDA J_BEST+1
        STA V2_PTR+1
        LDY #31
BR_RESTORE_BEST:
        LDA (V2_PTR),Y
        STA JE_FRAME,Y
        DEY
        BPL BR_RESTORE_BEST
        JMP BR_NEXT
BR_NEW_VALID:
        STZ BR_CONFLICT
        INC BR_VALID
        LDA J_SCAN+1
        STA J_BEST+1
BR_NEXT:
        INC J_SCAN+1
        LDA J_SCAN+1
        CMP #$E0
        BEQ P_LONG_90
        JMP BR_SCAN
P_LONG_90:
        LDA BR_CONFLICT
        BNE BR_NO_RECORD
        LDA BR_VALID
        BEQ BR_NO_RECORD
        SEC
        RTS
BR_NO_RECORD:
        STZ BR_VALID
        CLC
        RTS
B12_HELP:
        LDX #<B12_HELP_TEXT
        LDY #>B12_HELP_TEXT
        JSR BOOT_PRINT
        LDX #<B12_HELP_TAIL
        LDY #>B12_HELP_TAIL
        JMP BR_MESSAGE
B12_HELP_TEXT: DB 76,61,48,50,48,48,32,94,67,61,99,97,110,99,101,108,32,105,100,108,101,51,115,13,10,65,47,66,32,48,0
B14_FREE_B12_HELP_TEXT:
B12_FREE_B12_HELP_TEXT:
BOOT_CHECK_FIELDS:
        LDA JE_FRAME+6
        BEQ P_LONG_93
        JMP BR_FIELDS_BAD
P_LONG_93:
        LDA JE_FRAME+12
        CMP #10
        BCC BR_FIELDS_BAD
        LDA JE_FRAME+13
        AND #$F0
        BNE BR_FIELDS_BAD
        LDX #3
BR_ENTRY:
        LDA JE_FRAME+14,X
        CMP #8
        BCC BR_FIELDS_BAD
        CMP #15
        BCS BR_FIELDS_BAD
        CPX #3
        BNE BR_ENTRY_NEXT
        CMP #12
        BEQ BR_FIELDS_BAD
        CMP #13
        BEQ BR_FIELDS_BAD
BR_ENTRY_NEXT:
        DEX
        BPL BR_ENTRY
        LDA JE_FRAME+7
        CMP #'S'
        BEQ BR_FIELDS_OK
        CMP #'A'
        BEQ BR_FIELDS_OK
        CMP #'B'
        BEQ BR_FIELDS_OK
        CMP #'0'
        BCC BR_FIELDS_BAD
        CMP #'4'
        BCS BR_FIELDS_BAD
        SEC
        SBC #'0'
        TAX
        LDA #1
BR_TARGET_MASK:
        CPX #0
        BEQ BR_TARGET_ENABLED
        ASL A
        DEX
        JMP BR_TARGET_MASK
BR_TARGET_ENABLED:
        AND JE_FRAME+13
        BEQ BR_FIELDS_BAD
BR_FIELDS_OK: SEC
        RTS
BR_FIELDS_BAD: CLC
        RTS
B12_HELP_TAIL: DB 45,51,32,67,49,85,83,66,47,50,65,67,73,65,47,51,98,111,116,104,13,10,0
B14_FREE_B12_HELP_TAIL:
        DB $FF
B13_USB_START:
        LDY #20
BOOT_USB_WAIT:
        JSR BR_TENTH
        DEY
        BNE BOOT_USB_WAIT
        JMP BOOT_USB_WAIT_DONE
B13_FREE_B12_FREE_B12_HELP_TAIL:
        DB $FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF
BOOT_META_READ: LDA #0
        JMP BR_SERVICE
BOOT_META_CFG: LDA #1
        JMP BR_SERVICE
BOOT_META_ERASE: LDA #2
        JMP BR_SERVICE
BOOT_META_PROMOTE: LDA #3
        JMP BR_SERVICE
BOOT_REPORT: LDA #4
BR_SERVICE: JMP (JE_HANDLER)
BOOT_NO_SERVICE: CLC
        RTS
BOOT_UPDATE: JMP BOOT_RECOVERY
BOOT_COMPAT_DATA: DB "PR04"
BR_STRINGS:
BR_CHOICES:
BOOT_B08_READ_LINE:
        JSR BOOT_READ_LINE
        BCC B08_READ_DONE
        LDA V2_LINE+1
        BNE B08_READ_VALID
        LDA V2_LINE
        CMP #'0'
        BCC B08_READ_VALID
        CMP #'4'
        BCS B08_READ_VALID
        PHA
        JSR BOOT_SELECT
        PLA
        TAX
        PLA
        PLA
        TXA
        JMP BR_DISPATCH
B08_READ_VALID: SEC
B08_READ_DONE: RTS
        DB $EA
BR_RECOVERY: DB "Recovery L A/B 0-3 C1/2/3 ?",13,10,0
B14_FREE_BANNER:
        DB $FF,$FF

B12_FREE_BANNER:
        DB $FF,$FF

BR_PROMPT: DB "REC> ",0
BR_USAGE: DB "REFUSED: command",13,10,0
BR_REFUSED: DB "REFUSED: RAM range",13,10,0
B14_RX_TEXT: DB "REFUSED: receive error",13,10,0
RL_SEND: DB "SEND BIN",13,10,0
B14_FREE_MESSAGES:
        DB $FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF,$FF
BOOT_DRAIN_DONE:
        JSR V2W_RX_RESET
        STZ V2_SKIP_LF
        DB $EA,$EA,$EA
        JSR BOOT_SELECT
        JMP BOOT_START_CHOICES+3
B13_FREE_B12_FREE_LOADED:

BR_SIGNATURE: DB "SNBT",1,32
B14_FREE_SIGNATURE:
        DB $FF,$FF,$FF,$FF,$FF,$FF
BOOT_CON_SELECT:
        DEC A
        CMP #3
        BCC P_LONG_109
        JMP BOOT_CON_SELECT_BAD
P_LONG_109:
        INC A
        STA V2_CONSOLE
        JSR V2W_RX_RESET
        SEC
        RTS
BOOT_CON_SELECT_BAD:
        CLC
        RTS
BOOT_SLOT_CHECK:        LDA V2_PTR+1
                        STA BOOT_IO_PAGE
                        LDY #$00
                        LDA (V2_PTR),Y
                        CMP #'M'
        BNE FBC_SLOT_BAD
KEY_LONG_307:
                        INY
                        LDA (V2_PTR),Y
                        CMP #'I'
        BNE FBC_SLOT_BAD
KEY_LONG_311:
                        INY
                        LDA (V2_PTR),Y
                        CMP #$01
        BNE FBC_SLOT_BAD
KEY_LONG_315:
                        INY
                        LDA (V2_PTR),Y
                        CMP BOOT_DEST
        BNE FBC_SLOT_BAD
KEY_LONG_319:
                        INY
                        LDA (V2_PTR),Y
                        CMP #$03
        BNE FBC_SLOT_BAD
KEY_LONG_323:
                        INY
                        LDA (V2_PTR),Y
                        CMP #$01
        BNE FBC_SLOT_BAD
KEY_LONG_327:
                        LDY #$0D
                        LDA (V2_PTR),Y
                        CMP #$0F
        BCC BOOT_LENGTH_OK
        BNE FBC_SLOT_BAD
KEY_LONG_332:
                        DEY
                        LDA (V2_PTR),Y
                        CMP #$81
        BCS FBC_SLOT_BAD
KEY_LONG_336:
FBC_SLOT_SKIP:
        JMP BOOT_LENGTH_OK
FBC_SLOT_BAD: CLC
 RTS
BOOT_LENGTH_OK:         LDY #$0C
                        LDA (V2_PTR),Y
                        STA BOOT_LENGTH
                        INY
                        LDA (V2_PTR),Y
                        ORA BOOT_LENGTH
        BEQ FBC_SLOT_BAD
KEY_LONG_343:
                        INY
                        LDA (V2_PTR),Y
                        CMP #$84
        BNE FBC_SLOT_BAD
KEY_LONG_347:
                        INY
                        LDA (V2_PTR),Y
                        CMP BOOT_DEST
        BEQ P_LONG_121
        JMP BOOT_SLOT_BAD
P_LONG_121:
                        INY
                        LDA (V2_PTR),Y
                        CMP #$87
        BEQ P_LONG_122
        JMP BOOT_SLOT_BAD
P_LONG_122:
                        INY
                        LDA (V2_PTR),Y
                        CMP BOOT_DEST
        BEQ P_LONG_123
        JMP BOOT_SLOT_BAD
P_LONG_123:
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


BOOT_DRAIN_BEGIN:
BOOT_DRAIN_LOOP:
        ; Balanced ready/empty paths: drain both physical receivers, rather
        ; than waiting for a quiet gap or consuming one byte per timer tick.
        LDA #2
        BIT V2_CTRL
        BNE BOOT_DRAIN_FT_EMPTY
        LDA #8
        TRB V2_CTRL
        NOP
        NOP
        LDA V2_DATA
        LDA #8
        TSB V2_CTRL
        NOP
        BRA BOOT_DRAIN_FT_DONE
BOOT_DRAIN_FT_EMPTY:
        LDX #5
BOOT_DRAIN_FT_PAD:
        DEX
        BNE BOOT_DRAIN_FT_PAD
        NOP
BOOT_DRAIN_FT_DONE:
        LDA V2_ACIA_STATUS
        AND #V2_ACIA_RDRF
        BEQ BOOT_DRAIN_ACIA_EMPTY
        LDA V2_ACIA_DATA
        BRA BOOT_DRAIN_ACIA_DONE
BOOT_DRAIN_ACIA_EMPTY:
        NOP
        NOP
        NOP
BOOT_DRAIN_ACIA_DONE:
        LDX #38
BOOT_DRAIN_PAD:
        DEX
        BNE BOOT_DRAIN_PAD
        DEY
        BNE BOOT_DRAIN_LOOP
        DEC BR_TICKS
        BNE BOOT_DRAIN_LOOP
        JMP BOOT_DRAIN_DONE
B13_FREE_SLOT:
        DB $FF
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

BOOT_READ_LINE: JMP BOOT_API_LINE
BOOT_PRINT:             STX V2_PTR
                        STY V2_PTR+1
                        LDY #$00
BOOT_PRINT_BYTE:        LDA (V2_PTR),Y
        BNE P_LONG_134
        JMP BOOT_PRINT_END
P_LONG_134:
                        JSR V2W_PUTC
                        INY
        JMP BOOT_PRINT_BYTE
BOOT_PRINT_END:         RTS
J_CRC_INIT:             LDA #$FF
                        STA J_CRC
                        STA J_CRC+1
                        RTS
; CRC16/CCITT-FALSE, polynomial 1021, initial FFFF. Y preserved.
J_CRC_BYTE:             EOR J_CRC+1
                        STA J_CRC+1
                        LDX #$08
J_CRC_BIT:              ASL J_CRC
                        ROL J_CRC+1
        BCC P_LONG_135
        JMP str8n_v2_journal_LONG_414
P_LONG_135:
                        JMP J_CRC_NEXT
str8n_v2_journal_LONG_414:
                        LDA J_CRC
                        EOR #$21
                        STA J_CRC
                        LDA J_CRC+1
                        EOR #$10
                        STA J_CRC+1
J_CRC_NEXT:             DEX
        BNE P_LONG_136
        JMP str8n_v2_journal_LONG_422
P_LONG_136:
                        JMP J_CRC_BIT
str8n_v2_journal_LONG_422:
                        RTS

BOOT_HOLD:
        LDA BOOT_ACTIVE
        JMP BOOT_LAUNCH
BOOT_API_SKIP: JMP FC_SKIP_SPACES
        INCLUDE "prototype-console.inc"

BOOT_WORKER_IMAGE: INCLUDE "worker-image.inc"

BOOT_END:
        ENDMOD
        END
