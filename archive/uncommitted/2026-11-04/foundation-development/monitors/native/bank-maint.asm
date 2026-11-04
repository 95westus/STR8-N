; BANK MAINT algorithms above golden BASE1. Foreground65C02/816 emulation.
; Code2000-4FFF; editor5000-5FFF; state6000-63FF; return context6400-66FF.
; Sector staging6800-77FF is independent of the editor. Owner RAM0200-1FFF
; is the admitted C/V workspace. F and C/D are never raw maintenance targets.
        MODULE BANK_MAINT
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "vectors-symbols.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "batch-interface.inc"
        INCLUDE "monitor-ui.inc"
        CODE
MM_START:
        SEI
        CLD
        LDX #$FF
        TXS
        LDA #3
        STA V2_RESIDENT
        JSR V2W_SELECT
        LDA $7E60
        CMP #'R'
        BNE MB_REFUSE
        LDA $7E61
        CMP #'A'
        BNE MB_REFUSE
        LDA $7E62
        CMP #1
        BNE MB_REFUSE
        LDA $7E63
        CMP #$0D
        BCC MB_REFUSE
        LDA MU_ACTIVE
        CMP #$A0
        BEQ MB_SLOT
        CMP #$B0
        BNE MB_REFUSE
MB_SLOT:
        STA BOOT_DEST
        STA V2_PTR+1
        STZ V2_PTR
        JSR BOOT_SLOT_CHECK
        BCC MB_REFUSE
        LDA MU_ACTIVE
        STA V2_PTR+1
        STZ V2_PTR
        LDY #MU_DESCRIPTOR
        LDX #0
MB_UI:
        LDA (V2_PTR),Y
        CMP MB_UI_ID,X
        BNE MB_REFUSE
        INY
        INX
        CPX #8
        BCC MB_UI
        LDY #MU_VECTOR_BASE+2*MU_BYPASS
        LDA (V2_PTR),Y
        STA $66F0
        INY
        LDA (V2_PTR),Y
        STA $66F1
        LDY #MU_VECTOR_BASE+2*MU_VERSION
        LDA (V2_PTR),Y
        STA $66F2
        INY
        LDA (V2_PTR),Y
        STA $66F3
        LDX #MB_RETURN_END-MB_RETURN-1
MB_RET_COPY:
        LDA MB_RETURN,X
        STA $6600,X
        DEX
        BPL MB_RET_COPY
        LDX #$6F
MB_ZERO:
        STZ $6100,X
        STZ $6200,X
        DEX
        BPL MB_ZERO
        LDA #3
        STA MM_RESIDENT
        STA X28_BANK
        LDA #<JE_ENTER
        STA $7C60
        LDA #>JE_ENTER
        STA $7C61
        LDX #<MM_TITLE
        LDY #>MM_TITLE
        JSR MM_PRINT
        STZ MM_BM_LINE
        JMP MM_BM_HELP
MB_REFUSE:
        ; No unvalidated return vector is used. F is still mapped/golden.
        JMP $F004
MB_RETURN:
        SEI
        CLD
        LDX #$FF
        TXS
        LDA #3
        JSR V2W_SELECT
        LDX #0
MB_RET_MON:
        LDA $6500,X
        STA $6A00,X
        INX
        CPX #$D0
        BCC MB_RET_MON
        LDX #0
MB_RET_ZP:
        LDA $6400,X
        STA $00,X
        INX
        CPX #$E0
        BCC MB_RET_ZP
        STZ $4800
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE MB_RET_JUMP
        LDA BQ_PARENT
        STA BQ_PROVIDER
MB_RET_JUMP:
        JMP ($66F0)
MB_RETURN_END:
MB_UI_ID: DB "UI",1,7,"PR05"

        INCLUDE "bank-maint-classic.inc"
        INCLUDE "bank-maint-base1.inc"
        INCLUDE "bank-maint-table.inc"
        INCLUDE "maint-config-ui.inc"
        INCLUDE "maint-config-engine.inc"
MAINT_END:
        ENDMOD
        END
