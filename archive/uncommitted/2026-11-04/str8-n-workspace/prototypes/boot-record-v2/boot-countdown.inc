; Optional fixed three-second startup UI. Replaces BOOT_START_CHOICES through
; the instruction immediately before BR_DEFAULT; no journal writes occur here.
; The saved default still comes from BOOT_SELECT. The legacy timeout byte is
; preserved in the record but this UI deliberately uses a fixed three seconds.
BR_SLICES EQU $7C7D             ; BR_BANK scratch, before an opaque handoff
BOOT_START_CHOICES:
        JSR BOOT_SELECT
        LDX #<BR_CHOICES
        LDY #>BR_CHOICES
        JSR BOOT_PRINT
        LDA #3
        STA BR_TICKS
BR_COUNTDOWN:
        LDA BR_TICKS
        ORA #'0'
        JSR V2W_PUTC
        LDA BR_TICKS
        BEQ BR_COUNTDOWN_DONE
        LDA #' '
        JSR V2W_PUTC
        LDA #100
        STA BR_SLICES
BR_WINDOW:
        JSR V2W_RAW_POLL
        BCS BR_KEY
BR_NO_KEY:
        LDA BR_TICKS
        BEQ BR_COUNTDOWN_DEFAULT
        ; One ~10 ms slice, including polling/loop overhead at 8 MHz.
        ; Poll between slices so a key never waits for a full second.
        LDX #62
        JSR V2W_BOOT_DELAY_OUTER
        DEC BR_SLICES
        BNE BR_WINDOW
        DEC BR_TICKS
        JMP BR_COUNTDOWN
BR_COUNTDOWN_DONE:
        ; Include keys received during the final delay slice.
        JSR V2W_RAW_POLL
        BCS BR_KEY
BR_COUNTDOWN_DEFAULT:
        JSR V2V_RAM_NEWLINE
