; Entire mutation, polling, verification, failure and self-edit hold run in RAM.
; Shared 4K desired-sector image at $6900. No polling of console mid-mutation.
V2W_BEGIN:             LDA     V2_SELECTED
                        JSR     V2W_SELECT
V2W_INIT:              STZ     V2_FLASH_PTR
                        STZ     V2_BUF_PTR
                        LDA     V2_SECTOR
                        STA     V2_FLASH_PTR+1
                        LDA     #$69
                        STA     V2_BUF_PTR+1
                        RTS
V2W_NEXT:              INC     V2_BUF_PTR
                        INC     V2_FLASH_PTR
                        BNE     V2W_NEXT_DONE
                        INC     V2_BUF_PTR+1
                        INC     V2_FLASH_PTR+1
V2W_NEXT_DONE:         LDA     V2_BUF_PTR+1
                        CMP     #$79
                        RTS
V2W_SNAPSHOT:          JSR     V2W_BEGIN
V2W_SNAP_BYTE:         LDA     (V2_FLASH_PTR)
                        STA     (V2_BUF_PTR)
                        JSR     V2W_NEXT
                        BCC     V2W_SNAP_BYTE
V2W_RETURN:            LDA     V2_RESIDENT
                        BRA     V2W_SELECT
V2W_ANALYZE:           STZ     V2_ERASE
                        JSR     V2W_BEGIN
V2W_ANALYZE_BYTE:      LDA     (V2_FLASH_PTR)
                        AND     (V2_BUF_PTR)
                        CMP     (V2_BUF_PTR)
                        BEQ     V2W_ANALYZE_NEXT
                        INC     V2_ERASE
                        BRA     V2W_RETURN
V2W_ANALYZE_NEXT:      JSR     V2W_NEXT
                        BCC     V2W_ANALYZE_BYTE
                        BRA     V2W_RETURN

V2W_MUTATE:            SEI
                        STZ     V2_FLASH_ERROR
                        LDA     #$01
                        STA     V2_NMI_HOLD
                        JSR     V2W_BEGIN
                        LDA     V2_ERASE
                        BEQ     V2W_PROGRAM
                        JSR     V2W_UNLOCK
                        LDA     #$80
                        STA     $D555
                        JSR     V2W_UNLOCK
                        LDA     #$30
                        STA     (V2_FLASH_PTR)
                        LDA     #$FF
                        STA     V2_FLASH_DATA
                        LDA     #$08
                        JSR     V2W_WAIT
                        BCC     V2W_FINISH
; Per-byte transition checks and the final sector comparison validate the
; required result; a separate all-FF sweep after erase is unnecessary.
V2W_PROGRAM:           LDA     (V2_BUF_PTR)
                        STA     V2_FLASH_DATA
                        CMP     (V2_FLASH_PTR)
                        BEQ     V2W_PROGRAM_NEXT
                        AND     (V2_FLASH_PTR)
                        CMP     V2_FLASH_DATA
                        BNE     V2W_VERIFY_FAIL
                        JSR     V2W_UNLOCK
                        LDA     #$A0
                        STA     $D555
                        LDA     V2_FLASH_DATA
                        STA     (V2_FLASH_PTR)
                        LDA     #$02
                        JSR     V2W_WAIT
                        BCC     V2W_FINISH
V2W_PROGRAM_NEXT:      JSR     V2W_NEXT
                        BCC     V2W_PROGRAM
                        JSR     V2W_INIT
V2W_VERIFY:            LDA     (V2_FLASH_PTR)
                        CMP     (V2_BUF_PTR)
                        BNE     V2W_VERIFY_FAIL
                        JSR     V2W_NEXT
                        BCC     V2W_VERIFY
                        BRA     V2W_FINISH
V2W_VERIFY_FAIL:       LDA     #$02
                        STA     V2_FLASH_ERROR
V2W_FINISH:            LDA     #$F0
                        STA     $D555
                        JSR     V2W_RETURN
                        STZ     V2_NMI_HOLD
                        LDA     #V2_LED_RUNNING
                        STA     V2_LED
                        LDA     V2_SELF
                        BNE     V2W_SELF_RESULT
                        LDA     V2_FLASH_ERROR
                        CMP     #$01
                        RTS
; Never return through old ROM. Offer a deliberate CPU-level restart from
; RAM; this jumps to the fixed public RESET entry and does not pulse RESET.
V2W_SELF_RESULT:       LDX     #$00
                        LDA     V2_FLASH_ERROR
                        BEQ     V2W_SELF_OK
                        LDX     #(V2W_FAIL_TEXT-V2W_OK_TEXT)
V2W_SELF_OK:           LDA     V2W_OK_TEXT,X
                        BEQ     V2W_RESET_WAIT
                        JSR     V2W_PUTC
                        INX
                        BRA     V2W_SELF_OK
V2W_RESET_WAIT:        JSR     V2W_GETC
                        AND     #$DF
                        CMP     #'Y'
                        BNE     V2W_RESET_WAIT
                        SEI
                        CLD
                        LDX     #$FF
                        TXS
                        JMP     $F004
V2W_OK_TEXT:           DB      $0D,$0A,"OK; press Y to soft reset",$00
V2W_FAIL_TEXT:         DB      $0D,$0A,"Flash fail; press Y to soft reset",$00
; IN A=byte, output ready and DDRA=0. X/Y preserved; A clobbered.
; Also called by the resident console after its cancellable ready wait.
V2W_SEND:              STA     V2_DATA
                        NOP
                        NOP
                        LDA     #$04
                        TSB     V2_CTRL
                        DEC     V2_DDRA
                        NOP
                        NOP
                        LDA     #$04
                        TRB     V2_CTRL
                        STZ     V2_DDRA
                        RTS
; W65C51N TDRE is not usable. Pace every write by more than one 10-bit frame
; at 19200 baud. At 8 MHz this loop is at least 4,184 cycles (523 us), while
; preserving X/Y for the public console contract and RAM self-edit strings.
V2W_ACIA_SEND:         STA     V2_ACIA_DATA
                        PHX
                        PHY
                        LDY     #$04
V2W_ACIA_DELAY_OUTER:  LDX     #$D0
V2W_ACIA_DELAY_INNER:  DEX
                        BNE     V2W_ACIA_DELAY_INNER
                        DEY
                        BNE     V2W_ACIA_DELAY_OUTER
                        PLY
                        PLX
                        RTS
V2W_UNLOCK:            LDA     #V2_LED_FLASH
                        STA     V2_LED
                        LDA     #$AA
                        STA     $D555
                        LDA     #$55
                        STA     $AAAA
                        RTS
; A counts blocks of 65536 polls (2 program / 8 erase). Preserve that count
; on the stack, using X/Y for the lower counters. Mutation callers do not
; require X/Y; I saves its record position around the complete mutation.
V2W_WAIT:              PHA
                        LDX     #$00
                        LDY     #$00
V2W_POLL:              LDA     (V2_FLASH_PTR)
                        CMP     V2_FLASH_DATA
                        BEQ     V2W_POLL_OK
; BIT is intentional three-cycle padding: BIT zp + DEX/DEY takes the same
; five cycles as DEC zp, so freeing scratch does not shorten these counters.
                        BIT     V2_FLASH_DATA
                        DEX
                        BNE     V2W_POLL
                        BIT     V2_FLASH_DATA
                        DEY
                        BNE     V2W_POLL
                        PLA
                        DEC     A
                        BEQ     V2W_TIMEOUT
                        PHA
                        BRA     V2W_POLL
V2W_TIMEOUT:
                        LDA     #$01
                        STA     V2_FLASH_ERROR
                        CLC
                        RTS
; The equal comparison above already set carry for successful completion.
V2W_POLL_OK:           PLA
                        RTS
