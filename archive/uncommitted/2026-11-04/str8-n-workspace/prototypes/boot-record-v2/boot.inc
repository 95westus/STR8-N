; Read-only boot/config consumer. Never emits a flash command.
JE_FRAME EQU $6700
JE_HANDLER EQU $7C60
BR_TARGET EQU $7C64
BR_VALID EQU $7C65
BR_TICKS EQU $7C66
BR_CONFLICT EQU $7C67
RL_HEADER EQU $7C68
RL_VALID EQU $7C78
RL_START EQU $7C79
RL_LENGTH EQU $7C7B
RL_END EQU $7C7E
RL_PTR EQU $E2
RL_LEFT EQU $E8
BOOT_SELECT:
        JSR BOOT_READ_RECORD
        LDA #'S'
        BCC BR_USE_DEFAULT
        LDA JE_FRAME+7
BR_USE_DEFAULT:
        STA BR_TARGET
        RTS
BOOT_START_CHOICES:
        JSR BOOT_SELECT
        LDX #<BR_CHOICES
        LDY #>BR_CHOICES
        JSR BOOT_PRINT
        LDA #30
        LDX BR_VALID
        BEQ BR_SET_TICKS
        LDA JE_FRAME+12
BR_SET_TICKS:
        STA BR_TICKS
BR_WINDOW:
        JSR V2W_RAW_POLL
        BCS BR_KEY
        JSR BR_TENTH
        DEC BR_TICKS
        BNE BR_WINDOW
BR_DEFAULT:
        LDA BR_TARGET
        CMP #'A'
        BEQ BR_DEFAULT_MON
        CMP #'B'
        BNE BR_DISPATCH
BR_DEFAULT_MON:
        PHA
        CMP #'A'
        BEQ BR_DEFAULT_A
        LDA #$B0
        BRA BR_DEFAULT_GEN
BR_DEFAULT_A:
        LDA #$A0
BR_DEFAULT_GEN:
        STA V2_PTR+1
        STZ V2_PTR
        LDY #8
BR_GEN:
        LDA (V2_PTR),Y
        CMP JE_FRAME+10,Y
        BNE BR_GEN_BAD
        INY
        CPY #12
        BNE BR_GEN
        PLA
        BRA BR_DISPATCH
BR_GEN_BAD:
        PLA
        JMP BOOT_RECOVERY
BR_KEY:
        CMP #13
        BEQ BR_DEFAULT
        CMP #10
        BEQ BR_DEFAULT
        AND #$DF
BR_DISPATCH:
        CMP #'S'
        BEQ BOOT_RECOVERY
        CMP #3
        BEQ BOOT_RECOVERY
        CMP #'A'
        BEQ BR_A
        CMP #'B'
        BEQ BR_B
        ; AND #DF changes ASCII digits: accept both normalized and raw values.
        ORA #$20
        CMP #'0'
        BCC BR_WINDOW
        CMP #'4'
        BCS BR_WINDOW
        SEC
        SBC #'0'
        TAX
        STX BR_BANK
        LDA BR_VALID
        BEQ BR_BAD
        LDA #1
BR_MASK:
        CPX #0
        BEQ BR_MASK_READY
        ASL A
        DEX
        BRA BR_MASK
BR_MASK_READY:
        AND JE_FRAME+13
        BEQ BR_BAD
        LDX BR_BANK
        STX V2_SELECTED
        LDA JE_FRAME+14,X
        ASL A
        ASL A
        ASL A
        ASL A
        STA V2_VECTOR+1
        STZ V2_VECTOR
        JMP V2W_EXECUTE
BR_A:   LDA #$A0
        BRA BR_MON
BR_B:   LDA #$B0
BR_MON: STA BOOT_DEST
        STA V2_PTR+1
        STZ V2_PTR
        JSR BOOT_SLOT_CHECK
        BCC BR_BAD
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
        JSR V2W_RX_RESET
        STZ V2_SKIP_LF
        LDX #<BR_RECOVERY
        LDY #>BR_RECOVERY
        JSR BOOT_PRINT
BOOT_MENU:
        LDX #<BR_PROMPT
        LDY #>BR_PROMPT
        JSR BOOT_PRINT
        JSR BOOT_READ_LINE
        LDA V2_LINE+1
        BNE BR_SYNTAX
        LDA V2_LINE
        BEQ BOOT_MENU
        CMP #'L'
        BEQ RL_LOAD
        CMP #'R'
        BEQ RL_RUN
        CMP #'D'
        BEQ RL_DUMP
        CMP #'V'
        BEQ RL_VERIFY
        CMP #'A'
        BEQ BR_A
        CMP #'B'
        BEQ BR_B
BR_SYNTAX:
        LDX #<BR_USAGE
        BRA BR_MESSAGE
BR_ERROR:
        LDX #<BR_REFUSED
BR_MESSAGE:
        LDY #>BR_STRINGS
        ; Builder replaces this compact message helper with explicit pointers.
        JSR BOOT_PRINT
        JMP BOOT_MENU

RL_RUN:
        LDA RL_VALID
        BEQ BR_ERROR
        LDA RL_HEADER+10
        STA V2_VECTOR
        LDA RL_HEADER+11
        STA V2_VECTOR+1
        LDA #3
        STA V2_SELECTED
        JMP V2W_EXECUTE
RL_LOAD:
        STZ RL_VALID
        JSR V2W_BOOT_DELAY
        JSR V2W_RAW_POLL
        BCC RL_BINARY_READY
        CMP #10
        BNE BR_ERROR
RL_BINARY_READY:
        JSR V2W_RX_RESET
        STZ V2_SKIP_LF
        LDX #<RL_SEND
        LDY #>RL_SEND
        JSR BOOT_PRINT
        LDY #0
RL_HEADER_BYTE:
        JSR RL_GET
        BCC BR_ERROR
        STA RL_HEADER,Y
        INY
        CPY #16
        BNE RL_HEADER_BYTE
        JSR J_CRC_INIT
        LDY #0
RL_HCRC:
        LDA RL_HEADER,Y
        JSR J_CRC_BYTE
        INY
        CPY #14
        BNE RL_HCRC
        LDA J_CRC
        CMP RL_HEADER+14
        BNE BR_ERROR
        LDA J_CRC+1
        CMP RL_HEADER+15
        BNE BR_ERROR
        LDX #5
RL_MAGIC:
        LDA RL_HEADER,X
        CMP RL_SIGNATURE,X
        BNE BR_ERROR
        DEX
        BPL RL_MAGIC
        LDA RL_HEADER+6
        STA RL_START
        STA RL_PTR
        LDA RL_HEADER+7
        STA RL_START+1
        STA RL_PTR+1
        CMP #$20
        BCC BR_ERROR
        LDA RL_HEADER+8
        STA RL_LENGTH
        STA RL_LEFT
        LDA RL_HEADER+9
        STA RL_LENGTH+1
        STA RL_LEFT+1
        ORA RL_LEFT
        BEQ BR_ERROR
        CLC
        LDA RL_PTR
        ADC RL_LEFT
        STA RL_END
        LDA RL_PTR+1
        ADC RL_LEFT+1
        STA RL_END+1
        BCS BR_ERROR
        CMP #$60
        BCC RL_END_OK
        BNE BR_ERROR
        LDA RL_END
        BNE BR_ERROR
RL_END_OK:
        LDA RL_HEADER+10
        CMP RL_PTR
        LDA RL_HEADER+11
        SBC RL_PTR+1
        BCC BR_ERROR
        LDA RL_HEADER+10
        CMP RL_END
        LDA RL_HEADER+11
        SBC RL_END+1
        BCS BR_ERROR
        JSR J_CRC_INIT
RL_BODY:
        JSR RL_GET
        BCC BR_ERROR
        STA (RL_PTR)
        JSR J_CRC_BYTE
        JSR RL_ADVANCE
        BNE RL_BODY
        LDA J_CRC
        CMP RL_HEADER+12
        BNE BR_ERROR
        LDA J_CRC+1
        CMP RL_HEADER+13
        BNE BR_ERROR
        INC RL_VALID
        LDX #<RL_OK
        LDY #>RL_OK
        JSR BOOT_PRINT
        JMP BOOT_MENU
RL_GET:
        PHX
        PHY
        LDX #0
        LDY #0
RL_POLL:
        JSR V2W_RAW_POLL
        BCS RL_GOT
        DEX
        BNE RL_POLL
        DEY
        BNE RL_POLL
        CLC
RL_GOT: PLY
        PLX
        RTS
RL_ADVANCE:
        INC RL_PTR
        BNE RL_ADVANCE_COUNT
        INC RL_PTR+1
RL_ADVANCE_COUNT:
        LDA RL_LEFT
        BNE RL_DEC
        DEC RL_LEFT+1
RL_DEC: DEC RL_LEFT
        LDA RL_LEFT
        ORA RL_LEFT+1
        RTS
RL_DUMP:
        STZ RL_PTR
        LDA #$20
        STA RL_PTR+1
        STZ RL_LEFT
        LDA #$40
        STA RL_LEFT+1
        BRA RL_OUTPUT
RL_VERIFY:
        LDA RL_VALID
        BEQ BR_ERROR
        LDX #1
RL_DUMP_RANGE:
        LDA RL_START,X
        STA RL_PTR,X
        LDA RL_LENGTH,X
        STA RL_LEFT,X
        DEX
        BPL RL_DUMP_RANGE
RL_OUTPUT:
        JSR J_CRC_INIT
RL_OUT_BYTE:
        LDA (RL_PTR)
        PHA
        JSR J_CRC_BYTE
        PLA
        JSR V2W_PUTC
        JSR RL_ADVANCE
        BNE RL_OUT_BYTE
        LDA J_CRC
        JSR V2W_PUTC
        LDA J_CRC+1
        JSR V2W_PUTC
        JMP BOOT_MENU

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
        BNE BR_NEXT
        LDY #5
BR_RECORD_MAGIC:
        LDA (V2_PTR),Y
        CMP BR_SIGNATURE,Y
        BNE BR_NEXT
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
        BNE BR_NEXT
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
        BRA BR_NEXT
BR_CONFLICTING:
        INC BR_CONFLICT
        BRA BR_NEXT
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
        BRA BR_NEXT
BR_NEW_VALID:
        STZ BR_CONFLICT
        INC BR_VALID
        LDA J_SCAN+1
        STA J_BEST+1
BR_NEXT:
        INC J_SCAN+1
        LDA J_SCAN+1
        CMP #$E0
        BNE BR_SCAN
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
BOOT_CHECK_FIELDS:
        LDA JE_FRAME+6
        BNE BR_FIELDS_BAD
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
        BRA BR_TARGET_MASK
BR_TARGET_ENABLED:
        AND JE_FRAME+13
        BEQ BR_FIELDS_BAD
BR_FIELDS_OK: SEC
        RTS
BR_FIELDS_BAD: CLC
        RTS
BOOT_META_READ: LDA #0
        BRA BR_SERVICE
BOOT_META_CFG: LDA #1
        BRA BR_SERVICE
BOOT_META_ERASE: LDA #2
        BRA BR_SERVICE
BOOT_META_PROMOTE: LDA #3
        BRA BR_SERVICE
BOOT_REPORT: LDA #4
BR_SERVICE: JMP (JE_HANDLER)
BOOT_NO_SERVICE: CLC
        RTS
BOOT_UPDATE: JMP BOOT_RECOVERY
BOOT_COMPAT_DATA: DB "PR01"
BR_STRINGS:
BR_CHOICES: DB 13,10,"OFFLINE PROTOTYPE S A B 0 1 2 3",13,10,0
BR_RECOVERY: DB "RAM recovery L/R/D/V A/B",13,10,0
BR_PROMPT: DB "REC> ",0
BR_USAGE: DB "REFUSED: command",13,10,0
BR_REFUSED: DB "REFUSED: image/range/CRC/timeout",13,10,0
RL_SEND: DB "SEND HEADER+BIN",13,10,0
RL_OK: DB "LOADED; R runs, V reads back",13,10,0
BR_SIGNATURE: DB "SNBT",1,32
RL_SIGNATURE: DB "RLP1",1,1
