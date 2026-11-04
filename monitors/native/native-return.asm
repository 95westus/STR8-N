; Native overlays return without executing their overwritten workbench cache.
; Owner00-DF and the monitor6A session were escrowed before app initialization.
        MODULE NATIVE_RETURN
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "vectors-symbols.inc"
        INCLUDE "monitor-ui.inc"
        INCLUDE "batch-interface.inc"
        CODE
NR_START:
        SEI
        CLD
        LDX #$FF
        TXS
        LDA #3
        JSR V2W_SELECT
        LDX #0
NR_MON:
        LDA $5D00,X
        STA $6A00,X
        INX
        CPX #$D0
        BCC NR_MON
        LDA $5B02
        BEQ NR_MON_DONE
NR_FLASH_CONTEXT:
        LDA $5D00,X
        STA $6A00,X
        INX
        BNE NR_FLASH_CONTEXT
NR_MON_DONE:
        LDA BQ_MAGIC
        CMP #BQ_ON
        BNE NR_NO_BATCH
        LDA BQ_PARENT
        STA BQ_PROVIDER
NR_NO_BATCH:
        LDX #0
NR_ZP:
        LDA $5C00,X
        STA $00,X
        INX
        CPX #$E0
        BCC NR_ZP
        ; Force a complete WB/SP reload after either native overlay.
        STZ $4800
        LDA #MU_BYPASS
        JSR W_UI_CHECK
        BCC NR_LEGACY
        JMP (W_UI_TARGET)
NR_LEGACY:
        JMP STR8V2_RAM_HOLD
NR_CALL:
        JSR W_UI_CHECK
        BCC NR_CALL_END
        JSR NR_CALL_JUMP
        SEC
NR_CALL_END:
        RTS
NR_CALL_JUMP:
        JMP (W_UI_TARGET)
W_PTR EQU $E0
W_CRC EQU $5B00
W_CRC_START:
        LDA #$FF
        STA W_CRC
        STA W_CRC+1
        RTS
W_CRC_BYTE:
        EOR W_CRC+1
        STA W_CRC+1
        PHX
        LDX #8
NR_BIT:
        ASL W_CRC
        ROL W_CRC+1
        BCC NR_NEXT
        LDA W_CRC
        EOR #$21
        STA W_CRC
        LDA W_CRC+1
        EOR #$10
        STA W_CRC+1
NR_NEXT:
        DEX
        BNE NR_BIT
        PLX
        RTS
        INCLUDE "native-ui-check.inc"
W_UI_MI_MAGIC: DB "MI",1,0,3,1,0,0
W_UI_MAGIC: DB "UI",1,MU_VECTOR_COUNT,"PR05"
NR_END:
        ENDMOD
        END
