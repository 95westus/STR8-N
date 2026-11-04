; Appended startup wrapper: keep every existing PR04 private entry fixed.
; The patched BOOT_START_CHOICES entry jumps here instead of calling SELECT.
; Startup/J3 only; never entered by a binary-transfer operation.
BOOT_STARTUP:
        LDY #30
BOOT_USB_WAIT:
        JSR BR_TENTH
        DEY
        BNE BOOT_USB_WAIT
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
BOOT_DRAIN_DONE:
        JSR V2W_RX_RESET
        STZ V2_SKIP_LF
        STZ RL_VALID
        JSR BOOT_SELECT
        JMP BOOT_START_CHOICES+3
BOOT_CONSUMING: DB "Consuming input",13,10,0
