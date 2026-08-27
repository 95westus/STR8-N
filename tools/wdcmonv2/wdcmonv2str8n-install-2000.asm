; ----------------------------------------------------------------------------
; WDCMONV2STR8N-INSTALL-2000.ASM
;
; Conservative stock W65C02SXB (+ optional W65C02EDU) -> STR8-N installer.
; Load under stock WDCMONv2 at $2000.  The candidate STR8-N Bank-3 top sector
; is carried at $4000; $0A00-$19FF is the one-sector staging buffer.
;
; This installer deliberately supports only two safe Bank-0 states:
;   - B0 is completely erased: copy and verify the complete stock B3 into B0.
;   - B0 is already byte-identical to B3: keep it without rewriting.
; A used, different B0 is refused.  It must be archived and resolved by a
; separate operator policy; this first installer never silently replaces it.
;
; The operator/host must type the displayed whole-bank B3 FNV as
; `ARCHIVE xxxxxxxx` before any flash operation.  This is an acknowledgement
; gate.  The host archive extractor remains the proof that a local BIN exists.
;
; After B0 == original B3 is proven, the program installs only B3:F.  On
; success, RESET enters STR8-N.  STR8-N I then installs R-YORS B3:8-E, making
; STR8-N itself the ordinary payload installer.
;
; WARNING: power loss while B3:F is erased/programmed still requires an
; external programmer.  While this RAM process remains alive, B0:F can be
; selected as the old-top recovery source.
; ----------------------------------------------------------------------------

                        MODULE          WDCMONV2STR8N_INSTALL
                        XDEF            START

W2I_PTR_LO              EQU             $C0
W2I_PTR_HI              EQU             $C1
W2I_BUF_LO              EQU             $C2
W2I_BUF_HI              EQU             $C3
W2I_DATA                EQU             $C4
W2I_TMO0                EQU             $C5
W2I_TMO1                EQU             $C6
W2I_TMO2                EQU             $C7

W2I_FTDI_CTRL           EQU             $7FE0
W2I_FTDI_DATA           EQU             $7FE1
W2I_FTDI_DDRB           EQU             $7FE2
W2I_FTDI_DDRA           EQU             $7FE3
W2I_BANK_PCR            EQU             $7FEC

W2I_FTDI_TXE            EQU             $01
W2I_FTDI_RXF            EQU             $02
W2I_FTDI_WR             EQU             $04
W2I_FTDI_RD             EQU             $08
W2I_FTDI_INIT           EQU             $0C
W2I_BANK_MASK           EQU             $EE

W2I_FLASH_UNLOCK1       EQU             $D555
W2I_FLASH_UNLOCK2       EQU             $AAAA
W2I_FLASH_ID_MAN        EQU             $8000
W2I_FLASH_ID_DEV        EQU             $8001
W2I_FLASH_MAN_EXPECT    EQU             $BF
W2I_FLASH_DEV_EXPECT    EQU             $B5

W2I_STAGE_HI            EQU             $0A
W2I_CANDIDATE_HI        EQU             $40

                        CODE
                        ORG             $2000

START:
                        SEI
                        CLD
                        LDX             #$FF
                        TXS
                        JSR             W2I_CON_INIT
                        LDX             #<W2I_MSG_TITLE
                        LDY             #>W2I_MSG_TITLE
                        JSR             W2I_PUTS
                        JSR             W2I_FLASH_IDENTIFY
                        BCS             W2I_ID_OK
                        LDX             #<W2I_MSG_ID_FAIL
                        LDY             #>W2I_MSG_ID_FAIL
                        JMP             W2I_ABORT_XY

W2I_ID_OK:
                        LDX             #<W2I_MSG_ID_OK
                        LDY             #>W2I_MSG_ID_OK
                        JSR             W2I_PUTS
                        LDA             W2I_ID_MAN
                        JSR             W2I_HEX
                        LDA             #'/'
                        JSR             W2I_OUT
                        LDA             W2I_ID_DEV
                        JSR             W2I_HEX
                        JSR             W2I_CRLF

                        LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        JSR             W2I_HASH_BANK
                        JSR             W2I_SAVE_SOURCE_HASH
                        LDX             #<W2I_MSG_B3_HASH
                        LDY             #>W2I_MSG_B3_HASH
                        JSR             W2I_PUTS
                        JSR             W2I_PRINT_HASH
                        JSR             W2I_CRLF
                        JSR             W2I_BUILD_ARCHIVE_TOKEN
                        LDX             #<W2I_MSG_ARCHIVE
                        LDY             #>W2I_MSG_ARCHIVE
                        JSR             W2I_PUTS
                        JSR             W2I_PRINT_HASH
                        LDX             #<W2I_MSG_PROMPT_END
                        LDY             #>W2I_MSG_PROMPT_END
                        JSR             W2I_PUTS
                        JSR             W2I_READ_LINE
                        LDX             #<W2I_ARCHIVE_TOKEN
                        LDY             #>W2I_ARCHIVE_TOKEN
                        JSR             W2I_MATCH_INPUT
                        BCS             W2I_ARCHIVE_OK
                        LDX             #<W2I_MSG_ARCHIVE_FAIL
                        LDY             #>W2I_MSG_ARCHIVE_FAIL
                        JMP             W2I_ABORT_XY

W2I_ARCHIVE_OK:
                        LDA             #$00
                        JSR             W2I_SELECT_BANK_A
                        JSR             W2I_HASH_BANK
                        JSR             W2I_HASH_EQUALS_SOURCE
                        BCC             W2I_B0_NOT_EQUAL
                        JSR             W2I_COMPARE_B0_B3_EXACT
                        BCS             W2I_B0_PROVEN
                        LDX             #<W2I_MSG_HASH_COLLISION
                        LDY             #>W2I_MSG_HASH_COLLISION
                        JMP             W2I_ABORT_XY
W2I_B0_NOT_EQUAL:
                        LDA             W2I_ERASED
                        BNE             W2I_B0_EMPTY
                        LDX             #<W2I_MSG_B0_USED
                        LDY             #>W2I_MSG_B0_USED
                        JMP             W2I_ABORT_XY

W2I_B0_EMPTY:
                        LDX             #<W2I_MSG_COPY_CONFIRM
                        LDY             #>W2I_MSG_COPY_CONFIRM
                        JSR             W2I_PUTS
                        JSR             W2I_READ_LINE
                        LDX             #<W2I_TOKEN_COPY
                        LDY             #>W2I_TOKEN_COPY
                        JSR             W2I_MATCH_INPUT
                        BCS             W2I_COPY_CONFIRMED
                        LDX             #<W2I_MSG_CANCEL
                        LDY             #>W2I_MSG_CANCEL
                        JMP             W2I_ABORT_XY

W2I_COPY_CONFIRMED:
                        LDX             #<W2I_MSG_COPYING
                        LDY             #>W2I_MSG_COPYING
                        JSR             W2I_PUTS
                        JSR             W2I_COPY_B3_TO_B0
                        BCS             W2I_COPY_DONE
                        LDX             #<W2I_MSG_COPY_FAIL
                        LDY             #>W2I_MSG_COPY_FAIL
                        JMP             W2I_ABORT_XY

W2I_COPY_DONE:
                        LDA             #$00
                        JSR             W2I_SELECT_BANK_A
                        JSR             W2I_HASH_BANK
                        JSR             W2I_HASH_EQUALS_SOURCE
                        BCC             W2I_COMPARE_FAILED
                        JSR             W2I_COMPARE_B0_B3_EXACT
                        BCS             W2I_B0_PROVEN
W2I_COMPARE_FAILED:
                        LDX             #<W2I_MSG_COMPARE_FAIL
                        LDY             #>W2I_MSG_COMPARE_FAIL
                        JMP             W2I_ABORT_XY

W2I_B0_PROVEN:
                        LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        LDX             #<W2I_MSG_B0_OK
                        LDY             #>W2I_MSG_B0_OK
                        JSR             W2I_PUTS
                        JSR             W2I_HASH_CANDIDATE
                        LDA             W2I_HASH0
                        CMP             #W2I_CANDIDATE_FNV0
                        BNE             W2I_CANDIDATE_BAD
                        LDA             W2I_HASH1
                        CMP             #W2I_CANDIDATE_FNV1
                        BNE             W2I_CANDIDATE_BAD
                        LDA             W2I_HASH2
                        CMP             #W2I_CANDIDATE_FNV2
                        BNE             W2I_CANDIDATE_BAD
                        LDA             W2I_HASH3
                        CMP             #W2I_CANDIDATE_FNV3
                        BEQ             W2I_CANDIDATE_OK
W2I_CANDIDATE_BAD:
                        LDX             #<W2I_MSG_CANDIDATE_BAD
                        LDY             #>W2I_MSG_CANDIDATE_BAD
                        JMP             W2I_ABORT_XY

W2I_CANDIDATE_OK:
                        LDX             #<W2I_MSG_INSTALL_CONFIRM
                        LDY             #>W2I_MSG_INSTALL_CONFIRM
                        JSR             W2I_PUTS
                        JSR             W2I_READ_LINE
                        LDX             #<W2I_TOKEN_INSTALL
                        LDY             #>W2I_TOKEN_INSTALL
                        JSR             W2I_MATCH_INPUT
                        BCS             W2I_INSTALL_CONFIRMED
                        LDX             #<W2I_MSG_CANCEL
                        LDY             #>W2I_MSG_CANCEL
                        JMP             W2I_ABORT_XY

W2I_INSTALL_CONFIRMED:
                        LDX             #<W2I_MSG_INSTALLING
                        LDY             #>W2I_MSG_INSTALLING
                        JSR             W2I_PUTS
W2I_RETRY_CANDIDATE:
                        JSR             W2I_CANDIDATE_TO_STAGE
                        LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        LDA             #$F0
                        STA             W2I_SECTOR_HI
                        JSR             W2I_PROGRAM_STAGE
                        BCC             W2I_RECOVERY
                        LDX             #<W2I_MSG_INSTALLED
                        LDY             #>W2I_MSG_INSTALLED
                        JSR             W2I_PUTS
                        JMP             ($FFFC)

W2I_RECOVERY:
                        LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        LDX             #<W2I_MSG_RECOVERY
                        LDY             #>W2I_MSG_RECOVERY
                        JSR             W2I_PUTS
                        JSR             W2I_READ_LINE
                        LDA             W2I_INPUT+1
                        BNE             W2I_RECOVERY
                        LDA             W2I_INPUT
                        CMP             #'R'
                        BEQ             W2I_RETRY_CANDIDATE
                        CMP             #'O'
                        BNE             W2I_RECOVERY
                        LDA             #$00
                        JSR             W2I_SELECT_BANK_A
                        LDA             #$F0
                        STA             W2I_SECTOR_HI
                        JSR             W2I_FLASH_TO_STAGE
                        LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        JSR             W2I_PROGRAM_STAGE
                        BCC             W2I_RECOVERY
                        LDX             #<W2I_MSG_OLD_RESTORED
                        LDY             #>W2I_MSG_OLD_RESTORED
                        JSR             W2I_PUTS
                        JMP             ($FFFC)

W2I_ABORT_XY:
                        JSR             W2I_PUTS
                        LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        LDX             #<W2I_MSG_ABORT
                        LDY             #>W2I_MSG_ABORT
                        JSR             W2I_PUTS
?HALT:                  BRA             ?HALT

; Enter software product-identification mode, capture BF/B5, and always issue
; the one-cycle F0 exit before deciding whether the device is supported.
W2I_FLASH_IDENTIFY:
                        LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        LDA             #$AA
                        STA             W2I_FLASH_UNLOCK1
                        LDA             #$55
                        STA             W2I_FLASH_UNLOCK2
                        LDA             #$90
                        STA             W2I_FLASH_UNLOCK1
                        LDA             W2I_FLASH_ID_MAN
                        STA             W2I_ID_MAN
                        LDA             W2I_FLASH_ID_DEV
                        STA             W2I_ID_DEV
                        LDA             #$F0
                        STA             W2I_FLASH_ID_MAN
                        NOP
                        NOP
                        LDA             W2I_ID_MAN
                        CMP             #W2I_FLASH_MAN_EXPECT
                        BNE             ?FAIL
                        LDA             W2I_ID_DEV
                        CMP             #W2I_FLASH_DEV_EXPECT
                        BNE             ?FAIL
                        SEC
                        RTS
?FAIL:                  CLC
                        RTS

; Copy B3 to erased B0 one 4K sector at a time.  W2I_PROGRAM_STAGE performs
; erase, byte program, and exact full-sector readback before the next sector.
W2I_COPY_B3_TO_B0:
                        LDA             #$80
                        STA             W2I_SECTOR_HI
?SECTOR:               LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        JSR             W2I_FLASH_TO_STAGE
                        LDA             #$00
                        JSR             W2I_SELECT_BANK_A
                        JSR             W2I_PROGRAM_STAGE
                        BCC             ?FAIL
                        LDA             #'.'
                        JSR             W2I_OUT
                        LDA             W2I_SECTOR_HI
                        CLC
                        ADC             #$10
                        STA             W2I_SECTOR_HI
                        BNE             ?SECTOR
                        JSR             W2I_CRLF
                        SEC
                        RTS
?FAIL:                  LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        CLC
                        RTS

; A matching FNV is only a fast prefilter.  Establish the preservation gate
; by comparing every byte of B0 with B3 through the RAM staging sector.
W2I_COMPARE_B0_B3_EXACT:
                        LDA             #$80
                        STA             W2I_SECTOR_HI
?SECTOR:               LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        JSR             W2I_FLASH_TO_STAGE
                        LDA             #$00
                        JSR             W2I_SELECT_BANK_A
                        JSR             W2I_VERIFY_STAGE
                        BCC             ?FAIL
                        LDA             W2I_SECTOR_HI
                        CLC
                        ADC             #$10
                        STA             W2I_SECTOR_HI
                        BNE             ?SECTOR
                        LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        SEC
                        RTS
?FAIL:                  LDA             #$03
                        JSR             W2I_SELECT_BANK_A
                        CLC
                        RTS

W2I_FLASH_TO_STAGE:
                        STZ             W2I_PTR_LO
                        LDA             W2I_SECTOR_HI
                        STA             W2I_PTR_HI
                        STZ             W2I_BUF_LO
                        LDA             #W2I_STAGE_HI
                        STA             W2I_BUF_HI
                        LDX             #$10
?PAGE:                 LDY             #$00
?BYTE:                 LDA             (W2I_PTR_LO),Y
                        STA             (W2I_BUF_LO),Y
                        INY
                        BNE             ?BYTE
                        INC             W2I_PTR_HI
                        INC             W2I_BUF_HI
                        DEX
                        BNE             ?PAGE
                        RTS

W2I_CANDIDATE_TO_STAGE:
                        STZ             W2I_PTR_LO
                        LDA             #W2I_CANDIDATE_HI
                        STA             W2I_PTR_HI
                        STZ             W2I_BUF_LO
                        LDA             #W2I_STAGE_HI
                        STA             W2I_BUF_HI
                        LDX             #$10
?PAGE:                 LDY             #$00
?BYTE:                 LDA             (W2I_PTR_LO),Y
                        STA             (W2I_BUF_LO),Y
                        INY
                        BNE             ?BYTE
                        INC             W2I_PTR_HI
                        INC             W2I_BUF_HI
                        DEX
                        BNE             ?PAGE
                        RTS

W2I_PROGRAM_STAGE:
                        STZ             W2I_PTR_LO
                        LDA             W2I_SECTOR_HI
                        STA             W2I_PTR_HI
                        JSR             W2I_FLASH_ERASE_SECTOR
                        BCC             ?FAIL
                        JSR             W2I_SECTOR_ERASED
                        BCC             ?FAIL
                        STZ             W2I_PTR_LO
                        LDA             W2I_SECTOR_HI
                        STA             W2I_PTR_HI
                        STZ             W2I_BUF_LO
                        LDA             #W2I_STAGE_HI
                        STA             W2I_BUF_HI
?BYTE:                 LDY             #$00
                        LDA             (W2I_BUF_LO),Y
                        CMP             #$FF
                        BEQ             ?NEXT
                        STA             W2I_DATA
                        JSR             W2I_FLASH_WRITE_BYTE
                        BCC             ?FAIL
?NEXT:                 INC             W2I_PTR_LO
                        INC             W2I_BUF_LO
                        BNE             ?BYTE
                        INC             W2I_PTR_HI
                        INC             W2I_BUF_HI
                        LDA             W2I_BUF_HI
                        CMP             #(W2I_STAGE_HI+$10)
                        BNE             ?BYTE
                        JSR             W2I_VERIFY_STAGE
                        BCC             ?FAIL
                        LDA             #$F0
                        STA             W2I_FLASH_UNLOCK1
                        SEC
                        RTS
?FAIL:                  LDA             #$F0
                        STA             W2I_FLASH_UNLOCK1
                        CLC
                        RTS

W2I_FLASH_ERASE_SECTOR:
                        JSR             W2I_FLASH_UNLOCK
                        LDA             #$80
                        STA             W2I_FLASH_UNLOCK1
                        JSR             W2I_FLASH_UNLOCK
                        LDA             #$30
                        LDY             #$00
                        STA             (W2I_PTR_LO),Y
                        STZ             W2I_TMO0
                        STZ             W2I_TMO1
                        LDA             #$08
                        STA             W2I_TMO2
?WAIT:                 LDA             (W2I_PTR_LO),Y
                        CMP             #$FF
                        BEQ             ?DONE
                        DEC             W2I_TMO0
                        BNE             ?WAIT
                        DEC             W2I_TMO1
                        BNE             ?WAIT
                        DEC             W2I_TMO2
                        BNE             ?WAIT
                        CLC
                        RTS
?DONE:                 SEC
                        RTS

W2I_SECTOR_ERASED:
                        STZ             W2I_PTR_LO
                        LDA             W2I_SECTOR_HI
                        STA             W2I_PTR_HI
?PAGE:                 LDY             #$00
?BYTE:                 LDA             (W2I_PTR_LO),Y
                        CMP             #$FF
                        BNE             ?FAIL
                        INY
                        BNE             ?BYTE
                        INC             W2I_PTR_HI
                        LDA             W2I_PTR_HI
                        AND             #$0F
                        BNE             ?PAGE
                        SEC
                        RTS
?FAIL:                  CLC
                        RTS

W2I_FLASH_WRITE_BYTE:
                        LDY             #$00
                        LDA             (W2I_PTR_LO),Y
                        CMP             W2I_DATA
                        BEQ             ?DONE
                        AND             W2I_DATA
                        CMP             W2I_DATA
                        BNE             ?FAIL
                        JSR             W2I_FLASH_UNLOCK
                        LDA             #$A0
                        STA             W2I_FLASH_UNLOCK1
                        LDA             W2I_DATA
                        STA             (W2I_PTR_LO),Y
                        STZ             W2I_TMO0
                        STZ             W2I_TMO1
                        LDA             #$02
                        STA             W2I_TMO2
?WAIT:                 LDA             (W2I_PTR_LO),Y
                        CMP             W2I_DATA
                        BEQ             ?DONE
                        DEC             W2I_TMO0
                        BNE             ?WAIT
                        DEC             W2I_TMO1
                        BNE             ?WAIT
                        DEC             W2I_TMO2
                        BNE             ?WAIT
?FAIL:                  CLC
                        RTS
?DONE:                 SEC
                        RTS

W2I_VERIFY_STAGE:
                        STZ             W2I_PTR_LO
                        LDA             W2I_SECTOR_HI
                        STA             W2I_PTR_HI
                        STZ             W2I_BUF_LO
                        LDA             #W2I_STAGE_HI
                        STA             W2I_BUF_HI
?PAGE:                 LDY             #$00
?BYTE:                 LDA             (W2I_PTR_LO),Y
                        CMP             (W2I_BUF_LO),Y
                        BNE             ?FAIL
                        INY
                        BNE             ?BYTE
                        INC             W2I_PTR_HI
                        INC             W2I_BUF_HI
                        LDA             W2I_BUF_HI
                        CMP             #(W2I_STAGE_HI+$10)
                        BNE             ?PAGE
                        SEC
                        RTS
?FAIL:                  CLC
                        RTS

W2I_FLASH_UNLOCK:
                        LDA             #$AA
                        STA             W2I_FLASH_UNLOCK1
                        LDA             #$55
                        STA             W2I_FLASH_UNLOCK2
                        RTS

W2I_HASH_CANDIDATE:
                        JSR             W2I_FNV_INIT
                        STZ             W2I_PTR_LO
                        LDA             #W2I_CANDIDATE_HI
                        STA             W2I_PTR_HI
?BYTE:                 LDY             #$00
                        LDA             (W2I_PTR_LO),Y
                        JSR             W2I_FNV_UPDATE_A
                        INC             W2I_PTR_LO
                        BNE             ?BYTE
                        INC             W2I_PTR_HI
                        LDA             W2I_PTR_HI
                        CMP             #(W2I_CANDIDATE_HI+$10)
                        BNE             ?BYTE
                        RTS

; Whole-bank FNV-1a and erased-state scan, identical byte order to the archive
; tool and host extractor.
W2I_HASH_BANK:
                        JSR             W2I_FNV_INIT
                        LDA             #$FF
                        STA             W2I_ERASED
                        STZ             W2I_PTR_LO
                        LDA             #$80
                        STA             W2I_PTR_HI
?BYTE:                 LDY             #$00
                        LDA             (W2I_PTR_LO),Y
                        CMP             #$FF
                        BEQ             ?HASH
                        STZ             W2I_ERASED
?HASH:                 JSR             W2I_FNV_UPDATE_A
                        INC             W2I_PTR_LO
                        BNE             ?BYTE
                        INC             W2I_PTR_HI
                        BNE             ?BYTE
                        RTS

W2I_FNV_INIT:
                        LDX             #$03
?BYTE:                 LDA             W2I_FNV_OFFSET,X
                        STA             W2I_HASH0,X
                        DEX
                        BPL             ?BYTE
                        RTS

W2I_FNV_UPDATE_A:
                        EOR             W2I_HASH0
                        STA             W2I_HASH0
                        LDX             #$03
?COPY:                 LDA             W2I_HASH0,X
                        STA             W2I_TERM0,X
                        DEX
                        BPL             ?COPY
                        LDX             #$01
                        JSR             W2I_FNV_SHIFT_ADD
                        LDX             #$03
                        JSR             W2I_FNV_SHIFT_ADD
                        LDX             #$03
                        JSR             W2I_FNV_SHIFT_ADD
                        LDX             #$01
                        JSR             W2I_FNV_SHIFT_ADD
                        LDA             W2I_HASH3
                        CLC
                        ADC             W2I_TERM1
                        STA             W2I_HASH3
                        RTS

W2I_FNV_SHIFT_ADD:
?SHIFT:                ASL             W2I_TERM0
                        ROL             W2I_TERM1
                        ROL             W2I_TERM2
                        ROL             W2I_TERM3
                        DEX
                        BNE             ?SHIFT
                        CLC
                        LDA             W2I_HASH0
                        ADC             W2I_TERM0
                        STA             W2I_HASH0
                        LDA             W2I_HASH1
                        ADC             W2I_TERM1
                        STA             W2I_HASH1
                        LDA             W2I_HASH2
                        ADC             W2I_TERM2
                        STA             W2I_HASH2
                        LDA             W2I_HASH3
                        ADC             W2I_TERM3
                        STA             W2I_HASH3
                        RTS

W2I_SAVE_SOURCE_HASH:
                        LDX             #$03
?BYTE:                 LDA             W2I_HASH0,X
                        STA             W2I_SOURCE_HASH0,X
                        DEX
                        BPL             ?BYTE
                        RTS

W2I_HASH_EQUALS_SOURCE:
                        LDX             #$03
?BYTE:                 LDA             W2I_HASH0,X
                        CMP             W2I_SOURCE_HASH0,X
                        BNE             ?FAIL
                        DEX
                        BPL             ?BYTE
                        SEC
                        RTS
?FAIL:                  CLC
                        RTS

W2I_BUILD_ARCHIVE_TOKEN:
                        LDX             #$08
                        LDA             W2I_HASH3
                        JSR             W2I_STORE_HEX_TOKEN
                        LDA             W2I_HASH2
                        JSR             W2I_STORE_HEX_TOKEN
                        LDA             W2I_HASH1
                        JSR             W2I_STORE_HEX_TOKEN
                        LDA             W2I_HASH0
                        JSR             W2I_STORE_HEX_TOKEN
                        STZ             W2I_ARCHIVE_TOKEN,X
                        RTS

W2I_STORE_HEX_TOKEN:
                        PHA
                        LSR             A
                        LSR             A
                        LSR             A
                        LSR             A
                        JSR             W2I_NIBBLE_ASCII
                        STA             W2I_ARCHIVE_TOKEN,X
                        INX
                        PLA
                        AND             #$0F
                        JSR             W2I_NIBBLE_ASCII
                        STA             W2I_ARCHIVE_TOKEN,X
                        INX
                        RTS

W2I_NIBBLE_ASCII:
                        CMP             #$0A
                        BCC             ?DIGIT
                        CLC
                        ADC             #('A'-10)
                        RTS
?DIGIT:                CLC
                        ADC             #'0'
                        RTS

W2I_PRINT_HASH:
                        LDA             W2I_SOURCE_HASH3
                        JSR             W2I_HEX
                        LDA             W2I_SOURCE_HASH2
                        JSR             W2I_HEX
                        LDA             W2I_SOURCE_HASH1
                        JSR             W2I_HEX
                        LDA             W2I_SOURCE_HASH0
                        JMP             W2I_HEX

W2I_MATCH_INPUT:
                        STX             W2I_PTR_LO
                        STY             W2I_PTR_HI
                        LDY             #$00
?BYTE:                 LDA             (W2I_PTR_LO),Y
                        CMP             W2I_INPUT,Y
                        BNE             ?FAIL
                        CMP             #$00
                        BEQ             ?OK
                        INY
                        CPY             #$20
                        BNE             ?BYTE
?FAIL:                  CLC
                        RTS
?OK:                    SEC
                        RTS

W2I_READ_LINE:
                        LDY             #$00
?NEXT:                 JSR             W2I_IN
                        CMP             #$0D
                        BEQ             ?DONE
                        CMP             #$0A
                        BEQ             ?NEXT
                        CMP             #'a'
                        BCC             ?STORE
                        CMP             #'z'+1
                        BCS             ?STORE
                        AND             #$DF
?STORE:                CPY             #$1F
                        BCS             ?NEXT
                        STA             W2I_INPUT,Y
                        JSR             W2I_OUT
                        INY
                        BRA             ?NEXT
?DONE:                 LDA             #$00
                        STA             W2I_INPUT,Y
                        JMP             W2I_CRLF

W2I_SELECT_BANK_A:
                        AND             #$03
                        TAX
                        LDA             W2I_BANK_BITS,X
                        PHA
                        LDA             #W2I_BANK_MASK
                        TRB             W2I_BANK_PCR
                        PLA
                        TSB             W2I_BANK_PCR
                        RTS

W2I_CON_INIT:
                        LDA             #W2I_FTDI_INIT
                        STA             W2I_FTDI_CTRL
                        STA             W2I_FTDI_DDRB
                        STZ             W2I_FTDI_DDRA
                        RTS

W2I_IN:
                        STZ             W2I_FTDI_DDRA
                        LDA             #W2I_FTDI_RXF
?WAIT:                 BIT             W2I_FTDI_CTRL
                        BNE             ?WAIT
                        LDA             #W2I_FTDI_RD
                        TRB             W2I_FTDI_CTRL
                        NOP
                        NOP
                        LDA             W2I_FTDI_DATA
                        PHA
                        LDA             #W2I_FTDI_RD
                        TSB             W2I_FTDI_CTRL
                        PLA
                        RTS

W2I_OUT:
                        PHA
                        STZ             W2I_FTDI_DDRA
                        STA             W2I_FTDI_DATA
                        NOP
                        NOP
                        LDA             #W2I_FTDI_TXE
?WAIT:                 BIT             W2I_FTDI_CTRL
                        BNE             ?WAIT
                        LDA             #W2I_FTDI_WR
                        TSB             W2I_FTDI_CTRL
                        DEC             W2I_FTDI_DDRA
                        NOP
                        NOP
                        LDA             #W2I_FTDI_WR
                        TRB             W2I_FTDI_CTRL
                        STZ             W2I_FTDI_DDRA
                        PLA
                        RTS

W2I_PUTS:
                        STX             W2I_PTR_LO
                        STY             W2I_PTR_HI
                        LDY             #$00
?BYTE:                 LDA             (W2I_PTR_LO),Y
                        BEQ             ?DONE
                        JSR             W2I_OUT
                        INY
                        BNE             ?BYTE
                        INC             W2I_PTR_HI
                        BRA             ?BYTE
?DONE:                 RTS

W2I_HEX:
                        PHA
                        LSR             A
                        LSR             A
                        LSR             A
                        LSR             A
                        JSR             W2I_HEX_NIBBLE
                        PLA
                        AND             #$0F
W2I_HEX_NIBBLE:
                        JSR             W2I_NIBBLE_ASCII
                        JMP             W2I_OUT

W2I_CRLF:
                        LDA             #$0D
                        JSR             W2I_OUT
                        LDA             #$0A
                        JMP             W2I_OUT

W2I_BANK_BITS:          DB              $CC,$CE,$EC,$EE
W2I_FNV_OFFSET:         DB              $C5,$9D,$1C,$81

W2I_MSG_TITLE:          DB              $0D,$0A,"WDCMONV2 -> STR8-N SEED INSTALL 0.1",$0D,$0A
                        DB              "B0 PRESERVES STOCK; B3:F BECOMES STR8-N",$0D,$0A
                        DB              "NO RESET/NMI/POWER DURING ACTIVE WRITE",$0D,$0A,0
W2I_MSG_ID_OK:          DB              "FLASH ID=",0
W2I_MSG_ID_FAIL:        DB              "REFUSE: FLASH IS NOT SST39SF010A BF/B5",$0D,$0A,0
W2I_MSG_B3_HASH:        DB              "STOCK B3 FNV1A=",0
W2I_MSG_ARCHIVE:        DB              "AFTER LOCAL EXTRACTOR PASS TYPE ARCHIVE ",0
W2I_MSG_PROMPT_END:     DB              "> ",0
W2I_MSG_ARCHIVE_FAIL:   DB              "REFUSE: LOCAL ARCHIVE TOKEN MISMATCH",$0D,$0A,0
W2I_MSG_B0_USED:        DB              "REFUSE: B0 USED AND DIFFERENT; NOTHING WRITTEN",$0D,$0A,0
W2I_MSG_HASH_COLLISION: DB              "REFUSE: B0/B3 HASH MATCH BUT BYTES DIFFER",$0D,$0A,0
W2I_MSG_COPY_CONFIRM:   DB              "B0 ERASED; TYPE COPY B3 TO B0> ",0
W2I_MSG_COPYING:        DB              "COPY/VERIFY B3 -> B0 ",0
W2I_MSG_COPY_FAIL:      DB              "B0 COPY FAILED; B3 UNCHANGED",$0D,$0A,0
W2I_MSG_COMPARE_FAIL:   DB              "B0 WHOLE-BANK HASH/EXACT VERIFY FAILED",$0D,$0A,0
W2I_MSG_B0_OK:          DB              "B0 == ORIGINAL B3 VERIFIED",$0D,$0A,0
W2I_MSG_CANDIDATE_BAD:  DB              "CARRIED STR8-N TOP CHECK FAILED",$0D,$0A,0
W2I_MSG_INSTALL_CONFIRM: DB             "TYPE INSTALL STR8-N 1.23> ",0
W2I_MSG_INSTALLING:     DB              "ERASING/PROGRAMMING B3:F",$0D,$0A,0
W2I_MSG_INSTALLED:      DB              "STR8-N VERIFIED; RESET",$0D,$0A,0
W2I_MSG_RECOVERY:       DB              "B3:F FAIL: R=RETRY STR8 O=RESTORE OLD> ",0
W2I_MSG_OLD_RESTORED:   DB              "OLD B3:F RESTORED FROM B0:F; RESET",$0D,$0A,0
W2I_MSG_CANCEL:         DB              "CANCELLED; NOTHING FURTHER WRITTEN",$0D,$0A,0
W2I_MSG_ABORT:          DB              "HALTED IN RAM; PHYSICAL RESET SELECTS B3",$0D,$0A,0

W2I_TOKEN_COPY:         DB              "COPY B3 TO B0",0
W2I_TOKEN_INSTALL:      DB              "INSTALL STR8-N 1.23",0
W2I_ARCHIVE_TOKEN:      DB              "ARCHIVE ",0,0,0,0,0,0,0,0,0
W2I_INPUT:              DS              32

W2I_ID_MAN:             DB              $00
W2I_ID_DEV:             DB              $00
W2I_SECTOR_HI:          DB              $00
W2I_ERASED:             DB              $00
W2I_HASH0:              DB              $00
W2I_HASH1:              DB              $00
W2I_HASH2:              DB              $00
W2I_HASH3:              DB              $00
W2I_TERM0:              DB              $00
W2I_TERM1:              DB              $00
W2I_TERM2:              DB              $00
W2I_TERM3:              DB              $00
W2I_SOURCE_HASH0:       DB              $00
W2I_SOURCE_HASH1:       DB              $00
W2I_SOURCE_HASH2:       DB              $00
W2I_SOURCE_HASH3:       DB              $00

                        ORG             $4000
W2I_CANDIDATE_IMAGE:
                        INCLUDE         "str8n-v1.23-wdcmonv2-install-image.inc"

                        END
