; Load paired WORK 1.2 at 5000 first. This application starts at 2000.
; QUERY/CLAIM/READ/verified WRITE/READ/restore/verify/RELEASE. No format/resize.
; A failed restoration retains the possible claim and copied handle for inspection.
        MODULE WORK_AREA
        XDEF START
        XDEF APP_END
REQ EQU $3000
HANDLE EQU $3020
CLAIMED EQU $3028          ; 1: handle may still own a claim (errors can be partial).
BACKED_UP EQU $3029
DIRTY EQU $302A
PRIMARY EQU $3030
RESTORED EQU $3031
RELEASED EQU $3032
OVERALL EQU $3033
PATTERN EQU $3100
ORIGINAL EQU $3200
VERIFY EQU $3300
        CODE
START:  SEI
        CLD
        JSR EX_CHECK_RA
        BCC EX_NO_ABI
        STZ CLAIMED
        STZ BACKED_UP
        STZ DIRTY
        STZ PRIMARY
        STZ RESTORED
        STZ RELEASED
        STZ OVERALL
        LDA #8
        JSR EX_CHECK_SV
        BCC FINISH
        LDX #3
CHECK_SM:
        LDA $66A2,X
        CMP EXPECTED_SM,X
        BNE ABSENT
        DEX
        BPL CHECK_SM
        LDX #3
CHECK_WORK:
        LDA $5006,X
        CMP EXPECTED_WORK,X
        BNE ABSENT
        DEX
        BPL CHECK_WORK
        JSR ZERO_REQUEST
        LDA #0
        JSR CALL
        BCC FINISH
        LDA REQ+22          ; Legacy layout requires explicit administration.
        ORA REQ+23          ; Secondary-only layout requires explicit repair.
        BNE ADMIN_REQUIRED
        JSR ZERO_REQUEST
        LDA #$EF
        STA REQ+2
        LDA #$BE
        STA REQ+3           ; Demonstration owner BEEF; keep owner with handle.
        LDA #64
        STA REQ+18
        LDA #1
        JSR CALL
        PHP
        PHA                 ; A failed final verification can leave a live claim.
        LDX #7
COPY_HANDLE:
        LDA REQ+4,X
        STA HANDLE,X
        DEX
        BPL COPY_HANDLE
        PLA
        PLP
        BCS CLAIM_OK
        PHA
        LDA REQ+10
        ORA REQ+11          ; Nonzero returned ticket: retain/try releasing handle.
        BEQ CLAIM_UNCONFIRMED
        INC CLAIMED
CLAIM_UNCONFIRMED:
        PLA
        JMP FINISH
CLAIM_OK:
        INC CLAIMED
        LDA #64
        STA REQ+15
        STZ REQ+12
        STZ REQ+13
        STZ REQ+14
        STZ REQ+16
        LDA #>ORIGINAL
        STA REQ+17
        LDA #3
        JSR TRANSFER
        BCC FINISH
        INC BACKED_UP
        LDX #63
FILL_PATTERN:
        TXA
        EOR #$A5
        STA PATTERN,X
        DEX
        BPL FILL_PATTERN
        INC DIRTY           ; Set before WRITE: even an error can change bytes.
        LDA #>PATTERN
        STA REQ+17
        LDA #4
        JSR TRANSFER
        BCC FINISH
        LDA #>VERIFY
        STA REQ+17
        LDA #3
        JSR TRANSFER
        BCC FINISH
        LDX #63
CHECK_PATTERN:
        LDA VERIFY,X
        CMP PATTERN,X
        BNE VERIFY_FAILED
        DEX
        BPL CHECK_PATTERN
        LDA #0
        BRA FINISH
VERIFY_FAILED:
        LDA #$45
        BRA FINISH
ADMIN_REQUIRED:
        LDA #$49
        BRA FINISH
ABSENT: LDA #$80
FINISH: STA PRIMARY
        LDA CLAIMED
        BEQ REPORT
        LDA DIRTY
        BEQ RELEASE
        LDA BACKED_UP
        BEQ REPORT          ; Never restore from an incomplete backup.
        LDA #>ORIGINAL
        STA REQ+17
        LDA #4
        JSR TRANSFER
        BCC RESTORE_FAILED
        LDA #>VERIFY
        STA REQ+17
        LDA #3
        JSR TRANSFER
        BCC RESTORE_FAILED
        LDX #63
CHECK_ORIGINAL:
        LDA VERIFY,X
        CMP ORIGINAL,X
        BNE RESTORE_MISMATCH
        DEX
        BPL CHECK_ORIGINAL
        BRA RELEASE
RESTORE_MISMATCH:
        LDA #$45
RESTORE_FAILED:
        STA RESTORED
        BRA REPORT          ; Retain possible claim/handle if data is unverified.
RELEASE:
        LDA #2
        JSR CALL
        STA RELEASED
        BCC REPORT
        STZ CLAIMED
REPORT: LDA PRIMARY
        ORA RESTORED
        ORA RELEASED
        BEQ ALL_OK
        LDA PRIMARY
        BNE HAVE_OVERALL
        LDA RESTORED
        BNE HAVE_OVERALL
        LDA RELEASED
        BRA HAVE_OVERALL
ALL_OK: LDA #0
HAVE_OVERALL:
        STA OVERALL
        LDX #<RESULT_TEXT
        LDY #>RESULT_TEXT
        JSR EX_PRINT
        LDA OVERALL
        JSR HEX
        LDX #<OP_TEXT
        LDY #>OP_TEXT
        JSR EX_PRINT
        LDA PRIMARY
        JSR HEX
        LDX #<RESTORE_TEXT
        LDY #>RESTORE_TEXT
        JSR EX_PRINT
        LDA RESTORED
        JSR HEX
        LDX #<RELEASE_TEXT
        LDY #>RELEASE_TEXT
        JSR EX_PRINT
        LDA RELEASED
        JSR HEX
        LDX #<CLAIM_TEXT
        LDY #>CLAIM_TEXT
        JSR EX_PRINT
        LDA CLAIMED
        JSR HEX
        JSR NL
        JMP HOLD
ZERO_REQUEST:
        LDX #31
ZERO_LOOP:
        STZ REQ,X
        DEX
        BPL ZERO_LOOP
        RTS
CALL:   STA REQ
        LDA #<REQ
        LDX #>REQ
        JSR $5003
        RTS
TRANSFER:
        JSR CALL
        BCC TRANSFER_RETURN
        LDA REQ+22
        CMP #64
        BNE TRANSFER_SHORT
        LDA #0
        SEC
TRANSFER_RETURN:
        RTS
TRANSFER_SHORT:
        LDA #$46
        CLC
        RTS
EXPECTED_SM DB "SM",1,1
EXPECTED_WORK DB "WK",1,2
RESULT_TEXT DB "WORK: ",0
OP_TEXT DB " operation=",0
RESTORE_TEXT DB " restore=",0
RELEASE_TEXT DB " release=",0
CLAIM_TEXT DB " claim-may-remain=",0
        INCLUDE "example-abi.inc"
APP_END:
        ENDMOD
        END
