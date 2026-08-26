; Guarded directory-description rename extension for Bank Maintenance.
; The menu build places this in the unused $3D00-$3FFF top-update gap. The
; standalone maintenance image places it at $3700. Both paths reuse the main
; tool's validated scratch selection and three-step B3:F rewrite transaction.

        IF STR8_BANK_MAINT_TOP
        ORG $3D00
        ELSE
        ORG $3700
        ENDIF

BM_RENAME LDA #'N'
        STA $7C01
?BANK   LDX #<BM_MNBANK
        LDY #>BM_MNBANK
        JSR BM_PUTS
        JSR BM_READ
        BCC ?ABORT
        JSR BM_PARSE_BANK
        BCC ?BANK
        CMP #$04
        BCS ?BANK
        STA $7C03
        STA $7C05
        JSR BM_RENAME_VALIDATE
        BCC ?INVALID
?DESC   LDX #<BM_MCDESC
        LDY #>BM_MCDESC
        JSR BM_PUTS
        JSR BM_READ
        BCC ?ABORT
        LDA $7C25
        BNE ?DESC
        LDX #$00
?DESC_BYTE
        LDA $7C20,X
        JSR BM_DESC_BYTE
        BCC ?DESC
        STA $7C19,X
        INX
        CPX #$05
        BNE ?DESC_BYTE
        JSR BM_COPY_DIR_BASE
        LDX #$00
        LDY #$04
?SAME  LDA ($CA),Y
        CMP $7C19,X
        BNE ?CHANGED
        INX
        INY
        CPX #$05
        BNE ?SAME
        LDX #<BM_MNSAME
        LDY #>BM_MNSAME
        JSR BM_PUTS
        JMP BM_SUCCESS
?CHANGED
        JMP BM_RECLAIM_J3
?INVALID
        LDX #<BM_MNINVALID
        LDY #>BM_MNINVALID
        JSR BM_PUTS
?ABORT  JMP BM_ABORT

; Require the same immutable structure accepted by STR8-N and a legal,
; uninterrupted journal with at least one COMPLETE pair. Empty, incomplete,
; malformed, and fresh rows cannot be renamed.
BM_RENAME_VALIDATE
        LDA #$03
        JSR $0203
        JSR BM_COPY_DIR_BASE
        LDY #$01
?RESERVED
        LDA ($CA),Y
        CMP #$FF
        BNE ?BAD
        INY
        CPY #$04
        BNE ?RESERVED
        LDY #$04
?OLD_DESC
        LDA ($CA),Y
        JSR BM_DESC_BYTE
        BCC ?BAD
        INY
        CPY #$09
        BNE ?OLD_DESC
        LDA ($CA),Y
        CMP #$FE
        BNE ?BAD
        LDY #$0A
        LDA ($CA),Y
        INY
        AND ($CA),Y
        CMP #$FF
        BEQ ?JOURNAL
        LDA $7C03
        CMP #$03
        BNE ?BAD
        LDA ($CA),Y
        CMP #$80
        BCC ?BAD
        CMP #$F0
        BCS ?BAD
?JOURNAL
        STZ $7C0B
        LDX #$00
        LDY #$0C
?JBYTE LDA ($CA),Y
        STA $7C10
        LDA #$08
        STA $7C11
?JBIT  LSR $7C10
        BCS ?JONE
        LDA $7C0B
        BNE ?BAD
        INX
        BRA ?JNEXT
?JONE  INC $7C0B
?JNEXT DEC $7C11
        BNE ?JBIT
        INY
        CPY #$10
        BNE ?JBYTE
        TXA
        BEQ ?BAD
        AND #$01
        BNE ?BAD
        SEC
        RTS
?BAD   CLC
        RTS

; Scratch has already been found and printed by BM_RECLAIM_J3. Require the
; exact 15-character command `RENAME Dn XXXXX` before staging B3:F.
BM_RENAME_CONFIRM
        LDX #<BM_MNCONFIRM
        LDY #>BM_MNCONFIRM
        JSR BM_PUTS
        LDA $7C05
        CLC
        ADC #'0'
        JSR BM_OUT
        LDA #' '
        JSR BM_OUT
        LDX #$00
?SHOW  LDA $7C19,X
        JSR BM_OUT
        INX
        CPX #$05
        BNE ?SHOW
        LDA #'>'
        JSR BM_OUT
        LDA #' '
        JSR BM_OUT
        JSR BM_READ
        BCC ?BAD
        LDA $7C2F
        BNE ?BAD
        LDX #$00
?PREFIX
        LDA $7C20,X
        CMP BM_MNEXACT,X
        BNE ?BAD
        INX
        CPX #$08
        BNE ?PREFIX
        LDA $7C05
        CLC
        ADC #'0'
        CMP $7C28
        BNE ?BAD
        LDA $7C29
        CMP #' '
        BNE ?BAD
        LDX #$00
?NAME  LDA $7C2A,X
        CMP $7C19,X
        BNE ?BAD
        INX
        CPX #$05
        BNE ?NAME
        JMP BM_B3F_REWRITE_CONFIRMED
?BAD   JMP BM_ABORT

; B3:F is staged at $0A00-$19FF. Change only row-relative bytes +4..+8.
BM_RENAME_APPLY
        LDA $7C05
        ASL A
        ASL A
        ASL A
        ASL A
        CLC
        ADC #$B4
        STA $CA
        LDA #$19
        STA $CB
        LDX #$00
        LDY #$00
?BYTE  LDA $7C19,X
        STA ($CA),Y
        INX
        INY
        CPX #$05
        BNE ?BYTE
        RTS

BM_MNBANK DB $0D,$0A,'R','E','N','A','M','E',' ','D','I','R',' ','0','-','3','>',' ',0
BM_MNINVALID DB $0D,$0A,'D','I','R',' ','N','O','T',' ','C','O','M','P','L','E','T','E',$0D,$0A,0
BM_MNSAME DB $0D,$0A,'N','A','M','E',' ','U','N','C','H','A','N','G','E','D',$0D,$0A,0
BM_MNCONFIRM DB $0D,$0A,'T','Y','P','E',' ','R','E','N','A','M','E',' ','D',0
BM_MNEXACT DB 'R','E','N','A','M','E',' ','D'

; One-sector AP carrier put. The package is written at the selected sector
; base so the later HIMON command is simply AP Bn $s000 dst. The target line
; is also the exact destructive confirmation: for example, PUT B28000.
BM_PUT  BRA ?BODY
?MTARGET DB "TYPE PUT BnS000 (n=0-2,S=8-F)> ",0
?PREFIX DB 'P','U','T',' ','B'
?BAD    JMP BM_ABORT
?BODY   LDA #'P'
        STA $7C01
        IF STR8_BANK_MAINT_TOP
        LDA $7000
        ELSE
        LDA $4000
        ENDIF
        CMP #'A'
        BNE ?BAD
        IF STR8_BANK_MAINT_TOP
        LDA $7001
        ELSE
        LDA $4001
        ENDIF
        CMP #'P'
        BNE ?BAD
        IF STR8_BANK_MAINT_TOP
        LDA $7002
        ELSE
        LDA $4002
        ENDIF
        CMP #$02
        BNE ?BAD
        IF STR8_BANK_MAINT_TOP
        LDA $7004
        ELSE
        LDA $4004
        ENDIF
        BNE ?BAD
        IF STR8_BANK_MAINT_TOP
        LDA $7003
        ELSE
        LDA $4003
        ENDIF
        CMP #$05
        BCC ?BAD
        STA $7C05

        LDX #<?MTARGET
        LDY #>?MTARGET
        JSR BM_PUTS
        JSR BM_READ
        BCC ?BAD
        LDX #$00
?PREFIX_CHECK
        LDA $7C20,X
        CMP ?PREFIX,X
        BNE ?BAD
        INX
        CPX #$05
        BNE ?PREFIX_CHECK
        LDA $7C25
        SEC
        SBC #'0'
        BCC ?BAD
        CMP #$03
        BCS ?BAD
        STA $7C02
        STA $7C03
        LDA $7C26
        JSR BM_EHEX
        BCC ?BAD
        STA $7C04
        LDX #$07
?ZERO_CHECK
        LDA $7C20,X
        CMP #'0'
        BNE ?BAD
        INX
        CPX #$0A
        BNE ?ZERO_CHECK
        LDA $7C2A
        BNE ?BAD

; Reject configured WORK and B3F-backup roles even if their leading bytes
; happen to be erased. BM_ECHECK_ROLES consumes $7C05 as a sector count.
        LDA $7C05
        PHA
        LDA #$01
        STA $7C05
        JSR BM_ECHECK_ROLES
        PLA
        STA $7C05
        BCS ?ROLEOK
        JMP BM_EPROTECTED

?ROLEOK JSR BM_STAGE
        BCS ?STAGED
        JMP BM_FSTAGE
?STAGED
        LDX #$00
?ERASED LDA $0A00,X
        CMP #$FF
        BEQ ?ERASED_BYTE
        JMP BM_ABORT
?ERASED_BYTE
        INX
        CPX $7C05
        BNE ?ERASED

        LDX #$00
?OVERLAY
        IF STR8_BANK_MAINT_TOP
        LDA $7000,X
        ELSE
        LDA $4000,X
        ENDIF
        STA $0A00,X
        INX
        CPX $7C05
        BNE ?OVERLAY
        JSR BM_PROGRAM
        BCS ?PROGRAMMED
        JMP BM_FPROGRAM
?PROGRAMMED
        JMP BM_SUCCESS
