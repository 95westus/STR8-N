; Entire mutation, polling, verification, failure and self-edit hold run in RAM.
; Shared 4K desired-sector image at $6900. No polling of console mid-mutation.
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
V2W_SNAPSHOT:          LDA     V2_SELECTED
                        JSR     V2W_SELECT
                        JSR     V2W_INIT
V2W_SNAP_BYTE:         LDA     (V2_FLASH_PTR)
                        STA     (V2_BUF_PTR)
                        JSR     V2W_NEXT
                        BCC     V2W_SNAP_BYTE
V2W_RETURN:            LDA     V2_RESIDENT
                        JMP     V2W_SELECT
V2W_ANALYZE:           LDA     V2_SELECTED
                        JSR     V2W_SELECT
                        STZ     V2_ERASE
                        JSR     V2W_INIT
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
                        LDA     V2_SELECTED
                        JSR     V2W_SELECT
                        JSR     V2W_INIT
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
V2W_ERASE_CHECK:       LDA     (V2_FLASH_PTR)
                        CMP     #$FF
                        BNE     V2W_VERIFY_FAIL
                        JSR     V2W_NEXT
                        BCC     V2W_ERASE_CHECK
                        JSR     V2W_INIT
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
                        LDA     #$01
                        STA     V2_LED
                        LDA     V2_SELF
                        BNE     V2W_SELF_RESULT
                        LDA     V2_FLASH_ERROR
                        CMP     #$01
                        RTS
; Never return through old ROM, including on failure or an unchanged edit.
V2W_SELF_RESULT:       LDX     #$00
                        LDA     V2_FLASH_ERROR
                        BEQ     V2W_SELF_OK
                        LDX     #(V2W_FAIL_TEXT-V2W_OK_TEXT)
V2W_SELF_OK:           LDA     V2W_OK_TEXT,X
                        BEQ     V2W_HOLD
                        JSR     V2W_PUTC
                        INX
                        BRA     V2W_SELF_OK
V2W_HOLD:              BRA     V2W_HOLD
V2W_OK_TEXT:           DB      $0D,$0A,"Done; reset",$00
V2W_FAIL_TEXT:         DB      $0D,$0A,"Flash failed; reset",$00
V2W_PUTC:              PHA
                        STZ     V2_DDRA
                        LDA     #$01
V2W_TX_WAIT:           BIT     V2_CTRL
                        BNE     V2W_TX_WAIT
                        PLA
                        STA     V2_DATA
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
V2W_UNLOCK:            LDA     #$F0
                        STA     V2_LED
                        LDA     #$AA
                        STA     $D555
                        LDA     #$55
                        STA     $AAAA
                        RTS
V2W_WAIT:              STA     V2_TIMEOUT+2
                        STZ     V2_TIMEOUT
                        STZ     V2_TIMEOUT+1
V2W_POLL:              LDA     (V2_FLASH_PTR)
                        CMP     V2_FLASH_DATA
                        BEQ     V2W_POLL_OK
                        DEC     V2_TIMEOUT
                        BNE     V2W_POLL
                        DEC     V2_TIMEOUT+1
                        BNE     V2W_POLL
                        DEC     V2_TIMEOUT+2
                        BNE     V2W_POLL
                        LDA     #$01
                        STA     V2_FLASH_ERROR
                        CLC
                        RTS
V2W_POLL_OK:           SEC
                        RTS
