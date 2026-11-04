; Explicit !M override. Entire command parsed first; never erases.
; Raw RAM/I/O writes use unrolled absolute stores, so editing the ZP pointer
; or stack cannot redirect later writes in the same command. No I/O readback.
; Either RAM scratch page can host the raw writer; choose away from its target.
MF_PREFLIGHT:
        LDA M_ADDR+1
        BMI MF_FLASH_CHECK
        LDA M_LAST+1
        BMI MF_REFUSED
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS MF_CANCEL
        STZ M_PTR
        LDA #>MF_RAM
        LDX M_ADDR+1
        CPX #>MF_RAM
        BEQ MF_USE_ALT
        LDX M_LAST+1
        CPX #>MF_RAM
        BNE MF_BUILD_RAW
MF_USE_ALT:
        LDA #>MF_ALT
MF_BUILD_RAW:
        STA M_PTR+1
        LDX #0
        LDY #0
MF_RAW_NEXT:
        LDA #$A9
        STA (M_PTR),Y
        INY
        LDA M_EDIT,X
        STA (M_PTR),Y
        INY
        LDA #$8D
        STA (M_PTR),Y
        INY
        LDA M_ADDR
        STA (M_PTR),Y
        INY
        LDA M_ADDR+1
        STA (M_PTR),Y
        INY
        INC M_ADDR
        BNE MF_RAW_INDEX
        INC M_ADDR+1
MF_RAW_INDEX:
        INX
        CPX M_ROW
        BCC MF_RAW_NEXT
        LDA #$4C
        STA (M_PTR),Y
        INY
        LDA #<MF_RAW_DONE
        STA (M_PTR),Y
        INY
        LDA #>MF_RAW_DONE
        STA (M_PTR),Y
        JMP (M_PTR)
MF_RAW_DONE:
        ; Deliberate system edits cannot depend on the old return stack.
        LDX #$FF
        TXS
        LDX #<MF_RAW_TEXT
        LDY #>MF_RAW_TEXT
        JMP M_MESSAGE
MF_FLASH_CHECK:
        LDA M_BANK
        CMP #3
        BNE MF_FLASH_BITS
        LDA M_ADDR+1
        CMP #$C0
        BCC MF_BELOW_CD
        CMP #$E0
        BCC MF_REFUSED
        LDA M_LAST+1
        CMP #$F0
        BCS MF_REFUSED
        BRA MF_FLASH_BITS
MF_BELOW_CD:
        LDA M_LAST+1
        CMP #$C0
        BCS MF_REFUSED
MF_FLASH_BITS:
        JSR M_READ_BYTES
        LDX #0
MF_BIT_NEXT:
        LDA M_BUFFER,X
        AND M_EDIT,X
        CMP M_EDIT,X
        BNE MF_REFUSED
        INX
        CPX M_ROW
        BCC MF_BIT_NEXT
        JSR STR8V2_RAM_CHECK_CANCEL
        BCS MF_CANCEL
        LDX #MF_FLASH_END-MF_FLASH_IMAGE-1
MF_COPY_FLASH:
        LDA MF_FLASH_IMAGE,X
        STA MF_RAM,X
        DEX
        BPL MF_COPY_FLASH
        JMP MF_RAM
MF_REFUSED:
        JMP M_RANGE
MF_CANCEL:
        JMP M_INPUT_BAD
MF_FLASH_DONE:
        LDA M_ROW
        STA M_LEFT
        STZ M_LEFT+1
        SEC
        LDA M_ADDR
        SBC M_ROW
        STA M_ADDR
        BCS MF_FLASH_ECHO
        DEC M_ADDR+1
MF_FLASH_ECHO:
        LDA M_ROW
        JMP M_HAVE_ROW

; Position-independent RAM image: relative local branches and fixed RAM calls.
; The builder rejects any unexpected absolute jump inside this copied image.
MF_FLASH_IMAGE:
        LDA M_BANK
        JSR MON_F_SELECT
        STZ M_INDEX
MF_PROGRAM_NEXT:
        LDX M_INDEX
        LDA M_EDIT,X
        STA F_FLASH_DATA
        LDA M_ADDR
        STA F_FLASH_PTR
        LDA M_ADDR+1
        STA F_FLASH_PTR+1
        LDY #0
        LDA (F_FLASH_PTR),Y
        CMP F_FLASH_DATA
        BEQ MF_PROGRAM_SKIP
        JSR MON_F_BYTE
        BCC MF_PROGRAM_FAILED
MF_PROGRAM_SKIP:
        INC M_ADDR
        BNE MF_PROGRAM_INDEX
        INC M_ADDR+1
MF_PROGRAM_INDEX:
        INC M_INDEX
        LDA M_INDEX
        CMP M_ROW
        BCC MF_PROGRAM_NEXT
        LDA #3
        JSR MON_F_SELECT
        LDA #1
        STA F_LED
        JMP MF_FLASH_DONE
MF_PROGRAM_FAILED:
        ; Keep execution in RAM if programming never reaches a verified state.
        LDA #'!'
        JSR STR8V2_RAM_PUTC
        LDA #1
        STA F_LED
MF_FAILURE_HALT:
        BRA MF_FAILURE_HALT
MF_FLASH_END:
MF_RAW_TEXT: DB "Forced; no raw readback.",13,10,0
