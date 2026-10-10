; Reset-only EDU choice; all code in the verified existing E sector.
        MODULE STATUS_MODE
        XDEF START
        XDEF AUX_END
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "status-links.inc"
        CODE
START:  DB "ED",1,2
MODE_INIT:
        LDA $7D27
        BNE DECIDED
        JSR BOOT_API_READ
        BCC DEFAULT_ON
        JSR $EF00
        BCC DEFAULT_ON
        LDA V2_CONFIG+13
        CMP #$A5
        BNE DEFAULT_ON
        LDA #2
        BRA SAVE_MODE
DEFAULT_ON:
        LDA #1
SAVE_MODE:
        STA $7D27
        LDY #0
        CMP #2
        BNE SAVE_PENDING
        LDY #$A5
SAVE_PENDING:
        STY $7D28
DECIDED:
        CMP #2
        BNE ENABLED
        STZ SVC_DESC
        STZ SVC_FLAGS
        STZ SVC_DESC+4
        STZ SVC_DESC+5
        JSR SVC_DONE
        BRA FRAME_POINTER
ENABLED:
        JSR SVC_ENABLED
FRAME_POINTER:
        LDA SVC_BANNER_PTR
        STA $7D29
        LDA SVC_BANNER_PTR+1
        STA $7D2A
        LDA #$06
        STA SVC_BANNER_PTR
        LDA #$EF
        STA SVC_BANNER_PTR+1
        RTS
; Shared print uses no user/service RAM; cold OFF never touches 6500-66FF.
PRINT:  STX V2_PTR
        STY V2_PTR+1
        LDY #0
NEXT:   LDA (V2_PTR),Y
        BEQ RETURN
        JSR $7E6D
        INY
        BRA NEXT
RETURN: RTS
AUX_END:
        ENDMOD
