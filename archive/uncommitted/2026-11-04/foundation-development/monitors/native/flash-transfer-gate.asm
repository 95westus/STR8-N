; Optional pre-WB command gate; RAM7300-76FF, no owner RAM or NVM writes.
; Production +8 loads sealed overlays from B1. Private +11 qualifies parsing
; with an already loaded overlay; it still checks the full CRC and identity.
        MODULE FLASH_TRANSFER_GATE
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "str8n-v2-eq.inc"
        INCLUDE "worker-public-symbols.inc"
        INCLUDE "boot-symbols.inc"
        INCLUDE "auto-reload-defs.inc"
        CODE
GG_BEGIN:
        DB "FG",1,5,"PR05"
        JMP GG_ENTRY
        JMP GG_PRELOADED
GG_LINE EQU $6840
GG_MODE EQU $69F8
GG_HANDLED EQU $69F9
GG_SKIP_LOAD EQU $69FA
GG_PAGES EQU $69FB
GG_IS_RESTORE EQU $69FC
GG_SRC EQU $E0
GG_DST EQU $E2
GG_ENTRY:
        STZ GG_SKIP_LOAD
        BRA GG_PARSE
GG_PRELOADED:
        LDA #1
        STA GG_SKIP_LOAD
GG_PARSE:
        STZ GG_HANDLED
        STZ GG_IS_RESTORE
        LDX #0
        JSR GG_SKIP
        CMP #'S'
        BNE GG_RESTORE
        LDA GG_LINE+1,X
        CMP #'1'
        BNE GG_STORE
        LDA GG_LINE+2,X
        CMP #'9'
        BNE GG_NO
        INX
        INX
        INX
        JSR GG_SKIP
        BNE GG_NO
        LDA #0
        BRA GG_LOAD
GG_STORE:
        LDX #<GG_STORE_WORD
        LDY #>GG_STORE_WORD
        JSR GG_MATCH
        BCS GG_STORE_ARG
        LDX #<GG_S_WORD
        LDY #>GG_S_WORD
        JSR GG_MATCH
        BCC GG_NO
GG_STORE_ARG:
        JSR GG_SKIP
        CMP #'P'
        BNE GG_FLASH_ARG
        LDA GG_LINE+1,X
        CMP #' '
        BNE GG_NO
        LDA #1
        BRA GG_LOAD
GG_RESTORE:
        LDX #<GG_RESTORE_WORD
        LDY #>GG_RESTORE_WORD
        JSR GG_MATCH
        BCS GG_RESTORE_ARG
        LDX #<GG_R_WORD
        LDY #>GG_R_WORD
        JSR GG_MATCH
        BCC GG_NO
GG_RESTORE_ARG:
        INC GG_IS_RESTORE
        JSR GG_SKIP
GG_FLASH_ARG:
        SEC
        SBC #'0'
        CMP #2
        BCS GG_NO
        LDA GG_LINE+1,X
        CMP #' '
        BNE GG_NO
        ; AUTO now uses MON's saved AREA in the independent high worker.
        ; Never load WB over a large source or require its old cache CRC.
GG_RECORD_LOAD:
        LDA #2
GG_LOAD:
        STA GG_MODE
        LDA #1
        STA GG_HANDLED
        LDA #6
        STA GG_PAGES
        STZ GG_SRC
        LDA #$D9
        STA GG_SRC+1
        LDA GG_MODE
        CMP #2
        BNE GG_DEST
        LDA #8
        STA GG_PAGES
        LDA #$C0
        STA GG_SRC
        LDA #$A7
        STA GG_SRC+1
GG_DEST:
        STZ GG_DST
        LDA #$6B
        STA GG_DST+1
        LDA GG_SKIP_LOAD
        BNE GG_CRC
        LDA #1
        JSR V2W_SELECT
GG_COPY_PAGE:
        LDY #0
GG_COPY_BYTE:
        LDA (GG_SRC),Y
        STA (GG_DST),Y
        INY
        BNE GG_COPY_BYTE
        INC GG_SRC+1
        INC GG_DST+1
        DEC GG_PAGES
        BNE GG_COPY_PAGE
        LDA #3
        JSR V2W_SELECT
GG_CRC:
        LDA #6
        LDX GG_MODE
        CPX #2
        BNE GG_CRC_START
        LDA #8
GG_CRC_START:
        STA GG_PAGES
        JSR J_CRC_INIT
        STZ GG_SRC
        LDA #$6B
        STA GG_SRC+1
        LDY #0
GG_CRC_BYTE:
        LDA (GG_SRC),Y
        JSR J_CRC_BYTE
        INY
        BNE GG_CRC_BYTE
        INC GG_SRC+1
        DEC GG_PAGES
        BNE GG_CRC_BYTE
        LDA J_CRC
        ORA J_CRC+1
        BNE GG_INVALID
        LDA GG_MODE
        CMP #2
        BEQ GG_RECORD_ID
        LDX #7
GG_SL_ID:
        LDA $6B00,X
        CMP GG_SL_MAGIC,X
        BNE GG_INVALID
        DEX
        BPL GG_SL_ID
        LDA GG_MODE
        BNE GG_PROGRAM
        JMP $6B08
GG_PROGRAM:
        LDX #7
GG_WS_ID:
        LDA $6D00,X
        CMP GG_WS_MAGIC,X
        BNE GG_INVALID
        DEX
        BPL GG_WS_ID
        LDX #<GG_LINE
        LDY #>GG_LINE
        ; Tail-call: PROGRAM may overwrite the gate. Return directly to ROM.
        JMP $6D08
GG_RECORD_ID:
        LDX #7
GG_FR_ID:
        LDA $6B00,X
        CMP GG_FR_MAGIC,X
        BNE GG_INVALID
        DEX
        BPL GG_FR_ID
        LDX #<GG_LINE
        LDY #>GG_LINE
        JMP $6B08
GG_INVALID:
        LDX #<GG_INVALID_TEXT
        LDY #>GG_INVALID_TEXT
        JMP BOOT_PRINT
GG_AUTO:
        LDA #1
        STA GG_HANDLED
        LDX #0
GG_AUTO_COPY:
        LDA GG_AUTO_IMAGE,X
        STA $6A30,X
        INX
        CPX #AUTO_RELOAD_BYTES
        BCC GG_AUTO_COPY
        JMP $6A30
GG_NO:
        RTS
GG_SKIP:
        LDA GG_LINE,X
        CMP #' '
        BNE GG_SKIP_END
        INX
        BRA GG_SKIP
GG_SKIP_END:
        CMP #0
        RTS
GG_MATCH:
        STX GG_SRC
        STY GG_SRC+1
        LDX #0
        JSR GG_SKIP
        LDY #0
GG_MATCH_BYTE:
        LDA (GG_SRC),Y
        BEQ GG_MATCH_END
        CMP GG_LINE,X
        BNE GG_MATCH_NO
        INX
        INY
        BRA GG_MATCH_BYTE
GG_MATCH_END:
        LDA GG_LINE,X
        BEQ GG_MATCH_YES
        CMP #' '
        BNE GG_MATCH_NO
GG_MATCH_YES:
        SEC
        RTS
GG_MATCH_NO:
        CLC
        RTS
GG_STORE_WORD: DB "STORE",0
GG_S_WORD: DB "S",0
GG_RESTORE_WORD: DB "RESTORE",0
GG_R_WORD: DB "R",0
GG_SL_MAGIC: DB "SL",1,6,"PR05"
GG_WS_MAGIC: DB "WS",1,4,"PR05"
GG_FR_MAGIC: DB "FR",1,9,"PR05"
GG_INVALID_TEXT: DB "REFUSED: transfer image invalid",13,10,0
GG_AUTO_IMAGE:
        INCLUDE "auto-reload-bytes.inc"
GG_END:
        ENDMOD
        END
