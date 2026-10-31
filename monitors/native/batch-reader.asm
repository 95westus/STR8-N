; Called only with B3 selected, from an admitted native command prompt.
; A=provider, X/Y=destination; C=set/Y=len if queued line, clear=read live.
; Confirmation readers never call this entry. RESET clears the private marker.
        MODULE BATCH_READER
        INCLUDE "str8n-v2-public.inc"
        INCLUDE "batch-interface.inc"
BPTR EQU $E0
BSRC EQU $E2
BCTX EQU $E6
BSIZE EQU $E8
        CODE
BR_START: DB "BQ",1,1,"PR05"
        JMP BR_NEXT
BR_NEXT:
        PHA
        LDA BQ_MAGIC
        CMP #BQ_ON
        BEQ BR_ACTIVE
        PLA
        CLC
        RTS
BR_ACTIVE:
        STX BPTR
        STY BPTR+1
        PLA
        PHA
        LDX #$6A
        CMP #3
        BNE BR_CONTEXT
        ; FLASH's edit buffer covers6A; its queue lives in the5D escrow.
        LDX #$5D
BR_CONTEXT:
        STX BCTX+1
        STX BSRC+1
        LDA #$D0
        STA BCTX
        LDY #$26
        PLA
        CMP (BCTX),Y
        BNE BR_BAD
        LDY #$25
        LDA (BCTX),Y
        BNE BR_STOP
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS BR_CANCEL
        LDY #$23
        LDA (BCTX),Y
        STA BSIZE
        INY
        LDA (BCTX),Y
        CMP BSIZE
        BCC BR_COPY_START
        LDX #<BR_DONE_TEXT
        LDY #>BR_DONE_TEXT
        BRA BR_END
BR_COPY_START:
        TAX
        CLC
        ADC #$D0
        STA BSRC
        LDY #0
BR_COPY:
        CPX BSIZE
        BCS BR_COPY_END
        LDA (BSRC),Y
        INX
        CMP #';'
        BEQ BR_COPY_END
        STA (BPTR),Y
        JSR STR8V2_RAM_PUTC
        INY
        BRA BR_COPY
BR_COPY_END:
        LDA #0
        STA (BPTR),Y
        PHY
        TXA
        LDY #$24
        STA (BCTX),Y
        JSR STR8V2_RAM_NEWLINE
        PLY
        SEC
        RTS
BR_CANCEL:
        LDA #3
        BRA BR_ERROR
BR_BAD:
        LDA #2
BR_ERROR:
        LDY #$25
        STA (BCTX),Y
BR_STOP:
        LDX #<BR_STOP_TEXT
        LDY #>BR_STOP_TEXT
BR_END:
        STZ BQ_MAGIC
        JSR BR_PRINT_TEXT
        LDY #$26
        LDA (BCTX),Y
        LDX #<BR_CLOCK_PROMPT
        LDY #>BR_CLOCK_PROMPT
        CMP #3
        BNE BR_PROMPT
        LDX #<BR_FLASH_PROMPT
        LDY #>BR_FLASH_PROMPT
BR_PROMPT:
        JSR BR_PRINT_TEXT
        CLC
        RTS
BR_PRINT_TEXT:
        STX BPTR
        STY BPTR+1
        LDY #0
BR_PRINT:
        LDA (BPTR),Y
        BEQ BR_PRINTED
        JSR STR8V2_RAM_PUTC
        INY
        BRA BR_PRINT
BR_PRINTED:
        CLC
        RTS
BR_DONE_TEXT: DB "BATCH done",13,10,0
BR_STOP_TEXT: DB "BATCH stopped",13,10,0
BR_CLOCK_PROMPT: DB "CLOCK> ",0
BR_FLASH_PROMPT: DB "FLASH/MAINT> ",0
BR_END_CODE:
        ENDMOD
        END
