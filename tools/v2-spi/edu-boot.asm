; Sealed E-sector helper. $7D27/28 are existing reset-cleared monitor RAM.
        MODULE EDU_BOOT
        XDEF START
        XDEF AUX_END
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "edu-links.inc"
        CODE
START:  DB "ED",1,1
EDU_INIT:
        LDA $7D27
        BNE DECIDED
        JSR BOOT_API_READ
        BCC DEFAULT_ON
        JSR $EF50
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
        LDA #$56
        STA SVC_BANNER_PTR
        LDA #$EF
        STA SVC_BANNER_PTR+1
        JMP SVC_DONE
ENABLED:
        JMP SVC_ENABLED
OFF_TEXT DB "EDU: OFF; RAM top $66FF",13,10,0
AUX_END:
        ENDMOD
