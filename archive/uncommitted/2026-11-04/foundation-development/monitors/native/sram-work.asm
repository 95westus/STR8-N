; RAM-only SRAM management and WORK services above golden BASE1.
; Boot packet0200; callable descriptor2000; code below5B00.
; User requests/data0200-1FFF; scratch6400-6ACF; ZP D0-D7/E0-FF.
; Owner ZP and the complete MON session are escrowed at5C00/5D00.
        MODULE SRAM_WORK
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "worker-public-symbols.inc"
        INCLUDE "monitor-ui.inc"
        INCLUDE "batch-interface.inc"
        CODE
SW_START:
        JMP SW_INIT
        JMP SW_SRAM_API
        JMP WK_API
        JMP SM_ENTRY
        JMP WK_ENTRY
        DB "SW",1,2,"PR05"
SW_INIT:
        SEI
        CLD
        LDX #$FF
        TXS
        LDA $5D20
        STA SW_EDU
        STZ SW_UNLOCKED
        STZ WK_RESET_LATCH
        STZ SW_ERROR
        STZ SW_ENTRY_ROUTE
        LDA $5B02
        CMP #3
        BEQ SW_NATIVE_ROUTE
        CMP #4
        BNE SW_ROUTE_READY
SW_NATIVE_ROUTE:
        STA SW_ENTRY_ROUTE
SW_ROUTE_READY:
        LDA #3
        JSR V2W_SELECT
        LDA #MU_BYPASS
        JSR W_UI_CHECK
        BCC SW_BAD_RETURN
        LDA W_UI_TARGET
        STA SW_RETURN_VECTOR
        LDA W_UI_TARGET+1
        STA SW_RETURN_VECTOR+1
        LDA SW_ENTRY_ROUTE
        BEQ SW_MAIN_ENTRY
        LDX #<SW_ROUTE_HINT
        LDY #>SW_ROUTE_HINT
        JSR SW_PRINT
        LDA SW_ENTRY_ROUTE
        CMP #3
        BEQ SW_SRAM
        JMP SW_WORK
SW_MAIN_ENTRY:
        JMP SW_MENU
SW_BAD_RETURN:
        ; The host preservation receiver owns recovery of borrowed RAM.
        JMP $F004
SW_RETURN:
        SEI
        CLD
        LDX #$FF
        TXS
        STZ SW_UNLOCKED
        LDA #3
        JSR V2W_SELECT
        LDX #0
SW_RESTORE_MON:
        LDA $5D00,X
        STA $6A00,X
        INX
        BNE SW_RESTORE_MON
        LDX #0
SW_RESTORE_ZP:
        LDA $5C00,X
        STA $00,X
        INX
        CPX #$E0
        BCC SW_RESTORE_ZP
        STZ $4800
        JMP (SW_RETURN_VECTOR)
SW_SUB_Q:
        LDA SW_ENTRY_ROUTE
        BNE SW_RETURN
        JMP SW_MENU
SW_CONTROLS:
        ; Abandon the console reader frame, retaining the selected route.
        LDX #$FF
        TXS
        JMP SW_MENU
SW_MENU:
        LDX #<SW_TITLE
        LDY #>SW_TITLE
        JSR SW_PRINT
        LDX #<SW_LOCKED_TEXT
        LDY #>SW_LOCKED_TEXT
        LDA SW_UNLOCKED
        BEQ SW_MODE_PRINT
        LDX #<SW_UNLOCKED_TEXT
        LDY #>SW_UNLOCKED_TEXT
SW_MODE_PRINT:
        JSR SW_PRINT
SW_PROMPT:
        LDX #<SW_PROMPT_TEXT
        LDY #>SW_PROMPT_TEXT
        JSR SW_PRINT
        JSR SW_READLINE
        BCC SW_PROMPT
        LDA SW_LINE
        BEQ SW_PROMPT
        LDX #<SW_LINE
        LDY #>SW_LINE
        LDA #<SW_LINE
        STA SW_INPUT_PTR
        LDA #>SW_LINE
        STA SW_INPUT_PTR+1
        LDY #1
        LDA (SW_INPUT_PTR),Y
        BNE SW_LONG_COMMAND
        LDA SW_LINE
        CMP #'Q'
        BEQ SW_RETURN
        CMP #'S'
        BEQ SW_SRAM
        CMP #'W'
        BEQ SW_WORK
        CMP #'?'
        BEQ SW_MENU
        BRA SW_BAD
SW_SRAM:
        JSR SM_INIT
        JMP SM_C_START
SW_WORK:
        JMP WK_ENTRY
SW_LONG_COMMAND:
        LDX #<SW_PREP_WORD
        LDY #>SW_PREP_WORD
        JSR SW_MATCH
        BCS SW_PREP
        LDX #<SW_LOCK_WORD
        LDY #>SW_LOCK_WORD
        JSR SW_MATCH
        BCS SW_LOCK
        LDX #<SW_UNLOCK_WORD
        LDY #>SW_UNLOCK_WORD
        JSR SW_MATCH
        BCS SW_UNLOCK
        LDX #<SW_ON_WORD
        LDY #>SW_ON_WORD
        JSR SW_MATCH
        BCS SW_EDU_ON
        LDX #<SW_OFF_WORD
        LDY #>SW_OFF_WORD
        JSR SW_MATCH
        BCS SW_EDU_OFF
SW_BAD:
        LDX #<SW_BAD_TEXT
        LDY #>SW_BAD_TEXT
        JSR SW_PRINT
        JMP SW_PROMPT
SW_LOCK:
        STZ SW_UNLOCKED
        JMP SW_MENU
SW_UNLOCK:
        LDX #<SW_CONFIRM_TEXT
        LDY #>SW_CONFIRM_TEXT
        JSR SW_PRINT
        JSR SW_READLINE
        BCC SW_PROMPT
        LDX #<SW_YES_WORD
        LDY #>SW_YES_WORD
        JSR SW_MATCH
        BCC SW_BAD
        LDA #1
        STA SW_UNLOCKED
        JMP SW_MENU
SW_EDU_ON:
        LDA #1
        STA SW_EDU
        JMP SW_MENU
SW_EDU_OFF:
        STZ SW_EDU
        STZ SW_UNLOCKED
        JMP SW_MENU
SW_PREP:
        LDA SW_EDU
        CMP #1
        BEQ SW_PREP_GUARD
        LDA #$80
        JMP SW_STATUS
SW_PREP_GUARD:
        JSR W_SPI_GUARD
        BCC SW_STATUS
        LDA W_IFR
        AND #$18
        BEQ SW_PREP_DONE
        LDA W_ORB
        LDA W_IFR
        AND #$18
        BNE SW_PREP_BUSY
SW_PREP_DONE:
        LDA #0
        BRA SW_STATUS
SW_PREP_BUSY:
        LDA #1
SW_STATUS:
        PHA
        LDX #<SW_RESULT_TEXT
        LDY #>SW_RESULT_TEXT
        JSR SW_PRINT
        PLA
        JSR STR8V2_RAM_HEX_OUT
        JSR STR8V2_RAM_NEWLINE
        JMP SW_PROMPT
SW_SRAM_API:
        PHA
        PHX
        JSR SM_INIT
        PLX
        PLA
        JMP SM_C_API
SW_COPY_RANGE:
        LDA SM_D_LOAD+1
        CMP #2
        BCC SW_RANGE_BAD
        CLC
        LDA SM_D_LOAD
        ADC SM_D_LENGTH
        STA SW_TEMP
        LDA SM_D_LOAD+1
        ADC SM_D_LENGTH+1
        BCS SW_RANGE_BAD
        CMP #$20
        BCC SW_RANGE_OK
        BNE SW_RANGE_BAD
        LDA SW_TEMP
        BNE SW_RANGE_BAD
SW_RANGE_OK:
        LDA #0
        RTS
SW_RANGE_BAD:
        LDA #$44
        RTS
SW_RUN_CHECK:
        LDA BQ_MAGIC
        CMP #BQ_ON
        BEQ SW_RUN_REFUSED
        SEC
        RTS
SW_RUN_REFUSED:
        CLC
        RTS
SW_RUN:
        ; Deliberate G of an admitted small RAM program, like MON G.
        ; Restore caller session/ZP; the program returns via public HOLD.
        STZ SW_UNLOCKED
        LDA $FE
        STA SW_RUN_VECTOR
        LDA $FF
        STA SW_RUN_VECTOR+1
        LDX #0
SW_RUN_MON:
        LDA $5D00,X
        STA $6A00,X
        INX
        BNE SW_RUN_MON
        LDX #0
SW_RUN_ZP:
        LDA $5C00,X
        STA $00,X
        INX
        CPX #$E0
        BCC SW_RUN_ZP
        STZ $4800
        LDA SW_RUN_VECTOR
        STA $FE
        LDA SW_RUN_VECTOR+1
        STA $FF
        LDA #3
        STA $F3
        JMP V2W_EXECUTE
; Every console read is bounded and live. No BATCH line can confirm writes.
B29_LINE_2:
        JMP SM_C_READLINE
B29_LINE_3:
        JMP WK_LINE_READ
B29_ERROR_HOOK:
        PHP
        PHA
        LDA #2
        STA SW_ERROR
        PLA
        PLP
        RTS
B29_CANCEL_HOOK:
        PHP
        PHA
        LDA #3
        STA SW_ERROR
        PLA
        PLP
        RTS
SW_MATCH:
        STX SW_TEXT_PTR
        STY SW_TEXT_PTR+1
        LDY #0
SW_MATCH_BYTE:
        LDA (SW_TEXT_PTR),Y
        CMP SW_LINE,Y
        BNE SW_MATCH_NO
        CMP #0
        BEQ SW_MATCH_YES
        INY
        CPY #32
        BCC SW_MATCH_BYTE
SW_MATCH_NO:
        CLC
        RTS
SW_MATCH_YES:
        SEC
        RTS
SW_READLINE:
        STZ SW_LINE_COUNT
        STZ SW_OVERFLOW
SW_READ_BYTE:
        JSR STR8V2_RAM_GETC
        CMP #10
        BEQ SW_READ_BYTE
        CMP #3
        BEQ SW_READ_CANCEL
        CMP #$1B
        BEQ SW_READ_CANCEL
        CMP #13
        BEQ SW_READ_DONE
        CMP #'a'
        BCC SW_READ_CHAR
        CMP #'z'+1
        BCS SW_READ_CHAR
        AND #$DF
SW_READ_CHAR:
        LDX SW_LINE_COUNT
        CPX #31
        BCS SW_READ_LONG
        STA SW_LINE,X
        INC SW_LINE_COUNT
        JSR STR8V2_RAM_PUTC
        BRA SW_READ_BYTE
SW_READ_LONG:
        LDA #1
        STA SW_OVERFLOW
        BRA SW_READ_BYTE
SW_READ_DONE:
        LDX SW_LINE_COUNT
        STZ SW_LINE,X
        JSR STR8V2_RAM_NEWLINE
        LDA SW_OVERFLOW
        BNE SW_READ_CANCEL
        SEC
        RTS
SW_READ_CANCEL:
        JSR STR8V2_RAM_RX_RESET
        JSR STR8V2_RAM_NEWLINE
        CLC
        RTS
SW_PRINT:
        STX SW_TEXT_PTR
        STY SW_TEXT_PTR+1
        LDY #0
SW_PRINT_BYTE:
        LDA (SW_TEXT_PTR),Y
        BEQ SW_PRINT_DONE
        JSR STR8V2_RAM_PUTC
        INY
        BRA SW_PRINT_BYTE
SW_PRINT_DONE:
        RTS
SW_RAM_LAST: DB $FF,$66
SW_ENTRY_ROUTE EQU $5B3D
SW_TITLE: DB "SRAM / WORK gSW_GENERATION_TEXT - BASE1 PR05; S SRAM, W WORK, Q MON",13,10,0
SW_ROUTE_HINT: DB "READ ONLY; ! controls (UNLOCK/PREP); Q MON",13,10,0
SW_LOCKED_TEXT: DB "READ ONLY; UNLOCK + YES permits SRAM writes. LOCK / PREP / EDU ON|OFF",13,10,0
SW_UNLOCKED_TEXT: DB "SRAM writes enabled; F is never a target. LOCK disables writes.",13,10,0
SW_PROMPT_TEXT: DB "STORAGE> ",0
SW_CONFIRM_TEXT: DB "Enable SRAM writes for this RAM session? Type YES: ",0
SW_BAD_TEXT: DB "Use S W Q ? PREP LOCK UNLOCK EDU ON EDU OFF",13,10,0
SW_RESULT_TEXT: DB "Storage status $",0
SW_PREP_WORD: DB "PREP",0
SW_LOCK_WORD: DB "LOCK",0
SW_UNLOCK_WORD: DB "UNLOCK",0
SW_ON_WORD: DB "EDU ON",0
SW_OFF_WORD: DB "EDU OFF",0
SW_YES_WORD: DB "YES",0
        INCLUDE "sram-work-classic.inc"
        INCLUDE "sram-work-spi.inc"
        INCLUDE "sram-work-ui.inc"
SW_CODE_END:
        ENDMOD
        END
