; STR8-iN/65-only editor for the accepted Bank-3 $FFF2 scoped-search policy.
; It deliberately does not assign $FFF0/$FFF1 roles or invent a VTOC. The
; shared Bank Maintenance path takes a verified temporary B3:F backup before
; changing the staged byte, verifies rewritten B3:F, then erases the scratch.

        ORG $3A00

BM_FLAGS
        LDA #'F'
        STA $7C01
?PROMPT
        LDX #<BM_MF_PROMPT
        LDY #>BM_MF_PROMPT
        JSR BM_PUTS
        JSR BM_READ
        BCC ?ABORT
        LDA $7C20
        BNE ?TYPED
        LDA #$A6
        STA $7C35
        BRA ?VALID
?TYPED
        LDA $7C22
        BNE ?PROMPT
        LDA $7C20
        JSR BM_HEX_NIBBLE
        BCC ?PROMPT
        ASL A
        ASL A
        ASL A
        ASL A
        STA $7C35
        LDA $7C21
        JSR BM_HEX_NIBBLE
        BCC ?PROMPT
        ORA $7C35
        STA $7C35
        CMP #$FF
        BEQ ?VALID
        CMP #$A0
        BCC ?PROMPT
        CMP #$A8
        BCS ?PROMPT
?VALID
; Compare against a fresh staged B3:F before finding scratch. No write is
; offered when the requested policy is already present.
        LDA #$03
        STA $7C02
        LDA #$F0
        STA $7C04
        JSR BM_STAGE
        BCC ?STAGE_FAIL
        LDA $19F2
        CMP $7C35
        BNE ?CHANGED
        LDX #<BM_MF_SAME
        LDY #>BM_MF_SAME
        JSR BM_PUTS
        JMP BM_SUCCESS
?CHANGED
        JMP BM_RECLAIM_J3
?STAGE_FAIL
        JMP BM_FSTAGE
?ABORT JMP BM_ABORT

; Scratch is selected and displayed by BM_RECLAIM_J3. Require the exact
; target-specific confirmation before the shared B3:F backup/rewrite path.
BM_FLAGS_CONFIRM
        LDX #<BM_MF_CONFIRM
        LDY #>BM_MF_CONFIRM
        JSR BM_PUTS
        LDA $7C35
        JSR BM_HEX
        LDA #'>'
        JSR BM_OUT
        LDA #' '
        JSR BM_OUT
        JSR BM_READ
        BCC ?BAD
        LDA $7C28
        BNE ?BAD
        LDX #$00
?PREFIX
        LDA $7C20,X
        CMP BM_MF_EXACT,X
        BNE ?BAD
        INX
        CPX #$06
        BNE ?PREFIX
        LDA $7C26
        JSR BM_HEX_NIBBLE
        BCC ?BAD
        ASL A
        ASL A
        ASL A
        ASL A
        STA $7C36
        LDA $7C27
        JSR BM_HEX_NIBBLE
        BCC ?BAD
        ORA $7C36
        CMP $7C35
        BNE ?BAD
        JMP BM_B3F_REWRITE_CONFIRMED
?BAD   JMP BM_ABORT

; B3:F is staged at $0A00-$19FF, making $FFF2 appear at $19F2.
BM_FLAGS_APPLY
        LDA $7C35
        STA $19F2
        RTS

BM_MF_PROMPT DB $0D,$0A,'S','E','A','R','C','H',' ','F','L','A','G',' '
        DB 'F','F','/','A','0','-','A','7',' ','[','A','6',']','>',' ',0
BM_MF_SAME DB $0D,$0A,'F','L','A','G',' ','U','N','C','H','A','N','G','E','D',$0D,$0A,0
BM_MF_CONFIRM DB $0D,$0A,'T','Y','P','E',' ','F','L','A','G','S',' ',0
BM_MF_EXACT DB 'F','L','A','G','S',' '
