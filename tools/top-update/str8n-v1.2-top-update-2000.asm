; STR8-N v1.2 BANK-3 TOP-SECTOR UPDATE TOOL.
; Load with an installed STR8-N v1.1/v1.2 L command; S9 starts at $2000.
; The exact verified v1.2 top-sector BIN is generated into the $4000 image.
; This program uses direct FT245R and flash access after active erase begins.

                        MODULE          STR8N_V12_TOP_UPDATE
                        ORG             $2000

TU_FTDI_CTRL            EQU             $7FE0
TU_FTDI_DATA            EQU             $7FE1
TU_FTDI_DDRA            EQU             $7FE3
TU_FTDI_TXE             EQU             $01
TU_FTDI_RXF             EQU             $02
TU_FTDI_WR              EQU             $04
TU_FTDI_RD              EQU             $08
TU_PCR                   EQU             $7FEC
TU_BANK1                 EQU             $CE
TU_BANK3                 EQU             $EE

TU_STATUS                EQU             $7C00
TU_FAIL_LO               EQU             $7C01
TU_FAIL_HI               EQU             $7C02
TU_ACTIVE                EQU             $7C03
TU_OLD_SUM_LO            EQU             $7C04
TU_OLD_SUM_HI            EQU             $7C05
TU_INPUT                 EQU             $7C20
TU_META                  EQU             $7C40
TU_META_SIZE             EQU             $4A

TU_SRC_LO                EQU             $C8
TU_SRC_HI                EQU             $C9
TU_DST_LO                EQU             $CA
TU_DST_HI                EQU             $CB
TU_DATA                  EQU             $CC
TU_TMO0                  EQU             $CD
TU_TMO1                  EQU             $CE
TU_TMO2                  EQU             $CF
TU_SUM_LO                EQU             $D0
TU_SUM_HI                EQU             $D1

START:                  SEI
                        CLD
                        LDX             #$FF
                        TXS
                        STZ             TU_STATUS
                        STZ             TU_ACTIVE
                        LDX             #<TU_MSG_TITLE
                        LDY             #>TU_MSG_TITLE
                        JSR             TU_PUTS
                        LDA             #TU_BANK3
                        JSR             TU_SELECT
                        LDA             $F000
                        CMP             #$4C
                        BEQ             TU_PF_HEAD_OK
                        JMP             TU_PREFLIGHT_FAIL
TU_PF_HEAD_OK:
                        LDA             $F00C
                        CMP             #'S'
                        BEQ             TU_PF_SIG0_OK
                        JMP             TU_PREFLIGHT_FAIL
TU_PF_SIG0_OK:
                        LDA             $F00D
                        CMP             #'R'
                        BEQ             TU_PF_SIG1_OK
                        JMP             TU_PREFLIGHT_FAIL
TU_PF_SIG1_OK:
                        JSR             TU_SUM_CANDIDATE
                        LDA             TU_SUM_LO
                        CMP             #<TU_CANDIDATE_SUM
                        BEQ             TU_PF_SUM_LO_OK
                        JMP             TU_CANDIDATE_FAIL
TU_PF_SUM_LO_OK:
                        LDA             TU_SUM_HI
                        CMP             #>TU_CANDIDATE_SUM
                        BEQ             TU_PF_SUM_HI_OK
                        JMP             TU_CANDIDATE_FAIL
TU_PF_SUM_HI_OK:
                        JSR             TU_SAVE_META
                        LDX             #<TU_MSG_BACKUP
                        LDY             #>TU_MSG_BACKUP
                        JSR             TU_PUTS
                        JSR             TU_READ_LINE
                        LDX             #<TU_CONFIRM_BACKUP
                        LDY             #>TU_CONFIRM_BACKUP
                        JSR             TU_MATCH_INPUT
                        BCS             TU_BACKUP_CONFIRMED
                        JMP             TU_CANCEL
TU_BACKUP_CONFIRMED:
                        LDA             #TU_BANK3
                        JSR             TU_SELECT
                        JSR             TU_FLASH_TO_STAGE
                        JSR             TU_SUM_STAGE
                        LDA             TU_SUM_LO
                        STA             TU_OLD_SUM_LO
                        LDA             TU_SUM_HI
                        STA             TU_OLD_SUM_HI
                        LDA             #TU_BANK1
                        JSR             TU_SELECT
                        JSR             TU_PROGRAM_STAGE
                        BCS             TU_BACKUP_PROGRAMMED
                        JMP             TU_BACKUP_FAIL
TU_BACKUP_PROGRAMMED:
                        JSR             TU_FLASH_TO_STAGE
                        JSR             TU_SUM_STAGE
                        LDA             TU_SUM_LO
                        CMP             TU_OLD_SUM_LO
                        BEQ             TU_BACKUP_SUM_LO_OK
                        JMP             TU_BACKUP_FAIL
TU_BACKUP_SUM_LO_OK:
                        LDA             TU_SUM_HI
                        CMP             TU_OLD_SUM_HI
                        BEQ             TU_BACKUP_SUM_HI_OK
                        JMP             TU_BACKUP_FAIL
TU_BACKUP_SUM_HI_OK:
                        LDA             #TU_BANK3
                        JSR             TU_SELECT
                        LDX             #<TU_MSG_BACKUP_OK
                        LDY             #>TU_MSG_BACKUP_OK
                        JSR             TU_PUTS
                        LDX             #<TU_MSG_RECEIPT
                        LDY             #>TU_MSG_RECEIPT
                        JSR             TU_PUTS
                        LDA             TU_OLD_SUM_HI
                        JSR             TU_HEX
                        LDA             TU_OLD_SUM_LO
                        JSR             TU_HEX
                        LDA             #$0D
                        JSR             TU_OUT
                        LDA             #$0A
                        JSR             TU_OUT
                        JSR             TU_PREPARE_CANDIDATE
                        LDX             #<TU_MSG_FINAL
                        LDY             #>TU_MSG_FINAL
                        JSR             TU_PUTS
                        JSR             TU_READ_LINE
                        LDX             #<TU_CONFIRM_FINAL
                        LDY             #>TU_CONFIRM_FINAL
                        JSR             TU_MATCH_INPUT
                        BCS             TU_FINAL_CONFIRMED
                        JMP             TU_CANCEL
TU_FINAL_CONFIRMED:
                        LDX             #<TU_MSG_ERASE
                        LDY             #>TU_MSG_ERASE
                        JSR             TU_PUTS
                        LDA             #$01
                        STA             TU_ACTIVE
TU_RETRY_CANDIDATE:     JSR             TU_PREPARE_CANDIDATE
                        LDA             #TU_BANK3
                        JSR             TU_SELECT
                        JSR             TU_PROGRAM_STAGE
                        BCC             TU_RECOVERY
TU_SUCCESS:             LDX             #<TU_MSG_OK
                        LDY             #>TU_MSG_OK
                        JSR             TU_PUTS
                        JMP             ($FFFC)

TU_RECOVERY:            LDX             #<TU_MSG_RECOVERY
                        LDY             #>TU_MSG_RECOVERY
                        JSR             TU_PUTS
                        JSR             TU_READ_LINE
                        LDA             TU_INPUT+1
                        BNE             TU_RECOVERY
                        LDA             TU_INPUT
                        CMP             #'R'
                        BEQ             TU_RETRY_CANDIDATE
                        CMP             #'O'
                        BNE             TU_RECOVERY
                        LDA             #TU_BANK1
                        JSR             TU_SELECT
                        JSR             TU_FLASH_TO_STAGE
                        JSR             TU_SUM_STAGE
                        LDA             TU_SUM_LO
                        CMP             TU_OLD_SUM_LO
                        BNE             TU_RECOVERY
                        LDA             TU_SUM_HI
                        CMP             TU_OLD_SUM_HI
                        BNE             TU_RECOVERY
                        LDA             #TU_BANK3
                        JSR             TU_SELECT
                        JSR             TU_PROGRAM_STAGE
                        BCC             TU_RECOVERY
                        LDX             #<TU_MSG_OLD_OK
                        LDY             #>TU_MSG_OLD_OK
                        JSR             TU_PUTS
                        JMP             ($FFFC)

TU_PREFLIGHT_FAIL:      LDA             #$E0
                        BRA             TU_FAIL_SAFE
TU_CANDIDATE_FAIL:      LDA             #$E4
                        BRA             TU_FAIL_SAFE
TU_BACKUP_FAIL:         LDA             #$E5
                        BRA             TU_FAIL_SAFE
TU_CANCEL:              LDA             #$E0
TU_FAIL_SAFE:           STA             TU_STATUS
                        LDA             #TU_BANK3
                        JSR             TU_SELECT
                        LDX             #<TU_MSG_ABORT
                        LDY             #>TU_MSG_ABORT
                        JSR             TU_PUTS
                        RTS

; Save live directory/config $FFB0-$FFF9 before using the staging tray.
TU_SAVE_META:           LDX             #$00
TU_SAVE_META_BYTE:      LDA             $FFB0,X
                        STA             TU_META,X
                        INX
                        CPX             #TU_META_SIZE
                        BNE             TU_SAVE_META_BYTE
                        RTS

TU_PREPARE_CANDIDATE:   STZ             TU_SRC_LO
                        LDA             #$40
                        STA             TU_SRC_HI
                        STZ             TU_DST_LO
                        LDA             #$0A
                        STA             TU_DST_HI
                        LDX             #$10
TU_PC_PAGE:             LDY             #$00
TU_PC_BYTE:             LDA             (TU_SRC_LO),Y
                        STA             (TU_DST_LO),Y
                        INY
                        BNE             TU_PC_BYTE
                        INC             TU_SRC_HI
                        INC             TU_DST_HI
                        DEX
                        BNE             TU_PC_PAGE
                        LDX             #$00
TU_PC_META:             LDA             TU_META,X
                        STA             $19B0,X
                        INX
                        CPX             #TU_META_SIZE
                        BNE             TU_PC_META
                        RTS

TU_FLASH_TO_STAGE:      STZ             TU_SRC_LO
                        LDA             #$F0
                        STA             TU_SRC_HI
                        STZ             TU_DST_LO
                        LDA             #$0A
                        STA             TU_DST_HI
                        LDX             #$10
TU_FS_PAGE:             LDY             #$00
TU_FS_BYTE:             LDA             (TU_SRC_LO),Y
                        STA             (TU_DST_LO),Y
                        INY
                        BNE             TU_FS_BYTE
                        INC             TU_SRC_HI
                        INC             TU_DST_HI
                        DEX
                        BNE             TU_FS_PAGE
                        RTS

TU_PROGRAM_STAGE:      STZ             TU_FAIL_LO
                        STZ             TU_FAIL_HI
                        STZ             TU_DST_LO
                        LDA             #$F0
                        STA             TU_DST_HI
                        JSR             TU_UNLOCK
                        LDA             #$80
                        STA             $D555
                        JSR             TU_UNLOCK
                        LDA             #$30
                        LDY             #$00
                        STA             (TU_DST_LO),Y
                        STZ             TU_TMO0
                        STZ             TU_TMO1
                        LDA             #$08
                        STA             TU_TMO2
TU_ERASE_POLL:          LDA             (TU_DST_LO),Y
                        CMP             #$FF
                        BEQ             TU_ERASED
                        DEC             TU_TMO0
                        BNE             TU_ERASE_POLL
                        DEC             TU_TMO1
                        BNE             TU_ERASE_POLL
                        DEC             TU_TMO2
                        BNE             TU_ERASE_POLL
                        LDA             #$E1
                        STA             TU_STATUS
                        BRA             TU_FLASH_FAIL
TU_ERASED:              STZ             TU_SRC_LO
                        LDA             #$0A
                        STA             TU_SRC_HI
                        STZ             TU_DST_LO
                        LDA             #$F0
                        STA             TU_DST_HI
TU_PROGRAM_BYTE:        LDA             TU_DST_HI
                        CMP             #$FF
                        BNE             TU_PROGRAM_NORMAL
                        LDA             TU_DST_LO
                        CMP             #$FC
                        BEQ             TU_PROGRAM_NEXT
                        CMP             #$FD
                        BEQ             TU_PROGRAM_NEXT
TU_PROGRAM_NORMAL:      LDY             #$00
                        LDA             (TU_SRC_LO),Y
                        JSR             TU_PROGRAM_A
                        BCC             TU_PROGRAM_FAIL
TU_PROGRAM_NEXT:        INC             TU_SRC_LO
                        INC             TU_DST_LO
                        BNE             TU_PROGRAM_BYTE
                        INC             TU_SRC_HI
                        INC             TU_DST_HI
                        LDA             TU_DST_HI
                        BNE             TU_PROGRAM_BYTE
                        LDA             #$FC
                        STA             TU_SRC_LO
                        STA             TU_DST_LO
                        LDA             #$19
                        STA             TU_SRC_HI
                        LDA             #$FF
                        STA             TU_DST_HI
                        LDY             #$00
                        LDA             (TU_SRC_LO),Y
                        JSR             TU_PROGRAM_A
                        BCC             TU_PROGRAM_FAIL
                        INC             TU_SRC_LO
                        INC             TU_DST_LO
                        LDA             (TU_SRC_LO),Y
                        JSR             TU_PROGRAM_A
                        BCC             TU_PROGRAM_FAIL
                        JSR             TU_VERIFY_STAGE
                        BCC             TU_VERIFY_FAIL
                        LDA             #$AC
                        STA             TU_STATUS
                        LDA             #$F0
                        STA             $D555
                        SEC
                        RTS
TU_PROGRAM_FAIL:       LDA             #$E2
                        STA             TU_STATUS
                        BRA             TU_RECORD_FAIL
TU_VERIFY_FAIL:        LDA             #$E3
                        STA             TU_STATUS
TU_RECORD_FAIL:        LDA             TU_DST_LO
                        STA             TU_FAIL_LO
                        LDA             TU_DST_HI
                        STA             TU_FAIL_HI
TU_FLASH_FAIL:         LDA             #$F0
                        STA             $D555
                        CLC
                        RTS

TU_PROGRAM_A:          CMP             #$FF
                        BEQ             TU_PROGRAM_OK
                        STA             TU_DATA
                        JSR             TU_UNLOCK
                        LDA             #$A0
                        STA             $D555
                        LDA             TU_DATA
                        LDY             #$00
                        STA             (TU_DST_LO),Y
                        STZ             TU_TMO0
                        STZ             TU_TMO1
                        LDA             #$02
                        STA             TU_TMO2
TU_WRITE_POLL:         LDA             (TU_DST_LO),Y
                        CMP             TU_DATA
                        BEQ             TU_PROGRAM_OK
                        DEC             TU_TMO0
                        BNE             TU_WRITE_POLL
                        DEC             TU_TMO1
                        BNE             TU_WRITE_POLL
                        DEC             TU_TMO2
                        BNE             TU_WRITE_POLL
                        CLC
                        RTS
TU_PROGRAM_OK:         SEC
                        RTS

TU_VERIFY_STAGE:       STZ             TU_SRC_LO
                        LDA             #$0A
                        STA             TU_SRC_HI
                        STZ             TU_DST_LO
                        LDA             #$F0
                        STA             TU_DST_HI
TU_V_PAGE:             LDY             #$00
TU_V_BYTE:             LDA             (TU_SRC_LO),Y
                        CMP             (TU_DST_LO),Y
                        BNE             TU_V_FAIL
                        INY
                        BNE             TU_V_BYTE
                        INC             TU_SRC_HI
                        INC             TU_DST_HI
                        LDA             TU_DST_HI
                        BNE             TU_V_PAGE
                        SEC
                        RTS
TU_V_FAIL:             TYA
                        STA             TU_DST_LO
                        CLC
                        RTS

TU_UNLOCK:             LDA             #$AA
                        STA             $D555
                        LDA             #$55
                        STA             $AAAA
                        RTS

TU_SELECT:             PHA
                        LDA             #$EE
                        TRB             TU_PCR
                        PLA
                        TSB             TU_PCR
                        RTS

TU_SUM_CANDIDATE:      STZ             TU_SRC_LO
                        LDA             #$40
                        BRA             TU_SUM_START
TU_SUM_STAGE:          STZ             TU_SRC_LO
                        LDA             #$0A
TU_SUM_START:          STA             TU_SRC_HI
                        STZ             TU_SUM_LO
                        STZ             TU_SUM_HI
                        LDX             #$10
TU_SUM_PAGE:           LDY             #$00
TU_SUM_BYTE:           CLC
                        LDA             TU_SUM_LO
                        ADC             (TU_SRC_LO),Y
                        STA             TU_SUM_LO
                        BCC             TU_SUM_NO_CARRY
                        INC             TU_SUM_HI
TU_SUM_NO_CARRY:       INY
                        BNE             TU_SUM_BYTE
                        INC             TU_SRC_HI
                        DEX
                        BNE             TU_SUM_PAGE
                        RTS

TU_MATCH_INPUT:
                        STX             TU_SRC_LO
                        STY             TU_SRC_HI
                        LDY             #$00
TU_MATCH_BYTE:         LDA             (TU_SRC_LO),Y
                        CMP             TU_INPUT,Y
                        BNE             TU_MATCH_FAIL
                        CMP             #$00
                        BEQ             TU_MATCH_OK
                        INY
                        CPY             #$10
                        BNE             TU_MATCH_BYTE
TU_MATCH_FAIL:         CLC
                        RTS
TU_MATCH_OK:           SEC
                        RTS

TU_READ_LINE:          LDY             #$00
TU_READ_NEXT:          JSR             TU_IN
                        CMP             #$0D
                        BEQ             TU_READ_DONE
                        CMP             #$0A
                        BEQ             TU_READ_NEXT
                        CMP             #'a'
                        BCC             TU_READ_STORE
                        CMP             #'z'+1
                        BCS             TU_READ_STORE
                        AND             #$DF
TU_READ_STORE:         CPY             #$0F
                        BCS             TU_READ_NEXT
                        STA             TU_INPUT,Y
                        JSR             TU_OUT
                        INY
                        BRA             TU_READ_NEXT
TU_READ_DONE:          LDA             #$00
                        STA             TU_INPUT,Y
                        LDA             #$0D
                        JSR             TU_OUT
                        LDA             #$0A
                        JSR             TU_OUT
                        RTS

TU_PUTS:               STX             TU_SRC_LO
                        STY             TU_SRC_HI
                        LDY             #$00
TU_PUTS_BYTE:          LDA             (TU_SRC_LO),Y
                        BEQ             TU_PUTS_DONE
                        JSR             TU_OUT
                        INY
                        BNE             TU_PUTS_BYTE
                        INC             TU_SRC_HI
                        BRA             TU_PUTS_BYTE
TU_PUTS_DONE:          RTS

TU_HEX:                PHA
                        LSR             A
                        LSR             A
                        LSR             A
                        LSR             A
                        JSR             TU_NIBBLE
                        PLA
                        AND             #$0F
TU_NIBBLE:             CMP             #$0A
                        BCC             TU_HEX_DIGIT
                        ADC             #$06
TU_HEX_DIGIT:          ADC             #'0'
                        JMP             TU_OUT

TU_OUT:                PHA
                        STZ             TU_FTDI_DDRA
                        STA             TU_FTDI_DATA
TU_OUT_READY:          LDA             #TU_FTDI_TXE
                        BIT             TU_FTDI_CTRL
                        BNE             TU_OUT_READY
                        LDA             #TU_FTDI_WR
                        TSB             TU_FTDI_CTRL
                        DEC             TU_FTDI_DDRA
                        NOP
                        NOP
                        TRB             TU_FTDI_CTRL
                        STZ             TU_FTDI_DDRA
                        PLA
                        RTS

TU_IN:                 STZ             TU_FTDI_DDRA
TU_IN_READY:           LDA             #TU_FTDI_RXF
                        BIT             TU_FTDI_CTRL
                        BNE             TU_IN_READY
                        LDA             #TU_FTDI_RD
                        TRB             TU_FTDI_CTRL
                        NOP
                        NOP
                        LDA             TU_FTDI_DATA
                        PHA
                        LDA             #TU_FTDI_RD
                        TSB             TU_FTDI_CTRL
                        PLA
                        RTS

TU_MSG_TITLE:          DB              $0D,$0A,"STR8-N 1.2 TOP UPDATE",$0D,$0A
                        DB              "BACKUP B1:F; TARGET B3:F",$0D,$0A,0
TU_MSG_BACKUP:         DB              "TYPE BACKUP B1F> ",0
TU_MSG_BACKUP_OK:      DB              "BACKUP VERIFIED",$0D,$0A,0
TU_MSG_RECEIPT:        DB              "SAFE PHY $0F000-$0FFFF; TARGET PHY "
                        DB              "$1F000-$1FFFF; SUM=$",0
TU_MSG_FINAL:          DB              "TYPE STR8-N 1.2> ",0
TU_MSG_ERASE:          DB              "ERASING B3:F - NO RESET/NMI/POWER",$0D,$0A,0
TU_MSG_RECOVERY:       DB              "WRITE FAIL: R=RETRY O=RESTORE OLD> ",0
TU_MSG_OK:             DB              "STR8-N 1.2 VERIFIED; RESET",$0D,$0A,0
TU_MSG_OLD_OK:         DB              "OLD TOP RESTORED; RESET",$0D,$0A,0
TU_MSG_ABORT:          DB              "ABORT - NO ACTIVE TOP UPDATE",$0D,$0A,0
TU_CONFIRM_BACKUP:     DB              "BACKUP B1F",0
TU_CONFIRM_FINAL:      DB              "STR8-N 1.2",0

; TU_CONFIRM receives the expected string in X/Y. These call sites use a
; prompt pointer first, so expose small wrappers with fixed expected strings.
; The assembler resolves the rewritten calls below through these entry labels.

                        ORG             $4000
TU_CANDIDATE_IMAGE:
                        INCLUDE         "str8n-v1.2-top-image.inc"
                        END
